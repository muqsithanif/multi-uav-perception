# Gate 9 simulation and end-to-end evidence

## Result

Gate 9 passes for the stated software and 2D-simulation scope. The current ROS
assignment node adapts `TargetArray` records into the same configurable
priority/Hungarian engine used by the deterministic simulator. It publishes a
typed `Assignment`, the mission node publishes a typed `MissionCommand`, and a
renderer consumes captured ROS messages to make the 2D replay. No part of this
path is a flight-control or physical-UAV result.

The final graph smoke is
[G02_20260809_003](../results/day4/G02_20260809_003/summary.json). It passed
from revision `9dc8c60123293154c2409f56cefe8a74c2f1de63` with
`source_tracked_dirty: false`. Its launch log records the configured Hungarian
solver, two assignments per source sequence, typed mission commands/status,
and C++ monitor receipts.

```text
synthetic TargetArray
  -> shared priority + Hungarian assignment
  -> typed Assignment -> MissionCommand / MissionStatus
  -> captured ROS YAML -> 2D replay image and video
```

## Final artifacts

- [ROS graph summary](../results/day4/G02_20260809_003/summary.json),
  [captured targets](../results/day4/G02_20260809_003/targets.yaml),
  [captured mission command](../results/day4/G02_20260809_003/mission_commands.yaml),
  and [launch/C++ monitor log](../results/day4/G02_20260809_003/launch.log).
- [ROS-replay summary](../results/day6/ROS01_20260809_005/summary.json) and
  [final replay frame](../results/day6/ROS01_20260809_005/mission_command_replay_final.png).
  Its locally retained `mission_command_replay.mp4` is eight seconds at 15 FPS.
- [Final-demo summary](../results/day6/DEMO01_20260809_002/summary.json).
  The locally retained `final_demo.mp4` is 132 seconds (2 minutes 12 seconds),
  700 x 760 at 10 FPS. Large MP4 files are intentionally ignored by Git; the
  JSON summaries and PNG evidence remain versioned.
- [Six-scenario final-state image](../results/day6/SIM01_20260809_001/scenario_final_states.png)
  and [scenario metrics](../results/day6/SIM01_20260809_001/summary.json).

The final demo shows six configured twenty-step scenarios, followed by the
captured ROS mission-command replay. The `DEMO01` summary records the actual
in-process mean assignment time for each scenario. These values are not ROS
latency, network timing, or physical vehicle performance measurements.

## Required scenarios and behavior

`configs/simulation_scenarios.yaml` fixes the seed (`17`), three virtual UAVs,
20 steps, and the required scenarios: fewer targets, equal targets, overloaded
targets, critical arrival, unavailable UAV, and lost/reacquired target. The
overloaded, critical-arrival, and unavailable-UAV scenarios retain one
unassigned target when capacity or availability makes that unavoidable; the
recorded output exposes this rather than hiding it.

Mission transitions are documented in
[MISSION_STATE_MACHINE.md](MISSION_STATE_MACHINE.md) and enumerated by
`tests/test_mission.py`. In the lost/reacquired scenario the simulator enters
`REACQUIRE` and returns to `TRACKING` or `FOLLOWING` after the configured
reacquisition event.

## Reproduce

From the WSL repository root, after preparing the documented environment:

```bash
source /opt/ros/jazzy/setup.bash
cd ros2_ws
colcon build --merge-install --symlink-install
cd ..
bash scripts/run_ros_gate7_smoke.sh G02_<new-id>
YOLO_CONFIG_DIR=/tmp .venv/bin/python scripts/render_ros_mission_replay.py \
  --targets results/day4/G02_<new-id>/targets.yaml \
  --commands results/day4/G02_<new-id>/mission_commands.yaml \
  --output results/day6/ROS01_<new-id>
YOLO_CONFIG_DIR=/tmp .venv/bin/python scripts/render_final_demo.py \
  --ros-replay results/day6/ROS01_<new-id>/mission_command_replay.mp4 \
  --output results/day6/DEMO01_<new-id>
```

Each renderer refuses to overwrite an existing output directory. See
[REPRODUCTION.md](REPRODUCTION.md) for the clean-checkout verification.

## Limitations

- Source targets are deterministic synthetic image-space fixtures, not the
  detector/tracker stream replayed live into ROS.
- The target and mission-command YAML snapshots are independent `--once`
  captures. They share the static source and selected track ID; the launch log
  is the concurrent message-path evidence. The replay does not claim an exact
  timestamp pairing between those two snapshots.
- `ros_assignment.uavs` coordinates are synthetic image-space positions used
  only for the smoke and replay. Simulation coordinates are abstract units.
- The ROS workspace imports the shared pure-Python core from the checked-out
  repository through `MULTI_UAV_PROJECT_ROOT`; this is a reproducible source
  workspace integration, not a relocatable binary distribution.
