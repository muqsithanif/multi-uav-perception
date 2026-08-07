import pytest
import torch

from scripts.export_and_validate_detector import (
    aggregate_agreement,
    check_tolerance,
    compare_detection_sets,
    summarize_timings,
)


def detection(boxes, classes, confidences):
    return {
        "boxes": torch.tensor(boxes, dtype=torch.float32).reshape(-1, 4),
        "classes": torch.tensor(classes, dtype=torch.int64),
        "confidences": torch.tensor(confidences, dtype=torch.float32),
    }


def test_compare_detection_sets_reports_final_detection_agreement() -> None:
    reference = detection([[0, 0, 10, 10]], [1], [0.8])
    candidate = detection([[0, 0, 10, 10]], [1], [0.799])

    comparison = compare_detection_sets(reference, candidate, 0.99)

    assert comparison["matched_count"] == 1
    assert comparison["mean_box_iou"] == pytest.approx(1.0)
    assert comparison["max_confidence_abs_diff"] == pytest.approx(0.001, abs=1e-7)


def test_aggregate_agreement_weights_matches_not_images() -> None:
    rows = [
        {
            "reference_count": 2,
            "candidate_count": 2,
            "matched_count": 2,
            "mean_box_iou": 1.0,
            "min_box_iou": 1.0,
            "mean_confidence_abs_diff": 0.001,
            "max_confidence_abs_diff": 0.001,
        },
        {
            "reference_count": 1,
            "candidate_count": 1,
            "matched_count": 1,
            "mean_box_iou": 0.99,
            "min_box_iou": 0.99,
            "mean_confidence_abs_diff": 0.004,
            "max_confidence_abs_diff": 0.004,
        },
    ]

    aggregate = aggregate_agreement(rows)

    assert aggregate["mean_box_iou"] == pytest.approx((2.0 + 0.99) / 3)
    assert aggregate["mean_confidence_abs_diff"] == pytest.approx(0.002)


def test_check_tolerance_reports_each_condition() -> None:
    agreement = {
        "reference_match_rate": 1.0,
        "candidate_match_rate": 1.0,
        "mean_box_iou": 0.999,
        "max_confidence_abs_diff": 0.003,
    }
    tolerance = {
        "min_reference_match_rate": 0.99,
        "min_candidate_match_rate": 0.99,
        "min_mean_box_iou": 0.995,
        "max_confidence_abs_diff": 0.005,
    }

    result = check_tolerance(agreement, tolerance)

    assert result["passed"] is True
    assert all(result["checks"].values())


def test_summarize_timings_reports_required_statistics() -> None:
    summary = summarize_timings([1.0, 2.0, 3.0, 4.0])

    assert summary["mean"] == pytest.approx(2.5)
    assert summary["median"] == pytest.approx(2.5)
    assert summary["p95"] == pytest.approx(3.85)
