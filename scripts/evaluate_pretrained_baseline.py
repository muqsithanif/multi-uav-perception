#!/usr/bin/env python3
"""Evaluate a pretrained COCO detector on a locked VisDrone validation subset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import ultralytics
import yaml
from ultralytics import YOLO
from ultralytics.utils.metrics import DetMetrics, box_iou

if __package__:
    from .render_visdrone_audit import parse_yolo_boxes
    from .visdrone_dataset import collect_pairs, write_json_atomic
else:
    from render_visdrone_audit import parse_yolo_boxes
    from visdrone_dataset import collect_pairs, write_json_atomic


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "e00_pretrained_baseline.yaml"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evenly_spaced_indices(total: int, count: int) -> list[int]:
    """Return deterministic indexes spanning the full sorted collection."""
    if total <= 0:
        raise ValueError("total must be positive")
    if count <= 0 or count > total:
        raise ValueError("count must be in [1, total]")
    if count == 1:
        return [total // 2]
    indexes = [round(i * (total - 1) / (count - 1)) for i in range(count)]
    if len(set(indexes)) != count:
        raise ValueError("selection produced duplicate indexes")
    return indexes


def yolo_boxes_to_xyxy(
    label_path: Path,
    class_count: int,
    image_width: int,
    image_height: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Convert validated normalized YOLO labels to pixel xyxy tensors."""
    boxes = parse_yolo_boxes(label_path, class_count)
    classes = torch.tensor([box.class_id for box in boxes], dtype=torch.float32)
    xyxy = []
    for box in boxes:
        xyxy.append(
            [
                (box.center_x - box.width / 2) * image_width,
                (box.center_y - box.height / 2) * image_height,
                (box.center_x + box.width / 2) * image_width,
                (box.center_y + box.height / 2) * image_height,
            ]
        )
    return torch.tensor(xyxy, dtype=torch.float32).reshape(-1, 4), classes


def match_predictions(
    pred_classes: torch.Tensor,
    true_classes: torch.Tensor,
    iou: torch.Tensor,
    thresholds: torch.Tensor,
) -> torch.Tensor:
    """Match detections one-to-one using the pinned Ultralytics policy."""
    correct = np.zeros((pred_classes.shape[0], thresholds.shape[0]), dtype=bool)
    if pred_classes.numel() == 0 or true_classes.numel() == 0:
        return torch.from_numpy(correct)
    class_compatible_iou = iou * (true_classes[:, None] == pred_classes[None, :])
    compatible = class_compatible_iou.cpu().numpy()
    for threshold_index, threshold in enumerate(thresholds.cpu().tolist()):
        matches = np.array(np.nonzero(compatible >= threshold)).T
        if matches.shape[0] > 1:
            matches = matches[compatible[matches[:, 0], matches[:, 1]].argsort()[::-1]]
            matches = matches[np.unique(matches[:, 1], return_index=True)[1]]
            matches = matches[np.unique(matches[:, 0], return_index=True)[1]]
        if matches.shape[0]:
            correct[matches[:, 1].astype(int), threshold_index] = True
    return torch.from_numpy(correct)


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


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
        raise ValueError("baseline config must be a mapping")
    required = {
        "experiment_id",
        "model",
        "images_dir",
        "labels_dir",
        "subset_size",
        "project_classes",
        "model_class_mapping",
        "experiment_dir",
        "result_dir",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"missing config keys: {missing}")
    return config


def validate_mapping(config: dict[str, Any], model_names: dict[int, str]) -> dict[int, int]:
    project_classes = {int(key): value for key, value in config["project_classes"].items()}
    if sorted(project_classes) != list(range(len(project_classes))):
        raise ValueError("project classes must be contiguous from zero")
    mapping: dict[int, int] = {}
    mapped_projects: set[int] = set()
    for raw_model_id, details in config["model_class_mapping"].items():
        model_id = int(raw_model_id)
        project_id = int(details["project_id"])
        if model_names.get(model_id) != details["model_name"]:
            raise ValueError(f"model class mismatch at id {model_id}")
        if project_classes.get(project_id) != details["project_name"]:
            raise ValueError(f"project class mismatch at id {project_id}")
        if project_id in mapped_projects:
            raise ValueError(f"project class {project_id} has multiple model mappings")
        mapping[model_id] = project_id
        mapped_projects.add(project_id)
    unsupported = {int(item["project_id"]) for item in config["unsupported_project_classes"]}
    if mapped_projects | unsupported != set(project_classes):
        raise ValueError("mapped and unsupported classes must cover every project class")
    if mapped_projects & unsupported:
        raise ValueError("a project class cannot be both mapped and unsupported")
    return mapping


