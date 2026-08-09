# Mission state machine

The state machine models only high-level software/simulation intent. It does
not publish flight-control setpoints, plan trajectories, or make a physical
UAV safety claim. The implementation is `multi_uav_core.mission.transition`.

| Current state | Event | Next state | Use in the deterministic simulator |
| --- | --- | --- | --- |
| `IDLE` | `start` | `SEARCHING` | Available start transition. |
| `SEARCHING`, `ASSIGNED`, `TRACKING`, `FOLLOWING`, `REACQUIRE` | `assigned` | `ASSIGNED` | A selected or reassigned target. |
| `ASSIGNED` | `arrived` | `TRACKING` | The simulated UAV reaches its assigned target. |
| `TRACKING` | `follow` | `FOLLOWING` | Continue observing a tracked target. |
| `FOLLOWING` | `lost` | `REACQUIRE` | The configured target becomes lost. |
| `REACQUIRE` | `found` | `TRACKING` | The configured target is reacquired. |
| `REACQUIRE` | `timeout` | `SEARCHING` | Available timeout transition. |
| `ASSIGNED` | `hold` | `HOLD` | Available hold transition. |
| `HOLD` | `resume` | `SEARCHING` | Available resume transition. |
| Any state | `return` | `RETURNING` | Available high-level return intent. |
| `RETURNING` | `complete` | `IDLE` | Return is complete. |
| Any state | `unavailable` | `UNAVAILABLE` | The virtual UAV becomes unavailable. |

`tests/test_mission.py` enumerates every permitted transition and rejects an
invalid one. `tests/test_simulation.py` additionally checks the configured
lost/reacquired scenario reaches `REACQUIRE` and returns to `TRACKING` or
`FOLLOWING`.
