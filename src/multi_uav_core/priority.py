from typing import Any

from .models import Target


def priority_score(target: Target, config: dict[str, Any]) -> float:
    """Return a bounded, scenario-specific rule score rather than a risk claim."""
    rules = config["priority"]
    score = rules["class_scores"].get(target.class_label, rules["default_class_score"])
    score += rules["zone_scores"].get(target.zone, 0.0)
    motion = rules["motion"]
    if target.speed >= motion["high_speed_threshold"]:
        score += motion["high_speed_score"]
    if target.heading_change_deg >= motion["heading_change_threshold_deg"]:
        score += motion["heading_change_score"]
    if target.reacquired:
        score += motion["reacquired_score"]
    score += target.confidence * rules["confidence_weight"]
    return max(0.0, min(1.0, score))


def priority_level(score: float, config: dict[str, Any]) -> str:
    thresholds = config["priority"]["thresholds"]
    if score >= thresholds["critical"]:
        return "critical"
    if score >= thresholds["high"]:
        return "high"
    return "normal"
