# Final project report

## Outcome

This repository is complete for its declared scope: a ROS 2-based software and
2D simulation prototype for aerial-object perception artifacts, tracking,
priority scoring, Greedy/Hungarian target assignment, high-level mission
states, and a three-virtual-UAV visualization. It is not a physical UAV,
flight-safety, autonomy, or production-deployment result.

## Final evidence

| Area | Evidence |
| --- | --- |
| Detector and deployment | [Day 3 report](DAY_3_REPORT.md) and [machine-readable export summary](../experiments/B01_20260809_005/summary.json). |
| Tracking | [tracking report](TRACKING_REPORT.md) and [comparison summary](../experiments/T01_20260809_002/summary.json). |
| Priority and assignment | [assignment report](ASSIGNMENT_REPORT.md) and [100-repetition comparison](../results/day5/A01_20260809_002/summary.json). |
| State machine | [state table and tests](MISSION_STATE_MACHINE.md). |
| ROS graph | [clean solver-integrated smoke](../results/day4/G02_20260809_003/summary.json). |
| 2D image/video | [simulation report](SIMULATION_REPORT.md), [ROS replay image](../results/day6/ROS01_20260809_005/mission_command_replay_final.png), and local `final_demo.mp4` (132 seconds). |
| Reproduction | [clean-checkout run](../results/day7/R01_20260809_005/summary.json) and [instructions](REPRODUCTION.md). |

The 132-second final demo is rendered from six deterministic scenarios and the
recorded ROS mission-command replay. It reports visual behavior and stored
in-process assignment timing only; it does not establish real-time ROS,
network, or physical-flight performance.

## Limitations

- Detector, deployment, and tracking measurements retain the protocols and
  limitations in their linked reports; they should not be compared outside
  those declared subsets and hardware settings.
- The ROS source is synthetic and local. It demonstrates typed software
  transport, not a detector-to-radio-to-aircraft system.
- The solver and simulator use configured synthetic image-space or abstract 2D
  coordinates. No calibration, collision avoidance, path planning, or vehicle
  control is implemented.
- MP4 files are intentionally excluded from Git because they are generated
  media. Their versioned summaries, PNG frame, inputs, commands, and output
  IDs provide reproducible provenance.
