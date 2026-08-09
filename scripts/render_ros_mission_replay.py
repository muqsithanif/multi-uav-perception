"""Render a 2D replay from captured typed ROS target and mission-command messages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
COLORS = {"uav_1": (255, 80, 80), "uav_2": (80, 255, 80), "uav_3": (80, 80, 255)}


def _load_message(path: Path) -> dict:
    documents = [item for item in yaml.safe_load_all(path.read_text(encoding="utf-8")) if item is not None]
    if len(documents) != 1:
        raise ValueError(f"expected one non-empty YAML message in {path}")
    message = documents[0]
    if not isinstance(message, dict):
        raise ValueError(f"expected one YAML message in {path}")
    return message


def _draw_frame(
    uavs: dict[str, tuple[float, float]],
    targets: list[dict],
    command: dict,
    progress: float,
    frame_index: int,
    frame_count: int,
) -> np.ndarray:
    width, height, header_height = 640, 712, 72
    image = np.full((height, width, 3), 250, dtype=np.uint8)

    def canvas_point(x: float, y: float) -> tuple[int, int]:
        margin = 32
        scale = (width - 2 * margin) / width
        return (int(margin + x * scale), int(header_height + margin + y * scale))

    for coordinate in range(0, width + 1, 80):
        cv2.line(image, (coordinate, header_height), (coordinate, height), (230, 230, 230), 1)
        cv2.line(image, (0, header_height + coordinate), (width, header_height + coordinate), (230, 230, 230), 1)

    assigned_target = next(item for item in targets if int(item["track_id"]) == int(command["track_id"]))
    target_point = canvas_point(assigned_target["center_x_px"], assigned_target["center_y_px"])
    assigned_vehicle = command["vehicle_id"]
    start = uavs[assigned_vehicle]
    current = canvas_point(
        start[0] + (assigned_target["center_x_px"] - start[0]) * progress,
        start[1] + (assigned_target["center_y_px"] - start[1]) * progress,
    )
    cv2.arrowedLine(
        image,
        canvas_point(*start),
        target_point,
        COLORS[assigned_vehicle],
        2,
        tipLength=0.03,
    )
    for target in targets:
        point = canvas_point(target["center_x_px"], target["center_y_px"])
        active = int(target["track_id"]) == int(command["track_id"])
        color = (25, 25, 210) if active else (90, 90, 90)
        cv2.circle(image, point, 10 if active else 7, color, -1)
        label = f"track {target['track_id']} {target['class_label']}"
        cv2.putText(image, label, (point[0] + 12, point[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
    for vehicle_id, point in uavs.items():
        draw_point = current if vehicle_id == assigned_vehicle else canvas_point(*point)
        color = COLORS[vehicle_id]
        cv2.rectangle(image, (draw_point[0] - 8, draw_point[1] - 8), (draw_point[0] + 8, draw_point[1] + 8), color, -1)
        state = "MOVING" if vehicle_id == assigned_vehicle and progress < 1.0 else "HOLD"
        label_x = draw_point[0] + 10 if draw_point[0] < width - 100 else draw_point[0] - 78
        cv2.putText(image, f"{vehicle_id} {state}", (label_x, draw_point[1] + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)
    cv2.rectangle(image, (0, 0), (width, header_height), (255, 255, 255), -1)
    cv2.putText(image, "Recorded ROS MissionCommand replay", (14, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 20, 20), 2)
    detail = f"{command['command']}: {assigned_vehicle} -> track {command['track_id']}  frame {frame_index + 1}/{frame_count}"
    cv2.putText(image, detail, (14, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (20, 20, 20), 1)
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", type=Path, required=True, help="Captured ROS TargetArray YAML")
    parser.add_argument("--commands", type=Path, required=True, help="Captured ROS MissionCommand YAML")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    targets_message = _load_message(args.targets)
    command = _load_message(args.commands)
    if targets_message["source_id"] != command["source_id"]:
        raise SystemExit("target and command source_id differ")
    targets = targets_message["targets"]
    if not any(int(item["track_id"]) == int(command["track_id"]) for item in targets):
        raise SystemExit("command track_id is not present in captured TargetArray")
    config = yaml.safe_load((ROOT / "configs/priority_assignment.yaml").read_text(encoding="utf-8"))
    uavs = {
        str(item["uav_id"]): (float(item["x"]), float(item["y"]))
        for item in config["ros_assignment"]["uavs"]
    }
    if command["vehicle_id"] not in uavs:
        raise SystemExit("command vehicle_id is not configured for the 2D replay")

    args.output.mkdir(parents=True)
    fps, frame_count = 15.0, 120
    video_path = args.output / "mission_command_replay.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (640, 712))
    if not writer.isOpened():
        raise SystemExit("unable to open MP4 writer")
    final_frame = None
    for index in range(frame_count):
        progress = min(1.0, max(0.0, (index - 20) / 70))
        final_frame = _draw_frame(uavs, targets, command, progress, index, frame_count)
        writer.write(final_frame)
    writer.release()
    assert final_frame is not None
    image_path = args.output / "mission_command_replay_final.png"
    cv2.imwrite(str(image_path), final_frame)
    summary = {
        "status": "rendered",
        "source_id": command["source_id"],
        "target_snapshot_sequence": targets_message["sequence"],
        "mission_command_sequence": command["source_sequence"],
        "mission_command": {
            "track_id": int(command["track_id"]),
            "vehicle_id": command["vehicle_id"],
            "command": command["command"],
        },
        "frames": frame_count,
        "fps": fps,
        "duration_s": frame_count / fps,
        "inputs": {"targets": str(args.targets), "commands": str(args.commands)},
        "outputs": {"video": video_path.name, "final_frame": image_path.name},
        "coordinate_note": "synthetic image-space pixels; not physical UAV coordinates",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
