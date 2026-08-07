import pytest

from scripts.compare_detection_experiments import compare_summaries, metric_delta


def make_summary(map50: float, image_name_hash: str = "locked") -> dict:
    return {
        "status": "passed",
        "subset": {
            "size": 1,
            "population_size": 1,
            "selection_policy": "locked",
            "selection_sha256": image_name_hash,
            "ground_truth_class_counts": {"0": 1},
        },
        "protocol": {
            "image_size": 640,
            "confidence": 0.001,
            "iou_nms": 0.7,
            "max_detections": 300,
            "batch": 4,
            "device": "cpu",
            "half": False,
            "rect": True,
            "evaluation_iou_thresholds": [0.5, 0.95],
            "metric_implementation": "test",
        },
        "metrics": {
            "overall_macro": {
                "precision": 0.5,
                "recall": 0.25,
                "map50": map50,
                "map50_95": 0.1,
            },
            "per_class": [
                {
                    "class_id": 0,
                    "class_name": "pedestrian",
                    "instances": 1,
                    "precision": 0.5,
                    "recall": 0.25,
                    "map50": map50,
                    "map50_95": 0.1,
                }
            ],
        },
    }


def test_metric_delta_handles_zero_baseline() -> None:
    assert metric_delta(0.0, 0.3) == {
        "baseline": 0.0,
        "candidate": 0.3,
        "absolute_delta": 0.3,
        "relative_change_percent": None,
    }


def test_compare_summaries_calculates_locked_delta() -> None:
    comparison = compare_summaries(make_summary(0.2), make_summary(0.4))

    assert comparison["overall_macro"]["map50"]["absolute_delta"] == pytest.approx(
        0.2
    )
    assert comparison["overall_macro"]["map50"][
        "relative_change_percent"
    ] == pytest.approx(100.0)


def test_compare_summaries_rejects_different_subset() -> None:
    with pytest.raises(ValueError, match="selection_sha256"):
        compare_summaries(make_summary(0.2), make_summary(0.4, "different"))
