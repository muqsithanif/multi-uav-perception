from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    target_id: str
    class_label: str
    confidence: float
    x: float
    y: float
    zone: str = "normal"
    speed: float = 0.0
    heading_change_deg: float = 0.0
    waiting_s: float = 0.0
    reacquired: bool = False
    lost: bool = False
    forbidden_uav_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Uav:
    uav_id: str
    x: float
    y: float
    available: bool = True
    load: int = 0
    current_target_id: str | None = None
    current_target_priority: float | None = None


@dataclass(frozen=True)
class Assignment:
    target_id: str
    uav_id: str
    priority: float
    cost: float


@dataclass(frozen=True)
class AssignmentResult:
    algorithm: str
    assignments: tuple[Assignment, ...]
    unassigned_target_ids: tuple[str, ...]
    skipped_target_ids: tuple[str, ...]
    total_cost: float
