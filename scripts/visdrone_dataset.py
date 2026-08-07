"""VisDrone DET parsing, five-class conversion, and dataset validation."""

from __future__ import annotations

import json
import math
import os
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import cv2
import yaml


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
EXPECTED_SOURCE_CLASS_IDS = set(range(12))
EXPECTED_SCORE_VALUES = {0, 1}
EXPECTED_TRUNCATION_VALUES = {0, 1}
EXPECTED_OCCLUSION_VALUES = {0, 1, 2}


@dataclass(frozen=True)
class VisDroneAnnotation:
    left: float
    top: float
    width: float
    height: float
    score: int
    category: int
    truncation: int
    occlusion: int


def load_conversion_config(path: Path) -> dict[str, Any]:
    """Load and validate the conversion policy."""
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    required = {
        "dataset",
        "raw_root",
        "output_root",
        "manifest_path",
        "validation_report_path",
        "image_mode",
        "splits",
        "class_mapping",
        "ignored_source_class_ids",
        "excluded_source_class_ids",
    }
    missing = sorted(required.difference(config))
    if missing:
        raise ValueError(f"Missing conversion config keys: {', '.join(missing)}")

    mapping = {int(key): value for key, value in config["class_mapping"].items()}
    ignored = {int(value) for value in config["ignored_source_class_ids"]}
    excluded = {int(value) for value in config["excluded_source_class_ids"]}
    partitions = set(mapping), ignored, excluded
    if any(left & right for index, left in enumerate(partitions) for right in partitions[index + 1 :]):
        raise ValueError("Mapped, ignored, and excluded source classes must be disjoint")
    if set().union(*partitions) != EXPECTED_SOURCE_CLASS_IDS:
        raise ValueError("Conversion policy must account for every source class ID 0..11")

    project_ids = sorted(int(value["project_id"]) for value in mapping.values())
    if project_ids != list(range(len(project_ids))):
        raise ValueError("Project class IDs must be contiguous from zero")
    names = [
        value["name"]
        for _, value in sorted(mapping.items(), key=lambda item: int(item[1]["project_id"]))
    ]
    if len(names) != len(set(names)):
        raise ValueError("Project class names must be unique")
    if config["image_mode"] not in {"hardlink", "copy"}:
        raise ValueError("image_mode must be hardlink or copy")

    config["class_mapping"] = mapping
    config["ignored_source_class_ids"] = ignored
    config["excluded_source_class_ids"] = excluded
    config["project_names"] = names
    return config


def _parse_integer(value: str, field: str, path: Path, line_number: int) -> int:
    number = float(value)
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"{path}:{line_number}: {field} must be an integer")
    return int(number)


def parse_annotation_file(path: Path) -> list[VisDroneAnnotation]:
    """Parse one official eight-field VisDrone DET annotation file."""
    annotations: list[VisDroneAnnotation] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        fields = [field.strip() for field in raw_line.split(",")]
        if len(fields) != 8:
            raise ValueError(
                f"{path}:{line_number}: expected 8 comma-separated fields, found {len(fields)}"
            )
        left, top, width, height = (float(value) for value in fields[:4])
        if not all(math.isfinite(value) for value in (left, top, width, height)):
            raise ValueError(f"{path}:{line_number}: bounding box contains a non-finite value")
        if width <= 0 or height <= 0:
            raise ValueError(
                f"{path}:{line_number}: bounding-box width and height must be positive"
            )
        score = _parse_integer(fields[4], "score", path, line_number)
        category = _parse_integer(fields[5], "category", path, line_number)
        truncation = _parse_integer(fields[6], "truncation", path, line_number)
        occlusion = _parse_integer(fields[7], "occlusion", path, line_number)
        if score not in EXPECTED_SCORE_VALUES:
            raise ValueError(f"{path}:{line_number}: score outside {{0,1}}: {score}")
        if category not in EXPECTED_SOURCE_CLASS_IDS:
            raise ValueError(f"{path}:{line_number}: source class outside 0..11: {category}")
        if truncation not in EXPECTED_TRUNCATION_VALUES:
            raise ValueError(f"{path}:{line_number}: truncation outside {{0,1}}: {truncation}")
        if occlusion not in EXPECTED_OCCLUSION_VALUES:
            raise ValueError(f"{path}:{line_number}: occlusion outside {{0,1,2}}: {occlusion}")
        annotations.append(
            VisDroneAnnotation(
                left,
                top,
                width,
                height,
                score,
                category,
                truncation,
                occlusion,
            )
        )
    return annotations


