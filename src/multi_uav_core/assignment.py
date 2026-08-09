from math import hypot
from time import perf_counter
from typing import Any

from scipy.optimize import linear_sum_assignment

from .models import Assignment, AssignmentResult, Target, Uav
from .priority import priority_score

_BLOCKED_COST = 1_000_000.0


def assign_targets(
    uavs: list[Uav], targets: list[Target], config: dict[str, Any], algorithm: str | None = None
) -> tuple[AssignmentResult, float]:
    """Assign at most one eligible target per available UAV and return elapsed ms."""
    selected = algorithm or config["assignment"]["default_algorithm"]
    if selected not in {"greedy", "hungarian"}:
        raise ValueError("algorithm must be 'greedy' or 'hungarian'")
    scores = {target.target_id: priority_score(target, config) for target in targets}
    eligible = [target for target in targets if _eligible(target, scores[target.target_id], config)]
    skipped = tuple(target.target_id for target in targets if target not in eligible)
    started = perf_counter()
    if selected == "greedy":
        result = _greedy(uavs, eligible, scores, skipped, config)
    else:
        result = _hungarian(uavs, eligible, scores, skipped, config)
    return result, (perf_counter() - started) * 1000.0


def _eligible(target: Target, score: float, config: dict[str, Any]) -> bool:
    rules = config["assignment"]
    return not target.lost and target.confidence >= rules["minimum_confidence"] and score >= rules["minimum_priority"]


def _cost(uav: Uav, target: Target, score: float, config: dict[str, Any]) -> float:
    if not uav.available or uav.uav_id in target.forbidden_uav_ids:
        return _BLOCKED_COST
    rules = config["assignment"]
    weights = rules["cost_weights"]
    distance = hypot(uav.x - target.x, uav.y - target.y) / rules["distance_normalization"]
    switching = float(uav.current_target_id not in (None, target.target_id))
    return (
        weights["distance"] * distance
        + weights["load"] * uav.load
        + weights["priority"] * (1.0 - score)
        + weights["confidence"] * (1.0 - target.confidence)
        - weights["waiting"] * min(1.0, target.waiting_s / rules["waiting_normalization_s"])
        + weights["switching"] * switching
    )


def _make_result(
    algorithm: str,
    assignments: list[Assignment],
    eligible: list[Target],
    skipped: tuple[str, ...],
) -> AssignmentResult:
    assigned = {assignment.target_id for assignment in assignments}
    return AssignmentResult(
        algorithm=algorithm,
        assignments=tuple(assignments),
        unassigned_target_ids=tuple(target.target_id for target in eligible if target.target_id not in assigned),
        skipped_target_ids=skipped,
        total_cost=sum(assignment.cost for assignment in assignments),
    )


def _greedy(
    uavs: list[Uav], eligible: list[Target], scores: dict[str, float], skipped: tuple[str, ...], config: dict[str, Any]
) -> AssignmentResult:
    available = [uav for uav in uavs if uav.available]
    assignments: list[Assignment] = []
    for target in sorted(eligible, key=lambda item: (-scores[item.target_id], -item.waiting_s, item.target_id)):
        choices = [( _cost(uav, target, scores[target.target_id], config), uav) for uav in available]
        choices = [choice for choice in choices if choice[0] < _BLOCKED_COST]
        if not choices:
            continue
        cost, uav = min(choices, key=lambda item: (item[0], item[1].uav_id))
        assignments.append(Assignment(target.target_id, uav.uav_id, scores[target.target_id], cost))
        available.remove(uav)
    return _make_result("greedy", assignments, eligible, skipped)


def _hungarian(
    uavs: list[Uav], eligible: list[Target], scores: dict[str, float], skipped: tuple[str, ...], config: dict[str, Any]
) -> AssignmentResult:
    available = [uav for uav in uavs if uav.available]
    if not available or not eligible:
        return _make_result("hungarian", [], eligible, skipped)
    matrix = [[_cost(uav, target, scores[target.target_id], config) for uav in available] for target in eligible]
    rows, columns = linear_sum_assignment(matrix)
    assignments: list[Assignment] = []
    for row, column in zip(rows, columns):
        cost = matrix[row][column]
        if cost < _BLOCKED_COST:
            target, uav = eligible[row], available[column]
            assignments.append(Assignment(target.target_id, uav.uav_id, scores[target.target_id], cost))
    return _make_result("hungarian", assignments, eligible, skipped)
