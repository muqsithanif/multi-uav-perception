# ROS graph and assignment integration

## Scope

The ROS workspace provides typed local transport and a configured assignment
decision for the software prototype. The deterministic source keeps this gate
independent of detector frame rate and video availability.

```text
perception_source -- TargetArray --> assignment_relay -- Assignment --> mission_relay
                                            |                              |-- MissionCommand
                                            |                              |-- MissionStatus --> C++ mission_monitor
                                            +-- shared priority/Hungarian core
```

`gate7_bringup.launch.py` starts all four nodes. `assignment_relay` converts
the ROS targets to `multi_uav_core.Target` values and calls the same
`assign_targets` implementation used by Gate 8 comparison and Gate 9
simulation. The current launch selects `hungarian`; a configured
`ros_assignment.uavs` list supplies synthetic image-space positions. It no
longer uses the historical static track-ID routing helper.

## Interfaces and units

All topics use reliable, volatile QoS with depth 10. The values express
same-host local transport only; they do not measure a wireless UAV link.

| Topic | Type | Meaning |
| --- | --- | --- |
| `/perception/targets` | `multi_uav_interfaces/msg/TargetArray` | Source timestamp, source ID, sequence, and tracked targets in `synthetic_image_px`. |
| `/assignment/decisions` | `multi_uav_interfaces/msg/Assignment` | Solver-selected vehicle ID and configured priority score for each eligible target. |
| `/mission/commands` | `multi_uav_interfaces/msg/MissionCommand` | High-level `MOVE_TO_TARGET` simulation command; never a flight-control output. |
| `/mission/status` | `multi_uav_interfaces/msg/MissionStatus` | Dispatched status consumed by the C++ health monitor. |

`center_*_px` uses synthetic source-image pixels and `velocity_*_px_s` uses
pixels per second. The static values in `ros_assignment.uavs` are also
image-space positions solely to make the solver and 2D replay deterministic.
They are not latitude/longitude, metres, or physical UAV positions.

## Build and run

In WSL, from the repository root:

```bash
source /opt/ros/jazzy/setup.bash
cd ros2_ws
colcon build --merge-install --symlink-install
source install/setup.bash
cd ..
export MULTI_UAV_PROJECT_ROOT="$(pwd)"
ros2 launch multi_uav_bringup gate7_bringup.launch.py
```

For a repeatable capture after a successful build:

```bash
bash scripts/run_ros_gate7_smoke.sh G02_<new-id>
```

The runner refuses to overwrite an artifact ID, records target/command/status
messages plus the launch log, and requires the C++ monitor receipt. It exports
`MULTI_UAV_PROJECT_ROOT` so the launch passes the checked-out shared core and
configuration to the node process.

## Verified integration run

[G02_20260809_003](../results/day4/G02_20260809_003/summary.json) passed with
a clean tracked tree from revision `9dc8c60123293154c2409f56cefe8a74c2f1de63`.
The [log](../results/day4/G02_20260809_003/launch.log) records
`algorithm=hungarian`, two assigned targets, `MOVE_TO_TARGET` publication, and
C++ `mission_status_count` records. The typed
[command capture](../results/day4/G02_20260809_003/mission_commands.yaml) is
the input for the Gate 9 visualization replay.

The older `G01_20260809_005` evidence remains the historical Gate 7 transport
checkpoint, before the shared solver integration.
