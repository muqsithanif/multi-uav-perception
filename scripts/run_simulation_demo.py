"""Render deterministic 2D simulation evidence for Gate 9."""

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

from multi_uav_core.simulation import run_scenario  # noqa: E402

COLORS = {"uav_1": (255, 80, 80), "uav_2": (80, 255, 80), "uav_3": (80, 80, 255)}


def render(frame: dict, width: int, height: int, scale: int = 7) -> np.ndarray:
    image = np.full((height * scale, width * scale, 3), 250, dtype=np.uint8)
    for target in frame["targets"]:
        x, y = int(target["x"] * scale), int(target["y"] * scale)
        color = (30, 30, 220) if target.get("zone") == "restricted" else (50, 50, 50)
        cv2.circle(image, (x, y), 6, color, -1)
        cv2.putText(image, target["target_id"], (x + 7, y - 7), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    for uav in frame["uavs"]:
        x, y = int(uav["x"] * scale), int(uav["y"] * scale)
        color = COLORS[uav["uav_id"]]
        cv2.rectangle(image, (x - 6, y - 6), (x + 6, y + 6), color, -1)
        cv2.putText(image, f"{uav['uav_id']} {uav['state']}", (x + 8, y + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
    cv2.putText(image, f"step={frame['step']}  units=abstract  unassigned={','.join(frame['unassigned']) or '-'}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--algorithm", choices=["greedy", "hungarian"], default="hungarian")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    priority = yaml.safe_load((ROOT / "configs/priority_assignment.yaml").read_text())
    simulation_config = yaml.safe_load((ROOT / "configs/simulation_scenarios.yaml").read_text())
    simulation, specs = simulation_config["simulation"], simulation_config["scenarios"]
    args.output.mkdir(parents=True)
    results = {name: run_scenario(name, spec, priority, simulation, args.algorithm) for name, spec in specs.items()}
    video_path = args.output / "critical_arrival.mp4"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"mp4v"), 4.0, (simulation["width"] * 7, simulation["height"] * 7))
    for frame in results["critical_arrival"]["frames"]:
        writer.write(render(frame, simulation["width"], simulation["height"]))
    writer.release()
    tiles = [render(result["frames"][-1], simulation["width"], simulation["height"], 3) for result in results.values()]
    cv2.imwrite(str(args.output / "scenario_final_states.png"), cv2.vconcat([cv2.hconcat(tiles[:3]), cv2.hconcat(tiles[3:])]))
    summary = {name: {"event_count": len(result["events"]), "final_unassigned": result["frames"][-1]["unassigned"], "mean_assignment_ms": sum(item["compute_ms"] for item in result["assignments"]) / len(result["assignments"])} for name, result in results.items()}
    (args.output / "summary.json").write_text(json.dumps({"algorithm": args.algorithm, "simulation": simulation, "scenarios": summary}, indent=2) + "\n")


if __name__ == "__main__":
    main()
