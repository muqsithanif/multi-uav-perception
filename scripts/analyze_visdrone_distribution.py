#!/usr/bin/env python3
"""Create machine-readable and plotted VisDrone five-class distributions."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

if __package__:
    from .visdrone_dataset import write_json_atomic
else:
    from visdrone_dataset import write_json_atomic


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "experiments" / "D01_visdrone_validation" / "summary.json"
DEFAULT_OUTPUT = REPO_ROOT / "results" / "day2" / "dataset_analysis"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_distribution(report: dict[str, Any]) -> dict[str, Any]:
    names = list(report["project_class_names"])
    splits: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for split in ("train", "val"):
        raw_counts = report["splits"][split]["project_class_counts"]
        counts = [int(raw_counts.get(str(class_id), 0)) for class_id in range(len(names))]
        total = sum(counts)
        if total <= 0 or any(count <= 0 for count in counts):
            raise ValueError(f"Every project class must have a positive count in {split}")
        percentages = [count * 100.0 / total for count in counts]
        maximum_id = max(range(len(counts)), key=counts.__getitem__)
        minimum_id = min(range(len(counts)), key=counts.__getitem__)
        split_rows = []
        for class_id, (name, count, percentage) in enumerate(
            zip(names, counts, percentages, strict=True)
        ):
            row = {
                "split": split,
                "class_id": class_id,
                "class_name": name,
                "count": count,
                "percentage": round(percentage, 6),
            }
            split_rows.append(row)
            rows.append(row)
        splits[split] = {
            "total_objects": total,
            "classes": split_rows,
            "dominant_class": names[maximum_id],
            "dominant_class_id": maximum_id,
            "minority_class": names[minimum_id],
            "minority_class_id": minimum_id,
            "max_to_min_count_ratio": round(
                counts[maximum_id] / counts[minimum_id], 6
            ),
        }

    train_percentages = {
        row["class_id"]: row["percentage"] for row in splits["train"]["classes"]
    }
    val_percentages = {
        row["class_id"]: row["percentage"] for row in splits["val"]["classes"]
    }
    shifts = [
        {
            "class_id": class_id,
            "class_name": names[class_id],
            "val_minus_train_percentage_points": round(
                val_percentages[class_id] - train_percentages[class_id], 6
            ),
        }
        for class_id in range(len(names))
    ]
    largest_shift = max(shifts, key=lambda row: abs(row["val_minus_train_percentage_points"]))
    return {
        "schema_version": 1,
        "dataset": report["dataset"],
        "source_revision": report.get("source_revision"),
        "status": "passed",
        "project_class_names": names,
        "splits": splits,
        "cross_split_share_shift": shifts,
        "largest_absolute_share_shift": largest_shift,
        "rows": rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("split", "class_id", "class_name", "count", "percentage"),
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def plot_distribution(path: Path, analysis: dict[str, Any]) -> None:
    names = analysis["project_class_names"]
    train = analysis["splits"]["train"]["classes"]
    val = analysis["splits"]["val"]["classes"]
    positions = list(range(len(names)))
    width = 0.38
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.2), constrained_layout=True)

    axes[0].bar(
        [position - width / 2 for position in positions],
        [row["count"] for row in train],
        width,
        label="train",
        color="#2E86AB",
    )
    axes[0].bar(
        [position + width / 2 for position in positions],
        [row["count"] for row in val],
        width,
        label="val",
        color="#F18F01",
    )
    axes[0].set_yscale("log")
    axes[0].set_title("Object count (log scale)")
    axes[0].set_ylabel("Objects")
    axes[0].legend()

    axes[1].bar(
        [position - width / 2 for position in positions],
        [row["percentage"] for row in train],
        width,
        label="train",
        color="#2E86AB",
    )
    axes[1].bar(
        [position + width / 2 for position in positions],
        [row["percentage"] for row in val],
        width,
        label="val",
        color="#F18F01",
    )
    axes[1].set_title("Within-split class share")
    axes[1].set_ylabel("Percent")
    axes[1].legend()

    for axis in axes:
        axis.set_xticks(positions, names, rotation=25, ha="right")
        axis.grid(axis="y", alpha=0.25)
    figure.suptitle("VisDrone five-class distribution")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    report = json.loads(source.read_text(encoding="utf-8"))
    analysis = compute_distribution(report)
    analysis["created_at_utc"] = datetime.now(UTC).isoformat()
    analysis["source_report"] = source.relative_to(REPO_ROOT).as_posix()
    csv_path = output / "class_distribution.csv"
    plot_path = output / "class_distribution.png"
    write_csv(csv_path, analysis.pop("rows"))
    plot_distribution(plot_path, analysis)
    analysis["artifacts"] = {
        "csv": {
            "path": csv_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": sha256_file(csv_path),
        },
        "plot": {
            "path": plot_path.relative_to(REPO_ROOT).as_posix(),
            "sha256": sha256_file(plot_path),
        },
    }
    write_json_atomic(output / "class_distribution.json", analysis)
    print(json.dumps(analysis, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
