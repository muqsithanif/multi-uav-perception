# Project Blueprint

## 1. Locked outcome

Deliver a reproducible software prototype in which aerial detections become tracked targets, ROS 2 messages, fleet assignments, mission states, and 2D visualization for a configurable fleet whose main demo uses three UAVs.

## 2. Scope

### Required

- VisDrone validation/conversion and a pretrained baseline.
- YOLO nano fine-tuning and fair baseline comparison.
- Detection evaluation and speed/resource benchmarking.
- Aerial video inference with ByteTrack and BoT-SORT comparison.
- ONNX FP32 export and OpenVINO FP16 export/verification.
- ROS 2 Jazzy packages, documented topics/messages, and launch file.
- Configurable rule-based priority scoring.
- Greedy and global linear assignment using a shared interface.
- Configurable 2D fleet; main scenarios use three virtual UAVs.
- Mission state machine, reacquisition, reassignment, and failure scenario.
- A C++ ROS 2 monitoring node.
- Tests, results, README, diagram, limitations, and demo.

### Future work

- Physical UAVs or flight controller integration.
- PX4 SITL, Gazebo, AirSim, or full 3D dynamics.
- Jetson/TensorRT, INT8, or hardware-specific production deployment.
- SLAM, collision avoidance, path planning, reinforcement learning.
- Learned behavior recognition or cross-camera identity matching.
- Safety certification, redundancy, security hardening, and field testing.

## 3. Architecture

```text
Data/source layer
  VisDrone images | aerial video | synthetic target scenario
             |
Perception layer
  YOLO detector -> normalized detections -> ByteTrack/BoT-SORT
             |
Decision layer
  track features -> zone/behavior rules -> priority score
             |
ROS 2 integration layer
  source/perception -> assignment -> mission -> monitor
             |
Fleet layer
  Greedy/global assignment -> mission FSM -> 2D UAV dynamics
             |
Evidence layer
  video overlays | CSV/JSON | charts | logs | tests
```

The normalized target record should include at minimum: source/frame timestamp, track ID, class, confidence, bounding box/center, velocity estimate, zone/behavior flags, priority score/level, and assignment status. Units must be explicit: image-space measurements are pixels/pixels-per-second and must not be presented as physical distance or speed.

## 4. Dataset design

Use an official, legally accessible VisDrone detection release as the primary dataset. Preserve its official train/validation boundary unless a documented reason requires another split. Do not use the test split for iterative selection when labels are unavailable.

Initial classes of interest are pedestrian, car, van, truck, and bus. Before training:

1. Document original category IDs, ignored regions, truncation/occlusion fields, and chosen class mapping.
2. Validate missing/corrupt images, invalid boxes, zero-area boxes, label ranges, and image-label pairing.
3. Render random and edge-case samples after conversion.
4. Store only download instructions, checksums/manifest, conversion code, and small licensed samples in Git.

Use a small subset only for pipeline smoke training. Final claims must identify whether results use the full chosen training split or a subset.

## 5. Detection and optimization

Use the nano checkpoint supported by the pinned Ultralytics version as the completion path. A small model is optional only if compute/time remains after all required gates.

Evaluate baseline and fine-tuned checkpoints under the same class mapping, validation data, image size, confidence/IoU policy, and evaluation code. Core metrics are precision, recall, mAP50, and mAP50-95, supplemented by per-class results and qualitative error analysis for small/occluded objects.

Deployment path:

```text
fine-tuned PyTorch checkpoint -> ONNX FP32 -> OpenVINO FP16
```

For each exported backend, confirm it loads, runs on identical inputs, and remains within a declared prediction/metric tolerance. Benchmark supported devices separately; never combine CPU and GPU numbers in one comparison without labeling them.

## 6. Tracking

ByteTrack is the default because it offers a simple real-time completion path. BoT-SORT is the controlled comparison. Both use the same detector checkpoint, input sequence, thresholds where semantically comparable, and timing protocol.

Always report FPS/latency and qualitative failure cases. Report ID switches, track duration, IDF1, HOTA, or MOTA only when suitable identity ground truth and evaluation tooling exist. Tracker selection balances stability, speed, integration complexity, and downstream assignment churn—not a single unverified metric.

