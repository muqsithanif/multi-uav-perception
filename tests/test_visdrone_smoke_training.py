from pathlib import Path
import cv2
import numpy as np
import pytest
import torch

from scripts.run_visdrone_smoke_training import (
    inspect_resume_checkpoint,
    prepare_smoke_subset,
    read_results_csv,
)


def write_fixture_split(root: Path, split: str, count: int = 5) -> None:
    images = root / "images" / split
    labels = root / "labels" / split
    images.mkdir(parents=True)
    labels.mkdir(parents=True)
    for index in range(count):
        image = np.zeros((40, 60, 3), dtype=np.uint8)
        assert cv2.imwrite(str(images / f"{index:03d}.jpg"), image)
        labels.joinpath(f"{index:03d}.txt").write_text(
            f"{index} 0.5 0.5 0.2 0.2\n", encoding="utf-8"
        )


def test_prepare_smoke_subset_covers_classes_and_splits(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_fixture_split(source, "train")
    write_fixture_split(source, "val")
    output = tmp_path / "smoke"

    manifest = prepare_smoke_subset(
        source / "images",
        source / "labels",
        output,
        {"train": 5, "val": 5},
        ["a", "b", "c", "d", "e"],
    )

    assert manifest["splits"]["train"]["subset_size"] == 5
    assert manifest["splits"]["val"]["ground_truth_class_counts"] == {
        "0": 1,
        "1": 1,
        "2": 1,
        "3": 1,
        "4": 1,
    }
    assert len(list((output / "images" / "train").glob("*.jpg"))) == 5
    assert (output / "dataset.yaml").is_file()


def test_inspect_resume_checkpoint_requires_optimizer(tmp_path: Path) -> None:
    checkpoint = tmp_path / "resume.pt"
    torch.save(
        {"epoch": 1, "optimizer": {"state": {}}, "scaler": {}, "train_args": {"epochs": 3}},
        checkpoint,
    )

    record = inspect_resume_checkpoint(checkpoint, 2, 3)

    assert record["completed_epoch"] == 2
    assert record["optimizer_present"] is True
    assert record["planned_epochs"] == 3


def test_inspect_resume_checkpoint_rejects_stripped_checkpoint(tmp_path: Path) -> None:
    checkpoint = tmp_path / "stripped.pt"
    torch.save(
        {"epoch": -1, "optimizer": None, "train_args": {"epochs": 3}}, checkpoint
    )

    with pytest.raises(ValueError, match="checkpoint epoch"):
        inspect_resume_checkpoint(checkpoint, 2, 3)


def test_read_results_csv_requires_all_three_epochs(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    results.write_text("epoch,metric\n1,0.1\n2,0.2\n3,0.3\n", encoding="utf-8")

    rows, digest = read_results_csv(results, 3)

    assert [row["epoch"] for row in rows] == ["1", "2", "3"]
    assert len(digest) == 64