def collect_pairs(images_dir: Path, annotations_dir: Path) -> list[tuple[Path, Path]]:
    """Return one-to-one image/annotation pairs or fail with compact evidence."""
    images = {
        path.stem: path
        for path in images_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    }
    annotations = {
        path.stem: path
        for path in annotations_dir.glob("*.txt")
        if path.is_file()
    }
    missing_annotations = sorted(images.keys() - annotations.keys())
    missing_images = sorted(annotations.keys() - images.keys())
    if missing_annotations or missing_images:
        raise ValueError(
            "Image/annotation pairing mismatch: "
            f"missing_annotations={missing_annotations[:10]}, "
            f"missing_images={missing_images[:10]}"
        )
    if not images:
        raise ValueError(f"No supported images found in {images_dir}")
    return [(images[stem], annotations[stem]) for stem in sorted(images)]


def convert_box(
    annotation: VisDroneAnnotation, image_width: int, image_height: int
) -> tuple[tuple[float, float, float, float], bool]:
    """Clip an xywh source box to the image and return normalized YOLO xywh."""
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive")
    if annotation.width <= 0 or annotation.height <= 0:
        raise ValueError("Bounding-box width and height must be positive")

    x1 = annotation.left
    y1 = annotation.top
    x2 = annotation.left + annotation.width
    y2 = annotation.top + annotation.height
    clipped_x1 = min(max(x1, 0.0), float(image_width))
    clipped_y1 = min(max(y1, 0.0), float(image_height))
    clipped_x2 = min(max(x2, 0.0), float(image_width))
    clipped_y2 = min(max(y2, 0.0), float(image_height))
    if clipped_x2 <= clipped_x1 or clipped_y2 <= clipped_y1:
        raise ValueError("Bounding box is empty after clipping")
    clipped = (x1, y1, x2, y2) != (
        clipped_x1,
        clipped_y1,
        clipped_x2,
        clipped_y2,
    )
    width = clipped_x2 - clipped_x1
    height = clipped_y2 - clipped_y1
    center_x = clipped_x1 + width / 2
    center_y = clipped_y1 + height / 2
    return (
        center_x / image_width,
        center_y / image_height,
        width / image_width,
        height / image_height,
    ), clipped


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _materialize_image(source: Path, destination: Path, mode: str) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if destination.stat().st_size != source.stat().st_size:
            raise ValueError(f"Existing output image differs in size: {destination}")
        return "existing"
    if mode == "copy":
        shutil.copy2(source, destination)
        return "copy"
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy_fallback"


def validate_yolo_label_file(path: Path, class_count: int) -> int:
    """Validate one YOLO label file and return its object count."""
    count = 0
    tolerance = 1e-6
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        fields = raw_line.split()
        if len(fields) != 5:
            raise ValueError(f"{path}:{line_number}: expected 5 YOLO fields")
        class_value, *coordinates = (float(field) for field in fields)
        if not class_value.is_integer() or not 0 <= int(class_value) < class_count:
            raise ValueError(f"{path}:{line_number}: project class is out of range")
        center_x, center_y, width, height = coordinates
        if not all(math.isfinite(value) for value in coordinates):
            raise ValueError(f"{path}:{line_number}: coordinate is non-finite")
        if not (0 <= center_x <= 1 and 0 <= center_y <= 1):
            raise ValueError(f"{path}:{line_number}: center is outside [0,1]")
        if not (0 < width <= 1 and 0 < height <= 1):
            raise ValueError(f"{path}:{line_number}: size is outside (0,1]")
        if center_x - width / 2 < -tolerance or center_x + width / 2 > 1 + tolerance:
            raise ValueError(f"{path}:{line_number}: box crosses horizontal image bounds")
        if center_y - height / 2 < -tolerance or center_y + height / 2 > 1 + tolerance:
            raise ValueError(f"{path}:{line_number}: box crosses vertical image bounds")
        count += 1
    return count


