# Gate 7 ROS graph

## Scope

This workspace establishes the typed, observable data transport required for
Gate 7. It deliberately uses deterministic synthetic targets so the ROS gate
is independent of detector frame rate and video availability. The assignment
relay is a transport stub, not the configurable Greedy/Hungarian implementation
scheduled for Gate 8.

```text
perception_source -- TargetArray --> assignment_relay -- Assignment --> mission_relay
                                                                     |-- MissionCommand
                                                                     |-- MissionStatus --> C++ mission_monitor
```

`gate7_bringup.launch.py` starts all four nodes in one command.

## Interfaces and units

All topics use reliable, volatile QoS with depth 10. The values express
same-host local transport semantics; they do not measure a wireless UAV link.

| Topic | Type | Meaning |
| --- | --- | --- |
| `/perception/targets` | `multi_uav_interfaces/msg/TargetArray` | Source timestamp, source ID, monotonically increasing source sequence, and tracked targets. |
| `/assignment/decisions` | `multi_uav_interfaces/msg/Assignment` | A deterministic Gate 7 routing record for each target. |
| `/mission/commands` | `multi_uav_interfaces/msg/MissionCommand` | High-level `MOVE_TO_TARGET` simulation command; never a flight-control output. |
| `/mission/status` | `multi_uav_interfaces/msg/MissionStatus` | Dispatched state consumed by the C++ health monitor. |

`TargetArray.header.frame_id` is `synthetic_image_px`; `center_*_px` uses
source-image pixels, `velocity_*_px_s` uses pixels per second, and
`priority_hint` is a synthetic value in `[0, 1]`. The later priority gate owns
the actual configurable score and its interpretation.

## Build and run

In WSL, from the repository root:

```bash
source /opt/ros/jazzy/setup.bash
cd ros2_ws
colcon build --symlink-install --merge-install
source install/setup.bash
ros2 launch multi_uav_bringup gate7_bringup.launch.py
```

For the repeatable smoke run after a successful build:

```bash
bash scripts/run_ros_gate7_smoke.sh G01_20260809_001
```

The script refuses to overwrite an artifact ID, saves received typed messages
and the launch log under `results/day4/<run-id>/`, and requires the C++ monitor
to log a received mission status.

## Gate boundary

Gate 7 passes only after the workspace builds and the smoke artifact proves the
three-node message path plus C++ monitor. Gate 8 remains pending: this graph
does not claim optimization, fleet constraints, reassignment, or a tested
mission-state machine.
