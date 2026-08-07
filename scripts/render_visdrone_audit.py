#!/usr/bin/env python3
"""Render deterministic VisDrone YOLO label samples for visual auditing."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

if __package__:
    from .visdrone_dataset import (
        collect_pairs,
        load_conversion_config,
        write_json_atomic,
    )
else:
    from visdrone_dataset import (
        collect_pairs,
        load_conversion_config,
        write_json_atomic,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "visdrone_conversion.yaml"
DEFAULT_OUTPUT = REPO_ROOT / "results" / "day2" / "visual_audit"
CLASS_COLORS = (
    (61, 217, 255),
    (87, 235, 52),
    (255, 174, 66),
    (255, 92, 168),
    (196, 112, 255),
)


@dataclass(frozen=True)
class YoloBox:
    class_id: int
    center_x: float
    center_y: float
    width: float
    height: float


def parse_yolo_boxes(path: Path, class_count: int) -> list[YoloBox]:
    """Read an already-validated YOLO label file."""
    boxes: list[YoloBox] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        fields = raw_line.split()
        if len(fields) != 5:
            raise ValueError(f"{path}:{line_number}: expected 5 YOLO fields")
        class_value, center_x, center_y, width, height = (
            float(field) for field in fields
        )
        if not class_value.is_integer() or not 0 <= int(class_value) < class_count:
            raise ValueError(f"{path}:{line_number}: project class is out of range")
        boxes.append(YoloBox(int(class_value), center_x, center_y, width, height))
    return boxes


def select_audit_pairs(
    images_dir: Path,
    labels_dir: Path,
    class_count: int,
    sample_count: int,
) -> list[tuple[Path, Path]]:
    """Select deterministic samples, prioritizing complete class coverage."""
    if sample_count <= 0:
        raise ValueError("sample_count must be positive")
    pairs = collect_pairs(images_dir, labels_dir)
    candidates: list[tuple[Path, Path, set[int], int]] = []
    for image_path, label_path in pairs:
        boxes = parse_yolo_boxes(label_path, class_count)
        candidates.append(
            (image_path, label_path, {box.class_id for box in boxes}, len(boxes))
        )

    selected: list[tuple[Path, Path, set[int], int]] = []
    remaining = list(candidates)
    uncovered = set(range(class_count))
    limit = min(sample_count, len(remaining))
    while remaining and uncovered and len(selected) < limit:
        candidate = min(
            remaining,
            key=lambda item: (
                -len(item[2] & uncovered),
                abs(item[3] - 25),
                item[0].name,
            ),
        )
        if not candidate[2] & uncovered:
            break
        selected.append(candidate)
        remaining.remove(candidate)
        uncovered.difference_update(candidate[2])

    if remaining and len(selected) < limit:
        slots = limit - len(selected)
        if slots == 1:
            indexes = [len(remaining) // 2]
        else:
            indexes = [
                round(index * (len(remaining) - 1) / (slots - 1))
                for index in range(slots)
            ]
        selected.extend(remaining[index] for index in indexes)

    return [(image_path, label_path) for image_path, label_path, _, _ in selected]


def render_label_overlay(
    image_path: Path,
    label_path: Path,
    destination: Path,
    class_names: list[str],
) -> dict[str, Any]:
    """Draw YOLO labels on one image and return artifact metadata."""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unreadable image: {image_path}")
    image_height, image_width = image.shape[:2]
    boxes = parse_yolo_boxes(label_path, len(class_names))
    class_ids: set[int] = set()
    thickness = max(1, round(min(image_width, image_height) / 500))

    for box in boxes:
        class_ids.add(box.class_id)
        x1 = max(
            0,
            min(
                image_width - 1,
                round((box.center_x - box.width / 2) * image_width),
            ),
        )
        y1 = max(
            0,
            min(
                image_height - 1,
                round((box.center_y - box.height / 2) * image_height),
            ),
        )
        x2 = max(
            0,
            min(
                image_width - 1,
                round((box.center_x + box.width / 2) * image_width),
            ),
        )
        y2 = max(
            0,
            min(
                image_height - 1,
                round((box.center_y + box.height / 2) * image_height),
            ),
        )
        color = CLASS_COLORS[box.class_id % len(CLASS_COLORS)]
        cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness, cv2.LINE_AA)
        label = f"{box.class_id}:{class_names[box.class_id]}"
        (text_width, text_height), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1
        )
        text_top = max(0, y1 - text_height - baseline - 2)
        cv2.rectangle(
            image,
            (x1, text_top),
            (min(image_width - 1, x1 + text_width + 4), y1),
            color,
            cv2.FILLED,
        )
        cv2.putText(
            image,
            label,
            (x1 + 2, max(text_height, y1 - baseline - 1)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (20, 20, 20),
            1,
            cv2.LINE_AA,
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destination), image, [cv2.IMWRITE_JPEG_QUALITY, 92]):
        raise OSError(f"Failed to write visual audit image: {destination}")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return {
        "source_image": image_path.as_posix(),
        "source_label": label_path.as_posix(),
        "output_image": destination.as_posix(),
        "output_sha256": digest,
        "image_width": image_width,
        "image_height": image_height,
        "object_count": len(boxes),
        "class_ids": sorted(class_ids),
        "class_names": [class_names[class_id] for class_id in sorted(class_ids)],
    }


def render_audit(
    repo_root: Path,
    config_path: Path,
    split: str,
    sample_count: int,
    output_root: Path,
) -> dict[str, Any]:
    config = load_conversion_config(config_path)
    if split not in config["splits"]:
        raise ValueError(
            f"Unknown split {split!r}; expected one of {sorted(config['splits'])}"
        )
    dataset_root = (repo_root / config["output_root"]).resolve()
    pairs = select_audit_pairs(
        dataset_root / "images" / split,
        dataset_root / "labels" / split,
        len(config["project_names"]),
        sample_count,
    )
    artifacts = []
    for image_path, label_path in pairs:
        destination = output_root / f"{split}_{image_path.stem}.jpg"
        artifact = render_label_overlay(
            image_path, label_path, destination, config["project_names"]
        )
        for field in ("source_image", "source_label", "output_image"):
            artifact[field] = Path(artifact[field]).relative_to(repo_root).as_posix()
        artifacts.append(artifact)

    covered_ids = sorted(
        {class_id for artifact in artifacts for class_id in artifact["class_ids"]}
    )
    return {
        "schema_version": 1,
        "dataset": config["dataset"],
        "split": split,
        "selection_policy": "greedy_class_coverage_then_even_filename_sampling",
        "review_status": "rendered_pending_manual_visual_review",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "requested_sample_count": sample_count,
        "rendered_sample_count": len(artifacts),
        "covered_class_ids": covered_ids,
        "covered_class_names": [
            config["project_names"][index] for index in covered_ids
        ],
        "all_project_classes_covered": covered_ids
        == list(range(len(config["project_names"]))),
        "artifacts": artifacts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--split", default="val")
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = render_audit(
        REPO_ROOT,
        args.config.resolve(),
        args.split,
        args.samples,
        args.output.resolve(),
    )
    report_path = args.output.resolve() / "summary.json"
    write_json_atomic(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