def validate_converted_split(root: Path, split: str, class_count: int) -> dict[str, int]:
    images_dir = root / "images" / split
    labels_dir = root / "labels" / split
    pairs = collect_pairs(images_dir, labels_dir)
    object_count = sum(
        validate_yolo_label_file(label_path, class_count) for _, label_path in pairs
    )
    return {
        "image_count": len(pairs),
        "label_file_count": len(pairs),
        "object_count": object_count,
    }


def validate_split_integrity(split_stems: dict[str, set[str]]) -> dict[str, Any]:
    """Require disjoint file identities across all configured splits."""
    overlaps: dict[str, list[str]] = {}
    split_names = sorted(split_stems)
    for index, left in enumerate(split_names):
        for right in split_names[index + 1 :]:
            shared = sorted(split_stems[left] & split_stems[right])
            if shared:
                overlaps[f"{left}:{right}"] = shared[:10]
    if overlaps:
        raise ValueError(f"Split filename overlap detected: {overlaps}")
    return {"overlap_count": 0, "checked_splits": split_names}


def _counter_dict(counter: Counter[int | str]) -> dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter, key=lambda item: str(item))}


def convert_split(
    source_root: Path,
    output_root: Path,
    split: str,
    class_mapping: dict[int, dict[str, Any]],
    ignored_source_ids: set[int],
    excluded_source_ids: set[int],
    image_mode: str,
) -> tuple[dict[str, Any], set[str]]:
    """Convert one official split and return validation-ready statistics."""
    pairs = collect_pairs(source_root / "images", source_root / "annotations")
    output_images = output_root / "images" / split
    output_labels = output_root / "labels" / split
    source_categories: Counter[int] = Counter()
    project_categories: Counter[str] = Counter()
    ignored_categories: Counter[int] = Counter()
    excluded_categories: Counter[int] = Counter()
    occlusion: Counter[int] = Counter()
    truncation: Counter[int] = Counter()
    materialization: Counter[str] = Counter()
    image_widths: list[int] = []
    image_heights: list[int] = []
    converted_objects = 0
    clipped_boxes = 0
    score_zero_annotations = 0
    empty_label_images = 0

    for image_path, annotation_path in pairs:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Unreadable or corrupt image: {image_path}")
        image_height, image_width = image.shape[:2]
        image_widths.append(image_width)
        image_heights.append(image_height)
        output_lines: list[str] = []
        for annotation in parse_annotation_file(annotation_path):
            source_categories[annotation.category] += 1
            if annotation.score == 0:
                score_zero_annotations += 1
                ignored_categories[annotation.category] += 1
                continue
            if annotation.category in ignored_source_ids:
                ignored_categories[annotation.category] += 1
                continue
            if annotation.category in excluded_source_ids:
                excluded_categories[annotation.category] += 1
                continue
            mapping = class_mapping[annotation.category]
            normalized, clipped = convert_box(annotation, image_width, image_height)
            clipped_boxes += int(clipped)
            project_id = int(mapping["project_id"])
            project_categories[str(project_id)] += 1
            occlusion[annotation.occlusion] += 1
            truncation[annotation.truncation] += 1
            output_lines.append(
                f"{project_id} " + " ".join(f"{value:.8f}" for value in normalized)
            )
            converted_objects += 1
        if not output_lines:
            empty_label_images += 1
        label_path = output_labels / f"{image_path.stem}.txt"
        _write_text_atomic(label_path, "\n".join(output_lines) + ("\n" if output_lines else ""))
        materialization[_materialize_image(image_path, output_images / image_path.name, image_mode)] += 1

    stats: dict[str, Any] = {
        "source_image_count": len(pairs),
        "source_annotation_file_count": len(pairs),
        "source_annotation_count": sum(source_categories.values()),
        "source_class_counts": _counter_dict(source_categories),
        "converted_object_count": converted_objects,
        "project_class_counts": _counter_dict(project_categories),
        "ignored_source_class_counts": _counter_dict(ignored_categories),
        "excluded_source_class_counts": _counter_dict(excluded_categories),
        "score_zero_annotation_count": score_zero_annotations,
        "clipped_box_count": clipped_boxes,
        "empty_label_image_count": empty_label_images,
        "selected_occlusion_counts": _counter_dict(occlusion),
        "selected_truncation_counts": _counter_dict(truncation),
        "image_materialization_counts": _counter_dict(materialization),
        "image_width_min": min(image_widths),
        "image_width_max": max(image_widths),
        "image_height_min": min(image_heights),
        "image_height_max": max(image_heights),
    }
    return stats, {image_path.stem for image_path, _ in pairs}