def build_subset_manifest(
    images_dir: Path,
    labels_dir: Path,
    subset_size: int,
    class_count: int,
) -> tuple[list[tuple[Path, Path]], dict[str, Any]]:
    pairs = collect_pairs(images_dir, labels_dir)
    indexes = evenly_spaced_indices(len(pairs), subset_size)
    selected = [pairs[index] for index in indexes]
    class_counts = [0] * class_count
    entries = []
    for index, (image_path, label_path) in zip(indexes, selected, strict=True):
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"unreadable image: {image_path}")
        boxes = parse_yolo_boxes(label_path, class_count)
        for box in boxes:
            class_counts[box.class_id] += 1
        entries.append(
            {
                "source_index": index,
                "image_name": image_path.name,
                "label_name": label_path.name,
                "image_width": int(image.shape[1]),
                "image_height": int(image.shape[0]),
                "ground_truth_objects": len(boxes),
                "ground_truth_class_counts": {
                    str(class_id): sum(box.class_id == class_id for box in boxes)
                    for class_id in range(class_count)
                },
                "image_sha256": sha256_file(image_path),
                "label_sha256": sha256_file(label_path),
            }
        )
    if any(count == 0 for count in class_counts):
        raise ValueError(f"locked subset does not cover every project class: {class_counts}")
    canonical_selection = "\n".join(entry["image_name"] for entry in entries).encode()
    manifest = {
        "schema_version": 1,
        "selection_policy": "evenly_spaced_sorted_filename",
        "population_size": len(pairs),
        "subset_size": len(selected),
        "selection_sha256": hashlib.sha256(canonical_selection).hexdigest(),
        "ground_truth_class_counts": {
            str(class_id): count for class_id, count in enumerate(class_counts)
        },
        "entries": entries,
    }
    return selected, manifest


def index_pairs_by_image_name(
    pairs: list[tuple[Path, Path]],
) -> dict[str, tuple[Path, Path]]:
    """Index locked pairs without relying on predictor output ordering."""
    indexed: dict[str, tuple[Path, Path]] = {}
    for image_path, label_path in pairs:
        if image_path.name in indexed:
            raise ValueError(f"duplicate selected image name: {image_path.name}")
        indexed[image_path.name] = (image_path, label_path)
    return indexed


def write_metrics_csv(
    path: Path,
    overall: dict[str, float],
    per_class: list[dict[str, Any]],
    total_instances: int,
) -> None:
    fieldnames = (
        "scope",
        "class_id",
        "class_name",
        "instances",
        "precision",
        "recall",
        "map50",
        "map50_95",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "scope": "overall_macro",
                "class_id": "",
                "class_name": "all",
                "instances": total_instances,
                **overall,
            }
        )
        for row in per_class:
            writer.writerow({"scope": "class", **row})