## 7. Priority logic

Priority is explicitly rule-based, not learned behavior recognition:

```text
priority = class component
         + zone component
         + simple motion/behavior component
         + small confidence component
```

Example configurable behaviors include stationary duration, high image-space speed, sudden heading change, restricted-zone entry, and reacquisition. The repository may provide initial example weights and level thresholds, but they are scenario policy—not empirically universal risk scores.

## 8. Target assignment

Provide one interface such as `assign(uavs, targets, config) -> assignments` with two implementations:

- **Greedy:** sort eligible targets by priority/waiting policy and select the best available UAV sequentially.
- **Global linear assignment:** construct a fleet-target cost matrix and solve it with SciPy's linear sum assignment routine.

The configurable cost may combine normalized distance, UAV load/state, waiting time, target priority, confidence, and switching penalty. Constraints include UAV availability, capacity (default one target), minimum confidence/priority, and forbidden pairs.

Compare total cost/distance proxy, computation time, priority coverage, wait time, success rate, and reassignment count. The hypothesis that Greedy is faster and global assignment is more efficient must be tested rather than stated as fact.

## 9. Fleet simulation

The main demo uses three UAVs, while fleet size remains configurable. Each virtual UAV has ID, 2D position, velocity, speed limit, battery/status placeholder, capacity, state, and assigned target. Values are simulation units, not aircraft specifications.

Required scenarios:

1. Three UAVs, two targets: one remains searching.
2. Three UAVs, three targets: compare algorithms.
3. Three UAVs, more targets: queue lower-priority targets.
4. A critical target appears while all UAVs are busy: apply documented switching policy.
5. One UAV becomes unavailable: return its target for reassignment.
6. A target is lost and optionally reacquired.

Target input can originate from image-space tracking or a synthetic scenario, but both must adapt to the same target interface. No transformation from pixels to world coordinates may be implied without calibration/localization.

## 10. Mission state machine

Canonical states:

```text
IDLE -> SEARCHING -> ASSIGNED -> TRACKING -> FOLLOWING
                         |            |
                         +-> HOLD     +-> REACQUIRE -> SEARCHING
Any active state -> RETURNING / LOW_BATTERY / UNAVAILABLE
```

Transitions must be explicit, testable, and driven by events/timeouts. High-level commands such as `MOVE_LEFT`, `MOVE_RIGHT`, `HOLD`, `SEARCH`, or `RETURN` are simulation/mission directives, not flight-control outputs.

## 11. ROS 2 design

Minimum runtime graph:

- source/perception node publishes tracked target data;
- assignment node subscribes to targets/fleet state and publishes assignments;
- mission node publishes state/command updates;
- C++ monitor subscribes to status and reports message health/latency.

Use timestamps, frame IDs where applicable, QoS chosen for the data semantics, and documented message fields. Prefer custom messages for stable structured data; JSON strings are acceptable only for the earliest smoke test and must not become the final interface. Provide one launch entry point and a non-ROS unit-test path for algorithms.

## 12. Visualization and evidence

OpenCV overlays: box, class, confidence, track ID, priority, assigned UAV, mission state, FPS/latency, and trajectory. The 2D view shows UAV/target positions, assignment lines, zones, queued targets, algorithm, and total cost.

Matplotlib reports: learning curves, accuracy-speed trade-off, latency breakdown, tracker comparison where valid, assignment comparison, and resource use.

## 13. Repository/data policy

Keep source, configs, tests, compact CSV/JSON, diagrams, and documentation in Git. Ignore datasets, secrets, virtual environments, checkpoints, large media, TensorBoard bulk output, and ROS 2 `build/install/log`. Publish large demo artifacts through a release or external storage with checksums if needed.

## 14. Claim boundary

Safe claim: “software and 2D simulation prototype for ROS 2-based multi-UAV perception and high-level mission planning.”

Unsafe claims include production-ready swarm, autonomous flight deployment, real-world metric speed/distance without calibration, safety-critical behavior, or physical UAV validation.
