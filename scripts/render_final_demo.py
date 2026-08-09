"""Compose the reproducible 2D Gate 9 demo from simulation and ROS evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from multi_uav_core.simulation import run_scenario  # noqa: E402
from run_simulation_demo import render as render_simulation  # noqa: E402


def _chapter_frame(image: np.ndarray, title: str, detail: str) -> np.ndarray:
    canvas = np.full((760, 700, 3), 255, dtype=np.uint8)
    canvas[60:, :] = image
    cv2.putText(canvas, title, (14, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (20, 20, 20), 2)
    cv2.putText(canvas, detail, (14, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (50, 50, 50), 1)
    return canvas


def _event_label(events: list[dict], step: int) -> str:
    matching = [item for item in events if item["step"] == step]
    if not matching:
        return "no scheduled event"
    return "; ".join(f"event={item['type']}" for item in matching)


def _append_ros_replay(writer: cv2.VideoWriter, path: Path) -> int:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise SystemExit(f"unable to open ROS replay video: {path}")
    frame_count = 0
    while True:
        success, frame = capture.read()
        if not success:
            break
        resized = cv2.resize(frame, (630, 700), interpolation=cv2.INTER_AREA)
        image = np.full((700, 700, 3), 250, dtype=np.uint8)
        image[:, 35:665] = resized
        writer.write(
            _chapter_frame(
                image,
                "Chapter 7/7: recorded ROS MissionCommand replay",
                "Captured typed command; synthetic image-space pixels, not physical UAV coordinates.",
            )
        )
        frame_count += 1
    capture.release()
    return frame_count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ros-replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--algorithm", choices=["greedy", "hungarian"], default="hungarian")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    priority_config = yaml.safe_load((ROOT / "configs/priority_assignment.yaml").read_text(encoding="utf-8"))
    simulation_config = yaml.safe_load((ROOT / "configs/simulation_scenarios.yaml").read_text(encoding="utf-8"))
    simulation = simulation_config["simulation"]
    scenarios = simulation_config["scenarios"]
    args.output.mkdir(parents=True)
    fps = 10.0
    video_path = args.output / "final_demo.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (700, 760))
    if not writer.isOpened():
        raise SystemExit("unable to open final demo MP4 writer")

    chapter_summaries: list[dict] = []
    for chapter, (name, spec) in enumerate(scenarios.items(), start=1):
        result = run_scenario(name, spec, priority_config, simulation, args.algorithm)
        for frame in result["frames"]:
            rendered = render_simulation(frame, simulation["width"], simulation["height"])
            detail = (
                f"step={frame['step'] + 1}/{simulation['steps']} | {_event_label(result['events'], frame['step'])} | "
                "abstract simulation units"
            )
            chapter_frame = _chapter_frame(rendered, f"Chapter {chapter}/7: {name}", detail)
            for _ in range(int(fps)):
                writer.write(chapter_frame)
        mean_ms = sum(item["compute_ms"] for item in result["assignments"]) / len(result["assignments"])
        chapter_summaries.append(
            {
                "scenario": name,
                "frames": len(result["frames"]),
                "events": result["events"],
                "final_unassigned": result["frames"][-1]["unassigned"],
                "mean_assignment_ms": mean_ms,
            }
        )
    ros_frames = _append_ros_replay(writer, args.ros_replay)
    writer.release()

    summary = {
        "status": "rendered",
        "algorithm": args.algorithm,
        "fps": fps,
        "simulation_seconds": len(scenarios) * simulation["steps"],
        "ros_replay_frames": ros_frames,
        "ros_replay_seconds": ros_frames / fps,
        "duration_s": (len(scenarios) * simulation["steps"] + ros_frames / fps),
        "ros_replay_input": str(args.ros_replay),
        "video": video_path.name,
        "scenarios": chapter_summaries,
        "coordinate_note": "All simulation and replay coordinates are abstract units or synthetic image-space pixels; neither represents physical flight.",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