def prepare_dataset(config: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    """Convert every configured split, validate output, and return a report."""
    started_at = datetime.now(UTC)
    raw_root = (repo_root / config["raw_root"]).resolve()
    output_root = (repo_root / config["output_root"]).resolve()
    split_stats: dict[str, Any] = {}
    split_stems: dict[str, set[str]] = {}
    for split, source_directory in config["splits"].items():
        stats, stems = convert_split(
            raw_root / source_directory,
            output_root,
            split,
            config["class_mapping"],
            config["ignored_source_class_ids"],
            config["excluded_source_class_ids"],
            config["image_mode"],
        )
        split_stats[split] = stats
        split_stems[split] = stems

    integrity = validate_split_integrity(split_stems)
    validation = {
        split: validate_converted_split(output_root, split, len(config["project_names"]))
        for split in config["splits"]
    }
    for split in validation:
        if validation[split]["object_count"] != split_stats[split]["converted_object_count"]:
            raise ValueError(f"Converted object count mismatch for split {split}")

    finished_at = datetime.now(UTC)
    return {
        "schema_version": 1,
        "dataset": config["dataset"],
        "status": "passed",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds": (finished_at - started_at).total_seconds(),
        "source_splits_preserved": True,
        "project_class_names": config["project_names"],
        "source_to_project_class": {
            str(source_id): int(mapping["project_id"])
            for source_id, mapping in sorted(config["class_mapping"].items())
        },
        "ignored_source_class_ids": sorted(config["ignored_source_class_ids"]),
        "excluded_source_class_ids": sorted(config["excluded_source_class_ids"]),
        "splits": split_stats,
        "converted_validation": validation,
        "split_integrity": integrity,
    }


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def validate_dataset_yaml(path: Path, expected_names: Iterable[str]) -> dict[str, Any]:
    """Validate the portable Ultralytics dataset YAML without requiring data files."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("train", "val", "names"):
        if key not in payload:
            raise ValueError(f"Dataset YAML is missing {key}")
    names_value = payload["names"]
    if isinstance(names_value, dict):
        names = [names_value[index] for index in sorted(names_value)]
    else:
        names = list(names_value)
    expected = list(expected_names)
    if names != expected:
        raise ValueError(f"Dataset YAML names differ: expected={expected}, actual={names}")
    if Path(payload["train"]).is_absolute() or Path(payload["val"]).is_absolute():
        raise ValueError("Dataset YAML train/val paths must stay portable and relative")
    return payload
