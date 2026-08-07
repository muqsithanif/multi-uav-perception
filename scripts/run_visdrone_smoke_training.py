#!/usr/bin/env python3
"""Run a two-phase, three-epoch VisDrone smoke train with verified resume."""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import random
import shutil
import subprocess
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import ultralytics
import yaml
from ultralytics import YOLO

if __package__:
    from .evaluate_pretrained_baseline import evenly_spaced_indices, sha256_file
    from .render_visdrone_audit import parse_yolo_boxes
    from .visdrone_dataset import collect_pairs, write_json_atomic
else:
    from evaluate_pretrained_baseline import evenly_spaced_indices, sha256_file
    from render_visdrone_audit import parse_yolo_boxes
    from visdrone_dataset import collect_pairs, write_json_atomic


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "visdrone_smoke_train.yaml"


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def git_revision() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("smoke training config must be a mapping")
    required = {
        "experiment_id",
        "model",
        "expected_model_sha256",
        "source_images_root",
        "source_labels_root",
        "smoke_dataset_root",
        "train_subset_size",
        "val_subset_size",
        "class_names",
        "planned_epochs",
        "phase_1_stop_after_epoch",
        "resume_target_epoch",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"missing config keys: {missing}")
    if bool(config.get("full_fine_tuning")):
        raise ValueError("this runner refuses full fine-tuning")
    if int(config["planned_epochs"]) not in {2, 3}:
        raise ValueError("smoke training must be limited to two or three planned epochs")
    if not (
        0
        < int(config["phase_1_stop_after_epoch"])
        < int(config["resume_target_epoch"])
        == int(config["planned_epochs"])
    ):
        raise ValueError("resume plan must stop early and finish at the planned epoch")
    return config


def link_or_copy(source: Path, destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def prepare_smoke_subset(
    images_root: Path,
    labels_root: Path,
    output_root: Path,
    split_sizes: dict[str, int],
    class_names: list[str],
) -> dict[str, Any]:
    """Build deterministic train/val smoke subsets without modifying the source."""
    if output_root.exists():
        raise FileExistsError(f"smoke dataset output already exists: {output_root}")
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "selection_policy": "evenly_spaced_sorted_filename",
        "class_names": class_names,
        "splits": {},
    }
    for split, requested_size in split_sizes.items():
        pairs = collect_pairs(images_root / split, labels_root / split)
        indexes = evenly_spaced_indices(len(pairs), requested_size)
        class_counts = [0] * len(class_names)
        mode_counts = {"hardlink": 0, "copy": 0}
        entries = []
        for source_index in indexes:
            image_path, label_path = pairs[source_index]
            image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"unreadable image: {image_path}")
            boxes = parse_yolo_boxes(label_path, len(class_names))
            for box in boxes:
                class_counts[box.class_id] += 1
            target_image = output_root / "images" / split / image_path.name
            target_label = output_root / "labels" / split / label_path.name
            mode_counts[link_or_copy(image_path, target_image)] += 1
            target_label.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(label_path, target_label)
            entries.append(
                {
                    "source_index": source_index,
                    "image_name": image_path.name,
                    "image_width": int(image.shape[1]),
                    "image_height": int(image.shape[0]),
                    "ground_truth_objects": len(boxes),
                    "label_sha256": sha256_file(label_path),
                }
            )
        if any(count == 0 for count in class_counts):
            raise ValueError(f"{split} smoke subset misses a project class: {class_counts}")
        manifest["splits"][split] = {
            "population_size": len(pairs),
            "subset_size": len(entries),
            "ground_truth_class_counts": {
                str(class_id): count for class_id, count in enumerate(class_counts)
            },
            "image_transfer_modes": mode_counts,
            "entries": entries,
        }
    dataset_yaml = {
        "path": str(output_root),
        "train": "images/train",
        "val": "images/val",
        "names": {index: name for index, name in enumerate(class_names)},
    }
    (output_root / "dataset.yaml").write_text(
        yaml.safe_dump(dataset_yaml, sort_keys=False), encoding="utf-8"
    )
    manifest["dataset_yaml"] = str(output_root / "dataset.yaml")
    return manifest


