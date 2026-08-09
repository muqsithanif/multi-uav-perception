#!/usr/bin/env python3
"""Run ByteTrack and BoT-SORT on one locked aerial-video protocol."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import lap
import numpy as np
import torch
import ultralytics
import yaml
from ultralytics import YOLO

if __package__:
    from .visdrone_dataset import write_json_atomic
else:
    from visdrone_dataset import write_json_atomic


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "e01_tracking_comparison.yaml"


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (REPO_ROOT / path).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_command() -> str:
    return "git.exe" if shutil.which("git.exe") else "git"


def git_revision() -> str | None:
    completed = subprocess.run(
        [git_command(), "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def git_tracked_dirty_paths() -> list[str]:
    completed = subprocess.run(
        [git_command(), "diff", "--name-only", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        return []
    return sorted(line.strip() for line in completed.stdout.splitlines() if line.strip())


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("tracking config must be a mapping")
    required = {
        "comparison_id",
        "seed",
        "source",
        "model",
        "inference",
        "sampling",
        "trackers",
        "visualization",
        "experiment_dir",
        "result_dir",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"missing config keys: {missing}")
    if not isinstance(config["trackers"], list) or len(config["trackers"]) != 2:
        raise ValueError("tracking config must declare exactly two trackers")
    tracker_names = [str(item.get("name", "")) for item in config["trackers"]]
    if set(tracker_names) != {"bytetrack", "botsort"}:
        raise ValueError("trackers must be named bytetrack and botsort")
    return config


def summarize_values(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p95": None,
            "min": None,
            "max": None,
        }
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "min": float(np.min(array)),
        "max": float(np.max(array)),
    }


def track_statistics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_track: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_track[int(row["track_id"])].append(row)

    per_track: list[dict[str, Any]] = []
    total_gap_frames = 0
    tracks_with_gaps = 0
    class_observations: Counter[str] = Counter()
    for track_id, observations in sorted(by_track.items()):
        ordered = sorted(observations, key=lambda item: int(item["frame_index"]))
        frames = [int(item["frame_index"]) for item in ordered]
        gaps = [next_frame - current_frame - 1 for current_frame, next_frame in zip(frames, frames[1:])]
        gap_frames = sum(gap for gap in gaps if gap > 0)
        if gap_frames:
            tracks_with_gaps += 1
        total_gap_frames += gap_frames
        classes = Counter(str(item["class_name"]) for item in ordered)
        class_observations.update(str(item["class_name"]) for item in ordered)
        per_track.append(
            {
                "track_id": track_id,
                "class_name": classes.most_common(1)[0][0],
                "first_frame": frames[0],
                "last_frame": frames[-1],
                "observations": len(ordered),
                "span_frames": frames[-1] - frames[0] + 1,
                "gap_frames": gap_frames,
                "segments": 1 + sum(gap > 0 for gap in gaps),
            }
        )

    observation_lengths = [float(item["observations"]) for item in per_track]
    return {
        "unique_track_ids": len(per_track),
        "track_observations": len(rows),
        "track_length_observations": summarize_values(observation_lengths),
        "tracks_with_gaps": tracks_with_gaps,
        "total_gap_frames": total_gap_frames,
        "class_observations": dict(sorted(class_observations.items())),
        "per_track": per_track,
    }


def write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def probe_video(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"cannot open source video: {path}")
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if frame_count <= 0 or fps <= 0 or width <= 0 or height <= 0:
        raise ValueError(f"invalid video metadata: {path}")
    return {
        "frame_count": frame_count,
        "fps": fps,
        "width": width,
        "height": height,
        "duration_seconds": frame_count / fps,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def class_name(names: dict[int, str] | list[str], class_id: int) -> str:
    if isinstance(names, dict):
        return str(names.get(class_id, str(class_id)))
    return str(names[class_id]) if 0 <= class_id < len(names) else str(class_id)


def preview_frame(frame: np.ndarray, scale: float) -> np.ndarray:
    if scale == 1.0:
        return frame
    if scale <= 0.0 or scale > 1.0:
        raise ValueError("preview_scale must be in (0, 1]")
    return cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)


def create_video_writer(path: Path, frame: np.ndarray, fps: float) -> cv2.VideoWriter:
    height, width = frame.shape[:2]
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"cannot create annotated preview video: {path}")
    return writer


def tracker_config_record(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"tracker config must be a mapping: {path}")
    return {
        "path": path.relative_to(REPO_ROOT).as_posix(),
        "sha256": sha256_file(path),
        "parameters": config,
    }


def run_tracker(
    *,
    tracker: dict[str, Any],
    source_video: Path,
    source_metadata: dict[str, Any],
    model_path: Path,
    inference: dict[str, Any],
    sampling: dict[str, Any],
    visualization: dict[str, Any],
    result_dir: Path,
) -> dict[str, Any]:
    name = str(tracker["name"])
    tracker_path = resolve_repo_path(str(tracker["config"]))
    if not tracker_path.is_file():
        raise FileNotFoundError(f"tracker config missing: {tracker_path}")

    output_dir = result_dir / name
    output_dir.mkdir(parents=True)
    track_csv_path = output_dir / "tracks.csv"
    frame_csv_path = output_dir / "frames.csv"
    metrics_path = output_dir / "metrics.json"
    preview_path = output_dir / "annotated.mp4"
    preview_frames_dir = output_dir / "key_frames"

    model_started = time.perf_counter()
    model = YOLO(str(model_path), task="detect")
    model_load_seconds = time.perf_counter() - model_started
    predict_kwargs = {
        "imgsz": int(inference["image_size"]),
        "conf": float(inference["confidence"]),
        "iou": float(inference["iou_nms"]),
        "max_det": int(inference["max_detections"]),
        "device": str(inference["device"]),
        "rect": bool(inference["rect"]),
        "verbose": False,
        "tracker": str(tracker_path),
        "persist": True,
    }

    start_frame = int(sampling["start_frame"])
    frame_stride = int(sampling["frame_stride"])
    max_frames_value = sampling.get("max_frames")
    max_frames = int(max_frames_value) if max_frames_value is not None else None
    if start_frame < 0 or frame_stride < 1 or (max_frames is not None and max_frames < 1):
        raise ValueError("invalid sampling configuration")

    capture = cv2.VideoCapture(str(source_video))
    if not capture.isOpened():
        raise ValueError(f"cannot open source video: {source_video}")

    max_source_frame = source_metadata["frame_count"]
    target_last = max_source_frame - 1
    if max_frames is not None:
        target_last = min(
            target_last,
            start_frame + ((max_frames - 1) * frame_stride),
        )
    key_frame_indexes = {start_frame, start_frame + ((target_last - start_frame) // 2), target_last}

    track_rows: list[dict[str, Any]] = []
    frame_rows: list[dict[str, Any]] = []
    writer: cv2.VideoWriter | None = None
    source_index = -1
    processed_index = 0
    start_wall = time.perf_counter()
    try:
        while True:
            success, frame = capture.read()
            if not success:
                break
            source_index += 1
            if source_index < start_frame or (source_index - start_frame) % frame_stride:
                continue
            if max_frames is not None and processed_index >= max_frames:
                break

            started = time.perf_counter()
            result = model.track(frame, **predict_kwargs)[0]
            wall_ms = (time.perf_counter() - started) * 1000.0
            boxes = result.boxes
            detection_count = int(boxes.shape[0])
            is_tracked = bool(boxes.is_track) if boxes is not None else False
            track_count = 0
            if is_tracked and boxes.id is not None:
                box_values = boxes.xyxy.detach().cpu().tolist()
                class_values = boxes.cls.detach().cpu().to(torch.int64).tolist()
                confidence_values = boxes.conf.detach().cpu().tolist()
                track_ids = boxes.id.detach().cpu().to(torch.int64).tolist()
                track_count = len(track_ids)
                for values, class_id, confidence, track_id in zip(
                    box_values,
                    class_values,
                    confidence_values,
                    track_ids,
                ):
                    track_rows.append(
                        {
                            "source_frame_index": source_index,
                            "frame_index": processed_index,
                            "timestamp_seconds": source_index / float(source_metadata["fps"]),
                            "track_id": int(track_id),
                            "class_id": int(class_id),
                            "class_name": class_name(result.names, int(class_id)),
                            "confidence": float(confidence),
                            "x1": float(values[0]),
                            "y1": float(values[1]),
                            "x2": float(values[2]),
                            "y2": float(values[3]),
                            "center_x": float((values[0] + values[2]) / 2.0),
                            "center_y": float((values[1] + values[3]) / 2.0),
                        }
                    )

            frame_rows.append(
                {
                    "source_frame_index": source_index,
                    "frame_index": processed_index,
                    "timestamp_seconds": source_index / float(source_metadata["fps"]),
                    "wall_ms": wall_ms,
                    "preprocess_ms": float(result.speed.get("preprocess", 0.0)),
                    "inference_ms": float(result.speed.get("inference", 0.0)),
                    "postprocess_ms": float(result.speed.get("postprocess", 0.0)),
                    "detections": detection_count,
                    "tracked_detections": track_count,
                }
            )

            annotated = preview_frame(result.plot(), float(visualization["preview_scale"]))
            if writer is None:
                writer = create_video_writer(
                    preview_path,
                    annotated,
                    float(source_metadata["fps"]) / frame_stride,
                )
            writer.write(annotated)
            if source_index in key_frame_indexes:
                preview_frames_dir.mkdir(parents=True, exist_ok=True)
                key_path = preview_frames_dir / f"frame_{source_index:04d}.jpg"
                if not cv2.imwrite(str(key_path), annotated):
                    raise RuntimeError(f"cannot write key frame: {key_path}")
            processed_index += 1
    finally:
        capture.release()
        if writer is not None:
            writer.release()

    if not frame_rows:
        raise RuntimeError("tracking protocol processed no frames")
    if not track_rows:
        raise RuntimeError(f"{name} produced no tracked detections")

    track_fields = tuple(track_rows[0].keys())
    frame_fields = tuple(frame_rows[0].keys())
    write_csv(track_csv_path, track_fields, track_rows)
    write_csv(frame_csv_path, frame_fields, frame_rows)
    track_summary = track_statistics(track_rows)
    wall_values = [float(row["wall_ms"]) for row in frame_rows]
    metrics = {
        "schema_version": 1,
        "tracker": name,
        "tracker_config": tracker_config_record(tracker_path),
        "model_load_seconds": model_load_seconds,
        "processed_frames": len(frame_rows),
        "source_frame_range": {
            "first": int(frame_rows[0]["source_frame_index"]),
            "last": int(frame_rows[-1]["source_frame_index"]),
            "stride": frame_stride,
        },
        "wall_seconds": time.perf_counter() - start_wall,
        "timing": {
            "wall_ms": summarize_values(wall_values),
            "preprocess_ms": summarize_values([float(row["preprocess_ms"]) for row in frame_rows]),
            "inference_ms": summarize_values([float(row["inference_ms"]) for row in frame_rows]),
            "postprocess_ms": summarize_values([float(row["postprocess_ms"]) for row in frame_rows]),
            "fps_from_mean_wall": 1000.0 / float(np.mean(wall_values)),
            "timing_boundary": "one model.track call per decoded input frame including preprocess, detector, association, postprocess, and wrapper",
            "warmup_policy": "none; the complete selected video is measured",
        },
        "detections": {
            "per_frame": summarize_values([float(row["detections"]) for row in frame_rows]),
            "tracked_per_frame": summarize_values([float(row["tracked_detections"]) for row in frame_rows]),
        },
        "tracks": track_summary,
        "artifacts": {
            "tracks_csv": {
                "path": track_csv_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_file(track_csv_path),
            },
            "frames_csv": {
                "path": frame_csv_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_file(frame_csv_path),
            },
            "annotated_preview": {
                "path": preview_path.relative_to(REPO_ROOT).as_posix(),
                "sha256": sha256_file(preview_path),
            },
            "key_frames": [
                {
                    "path": path.relative_to(REPO_ROOT).as_posix(),
                    "sha256": sha256_file(path),
                }
                for path in sorted(preview_frames_dir.glob("*.jpg"))
            ],
        },
    }
    write_json_atomic(metrics_path, metrics)
    return metrics


def run(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    experiment_dir = resolve_repo_path(str(config["experiment_dir"]))
    result_dir = resolve_repo_path(str(config["result_dir"]))
    for target in (experiment_dir, result_dir):
        if target.exists():
            raise FileExistsError(f"tracking target already exists: {target}")
    experiment_dir.mkdir(parents=True)
    result_dir.mkdir(parents=True)
    shutil.copyfile(config_path, experiment_dir / "config.yaml")

    source_config = config["source"]
    source_video = resolve_repo_path(str(source_config["local_path"]))
    model_path = resolve_repo_path(str(config["model"]))
    if not source_video.is_file():
        raise FileNotFoundError(f"source video missing: {source_video}")
    if not model_path.is_file():
        raise FileNotFoundError(f"model checkpoint missing: {model_path}")

    np.random.seed(int(config["seed"]))
    torch.manual_seed(int(config["seed"]))
    source_metadata = {
        **probe_video(source_video),
        "local_path": source_video.relative_to(REPO_ROOT).as_posix(),
        "provider": source_config["provider"],
        "asset_id": str(source_config["asset_id"]),
        "page_url": source_config["page_url"],
        "license_url": source_config["license_url"],
        "attribution_required": bool(source_config["attribution_required"]),
    }
    write_json_atomic(experiment_dir / "source_video.json", source_metadata)
    command = (
        "YOLO_CONFIG_DIR=/tmp .venv/bin/python scripts/compare_trackers.py "
        "--config configs/e01_tracking_comparison.yaml\n"
    )
    (experiment_dir / "command.txt").write_text(command, encoding="utf-8")

    dirty_paths = git_tracked_dirty_paths()
    environment = {
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "source_revision": git_revision(),
        "source_tracked_dirty": bool(dirty_paths),
        "source_tracked_dirty_paths": dirty_paths,
        "platform": platform.platform(),
        "logical_cpu_count": os.cpu_count(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "ultralytics": ultralytics.__version__,
        "opencv": cv2.__version__,
        "numpy": np.__version__,
        "lap": lap.__version__,
        "cuda_available": torch.cuda.is_available(),
    }
    write_json_atomic(experiment_dir / "environment.json", environment)

    started_at = datetime.now(UTC)
    tracker_summaries: dict[str, Any] = {}
    for tracker in config["trackers"]:
        tracker_summaries[str(tracker["name"])] = run_tracker(
            tracker=tracker,
            source_video=source_video,
            source_metadata=source_metadata,
            model_path=model_path,
            inference=config["inference"],
            sampling=config["sampling"],
            visualization=config["visualization"],
            result_dir=result_dir,
        )

    summary = {
        "schema_version": 1,
        "comparison_id": config["comparison_id"],
        "status": "passed",
        "started_at_utc": started_at.isoformat(),
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "source_revision": environment["source_revision"],
        "environment": environment,
        "source_video": source_metadata,
        "model": {
            "path": model_path.relative_to(REPO_ROOT).as_posix(),
            "size_bytes": model_path.stat().st_size,
            "sha256": sha256_file(model_path),
        },
        "protocol": {
            "inference": config["inference"],
            "sampling": config["sampling"],
            "visualization": config["visualization"],
        },
        "trackers": tracker_summaries,
        "limitations": [
            "The source is a stock aerial-traffic clip and not a ground-truth tracking benchmark.",
            "No MOTA, IDF1, HOTA, or ID-switch count is reported because no valid track ground truth is available.",
            "Timing is a local WSL CPU observation, not a real-time or production guarantee.",
            "Both trackers use the same detector, source video, selected frames, thresholds, and measurement boundary.",
        ],
    }
    write_json_atomic(experiment_dir / "summary.json", summary)
    write_json_atomic(result_dir / "summary.json", summary)
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
