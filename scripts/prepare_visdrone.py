#!/usr/bin/env python3
"""Convert official VisDrone2019-DET train/val data into validated YOLO labels."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from visdrone_dataset import (
    load_conversion_config,
    prepare_dataset,
    validate_dataset_yaml,
    write_json_atomic,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "visdrone_conversion.yaml"
DATASET_YAML = REPO_ROOT / "configs" / "visdrone_5class.yaml"


def git_state() -> dict[str, object]:
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    tracked_status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    return {
        "source_revision": revision,
        "tracked_source_dirty": bool(tracked_status),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate conversion and dataset configs without reading dataset files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = load_conversion_config(config_path)
    dataset_yaml = validate_dataset_yaml(DATASET_YAML, config["project_names"])
    if args.check_config:
        print(
            json.dumps(
                {
                    "status": "passed",
                    "conversion_config": config_path.relative_to(REPO_ROOT).as_posix(),
                    "dataset_yaml": DATASET_YAML.relative_to(REPO_ROOT).as_posix(),
                    "train": dataset_yaml["train"],
                    "val": dataset_yaml["val"],
                    "names": config["project_names"],
                },
                indent=2,
            )
        )
        return 0

    report = prepare_dataset(config, REPO_ROOT)
    report.update(git_state())
    report["conversion_config"] = config_path.relative_to(REPO_ROOT).as_posix()
    report["dataset_yaml"] = DATASET_YAML.relative_to(REPO_ROOT).as_posix()
    manifest_path = REPO_ROOT / config["manifest_path"]
    report_path = REPO_ROOT / config["validation_report_path"]
    write_json_atomic(manifest_path, report)
    write_json_atomic(report_path, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise
