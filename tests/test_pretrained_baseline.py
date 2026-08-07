import json
from pathlib import Path

import pytest
import torch

from scripts.evaluate_pretrained_baseline import (
    evenly_spaced_indices,
    index_pairs_by_image_name,
    match_predictions,
    validate_mapping,
    validate_reference_subset_manifest,
    yolo_boxes_to_xyxy,
)


def test_evenly_spaced_indices_span_population() -> None:
    assert evenly_spaced_indices(5, 3) == [0, 2, 4]
    assert evenly_spaced_indices(5, 1) == [2]


def test_yolo_boxes_to_xyxy_uses_image_dimensions(tmp_path: Path) -> None:
    label = tmp_path / "sample.txt"
    label.write_text("1 0.5 0.5 0.2 0.4\n", encoding="utf-8")

    boxes, classes = yolo_boxes_to_xyxy(label, 5, 200, 100)

    assert torch.allclose(boxes, torch.tensor([[80.0, 30.0, 120.0, 70.0]]))
    assert torch.equal(classes, torch.tensor([1.0]))


def test_match_predictions_is_class_aware_and_one_to_one() -> None:
    predictions = torch.tensor([0.0, 0.0, 1.0])
    targets = torch.tensor([0.0, 1.0])
    iou = torch.tensor([[0.9, 0.8, 0.9], [0.1, 0.1, 0.7]])
    thresholds = torch.tensor([0.5, 0.85])

    correct = match_predictions(predictions, targets, iou, thresholds)

    assert correct.tolist() == [[True, True], [False, False], [True, False]]


def test_validate_mapping_requires_explicit_unsupported_class() -> None:
    config = {
        "project_classes": {0: "pedestrian", 1: "van"},
        "model_class_mapping": {
            0: {
                "model_name": "person",
                "project_id": 0,
                "project_name": "pedestrian",
            }
        },
        "unsupported_project_classes": [
            {"project_id": 1, "project_name": "van", "reason": "not in model"}
        ],
    }

    assert validate_mapping(config, {0: "person"}) == {0: 0}


def test_index_pairs_by_image_name_does_not_depend_on_order() -> None:
    pairs = [
        (Path("b.jpg"), Path("b.txt")),
        (Path("a.jpg"), Path("a.txt")),
    ]

    indexed = index_pairs_by_image_name(pairs)

    assert indexed["a.jpg"] == (Path("a.jpg"), Path("a.txt"))
    assert indexed["b.jpg"] == (Path("b.jpg"), Path("b.txt"))


def test_validate_reference_subset_manifest_accepts_identical_lock(
    tmp_path: Path, monkeypatch
) -> None:
    entry = {
        "source_index": 0,
        "image_name": "a.jpg",
        "label_name": "a.txt",
        "image_sha256": "image-hash",
        "label_sha256": "label-hash",
    }
    manifest = {
        "selection_policy": "evenly_spaced_sorted_filename",
        "population_size": 1,
        "subset_size": 1,
        "selection_sha256": "selection-hash",
        "ground_truth_class_counts": {"0": 1},
        "entries": [entry],
    }
    path = tmp_path / "subset.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(
        "scripts.evaluate_pretrained_baseline.REPO_ROOT", tmp_path
    )

    reference = validate_reference_subset_manifest(manifest, path)

    assert reference["path"] == "subset.json"
    assert len(reference["sha256"]) == 64


def test_validate_reference_subset_manifest_rejects_changed_entries(
    tmp_path: Path,
) -> None:
    manifest = {
        "selection_policy": "evenly_spaced_sorted_filename",
        "population_size": 1,
        "subset_size": 1,
        "selection_sha256": "selection-hash",
        "ground_truth_class_counts": {"0": 1},
        "entries": [
            {
                "source_index": 0,
                "image_name": "a.jpg",
                "label_name": "a.txt",
                "image_sha256": "image-hash",
                "label_sha256": "label-hash",
            }
        ],
    }
    reference = {
        **manifest,
        "entries": [{**manifest["entries"][0], "image_name": "b.jpg"}],
    }
    path = tmp_path / "subset.json"
    path.write_text(json.dumps(reference), encoding="utf-8")

    with pytest.raises(ValueError, match="entries"):
        validate_reference_subset_manifest(manifest, path)
