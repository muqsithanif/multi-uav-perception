#!/usr/bin/env python3
"""Analyze E01 detection errors using locked VisDrone source metadata."""

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
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import ultralytics
import yaml
from ultralytics import YOLO
from ultralytics.utils.metrics import box_iou

if __package__:
    from .evaluate_pretrained_baseline import yolo_boxes_to_xyxy
    from .visdrone_dataset import (
        convert_box,
        load_conversion_config,
        parse_annotation_file,
        write_json_atomic,
    )
else:
    from evaluate_pretrained_baseline import yolo_boxes_to_xyxy
    from visdrone_dataset import (
        convert_box,
        load_conversion_config,
        parse_annotation_file,
        write_json_atomic,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "e01_error_analysis.yaml"
OCCLUSION_NAMES = {0: "none", 1: "partial", 2: "heavy"}
TRUNCATION_NAMES = {0: "not_truncated", 1: "truncated"}
SIZE_ORDER = ("small", "medium", "large")


@dataclass(frozen=True)
class SourceObject:
    class_id: int
    class_name: str
    xyxy: tuple[float, float, float, float]
    source_category: int
    truncation: int
    occlusion: int
    source_line: int


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
        raise ValueError("error-analysis config must be a mapping")
    required = {
        "analysis_id",
        "model",
        "images_dir",
        "labels_dir",
        "source_annotations_dir",
        "conversion_config",
        "subset_manifest",
        "project_classes",
        "size_area_thresholds_px2",
        "experiment_dir",
        "result_dir",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"missing config keys: {missing}")
    return config


def size_bucket(area_px2: float, small_max: float, medium_max: float) -> str:
    if area_px2 < 0:
        raise ValueError("box area cannot be negative")
    if not 0 < small_max < medium_max:
        raise ValueError("size thresholds must be positive and increasing")
    if area_px2 < small_max:
        return "small"
    if area_px2 < medium_max:
        return "medium"
    return "large"


def match_boxes_at_iou(
    true_boxes: torch.Tensor,
    pred_boxes: torch.Tensor,
    threshold: float,
    true_classes: torch.Tensor | None = None,
    pred_classes: torch.Tensor | None = None,
    class_relation: str = "same",
) -> list[tuple[int, int, float]]:
    """Return deterministic one-to-one matches sorted by descending IoU."""
    if true_boxes.shape[0] == 0 or pred_boxes.shape[0] == 0:
        return []
    iou = box_iou(true_boxes, pred_boxes).cpu().numpy()
    if (true_classes is None) != (pred_classes is None):
        raise ValueError("both class tensors must be provided together")
    if true_classes is not None and pred_classes is not None:
        if class_relation not in {"same", "different"}:
            raise ValueError("class_relation must be same or different")
        same_class = (
            true_classes[:, None].cpu().numpy()
            == pred_classes[None, :].cpu().numpy()
        )
        compatible = same_class if class_relation == "same" else ~same_class
        iou = iou * compatible
    elif class_relation != "same":
        raise ValueError("different class relation requires class tensors")
    candidates = np.array(np.nonzero(iou >= threshold)).T
    if candidates.shape[0] == 0:
        return []
    candidates = candidates[iou[candidates[:, 0], candidates[:, 1]].argsort()[::-1]]
    selected: list[tuple[int, int, float]] = []
    used_true: set[int] = set()
    used_pred: set[int] = set()
    for true_index, pred_index in candidates.tolist():
        if true_index in used_true or pred_index in used_pred:
            continue
        used_true.add(true_index)
        used_pred.add(pred_index)
        selected.append((true_index, pred_index, float(iou[true_index, pred_index])))
    return selected


def build_source_objects(
    annotation_path: Path,
    image_width: int,
    image_height: int,
    conversion: dict[str, Any],
) -> list[SourceObject]:
    objects: list[SourceObject] = []
    mapping = conversion["class_mapping"]
    for annotation in parse_annotation_file(annotation_path):
        if annotation.score == 0:
            continue
        if annotation.category in conversion["ignored_source_class_ids"]:
            continue
        if annotation.category in conversion["excluded_source_class_ids"]:
            continue
        if annotation.width <= 0 or annotation.height <= 0:
            continue
        normalized, _ = convert_box(annotation, image_width, image_height)
        center_x, center_y, width, height = normalized
        xyxy = (
            (center_x - width / 2) * image_width,
            (center_y - height / 2) * image_height,
            (center_x + width / 2) * image_width,
            (center_y + height / 2) * image_height,
        )
        details = mapping[annotation.category]
        objects.append(
            SourceObject(
                class_id=int(details["project_id"]),
                class_name=str(details["name"]),
                xyxy=xyxy,
                source_category=annotation.category,
                truncation=annotation.truncation,
                occlusion=annotation.occlusion,
                source_line=annotation.line_number,
            )
        )
    return objects


def validate_source_alignment(
    objects: list[SourceObject],
    label_path: Path,
    class_count: int,
    image_width: int,
    image_height: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    boxes, classes = yolo_boxes_to_xyxy(
        label_path, class_count, image_width, image_height
    )
    source_boxes = torch.tensor([item.xyxy for item in objects], dtype=torch.float32)
    source_boxes = source_boxes.reshape(-1, 4)
    source_classes = torch.tensor(
        [item.class_id for item in objects], dtype=torch.float32
    )
    if not torch.equal(classes, source_classes):
        raise ValueError(f"source/project class order differs: {label_path.name}")
    if not torch.allclose(boxes, source_boxes, atol=0.001, rtol=0.0):
        difference = float(torch.max(torch.abs(boxes - source_boxes)))
        raise ValueError(
            f"source/project boxes differ: {label_path.name}, max_delta={difference}"
        )
    return boxes, classes


def aggregate_ground_truth(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, dict[str, int | float]] = {}
    for row in rows:
        value = str(row[key])
        counts = grouped.setdefault(value, {"ground_truth": 0, "matched": 0})
        counts["ground_truth"] = int(counts["ground_truth"]) + 1
        counts["matched"] = int(counts["matched"]) + int(bool(row["matched"]))
    for counts in grouped.values():
        ground_truth = int(counts["ground_truth"])
        matched = int(counts["matched"])
        counts["missed"] = ground_truth - matched
        counts["recall_at_operating_point"] = matched / ground_truth
    return grouped


def select_examples(
    image_rows: list[dict[str, Any]], max_examples: int
) -> list[dict[str, Any]]:
    if max_examples <= 0:
        return []
    reasons = (
        ("small_false_negatives", "small_false_negatives"),
        ("heavy_occlusion_false_negatives", "heavy_occlusion_false_negatives"),
        ("truncated_false_negatives", "truncated_false_negatives"),
        ("classification_confusions", "classification_confusions"),
        ("false_positives", "false_positives"),
        ("total_errors", "total_errors"),
    )
    chosen: list[dict[str, Any]] = []
    used: set[str] = set()
    for reason, field in reasons:
        candidates = [
            row
            for row in image_rows
            if row["image_name"] not in used and int(row[field]) > 0
        ]
        candidates.sort(
            key=lambda row: (-int(row[field]), -int(row["total_errors"]), row["image_name"])
        )
        if candidates:
            selected = dict(candidates[0])
            selected["selection_reason"] = reason
            chosen.append(selected)
            used.add(selected["image_name"])
        if len(chosen) >= max_examples:
            return chosen
    remaining = [row for row in image_rows if row["image_name"] not in used]
    remaining.sort(key=lambda row: (-int(row["total_errors"]), row["image_name"]))
    for row in remaining:
        selected = dict(row)
        selected["selection_reason"] = "total_errors_fallback"
        chosen.append(selected)
        if len(chosen) >= max_examples:
            break
    return chosen


def write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def draw_box(
    image: np.ndarray,
    xyxy: tuple[float, float, float, float] | list[float],
    color: tuple[int, int, int],
    label: str,
    thickness: int,
) -> None:
    x1, y1, x2, y2 = (int(round(value)) for value in xyxy)
    cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
    if label:
        cv2.putText(
            image,
            label,
            (max(0, x1), max(12, y1 - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            color,
            1,
            cv2.LINE_AA,
        )


def render_overlay(
    destination: Path,
    image_path: Path,
    objects: list[SourceObject],
    pred_boxes: list[list[float]],
    pred_classes: list[int],
    pred_confidences: list[float],
    matches: list[tuple[int, int, float]],
    confusions: list[tuple[int, int, float]],
    class_names: dict[int, str],
    image_row: dict[str, Any],
    max_false_positives: int,
) -> None:
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"unreadable image: {image_path}")
    matched_true = {true_index for true_index, _, _ in matches}
    matched_pred = {pred_index for _, pred_index, _ in matches}
    confusion_pred = {pred_index for _, pred_index, _ in confusions}
    thickness = max(1, round(max(image.shape[:2]) / 900))

    for true_index, item in enumerate(objects):
        if true_index in matched_true:
            continue
        area = (item.xyxy[2] - item.xyxy[0]) * (item.xyxy[3] - item.xyxy[1])
        label = (
            f"FN {item.class_name} a={area:.0f} "
            f"o={item.occlusion} t={item.truncation}"
        )
        draw_box(image, item.xyxy, (0, 0, 255), label, thickness)

    false_positive_indexes = [
        index for index in range(len(pred_boxes)) if index not in matched_pred
    ]
    false_positive_indexes.sort(key=lambda index: -pred_confidences[index])
    shown = false_positive_indexes[:max_false_positives]
    for pred_index in shown:
        color = (255, 0, 255) if pred_index in confusion_pred else (0, 165, 255)
        prefix = "CLS" if pred_index in confusion_pred else "FP"
        label = (
            f"{prefix} {class_names[pred_classes[pred_index]]} "
            f"{pred_confidences[pred_index]:.2f}"
        )
        draw_box(image, pred_boxes[pred_index], color, label, thickness)

    header_height = 50
    cv2.rectangle(image, (0, 0), (image.shape[1], header_height), (20, 20, 20), -1)
    cv2.putText(
        image,
        f"{image_row['selection_reason']} | TP {image_row['true_positives']} "
        f"FN {image_row['false_negatives']} FP {image_row['false_positives']}",
        (8, 19),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        f"red=FN orange=FP magenta=class confusion | FP shown {len(shown)}/{len(false_positive_indexes)}",
        (8, 41),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), image):
        raise OSError(f"failed to write overlay: {destination}")


def run(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    random.seed(int(config["seed"]))
    np.random.seed(int(config["seed"]))
    torch.manual_seed(int(config["seed"]))

    experiment_dir = resolve_repo_path(config["experiment_dir"])
    result_dir = resolve_repo_path(config["result_dir"])
    if experiment_dir.exists() or result_dir.exists():
        raise FileExistsError("analysis experiment/result directory already exists")
    experiment_dir.mkdir(parents=True)
    result_dir.mkdir(parents=True)
    shutil.copyfile(config_path, experiment_dir / "config.yaml")
    command = (
        "YOLO_CONFIG_DIR=/tmp .venv/bin/python scripts/analyze_detection_errors.py "
        "--config configs/e01_error_analysis.yaml\n"
    )
    (experiment_dir / "command.txt").write_text(command, encoding="utf-8")

    started_at = datetime.now(UTC)
    wall_start = time.perf_counter()
    model_path = resolve_repo_path(config["model"])
    images_dir = resolve_repo_path(config["images_dir"])
    labels_dir = resolve_repo_path(config["labels_dir"])
    source_annotations_dir = resolve_repo_path(config["source_annotations_dir"])
    subset_path = resolve_repo_path(config["subset_manifest"])
    subset = json.loads(subset_path.read_text(encoding="utf-8"))
    conversion = load_conversion_config(resolve_repo_path(config["conversion_config"]))
    class_names = {int(key): str(value) for key, value in config["project_classes"].items()}

    model = YOLO(str(model_path))
    model_names = {int(key): str(value) for key, value in model.names.items()}
    if model_names != class_names:
        raise ValueError(f"checkpoint classes differ from project classes: {model_names}")

    entries_by_name = {entry["image_name"]: entry for entry in subset["entries"]}
    source_paths = [images_dir / entry["image_name"] for entry in subset["entries"]]
    for entry, image_path in zip(subset["entries"], source_paths, strict=True):
        label_path = labels_dir / entry["label_name"]
        if sha256_file(image_path) != entry["image_sha256"]:
            raise ValueError(f"locked image hash differs: {image_path.name}")
        if sha256_file(label_path) != entry["label_sha256"]:
            raise ValueError(f"locked label hash differs: {label_path.name}")
    source_list_path = experiment_dir / "source_files.txt"
    source_list_path.write_text(
        "\n".join(str(path) for path in source_paths) + "\n", encoding="utf-8"
    )

    predictions = model.predict(
        source=str(source_list_path),
        imgsz=int(config["image_size"]),
        conf=float(config["confidence"]),
        iou=float(config["iou_nms"]),
        max_det=int(config["max_detections"]),
        batch=int(config["batch"]),
        device=config["device"],
        half=bool(config["half"]),
        rect=bool(config["rect"]),
        stream=True,
        verbose=False,
    )

    thresholds = config["size_area_thresholds_px2"]
    small_max = float(thresholds["small_max_exclusive"])
    medium_max = float(thresholds["medium_max_exclusive"])
    gt_rows: list[dict[str, Any]] = []
    fp_rows: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []
    image_rows: list[dict[str, Any]] = []
    render_data: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()

    for result in predictions:
        image_name = Path(result.path).name
        if image_name not in entries_by_name or image_name in seen:
            raise RuntimeError(f"unexpected or duplicate prediction: {image_name}")
        seen.add(image_name)
        entry = entries_by_name[image_name]
        image_path = images_dir / image_name
        label_path = labels_dir / entry["label_name"]
        annotation_path = source_annotations_dir / f"{Path(image_name).stem}.txt"
        image_height, image_width = result.orig_shape
        objects = build_source_objects(
            annotation_path, image_width, image_height, conversion
        )
        true_boxes, true_classes = validate_source_alignment(
            objects, label_path, len(class_names), image_width, image_height
        )
        pred_boxes_tensor = result.boxes.xyxy.detach().cpu().float()
        pred_classes_tensor = result.boxes.cls.detach().cpu().to(torch.int64)
        pred_confidences = result.boxes.conf.detach().cpu().tolist()
        matches = match_boxes_at_iou(
            true_boxes,
            pred_boxes_tensor,
            float(config["match_iou"]),
            true_classes.to(torch.int64),
            pred_classes_tensor,
        )
        matched_true = {true_index: (pred_index, iou) for true_index, pred_index, iou in matches}
        matched_pred = {pred_index for _, pred_index, _ in matches}
        unmatched_true = [index for index in range(len(objects)) if index not in matched_true]
        unmatched_pred = [
            index for index in range(pred_boxes_tensor.shape[0]) if index not in matched_pred
        ]
        confusion_matches: list[tuple[int, int, float]] = []
        if unmatched_true and unmatched_pred:
            local_matches = match_boxes_at_iou(
                true_boxes[unmatched_true],
                pred_boxes_tensor[unmatched_pred],
                float(config["match_iou"]),
                true_classes[unmatched_true].to(torch.int64),
                pred_classes_tensor[unmatched_pred],
                class_relation="different",
            )
            for local_true, local_pred, iou in local_matches:
                true_index = unmatched_true[local_true]
                pred_index = unmatched_pred[local_pred]
                confusion_matches.append((true_index, pred_index, iou))
                confusion_rows.append(
                    {
                        "image_name": image_name,
                        "true_index": true_index,
                        "true_class_id": int(true_classes[true_index]),
                        "true_class_name": class_names[int(true_classes[true_index])],
                        "pred_index": pred_index,
                        "pred_class_id": int(pred_classes_tensor[pred_index]),
                        "pred_class_name": class_names[int(pred_classes_tensor[pred_index])],
                        "confidence": float(pred_confidences[pred_index]),
                        "iou": iou,
                    }
                )
        confusion_pred_indexes = {pred_index for _, pred_index, _ in confusion_matches}

        small_fn = 0
        heavy_fn = 0
        truncated_fn = 0
        for true_index, item in enumerate(objects):
            x1, y1, x2, y2 = item.xyxy
            area = (x2 - x1) * (y2 - y1)
            size = size_bucket(area, small_max, medium_max)
            matched = true_index in matched_true
            pred_index, matched_iou = matched_true.get(true_index, (None, None))
            if not matched:
                small_fn += int(size == "small")
                heavy_fn += int(item.occlusion == 2)
                truncated_fn += int(item.truncation == 1)
            gt_rows.append(
                {
                    "image_name": image_name,
                    "true_index": true_index,
                    "class_id": item.class_id,
                    "class_name": item.class_name,
                    "source_category": item.source_category,
                    "source_line": item.source_line,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "area_px2": area,
                    "size": size,
                    "occlusion": item.occlusion,
                    "occlusion_name": OCCLUSION_NAMES[item.occlusion],
                    "truncation": item.truncation,
                    "truncation_name": TRUNCATION_NAMES[item.truncation],
                    "matched": matched,
                    "matched_pred_index": pred_index,
                    "matched_confidence": (
                        None if pred_index is None else float(pred_confidences[pred_index])
                    ),
                    "matched_iou": matched_iou,
                }
            )
        for pred_index in unmatched_pred:
            x1, y1, x2, y2 = pred_boxes_tensor[pred_index].tolist()
            class_id = int(pred_classes_tensor[pred_index])
            fp_rows.append(
                {
                    "image_name": image_name,
                    "pred_index": pred_index,
                    "class_id": class_id,
                    "class_name": class_names[class_id],
                    "confidence": float(pred_confidences[pred_index]),
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "area_px2": (x2 - x1) * (y2 - y1),
                    "classification_confusion": pred_index in confusion_pred_indexes,
                }
            )
        false_negatives = len(objects) - len(matches)
        false_positives = pred_boxes_tensor.shape[0] - len(matches)
        image_row = {
            "image_name": image_name,
            "ground_truth": len(objects),
            "predictions": int(pred_boxes_tensor.shape[0]),
            "true_positives": len(matches),
            "false_negatives": false_negatives,
            "false_positives": false_positives,
            "small_false_negatives": small_fn,
            "heavy_occlusion_false_negatives": heavy_fn,
            "truncated_false_negatives": truncated_fn,
            "classification_confusions": len(confusion_matches),
            "total_errors": false_negatives + false_positives,
        }
        image_rows.append(image_row)
        render_data[image_name] = {
            "image_path": image_path,
            "objects": objects,
            "pred_boxes": pred_boxes_tensor.tolist(),
            "pred_classes": pred_classes_tensor.tolist(),
            "pred_confidences": pred_confidences,
            "matches": matches,
            "confusions": confusion_matches,
        }

    missing = sorted(entries_by_name.keys() - seen)
    if missing:
        raise RuntimeError(f"missing predictions: {missing[:3]}")

    gt_fields = tuple(gt_rows[0].keys())
    fp_fields = tuple(fp_rows[0].keys()) if fp_rows else (
        "image_name",
        "pred_index",
        "class_id",
        "class_name",
        "confidence",
        "x1",
        "y1",
        "x2",
        "y2",
        "area_px2",
        "classification_confusion",
    )
    confusion_fields = (
        tuple(confusion_rows[0].keys())
        if confusion_rows
        else (
            "image_name",
            "true_index",
            "true_class_id",
            "true_class_name",
            "pred_index",
            "pred_class_id",
            "pred_class_name",
            "confidence",
            "iou",
        )
    )
    image_fields = tuple(image_rows[0].keys())
    gt_path = result_dir / "ground_truth_outcomes.csv"
    fp_path = result_dir / "false_positives.csv"
    confusion_path = result_dir / "classification_confusions.csv"
    image_path_csv = result_dir / "image_summary.csv"
    write_csv(gt_path, gt_fields, gt_rows)
    write_csv(fp_path, fp_fields, fp_rows)
    write_csv(confusion_path, confusion_fields, confusion_rows)
    write_csv(image_path_csv, image_fields, image_rows)

    examples = select_examples(image_rows, int(config["max_examples"]))
    overlay_dir = result_dir / "overlays"
    for position, example in enumerate(examples, start=1):
        data = render_data[example["image_name"]]
        destination = overlay_dir / (
            f"{position:02d}_{example['selection_reason']}_{Path(example['image_name']).stem}.jpg"
        )
        render_overlay(
            destination,
            data["image_path"],
            data["objects"],
            data["pred_boxes"],
            data["pred_classes"],
            data["pred_confidences"],
            data["matches"],
            data["confusions"],
            class_names,
            example,
            int(config["max_overlay_false_positives"]),
        )
        example["overlay"] = destination.relative_to(REPO_ROOT).as_posix()

    environment = {
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "source_revision": git_revision(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "cuda_available": torch.cuda.is_available(),
    }
    environment_path = experiment_dir / "environment.json"
    write_json_atomic(environment_path, environment)

    true_positives = sum(int(row["matched"]) for row in gt_rows)
    false_negatives = len(gt_rows) - true_positives
    false_positive_counts = Counter(row["class_name"] for row in fp_rows)
    confusion_counts = Counter(
        f"{row['true_class_name']}->{row['pred_class_name']}"
        for row in confusion_rows
    )
    finished_at = datetime.now(UTC)
    artifact_paths = {
        "ground_truth_outcomes": gt_path,
        "false_positives": fp_path,
        "classification_confusions": confusion_path,
        "image_summary": image_path_csv,
    }
    summary = {
        "schema_version": 1,
        "analysis_id": config["analysis_id"],
        "status": "passed",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds": time.perf_counter() - wall_start,
        "source_revision": environment["source_revision"],
        "model": {
            "path": config["model"],
            "size_bytes": model_path.stat().st_size,
            "sha256": sha256_file(model_path),
            "class_names": class_names,
        },
        "locked_subset": {
            "manifest": config["subset_manifest"],
            "manifest_sha256": sha256_file(subset_path),
            "size": len(entries_by_name),
            "selection_sha256": subset["selection_sha256"],
        },
        "protocol": {
            "image_size": int(config["image_size"]),
            "confidence": float(config["confidence"]),
            "iou_nms": float(config["iou_nms"]),
            "match_iou": float(config["match_iou"]),
            "max_detections": int(config["max_detections"]),
            "batch": int(config["batch"]),
            "device": config["device"],
            "half": bool(config["half"]),
            "rect": bool(config["rect"]),
            "size_definition": {
                "basis": "original-image bounding-box area in pixels squared",
                "small": f"area < {small_max:g}",
                "medium": f"{small_max:g} <= area < {medium_max:g}",
                "large": f"area >= {medium_max:g}",
            },
            "occlusion_definition": OCCLUSION_NAMES,
            "truncation_definition": TRUNCATION_NAMES,
        },
        "totals_at_operating_point": {
            "ground_truth": len(gt_rows),
            "predictions": true_positives + len(fp_rows),
            "true_positives": true_positives,
            "false_negatives": false_negatives,
            "false_positives": len(fp_rows),
            "classification_confusions": len(confusion_rows),
            "precision": true_positives / (true_positives + len(fp_rows)),
            "recall": true_positives / len(gt_rows),
        },
        "ground_truth_breakdown": {
            "by_class": aggregate_ground_truth(gt_rows, "class_name"),
            "by_size": aggregate_ground_truth(gt_rows, "size"),
            "by_occlusion": aggregate_ground_truth(gt_rows, "occlusion_name"),
            "by_truncation": aggregate_ground_truth(gt_rows, "truncation_name"),
        },
        "false_positives_by_class": dict(sorted(false_positive_counts.items())),
        "classification_confusion_counts": dict(sorted(confusion_counts.items())),
        "selected_failure_examples": examples,
        "artifacts": {
            key: {
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_file(path),
            }
            for key, path in artifact_paths.items()
        },
        "limitations": [
            "Counts use one declared confidence/IoU operating point and are not AP metrics.",
            "Small/medium/large use original-image pixel area, not physical object size.",
            "Occlusion and truncation come from VisDrone annotations and may contain labeling ambiguity.",
            "Qualitative overlays are deterministic selected examples, not a manual review of every image.",
        ],
    }
    write_json_atomic(experiment_dir / "summary.json", summary)
    write_json_atomic(result_dir / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    summary = run(parse_args().config.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
