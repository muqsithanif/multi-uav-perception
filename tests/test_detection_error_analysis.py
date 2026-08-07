import pytest
import torch

from scripts.analyze_detection_errors import (
    aggregate_ground_truth,
    match_boxes_at_iou,
    select_examples,
    size_bucket,
)


def test_size_bucket_uses_declared_pixel_area_boundaries() -> None:
    assert size_bucket(1023.9, 1024, 9216) == "small"
    assert size_bucket(1024, 1024, 9216) == "medium"
    assert size_bucket(9216, 1024, 9216) == "large"


def test_match_boxes_at_iou_is_class_aware_and_one_to_one() -> None:
    true_boxes = torch.tensor([[0, 0, 10, 10], [20, 20, 30, 30]], dtype=torch.float32)
    pred_boxes = torch.tensor(
        [[0, 0, 10, 10], [0, 0, 9, 9], [20, 20, 30, 30]], dtype=torch.float32
    )
    true_classes = torch.tensor([0, 1])
    pred_classes = torch.tensor([1, 0, 1])

    matches = match_boxes_at_iou(
        true_boxes, pred_boxes, 0.5, true_classes, pred_classes
    )

    assert [(true_index, pred_index) for true_index, pred_index, _ in matches] == [
        (1, 2),
        (0, 1),
    ]

    confusions = match_boxes_at_iou(
        true_boxes,
        pred_boxes,
        0.5,
        true_classes,
        pred_classes,
        class_relation="different",
    )
    assert [(true_index, pred_index) for true_index, pred_index, _ in confusions] == [
        (0, 0)
    ]


def test_aggregate_ground_truth_reports_operating_point_recall() -> None:
    rows = [
        {"size": "small", "matched": True},
        {"size": "small", "matched": False},
        {"size": "large", "matched": True},
    ]

    grouped = aggregate_ground_truth(rows, "size")

    assert grouped["small"] == {
        "ground_truth": 2,
        "matched": 1,
        "missed": 1,
        "recall_at_operating_point": 0.5,
    }
    assert grouped["large"]["recall_at_operating_point"] == 1.0


def test_select_examples_prefers_distinct_reason_leaders() -> None:
    base = {
        "ground_truth": 1,
        "predictions": 1,
        "true_positives": 0,
        "false_negatives": 1,
        "false_positives": 1,
        "small_false_negatives": 0,
        "heavy_occlusion_false_negatives": 0,
        "truncated_false_negatives": 0,
        "classification_confusions": 0,
        "total_errors": 2,
    }
    rows = [
        {**base, "image_name": "small.jpg", "small_false_negatives": 3},
        {
            **base,
            "image_name": "occluded.jpg",
            "heavy_occlusion_false_negatives": 2,
        },
        {**base, "image_name": "fp.jpg", "false_positives": 5, "total_errors": 6},
    ]

    selected = select_examples(rows, 3)

    assert [row["image_name"] for row in selected] == [
        "small.jpg",
        "occluded.jpg",
        "fp.jpg",
    ]
    assert selected[0]["selection_reason"] == "small_false_negatives"


def test_size_bucket_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        size_bucket(10, 100, 50)
