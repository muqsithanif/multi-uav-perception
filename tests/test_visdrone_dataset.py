from pathlib import Path

import cv2
import numpy as np
import pytest

from scripts.visdrone_dataset import (
    VisDroneAnnotation,
    collect_pairs,
    convert_box,
    load_conversion_config,
    parse_annotation_file,
    prepare_dataset,
    validate_dataset_yaml,
    validate_split_integrity,
    validate_yolo_label_file,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def write_image(path: Path, width: int = 100, height: int = 50) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.zeros((height, width, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def write_source_split(root: Path, split_dir: str, stem: str) -> None:
    write_image(root / split_dir / "images" / f"{stem}.jpg")
    annotation_path = root / split_dir / "annotations" / f"{stem}.txt"
    annotation_path.parent.mkdir(parents=True, exist_ok=True)
    annotation_path.write_text(
        "10,5,20,10,1,1,0,0\n"  # pedestrian -> project 0
        "40,10,20,20,1,5,1,2\n"  # van -> project 2
        "0,0,10,10,0,0,0,0\n"  # ignored by score
        "20,20,10,10,1,3,0,1\n"  # excluded bicycle
        "90,40,20,20,1,9,1,1\n",  # bus clipped to image
        encoding="utf-8",
    )


def fixture_config(tmp_path: Path) -> dict:
    source_config = load_conversion_config(REPO_ROOT / "configs" / "visdrone_conversion.yaml")
    source_config["raw_root"] = "raw"
    source_config["output_root"] = "processed"
    source_config["manifest_path"] = "manifest.json"
    source_config["validation_report_path"] = "report.json"
    return source_config


def test_repository_configs_are_consistent() -> None:
    config = load_conversion_config(REPO_ROOT / "configs" / "visdrone_conversion.yaml")
    dataset = validate_dataset_yaml(
        REPO_ROOT / "configs" / "visdrone_5class.yaml", config["project_names"]
    )
    assert dataset["train"].endswith("images/train")
    assert dataset["val"].endswith("images/val")


def test_parse_rejects_source_class_outside_range(tmp_path: Path) -> None:
    label = tmp_path / "bad.txt"
    label.write_text("0,0,10,10,1,12,0,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source class outside"):
        parse_annotation_file(label)


def test_parse_rejects_invalid_box_even_for_excluded_class(tmp_path: Path) -> None:
    label = tmp_path / "bad_box.txt"
    label.write_text("0,0,0,10,1,3,0,0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be positive"):
        parse_annotation_file(label)


@pytest.mark.parametrize("width,height", [(0, 10), (10, 0), (-1, 5)])
def test_convert_rejects_invalid_box_size(width: float, height: float) -> None:
    annotation = VisDroneAnnotation(1, 1, width, height, 1, 1, 0, 0)
    with pytest.raises(ValueError, match="must be positive"):
        convert_box(annotation, 100, 50)


def test_convert_clips_and_normalizes_box() -> None:
    annotation = VisDroneAnnotation(90, 40, 20, 20, 1, 9, 1, 1)
    normalized, clipped = convert_box(annotation, 100, 50)
    assert clipped is True
    assert normalized == pytest.approx((0.95, 0.9, 0.1, 0.2))


def test_collect_pairs_rejects_missing_annotation(tmp_path: Path) -> None:
    images = tmp_path / "images"
    annotations = tmp_path / "annotations"
    write_image(images / "orphan.jpg")
    annotations.mkdir()
    with pytest.raises(ValueError, match="pairing mismatch"):
        collect_pairs(images, annotations)


def test_yolo_validator_rejects_class_and_bounds(tmp_path: Path) -> None:
    invalid_class = tmp_path / "class.txt"
    invalid_class.write_text("5 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="class is out of range"):
        validate_yolo_label_file(invalid_class, 5)

    invalid_bounds = tmp_path / "bounds.txt"
    invalid_bounds.write_text("0 0.95 0.5 0.2 0.2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="horizontal image bounds"):
        validate_yolo_label_file(invalid_bounds, 5)


def test_split_integrity_rejects_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        validate_split_integrity({"train": {"shared"}, "val": {"shared"}})


def test_fixture_conversion_maps_ignores_excludes_and_validates(tmp_path: Path) -> None:
    config = fixture_config(tmp_path)
    write_source_split(tmp_path / "raw", config["splits"]["train"], "train_001")
    write_source_split(tmp_path / "raw", config["splits"]["val"], "val_001")

    report = prepare_dataset(config, tmp_path)

    assert report["status"] == "passed"
    assert report["split_integrity"]["overlap_count"] == 0
    for split in ("train", "val"):
        stats = report["splits"][split]
        assert stats["converted_object_count"] == 3
        assert stats["project_class_counts"] == {"0": 1, "2": 1, "4": 1}
        assert stats["score_zero_annotation_count"] == 1
        assert stats["excluded_source_class_counts"] == {"3": 1}
        assert stats["clipped_box_count"] == 1
        assert report["converted_validation"][split]["object_count"] == 3

        label_path = tmp_path / "processed" / "labels" / split / f"{split}_001.txt"
        classes = [int(line.split()[0]) for line in label_path.read_text().splitlines()]
        assert classes == [0, 2, 4]