def inspect_resume_checkpoint(
    checkpoint_path: Path, expected_completed_epoch: int, planned_epochs: int
) -> dict[str, Any]:
    """Verify that a checkpoint retains the state required for true resume."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    epoch_zero_based = int(checkpoint.get("epoch", -1))
    optimizer_present = checkpoint.get("optimizer") is not None
    scaler_present = checkpoint.get("scaler") is not None
    train_args = checkpoint.get("train_args") or {}
    recorded_epochs = int(train_args.get("epochs", -1))
    if epoch_zero_based + 1 != expected_completed_epoch:
        raise ValueError(
            f"resume checkpoint epoch is {epoch_zero_based + 1}, expected {expected_completed_epoch}"
        )
    if not optimizer_present:
        raise ValueError("resume checkpoint has no optimizer state")
    if recorded_epochs != planned_epochs:
        raise ValueError(
            f"resume checkpoint planned epochs is {recorded_epochs}, expected {planned_epochs}"
        )
    return {
        "path": str(checkpoint_path),
        "bytes": checkpoint_path.stat().st_size,
        "sha256": sha256_file(checkpoint_path),
        "completed_epoch": epoch_zero_based + 1,
        "optimizer_present": optimizer_present,
        "scaler_present": scaler_present,
        "planned_epochs": recorded_epochs,
    }


def read_results_csv(path: Path, expected_rows: int) -> tuple[list[dict[str, str]], str]:
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    if len(rows) != expected_rows:
        raise ValueError(f"results.csv has {len(rows)} rows, expected {expected_rows}")
    return rows, sha256_file(path)


def copy_compact_results(train_dir: Path, result_dir: Path) -> list[str]:
    result_dir.mkdir(parents=True, exist_ok=False)
    copied = []
    allowed_names = {"results.csv", "results.png", "args.yaml"}
    for path in sorted(train_dir.iterdir()):
        if path.is_file() and (path.name in allowed_names or path.suffix.lower() == ".png"):
            destination = result_dir / path.name
            shutil.copy2(path, destination)
            copied.append(destination.relative_to(REPO_ROOT).as_posix())
    if not (result_dir / "results.csv").is_file():
        raise FileNotFoundError("compact result copy is missing results.csv")
    return copied


def environment_record(source_revision: str | None) -> dict[str, Any]:
    cuda_available = torch.cuda.is_available()
    return {
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "source_revision": source_revision,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "cuda_available": cuda_available,
        "cuda_device_count": torch.cuda.device_count(),
        "cuda_device_name": torch.cuda.get_device_name(0) if cuda_available else None,
        "cuda_total_memory_bytes": (
            torch.cuda.get_device_properties(0).total_memory if cuda_available else None
        ),
    }


def run(config_path: Path, persistent_root: Path) -> dict[str, Any]:
    config = load_config(config_path)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is required for the Colab smoke run")
    revision = git_revision()
    experiment_id = str(config["experiment_id"])
    persistent_root = persistent_root.resolve()
    persistent_experiment = persistent_root / experiment_id
    train_project = persistent_experiment / "ultralytics"
    train_dir = train_project / experiment_id
    checkpoint_dir = persistent_experiment / "checkpoints"
    repo_experiment_dir = REPO_ROOT / "experiments" / experiment_id
    repo_result_dir = REPO_ROOT / "results" / "day2" / experiment_id
    for path in (persistent_experiment, repo_experiment_dir, repo_result_dir):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite existing run path: {path}")
    persistent_experiment.mkdir(parents=True)
    checkpoint_dir.mkdir()
    repo_experiment_dir.mkdir(parents=True)
    shutil.copy2(config_path, repo_experiment_dir / "config.yaml")
    (repo_experiment_dir / "command.txt").write_text(
        ".venv/bin/python scripts/run_visdrone_smoke_training.py "
        "--config configs/visdrone_smoke_train.yaml "
        f"--persistent-root {persistent_root}\n",
        encoding="utf-8",
    )

    started_at = datetime.now(UTC)
    environment = environment_record(revision)
    write_json_atomic(repo_experiment_dir / "environment.json", environment)
    write_json_atomic(persistent_experiment / "environment.json", environment)

    random.seed(int(config["seed"]))
    np.random.seed(int(config["seed"]))
    torch.manual_seed(int(config["seed"]))
    torch.cuda.manual_seed_all(int(config["seed"]))

    smoke_root = resolve_repo_path(config["smoke_dataset_root"])
    subset_manifest = prepare_smoke_subset(
        resolve_repo_path(config["source_images_root"]),
        resolve_repo_path(config["source_labels_root"]),
        smoke_root,
        {
            "train": int(config["train_subset_size"]),
            "val": int(config["val_subset_size"]),
        },
        list(config["class_names"]),
    )
    subset_manifest.update(
        {
            "created_at_utc": datetime.now(UTC).isoformat(),
            "dataset": config["dataset"],
            "source_revision": revision,
            "scope": config["scope"],
        }
    )
    write_json_atomic(repo_experiment_dir / "subset_manifest.json", subset_manifest)

    model_path = resolve_repo_path(config["model"])
    if not model_path.is_file():
        YOLO(str(config["model"]))
    if not model_path.is_file():
        raise FileNotFoundError(f"model was not resolved to {model_path}")
    model_sha256 = sha256_file(model_path)
    if model_sha256 != config["expected_model_sha256"]:
        raise ValueError(f"unexpected pretrained model SHA-256: {model_sha256}")

    resume_checkpoint = checkpoint_dir / "epoch2_resume.pt"
    phase1_model = YOLO(str(model_path))

    def preserve_resume_checkpoint(trainer) -> None:
        if trainer.epoch + 1 == int(config["phase_1_stop_after_epoch"]):
            shutil.copy2(trainer.last, resume_checkpoint)

    def stop_phase_one(trainer) -> None:
        if trainer.epoch + 1 >= int(config["phase_1_stop_after_epoch"]):
            trainer.stop = True

    phase1_model.add_callback("on_model_save", preserve_resume_checkpoint)
    phase1_model.add_callback("on_fit_epoch_end", stop_phase_one)
    train_wall_start = time.perf_counter()
    phase1_model.train(
        data=str(smoke_root / "dataset.yaml"),
        epochs=int(config["planned_epochs"]),
        imgsz=int(config["image_size"]),
        batch=int(config["batch"]),
        workers=int(config["workers"]),
        device=config["device"],
        seed=int(config["seed"]),
        deterministic=bool(config["deterministic"]),
        amp=bool(config["amp"]),
        optimizer=config["optimizer"],
        patience=int(config["patience"]),
        cache=bool(config["cache"]),
        plots=bool(config["plots"]),
        save=True,
        save_period=int(config["save_period"]),
        close_mosaic=int(config["close_mosaic"]),
        project=str(train_project),
        name=experiment_id,
        exist_ok=False,
        verbose=True,
    )
    if not resume_checkpoint.is_file():
        raise FileNotFoundError("phase 1 did not preserve the raw epoch-2 checkpoint")
    resume_checkpoint_record = inspect_resume_checkpoint(
        resume_checkpoint,
        int(config["phase_1_stop_after_epoch"]),
        int(config["planned_epochs"]),
    )

    resume_observation: dict[str, Any] = {}
    phase2_model = YOLO(str(resume_checkpoint))

    def capture_resume_start(trainer) -> None:
        resume_observation.update(
            {
                "start_epoch_zero_based": int(trainer.start_epoch),
                "start_epoch_one_based": int(trainer.start_epoch) + 1,
                "target_epochs": int(trainer.epochs),
                "resume_flag": bool(trainer.resume),
            }
        )

    phase2_model.add_callback("on_train_start", capture_resume_start)
    phase2_model.train(
        resume=True,
        device=config["device"],
        workers=int(config["workers"]),
        plots=bool(config["plots"]),
        save_period=int(config["save_period"]),
        verbose=True,
    )
    training_wall_seconds = time.perf_counter() - train_wall_start
    if resume_observation != {
        "start_epoch_zero_based": int(config["phase_1_stop_after_epoch"]),
        "start_epoch_one_based": int(config["resume_target_epoch"]),
        "target_epochs": int(config["planned_epochs"]),
        "resume_flag": True,
    }:
        raise ValueError(f"unexpected resume observation: {resume_observation}")

    results_rows, results_csv_sha256 = read_results_csv(
        train_dir / "results.csv", int(config["planned_epochs"])
    )
    compact_artifacts = copy_compact_results(train_dir, repo_result_dir)
    final_last = train_dir / "weights" / "last.pt"
    final_best = train_dir / "weights" / "best.pt"
    if not final_last.is_file() or not final_best.is_file():
        raise FileNotFoundError("final last.pt/best.pt checkpoint is missing")

    summary = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "status": "passed",
        "scope": "subset_smoke_only",
        "full_fine_tuning": False,
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "source_revision": revision,
        "dataset": config["dataset"],
        "subset": {
            split: {
                "population_size": details["population_size"],
                "subset_size": details["subset_size"],
                "ground_truth_class_counts": details["ground_truth_class_counts"],
            }
            for split, details in subset_manifest["splits"].items()
        },
        "model": {
            "path": config["model"],
            "sha256": model_sha256,
            "bytes": model_path.stat().st_size,
        },
        "protocol": {
            "planned_epochs": int(config["planned_epochs"]),
            "phase_1_completed_epochs": int(config["phase_1_stop_after_epoch"]),
            "resume_target_epoch": int(config["resume_target_epoch"]),
            "image_size": int(config["image_size"]),
            "batch": int(config["batch"]),
            "device": config["device"],
            "amp": bool(config["amp"]),
            "seed": int(config["seed"]),
        },
        "resume_proof": {
            "status": "passed",
            "checkpoint_before_resume": resume_checkpoint_record,
            "observed_resume_start": resume_observation,
            "final_results_csv_rows": len(results_rows),
        },
        "smoke_metrics_last_epoch": results_rows[-1],
        "timing": {"training_wall_seconds": training_wall_seconds},
        "persistent_artifacts": {
            "root": str(persistent_experiment),
            "resume_checkpoint": str(resume_checkpoint),
            "final_last": {
                "path": str(final_last),
                "bytes": final_last.stat().st_size,
                "sha256": sha256_file(final_last),
            },
            "final_best": {
                "path": str(final_best),
                "bytes": final_best.stat().st_size,
                "sha256": sha256_file(final_best),
            },
            "results_csv_sha256": results_csv_sha256,
        },
        "compact_artifacts": compact_artifacts,
        "limitations": [
            "three-epoch smoke result on deterministic subsets, not full fine-tuning",
            "smoke validation subset differs from the locked E00 subset and is not an accuracy comparison",
        ],
    }
    write_json_atomic(repo_experiment_dir / "summary.json", summary)
    write_json_atomic(repo_result_dir / "summary.json", summary)
    write_json_atomic(persistent_experiment / "summary.json", summary)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--persistent-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = run(args.config.resolve(), args.persistent_root)
    except Exception as error:
        failure_root = args.persistent_root.resolve() / "failures"
        failure_root.mkdir(parents=True, exist_ok=True)
        failure = {
            "recorded_at_utc": datetime.now(UTC).isoformat(),
            "status": "failed",
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "source_revision": git_revision(),
        }
        write_json_atomic(
            failure_root / f"smoke_failure_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json",
            failure,
        )
        raise
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
