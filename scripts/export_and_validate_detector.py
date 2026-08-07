#!/usr/bin/env python3
"""Export E01 to ONNX/OpenVINO and validate fixed-sample agreement."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import shutil
import subprocess
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnx
import onnxruntime
import openvino
import torch
import ultralytics
import yaml
from openvino import Core
from ultralytics import YOLO

if __package__:
    from .analyze_detection_errors import match_boxes_at_iou
    from .evaluate_pretrained_baseline import evenly_spaced_indices
    from .visdrone_dataset import write_json_atomic
else:
    from analyze_detection_errors import match_boxes_at_iou
    from evaluate_pretrained_baseline import evenly_spaced_indices
    from visdrone_dataset import write_json_atomic


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "e01_deployment_export.yaml"
BACKEND_ORDER = ("pytorch", "onnx", "openvino")


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_revision() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("deployment config must be a mapping")
    required = {
        "deployment_id",
        "source_model",
        "export_root",
        "subset_manifest",
        "images_dir",
        "export",
        "inference",
        "benchmark",
        "agreement",
        "experiment_dir",
        "result_dir",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"missing config keys: {missing}")
    return config


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("cannot calculate percentile of empty values")
    return float(np.percentile(np.asarray(values, dtype=np.float64), quantile))


def summarize_timings(values: list[float]) -> dict[str, float]:
    if not values:
        raise ValueError("timing values cannot be empty")
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p95": percentile(values, 95),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


def result_to_detection(result: Any) -> dict[str, Any]:
    return {
        "boxes": result.boxes.xyxy.detach().cpu().float(),
        "classes": result.boxes.cls.detach().cpu().to(torch.int64),
        "confidences": result.boxes.conf.detach().cpu().float(),
    }


def compare_detection_sets(
    reference: dict[str, Any], candidate: dict[str, Any], match_iou: float
) -> dict[str, Any]:
    matches = match_boxes_at_iou(
        reference["boxes"],
        candidate["boxes"],
        match_iou,
        reference["classes"],
        candidate["classes"],
    )
    ious = [iou for _, _, iou in matches]
    confidence_differences = [
        abs(
            float(reference["confidences"][reference_index])
            - float(candidate["confidences"][candidate_index])
        )
        for reference_index, candidate_index, _ in matches
    ]
    reference_count = int(reference["boxes"].shape[0])
    candidate_count = int(candidate["boxes"].shape[0])
    matched_count = len(matches)

    def match_rate(total: int) -> float:
        if total:
            return matched_count / total
        return 1.0 if matched_count == 0 else 0.0

    return {
        "reference_count": reference_count,
        "candidate_count": candidate_count,
        "matched_count": matched_count,
        "unmatched_reference": reference_count - matched_count,
        "unmatched_candidate": candidate_count - matched_count,
        "reference_match_rate": match_rate(reference_count),
        "candidate_match_rate": match_rate(candidate_count),
        "mean_box_iou": float(np.mean(ious)) if ious else (1.0 if not reference_count and not candidate_count else 0.0),
        "min_box_iou": float(np.min(ious)) if ious else (1.0 if not reference_count and not candidate_count else 0.0),
        "mean_confidence_abs_diff": (
            float(np.mean(confidence_differences)) if confidence_differences else 0.0
        ),
        "max_confidence_abs_diff": max(confidence_differences, default=0.0),
    }


def aggregate_agreement(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reference_count = sum(int(row["reference_count"]) for row in rows)
    candidate_count = sum(int(row["candidate_count"]) for row in rows)
    matched_count = sum(int(row["matched_count"]) for row in rows)

    def rate(total: int) -> float:
        return matched_count / total if total else 1.0

    if matched_count:
        mean_iou = sum(
            float(row["mean_box_iou"]) * int(row["matched_count"]) for row in rows
        ) / matched_count
        mean_confidence = sum(
            float(row["mean_confidence_abs_diff"]) * int(row["matched_count"])
            for row in rows
        ) / matched_count
        min_iou = min(
            float(row["min_box_iou"])
            for row in rows
            if int(row["matched_count"]) > 0
        )
    else:
        mean_iou = 1.0 if not reference_count and not candidate_count else 0.0
        mean_confidence = 0.0
        min_iou = mean_iou
    return {
        "sample_count": len(rows),
        "reference_count": reference_count,
        "candidate_count": candidate_count,
        "matched_count": matched_count,
        "unmatched_reference": reference_count - matched_count,
        "unmatched_candidate": candidate_count - matched_count,
        "reference_match_rate": rate(reference_count),
        "candidate_match_rate": rate(candidate_count),
        "mean_box_iou": mean_iou,
        "min_box_iou": min_iou,
        "mean_confidence_abs_diff": mean_confidence,
        "max_confidence_abs_diff": max(
            (float(row["max_confidence_abs_diff"]) for row in rows), default=0.0
        ),
    }


def check_tolerance(
    agreement: dict[str, Any], tolerance: dict[str, Any]
) -> dict[str, Any]:
    checks = {
        "reference_match_rate": agreement["reference_match_rate"]
        >= float(tolerance["min_reference_match_rate"]),
        "candidate_match_rate": agreement["candidate_match_rate"]
        >= float(tolerance["min_candidate_match_rate"]),
        "mean_box_iou": agreement["mean_box_iou"]
        >= float(tolerance["min_mean_box_iou"]),
        "max_confidence_abs_diff": agreement["max_confidence_abs_diff"]
        <= float(tolerance["max_confidence_abs_diff"]),
    }
    return {"passed": all(checks.values()), "checks": checks, "thresholds": tolerance}


def cpu_model_name() -> str | None:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return platform.processor() or None
    for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", maxsplit=1)[1].strip()
    return platform.processor() or None


def validate_onnx(path: Path) -> dict[str, Any]:
    model = onnx.load(path)
    onnx.checker.check_model(model)
    session = onnxruntime.InferenceSession(
        str(path), providers=["CPUExecutionProvider"]
    )
    return {
        "checker": "passed",
        "ir_version": model.ir_version,
        "opsets": {item.domain or "ai.onnx": item.version for item in model.opset_import},
        "inputs": [
            {"name": item.name, "shape": item.shape, "type": item.type}
            for item in session.get_inputs()
        ],
        "outputs": [
            {"name": item.name, "shape": item.shape, "type": item.type}
            for item in session.get_outputs()
        ],
        "providers": session.get_providers(),
    }


def validate_openvino(directory: Path) -> dict[str, Any]:
    xml_files = sorted(directory.glob("*.xml"))
    bin_files = sorted(directory.glob("*.bin"))
    if len(xml_files) != 1 or len(bin_files) != 1:
        raise ValueError("OpenVINO export must contain exactly one XML and BIN")
    core = Core()
    model = core.read_model(xml_files[0])
    compiled = core.compile_model(model, "CPU")
    constant_types = Counter(
        str(operation.get_output_element_type(0))
        for operation in model.get_ops()
        if operation.get_type_name() == "Constant"
    )
    return {
        "read_model": "passed",
        "compile_cpu": "passed",
        "available_devices": core.available_devices,
        "inputs": [
            {"name": item.any_name, "shape": str(item.partial_shape), "type": str(item.element_type)}
            for item in compiled.inputs
        ],
        "outputs": [
            {"name": item.any_name, "shape": str(item.partial_shape), "type": str(item.element_type)}
            for item in compiled.outputs
        ],
        "constant_element_types": dict(sorted(constant_types.items())),
        "xml": xml_files[0].name,
        "bin": bin_files[0].name,
    }


def artifact_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def run_backend(
    backend: str,
    model_path: Path,
    image_paths: list[Path],
    inference: dict[str, Any],
    warmup_runs: int,
    repetitions: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    load_start = time.perf_counter()
    model = YOLO(str(model_path), task="detect")
    load_seconds = time.perf_counter() - load_start
    predict_kwargs = {
        "imgsz": int(inference["image_size"]),
        "conf": float(inference["confidence"]),
        "iou": float(inference["iou_nms"]),
        "max_det": int(inference["max_detections"]),
        "device": inference["device"],
        "rect": bool(inference["rect"]),
        "verbose": False,
    }
    for index in range(warmup_runs):
        model.predict(source=str(image_paths[index % len(image_paths)]), **predict_kwargs)

    detections: dict[str, dict[str, Any]] = {}
    timing_rows: list[dict[str, Any]] = []
    for repetition in range(repetitions):
        for image_path in image_paths:
            started = time.perf_counter()
            result = model.predict(source=str(image_path), **predict_kwargs)[0]
            wall_ms = (time.perf_counter() - started) * 1000.0
            timing_rows.append(
                {
                    "backend": backend,
                    "repetition": repetition,
                    "image_name": image_path.name,
                    "wall_ms": wall_ms,
                    "preprocess_ms": float(result.speed.get("preprocess", 0.0)),
                    "inference_ms": float(result.speed.get("inference", 0.0)),
                    "postprocess_ms": float(result.speed.get("postprocess", 0.0)),
                    "detections": int(result.boxes.shape[0]),
                }
            )
            if repetition == 0:
                detections[image_path.name] = result_to_detection(result)
    wall_values = [float(row["wall_ms"]) for row in timing_rows]
    timing = {
        "model_load_seconds": load_seconds,
        "warmup_runs": warmup_runs,
        "timed_images": len(timing_rows),
        "wall_ms": summarize_timings(wall_values),
        "preprocess_ms": summarize_timings(
            [float(row["preprocess_ms"]) for row in timing_rows]
        ),
        "inference_ms": summarize_timings(
            [float(row["inference_ms"]) for row in timing_rows]
        ),
        "postprocess_ms": summarize_timings(
            [float(row["postprocess_ms"]) for row in timing_rows]
        ),
        "fps_from_mean_wall": 1000.0 / float(np.mean(wall_values)),
        "process_peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * 1024,
    }
    return detections, timing, timing_rows


def write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    experiment_dir = resolve_repo_path(config["experiment_dir"])
    result_dir = resolve_repo_path(config["result_dir"])
    export_root = resolve_repo_path(config["export_root"])
    for target in (experiment_dir, result_dir, export_root):
        if target.exists():
            raise FileExistsError(f"deployment target already exists: {target}")
    experiment_dir.mkdir(parents=True)
    result_dir.mkdir(parents=True)
    export_root.mkdir(parents=True)
    shutil.copyfile(config_path, experiment_dir / "config.yaml")
    command = (
        "YOLO_CONFIG_DIR=/tmp .venv/bin/python scripts/export_and_validate_detector.py "
        "--config configs/e01_deployment_export.yaml\n"
    )
    (experiment_dir / "command.txt").write_text(command, encoding="utf-8")

    started_at = datetime.now(UTC)
    source_model = resolve_repo_path(config["source_model"])
    export_checkpoint = export_root / "best.pt"
    shutil.copyfile(source_model, export_checkpoint)
    export_config = config["export"]

    onnx_started = time.perf_counter()
    onnx_output = YOLO(str(export_checkpoint)).export(
        format="onnx",
        imgsz=int(export_config["image_size"]),
        batch=int(export_config["batch"]),
        dynamic=bool(export_config["dynamic"]),
        nms=bool(export_config["nms"]),
        opset=int(export_config["onnx"]["opset"]),
        simplify=bool(export_config["onnx"]["simplify"]),
        quantize=export_config["onnx"]["quantize"],
        device="cpu",
    )
    onnx_export_seconds = time.perf_counter() - onnx_started
    onnx_path = Path(str(onnx_output)).resolve()
    if not onnx_path.is_file():
        raise FileNotFoundError(f"ONNX export missing: {onnx_path}")

    openvino_started = time.perf_counter()
    openvino_output = YOLO(str(export_checkpoint)).export(
        format="openvino",
        imgsz=int(export_config["image_size"]),
        batch=int(export_config["batch"]),
        dynamic=bool(export_config["dynamic"]),
        nms=bool(export_config["nms"]),
        quantize=int(export_config["openvino"]["quantize"]),
        device="cpu",
    )
    openvino_export_seconds = time.perf_counter() - openvino_started
    openvino_dir = Path(str(openvino_output)).resolve()
    if not openvino_dir.is_dir():
        raise FileNotFoundError(f"OpenVINO export missing: {openvino_dir}")

    onnx_validation = validate_onnx(onnx_path)
    openvino_validation = validate_openvino(openvino_dir)
    subset_path = resolve_repo_path(config["subset_manifest"])
    subset = json.loads(subset_path.read_text(encoding="utf-8"))
    indexes = evenly_spaced_indices(
        len(subset["entries"]), int(config["benchmark"]["sample_count"])
    )
    images_dir = resolve_repo_path(config["images_dir"])
    image_paths = [images_dir / subset["entries"][index]["image_name"] for index in indexes]
    for image_path in image_paths:
        if cv2.imread(str(image_path), cv2.IMREAD_COLOR) is None:
            raise ValueError(f"unreadable benchmark image: {image_path}")
    sample_manifest = {
        "selection": config["benchmark"]["selection"],
        "population_size": len(subset["entries"]),
        "sample_count": len(image_paths),
        "source_indexes": indexes,
        "image_names": [path.name for path in image_paths],
        "selection_sha256": hashlib.sha256(
            "\n".join(path.name for path in image_paths).encode()
        ).hexdigest(),
    }
    write_json_atomic(experiment_dir / "sample_manifest.json", sample_manifest)

    backend_paths = {
        "pytorch": source_model,
        "onnx": onnx_path,
        "openvino": openvino_dir,
    }
    backend_detections: dict[str, dict[str, dict[str, Any]]] = {}
    timings: dict[str, Any] = {}
    timing_rows: list[dict[str, Any]] = []
    for backend in BACKEND_ORDER:
        detections, timing, rows = run_backend(
            backend,
            backend_paths[backend],
            image_paths,
            config["inference"],
            int(config["benchmark"]["warmup_runs"]),
            int(config["benchmark"]["timed_repetitions"]),
        )
        backend_detections[backend] = detections
        timings[backend] = timing
        timing_rows.extend(rows)

    agreement_rows: list[dict[str, Any]] = []
    agreement_summary: dict[str, Any] = {}
    for backend in ("onnx", "openvino"):
        backend_rows = []
        for image_path in image_paths:
            comparison = compare_detection_sets(
                backend_detections["pytorch"][image_path.name],
                backend_detections[backend][image_path.name],
                float(config["agreement"]["match_iou"]),
            )
            row = {"backend": backend, "image_name": image_path.name, **comparison}
            agreement_rows.append(row)
            backend_rows.append(row)
        aggregate = aggregate_agreement(backend_rows)
        aggregate["tolerance"] = check_tolerance(
            aggregate, config["agreement"][backend]
        )
        agreement_summary[backend] = aggregate

    timing_path = result_dir / "benchmark.csv"
    agreement_path = result_dir / "agreement.csv"
    write_csv(timing_path, tuple(timing_rows[0].keys()), timing_rows)
    write_csv(agreement_path, tuple(agreement_rows[0].keys()), agreement_rows)

    xml_path = next(openvino_dir.glob("*.xml"))
    bin_path = next(openvino_dir.glob("*.bin"))
    metadata_path = openvino_dir / "metadata.yaml"
    artifacts = {
        "source_checkpoint": artifact_record(source_model),
        "onnx": artifact_record(onnx_path),
        "openvino_xml": artifact_record(xml_path),
        "openvino_bin": artifact_record(bin_path),
        "openvino_metadata": artifact_record(metadata_path),
        "benchmark_csv": artifact_record(timing_path),
        "agreement_csv": artifact_record(agreement_path),
    }
    status = (
        "passed"
        if all(item["tolerance"]["passed"] for item in agreement_summary.values())
        else "failed_tolerance"
    )
    environment = {
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "source_revision": git_revision(),
        "platform": platform.platform(),
        "cpu": cpu_model_name(),
        "logical_cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "onnx": onnx.__version__,
        "onnxruntime": onnxruntime.__version__,
        "openvino": openvino.__version__,
        "onnxruntime_available_providers": onnxruntime.get_available_providers(),
        "openvino_available_devices": Core().available_devices,
    }
    write_json_atomic(experiment_dir / "environment.json", environment)
    summary = {
        "schema_version": 1,
        "deployment_id": config["deployment_id"],
        "status": status,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "source_revision": environment["source_revision"],
        "environment": environment,
        "sample_manifest": sample_manifest,
        "protocol": {
            "export": export_config,
            "inference": config["inference"],
            "benchmark": config["benchmark"],
            "agreement_match_iou": config["agreement"]["match_iou"],
        },
        "exports": {
            "onnx_fp32": {
                "status": "passed",
                "duration_seconds": onnx_export_seconds,
                "validation": onnx_validation,
            },
            "openvino_fp16": {
                "status": "passed",
                "duration_seconds": openvino_export_seconds,
                "validation": openvino_validation,
            },
        },
        "agreement": agreement_summary,
        "timing": timings,
        "artifacts": artifacts,
        "limitations": [
            "Benchmark uses 16 deterministic images and one timed repetition after two warm-ups.",
            "Wall timing is a local WSL CPU observation, not a production or real-time guarantee.",
            "OpenVINO was tested only on the CPU device exposed to this WSL environment.",
            "Export agreement is measured on final detections at confidence 0.25, not raw tensors across all values.",
        ],
    }
    write_json_atomic(experiment_dir / "summary.json", summary)
    write_json_atomic(result_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if status != "passed":
        raise RuntimeError("one or more exported backends failed agreement tolerance")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    run(parse_args().config.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
