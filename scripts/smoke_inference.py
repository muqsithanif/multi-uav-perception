#!/usr/bin/env python3
"""Run and record the Day 1 one-image pretrained inference smoke test."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torchvision
import ultralytics
import yaml
from ultralytics import YOLO


REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "configs" / "smoke_pretrained.yaml",
        help="Path to the smoke-test YAML configuration.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def git_output(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip()


def first_cpu_model() -> str | None:
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return None
    for line in cpuinfo.read_text(encoding="utf-8").splitlines():
        if line.lower().startswith("model name"):
            return line.split(":", maxsplit=1)[1].strip()
    return None


def memory_total_kib() -> int | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    for line in meminfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            return int(line.split()[1])
    return None


def environment_record() -> dict[str, Any]:
    return {
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "kernel_release": platform.release(),
        "machine": platform.machine(),
        "cpu_model": first_cpu_model(),
        "logical_cpu_count": os.cpu_count(),
        "memory_total_kib": memory_total_kib(),
        "python": platform.python_version(),
        "packages": {
            "opencv_python": cv2.__version__,
            "numpy": np.__version__,
            "pyyaml": yaml.__version__,
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "ultralytics": ultralytics.__version__,
        },
        "torch": {
            "cuda_available": torch.cuda.is_available(),
            "thread_count": torch.get_num_threads(),
        },
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def validate_config(config: dict[str, Any]) -> None:
    required = {
        "experiment_id",
        "seed",
        "model",
        "source",
        "source_metadata",
        "device",
        "image_size",
        "confidence",
        "iou",
        "max_detections",
        "half",
        "experiment_dir",
        "result_dir",
    }
    missing = sorted(required.difference(config))
    if missing:
        raise ValueError(f"Missing configuration keys: {', '.join(missing)}")
    if config["device"] != "cpu":
        raise ValueError("The Day 1 fallback smoke test must use device: cpu")
    if config["half"] is not False:
        raise ValueError("The CPU smoke test must use half: false")


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validate_config(config)

    source_path = repo_path(config["source"])
    source_metadata_path = repo_path(config["source_metadata"])
    experiment_dir = repo_path(config["experiment_dir"])
    result_dir = repo_path(config["result_dir"])
    if not source_path.is_file():
        raise FileNotFoundError(f"Smoke source not found: {source_path}")
    if not source_metadata_path.is_file():
        raise FileNotFoundError(f"Source metadata not found: {source_metadata_path}")

    source_metadata = yaml.safe_load(source_metadata_path.read_text(encoding="utf-8"))
    source_sha256 = sha256_file(source_path)
    if source_sha256 != source_metadata["sha256"]:
        raise ValueError("Source checksum does not match its metadata record")

    experiment_dir.mkdir(parents=True, exist_ok=False)
    result_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(config_path, experiment_dir / "config.yaml")

    seed = int(config["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    started_at = datetime.now(UTC)
    overall_started = time.perf_counter()
    source_revision = git_output("rev-parse", "HEAD")
    tracked_changes = git_output("status", "--porcelain", "--untracked-files=no")
    environment = environment_record()
    write_json(experiment_dir / "environment.json", environment)

    model_started = time.perf_counter()
    model = YOLO(str(config["model"]), task="detect")
    model_load_ms = (time.perf_counter() - model_started) * 1000.0

    prediction_started = time.perf_counter()
    results = model.predict(
        source=str(source_path),
        imgsz=int(config["image_size"]),
        conf=float(config["confidence"]),
        iou=float(config["iou"]),
        max_det=int(config["max_detections"]),
        device=str(config["device"]),
        half=bool(config["half"]),
        verbose=False,
        save=False,
    )
    prediction_wall_ms = (time.perf_counter() - prediction_started) * 1000.0
    if len(results) != 1:
        raise RuntimeError(f"Expected one result, received {len(results)}")

    result = results[0]
    detections: list[dict[str, Any]] = []
    if result.boxes is not None:
        for box in result.boxes:
            class_id = int(box.cls.item())
            detections.append(
                {
                    "class_id": class_id,
                    "class_name": result.names[class_id],
                    "confidence": round(float(box.conf.item()), 6),
                    "xyxy_px": [round(float(value), 3) for value in box.xyxy[0].tolist()],
                }
            )

    render_started = time.perf_counter()
    prediction_path = result_dir / "prediction.jpg"
    if not cv2.imwrite(str(prediction_path), result.plot()):
        raise RuntimeError(f"Failed to save prediction image: {prediction_path}")
    render_and_save_ms = (time.perf_counter() - render_started) * 1000.0
    if prediction_path.stat().st_size == 0:
        raise RuntimeError("Prediction image is empty")

    detections_path = result_dir / "detections.json"
    write_json(detections_path, detections)

    checkpoint_path = Path(str(model.ckpt_path)).resolve()
    completed_at = datetime.now(UTC)
    summary = {
        "schema_version": 1,
        "status": "success",
        "experiment_id": config["experiment_id"],
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": completed_at.isoformat(),
        "source_revision": source_revision,
        "tracked_worktree_clean_at_start": tracked_changes == "",
        "invocation": [sys.executable, *sys.argv],
        "seed": seed,
        "input": {
            "path": relative_path(source_path),
            "metadata_path": relative_path(source_metadata_path),
            "sha256": source_sha256,
            "width_px": int(result.orig_shape[1]),
            "height_px": int(result.orig_shape[0]),
            "license": source_metadata["license"],
            "source_page": source_metadata["source_page"],
        },
        "model": {
            "requested": config["model"],
            "checkpoint_path": relative_path(checkpoint_path),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "checkpoint_size_bytes": checkpoint_path.stat().st_size,
            "task": "detect",
        },
        "settings": {
            "device": config["device"],
            "image_size": int(config["image_size"]),
            "confidence": float(config["confidence"]),
            "iou": float(config["iou"]),
            "max_detections": int(config["max_detections"]),
            "half": bool(config["half"]),
        },
        "timing": {
            "classification": "smoke_only_not_a_benchmark",
            "warmup_runs": 0,
            "sample_count": 1,
            "model_load_wall_ms": round(model_load_ms, 3),
            "prediction_wall_ms": round(prediction_wall_ms, 3),
            "ultralytics_speed_ms": {
                key: round(float(value), 3) for key, value in result.speed.items()
            },
            "render_and_save_wall_ms": round(render_and_save_ms, 3),
            "total_wall_ms": round((time.perf_counter() - overall_started) * 1000.0, 3),
        },
        "detections": {
            "count": len(detections),
            "class_counts": dict(sorted(Counter(item["class_name"] for item in detections).items())),
            "path": relative_path(detections_path),
        },
        "artifacts": {
            "config_snapshot": relative_path(experiment_dir / "config.yaml"),
            "environment": relative_path(experiment_dir / "environment.json"),
            "prediction": relative_path(prediction_path),
        },
    }
    summary_path = experiment_dir / "summary.json"
    write_json(summary_path, summary)
    (experiment_dir / "command.txt").write_text(
        " ".join(summary["invocation"]) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "status": summary["status"],
        "experiment_id": summary["experiment_id"],
        "detections": summary["detections"]["count"],
        "prediction_wall_ms": summary["timing"]["prediction_wall_ms"],
        "summary": relative_path(summary_path),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