def run(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    random.seed(int(config["seed"]))
    np.random.seed(int(config["seed"]))
    torch.manual_seed(int(config["seed"]))

    experiment_dir = resolve_repo_path(config["experiment_dir"])
    result_dir = resolve_repo_path(config["result_dir"])
    if experiment_dir.exists() or result_dir.exists():
        raise FileExistsError("experiment/result directory already exists; use a new experiment ID")
    experiment_dir.mkdir(parents=True)
    result_dir.mkdir(parents=True)
    shutil.copyfile(config_path, experiment_dir / "config.yaml")

    started_at = datetime.now(UTC)
    revision = git_revision()
    model_path = resolve_repo_path(config["model"])
    model = YOLO(str(model_path))
    model_names = {int(key): value for key, value in model.names.items()}
    mapping = validate_mapping(config, model_names)
    class_names = {int(key): value for key, value in config["project_classes"].items()}
    thresholds = torch.tensor(config["evaluation_iou_thresholds"], dtype=torch.float32)

    selected, subset_manifest = build_subset_manifest(
        resolve_repo_path(config["images_dir"]),
        resolve_repo_path(config["labels_dir"]),
        int(config["subset_size"]),
        len(class_names),
    )
    subset_manifest.update(
        {
            "created_at_utc": datetime.now(UTC).isoformat(),
            "dataset": config["dataset"],
            "split": config["split"],
            "source_revision": revision,
        }
    )
    write_json_atomic(experiment_dir / "subset_manifest.json", subset_manifest)

    environment = {
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "source_revision": revision,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "cuda_available": torch.cuda.is_available(),
        "torch_num_threads": torch.get_num_threads(),
    }
    write_json_atomic(experiment_dir / "environment.json", environment)

    metrics = DetMetrics(names=class_names)
    prediction_counts = {str(class_id): 0 for class_id in class_names}
    stage_seconds = {"preprocess": 0.0, "inference": 0.0, "postprocess": 0.0}
    wall_start = time.perf_counter()
    predictions = model.predict(
        source=[str(image_path) for image_path, _ in selected],
        imgsz=int(config["image_size"]),
        conf=float(config["confidence"]),
        iou=float(config["iou_nms"]),
        max_det=int(config["max_detections"]),
        batch=int(config["batch"]),
        device=config["device"],
        half=bool(config["half"]),
        rect=bool(config["rect"]),
        classes=sorted(mapping),
        stream=True,
        verbose=False,
    )
    selected_by_name = index_pairs_by_image_name(selected)
    seen_names: set[str] = set()
    for result in predictions:
        result_name = Path(result.path).name
        if result_name not in selected_by_name:
            raise RuntimeError(f"prediction is outside locked subset: {result_name}")
        if result_name in seen_names:
            raise RuntimeError(f"duplicate prediction result: {result_name}")
        image_path, label_path = selected_by_name[result_name]
        seen_names.add(result_name)
        image_height, image_width = result.orig_shape
        true_boxes, true_classes = yolo_boxes_to_xyxy(
            label_path, len(class_names), image_width, image_height
        )
        pred_boxes = result.boxes.xyxy.detach().cpu().float()
        pred_conf = result.boxes.conf.detach().cpu().numpy()
        raw_pred_classes = result.boxes.cls.detach().cpu().to(torch.int64)
        pred_classes = torch.tensor(
            [mapping[int(class_id)] for class_id in raw_pred_classes.tolist()],
            dtype=torch.float32,
        )
        for project_id in pred_classes.to(torch.int64).tolist():
            prediction_counts[str(project_id)] += 1
        iou = box_iou(true_boxes, pred_boxes)
        correct = match_predictions(pred_classes, true_classes, iou, thresholds)
        metrics.update_stats(
            {
                "tp": correct.numpy(),
                "conf": pred_conf,
                "pred_cls": pred_classes.numpy(),
                "target_cls": true_classes.numpy(),
                "target_img": np.unique(true_classes.numpy()),
                "im_name": image_path.name,
            }
        )
        for stage in stage_seconds:
            stage_seconds[stage] += float(result.speed.get(stage, 0.0)) / 1000.0
    wall_seconds = time.perf_counter() - wall_start
    missing_results = sorted(selected_by_name.keys() - seen_names)
    if missing_results:
        raise RuntimeError(
            f"missing {len(missing_results)} prediction results; first={missing_results[0]}"
        )
    seen = len(seen_names)

    curves_dir = result_dir / "curves"
    curves_dir.mkdir(parents=True)
    metrics.process(save_dir=curves_dir, plot=True)
    mean_precision, mean_recall, map50, map50_95 = metrics.mean_results()
    overall = {
        "precision": float(mean_precision),
        "recall": float(mean_recall),
        "map50": float(map50),
        "map50_95": float(map50_95),
    }
    per_class = []
    class_result_by_id = {
        int(class_id): metrics.class_result(position)
        for position, class_id in enumerate(metrics.ap_class_index)
    }
    for class_id, class_name in class_names.items():
        precision, recall, class_map50, class_map = class_result_by_id[class_id]
        per_class.append(
            {
                "class_id": class_id,
                "class_name": class_name,
                "instances": int(subset_manifest["ground_truth_class_counts"][str(class_id)]),
                "precision": float(precision),
                "recall": float(recall),
                "map50": float(class_map50),
                "map50_95": float(class_map),
            }
        )
    metrics_path = result_dir / "metrics.csv"
    write_metrics_csv(
        metrics_path,
        overall,
        per_class,
        sum(subset_manifest["ground_truth_class_counts"].values()),
    )
    finished_at = datetime.now(UTC)
    summary = {
        "schema_version": 1,
        "experiment_id": config["experiment_id"],
        "status": "passed",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "source_revision": revision,
        "dataset": config["dataset"],
        "split": config["split"],
        "subset": {
            "size": len(selected),
            "population_size": subset_manifest["population_size"],
            "selection_policy": subset_manifest["selection_policy"],
            "selection_sha256": subset_manifest["selection_sha256"],
            "ground_truth_class_counts": subset_manifest["ground_truth_class_counts"],
        },
        "model": {
            "path": config["model"],
            "bytes": model_path.stat().st_size,
            "sha256": sha256_file(model_path),
            "source_classes": len(model_names),
        },
        "class_mapping": config["model_class_mapping"],
        "unsupported_project_classes": config["unsupported_project_classes"],
        "protocol": {
            "image_size": int(config["image_size"]),
            "confidence": float(config["confidence"]),
            "iou_nms": float(config["iou_nms"]),
            "max_detections": int(config["max_detections"]),
            "batch": int(config["batch"]),
            "device": config["device"],
            "half": bool(config["half"]),
            "rect": bool(config["rect"]),
            "evaluation_iou_thresholds": config["evaluation_iou_thresholds"],
            "metric_implementation": "ultralytics.utils.metrics.DetMetrics",
        },
        "metrics": {"overall_macro": overall, "per_class": per_class},
        "prediction_counts": prediction_counts,
        "timing": {
            "evaluation_wall_seconds": wall_seconds,
            "wall_milliseconds_per_image": wall_seconds * 1000.0 / seen,
            "reported_stage_seconds": stage_seconds,
        },
        "artifacts": {
            "config": "config.yaml",
            "environment": "environment.json",
            "subset_manifest": "subset_manifest.json",
            "metrics_csv": metrics_path.relative_to(REPO_ROOT).as_posix(),
            "curves_dir": curves_dir.relative_to(REPO_ROOT).as_posix(),
        },
    }
    write_json_atomic(experiment_dir / "summary.json", summary)
    write_json_atomic(result_dir / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run(args.config.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
