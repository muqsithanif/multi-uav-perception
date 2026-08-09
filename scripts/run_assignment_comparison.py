"""Run deterministic Greedy/Hungarian comparison scenarios for Gate 8."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from multi_uav_core import Target, Uav, assign_targets  # noqa: E402


def scenarios() -> dict[str, tuple[list[Uav], list[Target]]]:
    fleet = [Uav("uav_1", 0, 0), Uav("uav_2", 20, 0), Uav("uav_3", 10, 20)]
    return {
        "underloaded": (fleet, [Target("t1", "person", 0.9, 2, 0), Target("t2", "car", 0.8, 19, 0)]),
        "balanced": (fleet, [Target("t1", "person", 0.9, 2, 0), Target("t2", "car", 0.8, 19, 0), Target("t3", "truck", 0.9, 10, 18)]),
        "overloaded_critical": (fleet, [Target("t1", "car", 0.8, 2, 0), Target("t2", "van", 0.8, 19, 0), Target("t3", "truck", 0.9, 10, 18), Target("critical", "person", 0.99, 30, 30, zone="restricted", speed=10, waiting_s=20)]),
        "unavailable_lost": ([Uav("uav_1", 0, 0, available=False), Uav("uav_2", 20, 0), Uav("uav_3", 10, 20)], [Target("lost", "person", 0.9, 0, 0, lost=True), Target("live", "car", 0.9, 19, 0)]),
        "critical_reassignment": ([Uav("busy", 0, 0, current_target_id="low", current_target_priority=0.28)], [Target("critical", "person", 0.99, 20, 0, zone="restricted", speed=10)]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs/priority_assignment.yaml")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=50)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    config = yaml.safe_load(args.config.read_text())
    rows = []
    for name, (uavs, targets) in scenarios().items():
        for algorithm in ("greedy", "hungarian"):
            timings, final = [], None
            for _ in range(args.repetitions):
                final, elapsed = assign_targets(uavs, targets, config, algorithm)
                timings.append(elapsed)
            assert final is not None
            rows.append({"scenario": name, "algorithm": algorithm, "repetitions": args.repetitions, "mean_compute_ms": sum(timings) / len(timings), "total_cost": final.total_cost, "assigned_count": len(final.assignments), "unassigned_target_ids": list(final.unassigned_target_ids), "skipped_target_ids": list(final.skipped_target_ids), "assignments": [item.__dict__ for item in final.assignments]})
    args.output.parent.mkdir(parents=True, exist_ok=False)
    args.output.write_text(json.dumps({"config": str(args.config.relative_to(ROOT)), "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
