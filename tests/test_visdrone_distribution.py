from scripts.analyze_visdrone_distribution import compute_distribution, sha256_file


def test_compute_distribution_reports_counts_shares_and_imbalance() -> None:
    report = {
        "dataset": "fixture",
        "source_revision": "abc123",
        "project_class_names": ["a", "b"],
        "splits": {
            "train": {"project_class_counts": {"0": 75, "1": 25}},
            "val": {"project_class_counts": {"0": 50, "1": 50}},
        },
    }

    analysis = compute_distribution(report)

    assert analysis["status"] == "passed"
    assert analysis["splits"]["train"]["total_objects"] == 100
    assert analysis["splits"]["train"]["dominant_class"] == "a"
    assert analysis["splits"]["train"]["minority_class"] == "b"
    assert analysis["splits"]["train"]["max_to_min_count_ratio"] == 3
    assert analysis["splits"]["val"]["classes"][1]["percentage"] == 50
    assert analysis["largest_absolute_share_shift"] == {
        "class_id": 0,
        "class_name": "a",
        "val_minus_train_percentage_points": -25,
    }


def test_sha256_file_matches_known_digest(tmp_path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"VisDrone")

    assert sha256_file(artifact) == (
        "53ff48336bf85d0638d488ae84f32769b056e39e0d7174a91a5a15f456b09f00"
    )
