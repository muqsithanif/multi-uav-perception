#!/usr/bin/env python3
"""Compare two detector summaries only when their locked protocols match."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

if __package__:
    from .visdrone_dataset import write_json_atomic
else:
    from visdrone_dataset import write_json_atomic


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "e00_vs_e01_comparison.yaml"
METRICS = ("precision", "recall", "map50", "map50_95")
PROTOCOL_KEYS = (
    "image_size",
    "confidence",
    "iou_nms",
    "max_detections",
    "batch",
    "device",
    "half",
    "rect",
    "evaluation_iou_thresholds",
    "metric_implementation",
)
SUBSET_KEYS = (
    "size",
    "population_size",
    "selection_policy",
    "selection_sha256",
    "ground_truth_class_counts",
)


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_mapping(path: Path, description: str) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a mapping")
    return value


def metric_delta(baseline: float, candidate: float) -> dict[str, float | None]:
    delta = candidate - baseline
    return {
        "baseline": baseline,
        "candidate": candidate,
        "absolute_delta": delta,
        "relative_change_percent": None if baseline == 0.0 else delta / baseline * 100.0,
    }


def compare_summaries(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    for role, summary in (("baseline", baseline), ("candidate", candidate)):
        if summary.get("status") != "passed":
            raise ValueError(f"{role} summary status is not passed")

    subset_mismatches = [
        key
        for key in SUBSET_KEYS
        if baseline.get("subset", {}).get(key) != candidate.get("subset", {}).get(key)
    ]
    if subset_mismatches:
        raise ValueError(
            "locked subsets are not comparable: " + ", ".join(subset_mismatches)
        )
    protocol_mismatches = [
        key
        for key in PROTOCOL_KEYS
        if baseline.get("protocol", {}).get(key)
        != candidate.get("protocol", {}).get(key)
    ]
    if protocol_mismatches:
        raise ValueError(
            "evaluation protocols are not comparable: "
            + ", ".join(protocol_mismatches)
        )

    overall = {
        metric: metric_delta(
            float(baseline["metrics"]["overall_macro"][metric]),
            float(candidate["metrics"]["overall_macro"][metric]),
        )
        for metric in METRICS
    }
    baseline_classes = {
        int(row["class_id"]): row for row in baseline["metrics"]["per_class"]
    }
    candidate_classes = {
        int(row["class_id"]): row for row in candidate["metrics"]["per_class"]
    }
    if baseline_classes.keys() != candidate_classes.keys():
        raise ValueError("per-class IDs do not match")

    per_class = []
    for class_id in sorted(baseline_classes):
        baseline_row = baseline_classes[class_id]
        candidate_row = candidate_classes[class_id]
        for key in ("class_name", "instances"):
            if baseline_row[key] != candidate_row[key]:
                raise ValueError(f"class {class_id} differs at {key}")
        per_class.append(
            {
                "class_id": class_id,
                "class_name": baseline_row["class_name"],
                "instances": int(baseline_row["instances"]),
                "metrics": {
                    metric: metric_delta(
                        float(baseline_row[metric]), float(candidate_row[metric])
                    )
                    for metric in METRICS
                },
            }
        )
    return {"overall_macro": overall, "per_class": per_class}


def write_comparison_csv(path: Path, comparison: dict[str, Any]) -> None:
    fieldnames = (
        "scope",
        "class_id",
        "class_name",
        "instances",
        "metric",
        "baseline",
        "candidate",
        "absolute_delta",
        "relative_change_percent",
    )
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for metric, values in comparison["overall_macro"].items():
            writer.writerow(
                {
                    "scope": "overall_macro",
                    "class_id": "",
                    "class_name": "all",
                    "instances": "",
                    "metric": metric,
                    **values,
                }
            )
        for class_row in comparison["per_class"]:
            for metric, values in class_row["metrics"].items():
                writer.writerow(
                    {
                        "scope": "class",
                        "class_id": class_row["class_id"],
                        "class_name": class_row["class_name"],
                        "instances": class_row["instances"],
                        "metric": metric,
                        **values,
                    }
                )


def run(config_path: Path) -> dict[str, Any]:
    config = load_mapping(config_path, "comparison config")
    required = {
        "comparison_id",
        "baseline_summary",
        "candidate_summary",
        "output_dir",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"missing config keys: {missing}")

    baseline_path = resolve_repo_path(config["baseline_summary"])
    candidate_path = resolve_repo_path(config["candidate_summary"])
    output_dir = resolve_repo_path(config["output_dir"])
    if output_dir.exists():
        raise FileExistsError(f"comparison output already exists: {output_dir}")
    baseline = load_mapping(baseline_path, "baseline summary")
    candidate = load_mapping(candidate_path, "candidate summary")
    comparison = compare_summaries(baseline, candidate)

    output_dir.mkdir(parents=True)
    shutil.copyfile(config_path, output_dir / "config.yaml")
    command = (
        ".venv/bin/python scripts/compare_detection_experiments.py "
        "--config configs/e00_vs_e01_comparison.yaml\n"
    )
    (output_dir / "command.txt").write_text(command, encoding="utf-8")
    csv_path = output_dir / "comparison.csv"
    write_comparison_csv(csv_path, comparison)
    summary = {
        "schema_version": 1,
        "comparison_id": config["comparison_id"],
        "status": "passed",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "baseline": {
            "experiment_id": baseline["experiment_id"],
            "summary": config["baseline_summary"],
            "summary_sha256": sha256_file(baseline_path),
        },
        "candidate": {
            "experiment_id": candidate["experiment_id"],
            "summary": config["candidate_summary"],
            "summary_sha256": sha256_file(candidate_path),
        },
        "locked_subset": {key: baseline["subset"][key] for key in SUBSET_KEYS},
        "protocol": {key: baseline["protocol"][key] for key in PROTOCOL_KEYS},
        "comparison": comparison,
        "artifacts": {
            "config": "config.yaml",
            "command": "command.txt",
            "comparison_csv": "comparison.csv",
        },
    }
    write_json_atomic(output_dir / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    summary = run(parse_args().config.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
