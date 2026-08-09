import pytest

from scripts.compare_trackers import summarize_values, track_statistics


def test_summarize_values_reports_percentiles() -> None:
    summary = summarize_values([1.0, 2.0, 3.0, 4.0])

    assert summary["count"] == 4
    assert summary["mean"] == pytest.approx(2.5)
    assert summary["median"] == pytest.approx(2.5)
    assert summary["p95"] == pytest.approx(3.85)


def test_track_statistics_counts_gaps_and_segments() -> None:
    rows = [
        {"track_id": 1, "frame_index": 0, "class_name": "car"},
        {"track_id": 1, "frame_index": 1, "class_name": "car"},
        {"track_id": 1, "frame_index": 3, "class_name": "car"},
        {"track_id": 2, "frame_index": 2, "class_name": "bus"},
    ]

    summary = track_statistics(rows)

    assert summary["unique_track_ids"] == 2
    assert summary["track_observations"] == 4
    assert summary["tracks_with_gaps"] == 1
    assert summary["total_gap_frames"] == 1
    assert summary["track_length_observations"]["mean"] == pytest.approx(2.0)
    assert summary["class_observations"] == {"bus": 1, "car": 3}
    assert summary["per_track"][0]["segments"] == 2
