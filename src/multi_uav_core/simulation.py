"""Deterministic 2D assignment/mission simulation using abstract units."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import hypot
from typing import Any

from .assignment import assign_targets
from .mission import MissionState, transition
from .models import Target, Uav


@dataclass
class SimUav:
    uav_id: str
    x: float
    y: float
    state: MissionState = MissionState.SEARCHING
    available: bool = True
    target_id: str | None = None


def run_scenario(name: str, spec: dict[str, Any], config: dict[str, Any], simulation: dict[str, Any], algorithm: str) -> dict[str, Any]:
    """Execute one seeded discrete scenario and retain every state frame."""
    uavs = [SimUav("uav_1", 10, 10), SimUav("uav_2", 90, 10), SimUav("uav_3", 50, 90)]
    targets = {item["target_id"]: _target(item) for item in spec["targets"]}
    frames, events, assignments = [], [], []
    events_by_step = {event["step"]: event for event in spec.get("events", [])}
    for step in range(simulation["steps"]):
        event = events_by_step.get(step)
        if event:
            _apply_event(event, targets, uavs, events)
        core_uavs = [_core_uav(uav, targets, config) for uav in uavs]
        result, elapsed_ms = assign_targets(core_uavs, list(targets.values()), config, algorithm)
        assignment_map = {item.uav_id: item.target_id for item in result.assignments}
        for uav in uavs:
            if not uav.available:
                uav.state = MissionState.UNAVAILABLE
                uav.target_id = None
                continue
            next_target = assignment_map.get(uav.uav_id)
            if next_target:
                if uav.target_id != next_target:
                    uav.state = MissionState.ASSIGNED
                uav.target_id = next_target
                target = targets[next_target]
                _move(uav, target, simulation["uav_speed_units_s"] * simulation["timestep_s"])
                if hypot(uav.x - target.x, uav.y - target.y) < 1.0:
                    uav.state = transition(uav.state, "arrived") if uav.state == MissionState.ASSIGNED else uav.state
            elif uav.target_id is None:
                uav.state = MissionState.SEARCHING
        assignments.append({"step": step, "assignments": [asdict(item) for item in result.assignments], "compute_ms": elapsed_ms})
        frames.append({"step": step, "uavs": [asdict(item) | {"state": item.state.value} for item in uavs], "targets": [asdict(item) for item in targets.values()], "unassigned": list(result.unassigned_target_ids), "skipped": list(result.skipped_target_ids)})
    return {"scenario": name, "algorithm": algorithm, "frames": frames, "events": events, "assignments": assignments}


def _target(values: dict[str, Any]) -> Target:
    return Target(**values)


def _core_uav(uav: SimUav, targets: dict[str, Target], config: dict[str, Any]) -> Uav:
    current_priority = None
    if uav.target_id and uav.target_id in targets:
        from .priority import priority_score
        current_priority = priority_score(targets[uav.target_id], config)
    return Uav(uav.uav_id, uav.x, uav.y, available=uav.available, current_target_id=uav.target_id, current_target_priority=current_priority)


def _move(uav: SimUav, target: Target, distance: float) -> None:
    gap = hypot(target.x - uav.x, target.y - uav.y)
    if gap == 0:
        return
    factor = min(1.0, distance / gap)
    uav.x += (target.x - uav.x) * factor
    uav.y += (target.y - uav.y) * factor


def _apply_event(event: dict[str, Any], targets: dict[str, Target], uavs: list[SimUav], events: list[dict[str, Any]]) -> None:
    events.append(event)
    if event["type"] == "add_target":
        targets[event["target"]["target_id"]] = _target(event["target"])
    elif event["type"] == "unavailable":
        next(uav for uav in uavs if uav.uav_id == event["uav_id"]).available = False
    elif event["type"] == "lost":
        target = targets[event["target_id"]]
        targets[target.target_id] = Target(**(asdict(target) | {"lost": True}))
    elif event["type"] == "reacquire":
        target = targets[event["target_id"]]
        targets[target.target_id] = Target(**(asdict(target) | {"lost": False, "reacquired": True}))
    else:
        raise ValueError(f"unknown event type {event['type']}")
