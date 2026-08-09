# Day 4 report — ROS 2 Gate 7

## Objective

Build a typed, observable ROS 2 Jazzy path from synthetic tracked targets to
high-level mission status, with a C++ subscriber that proves status reception.

## Files and configuration changed

- `ros2_ws/src/multi_uav_interfaces/` defines five stable message types:
  tracked targets, target arrays, assignments, mission commands, and mission
  status.
- `ros2_ws/src/multi_uav_bringup/` provides deterministic synthetic source,
  assignment relay, mission relay, routing unit tests, and the single
  `gate7_bringup.launch.py` entry point.
- `ros2_ws/src/multi_uav_monitor/` builds the C++ `mission_monitor` subscriber.
- `scripts/run_ros_gate7_smoke.sh` launches the graph, captures typed target and
  status records, checks monitor output, and refuses to overwrite an artifact
  ID.
- `docs/ROS_GRAPH.md` documents fields, image-space units, QoS, commands, and
  the Gate 8 boundary.

## Verification run and actual result

The workspace was built in WSL Ubuntu 24.04 with ROS 2 Jazzy:

```bash
source /opt/ros/jazzy/setup.bash
cd ros2_ws
colcon build --symlink-install --merge-install
cd ..
bash scripts/run_ros_gate7_smoke.sh G01_20260809_005
```

`colcon` finished all three packages: `multi_uav_interfaces`,
`multi_uav_bringup`, and `multi_uav_monitor`. The final smoke run passed from
source revision `c9b60a9b140dd62e04adb28c5c5ff66ef38f0e56` with
`source_tracked_dirty: false`.

The captured source record had `source_id: synthetic_gate7`, image-space frame
`synthetic_image_px`, and two typed targets. The captured mission record was
`state: DISPATCHED` for source sequence 11, track 101, and `vehicle_id: uav_2`.
The C++ monitor logged its first three received status records with sequence,
vehicle, track, state, and local message-age fields. These local ages are
observability data, not a network-latency or physical-UAV benchmark.

The workspace test command completed with `12 tests, 0 errors, 0 failures, 1
skipped`. It includes the two deterministic routing unit tests and the C++
copyright, cpplint, CMake, XML, and formatting checks. `cppcheck` reported a
known slow-version skip but exited successfully; it was not treated as a static
analysis result.

## Artifacts created

- [Final summary](../results/day4/G01_20260809_005/summary.json)
- [Typed target capture](../results/day4/G01_20260809_005/targets.yaml)
- [Typed mission-status capture](../results/day4/G01_20260809_005/mission_status.yaml)
- [Launch and C++ monitor log](../results/day4/G01_20260809_005/launch.log)
- [Failed/recovery provenance](../results/day4/G01_20260809_001/run_review.json)

## Failures and recovery retained

- `G01_20260809_001` stopped before launch because Bash `nounset` was enabled
  before ROS setup scripts. The runner now enables it after setup.
- `G01_20260809_002` captured typed source/status messages, but the monitor was
  absent from an incomplete isolated overlay. A clean `--merge-install` rebuild
  fixed the overlay.
- `G01_20260809_004` passed the graph checks but WSL Git falsely reported CRLF
  changes. The runner now reads the Windows host Git state when available; the
  clean reference is `G01_20260809_005`.
- The first workspace test run had no unittest discovery and lacked the C++
  license header required by ament lint. The routing test is now a discoverable
  unittest package, and the monitor has an Apache-2.0 header; the rerun passed.

## Known limitations

The source data and routing are deterministic Gate 7 transport fixtures. They
do not implement priority scoring, greedy/Hungarian optimization, fleet
constraints, reassignment, a mission state machine, 2D dynamics, or physical
flight control.

## Next smallest milestone

Gate 8: implement configurable priority and a shared interface for Greedy and
Hungarian assignment, then unit-test unequal fleet/target counts, critical and
lost targets, and unavailable UAVs.
