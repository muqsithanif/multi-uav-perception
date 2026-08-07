# Definition of Done

The project is complete only when every **Required** item below has objective evidence. A checkbox is not evidence by itself; link the command, test, log, metric file, screenshot/video, or artifact in the final project report.

## Required acceptance checklist

### Foundation and reproducibility

- [ ] Supported environment and pinned dependencies are documented.
- [ ] One-command or clearly sequenced setup works on the stated Ubuntu 24.04/ROS 2 Jazzy environment.
- [ ] Pretrained one-image smoke inference succeeds and saves a prediction plus actual metadata.
- [ ] Configs, seeds, dataset manifest/source, license notes, and experiment IDs are recorded.
- [ ] Dataset, weights, secrets, large video, and ROS build outputs are excluded from Git.

### Dataset and detector

- [ ] VisDrone category mapping and ignored-annotation handling are documented.
- [ ] Converter/validator tests invalid boxes, label ranges, image-label pairs, and split integrity.
- [ ] Converted annotations are visually spot-checked on representative samples.
- [ ] A pretrained baseline is evaluated using the locked validation protocol.
- [ ] A real fine-tuned YOLO nano checkpoint, config snapshot, training log, and curves exist.
- [ ] Baseline and fine-tuned results use comparable settings and report precision, recall, mAP50, and mAP50-95.
- [ ] Error analysis includes small/occluded objects and at least several concrete failure examples.

### Deployment and performance

- [ ] ONNX FP32 export loads and runs.
- [ ] OpenVINO FP16 export loads and runs, or a genuine environment/tool limitation is reproduced and documented with logs and a fallback.
- [ ] Prediction/metric agreement against the PyTorch reference is checked with declared tolerance.
- [ ] Benchmarks record hardware, software versions, backend, device, precision, resolution, thresholds, warm-up, sample count, and timing boundary.
- [ ] FPS, mean/median and percentile latency, model size, and available CPU/RAM data are stored in machine-readable form.

### Tracking

- [ ] ByteTrack runs on the selected aerial video and produces stable IDs/trajectory output.
- [ ] BoT-SORT runs on the same detector/input under a documented comparison protocol.
- [ ] Latency/FPS and qualitative failure cases are compared.
- [ ] Identity metrics are reported only if valid ground truth exists; otherwise the limitation is explicit.
- [ ] The chosen default tracker and trade-off rationale are documented.

### Priority, assignment, and mission

- [ ] Priority classes, rules, weights, and thresholds are configurable in YAML.
- [ ] Unit tests cover class, zone, motion-rule, and confidence contributions.
- [ ] Greedy and global linear assignment implement the same interface.
- [ ] Assignment cost components, normalization, constraints, and switching policy are documented.
- [ ] Tests cover targets fewer/equal/more than UAVs, unavailable UAV, critical target, lost target, and reassignment.
- [ ] Greedy/global comparison records computation time, cost/distance proxy, wait/coverage, success, and reassignment metrics where applicable.
- [ ] Mission states and every permitted transition are documented and unit-tested.

### ROS 2 and C++

- [ ] ROS 2 interfaces have typed fields, timestamps, documented units, and chosen QoS.
- [ ] At least perception/source, assignment, and mission nodes exchange valid data.
- [ ] A C++ monitoring node receives useful status data and is built/tested with the workspace.
- [ ] One launch command starts the required graph.
- [ ] A smoke/integration test demonstrates messages progressing through the graph.

### Simulation and end-to-end demo

- [ ] Fleet size is configurable; the main demo uses three virtual UAVs.
- [ ] The six required scenarios in `PROJECT_BLUEPRINT.md` execute with deterministic/repeatable configs.
- [ ] One end-to-end path reaches target priority, assignment, mission command, 2D visualization, and saved metrics.
- [ ] Visualization distinguishes image-space/simulation units from physical units.
- [ ] Final demo video is 2–4 minutes and can be reproduced from documented inputs/config.

### Handoff

- [ ] README quick start, architecture diagram, configs, tests, benchmark report, and troubleshooting notes match the implementation.
- [ ] Raw metrics and charts are present; every headline number traces to a raw record.
- [ ] Limitations and future work are explicit.
- [ ] No professional claim exceeds the measured software/simulation evidence.
- [ ] A fresh-environment or second-user reproduction check is documented.

## Completion rule for constrained environments

The core software, detector, tracking, ROS 2, assignment, state machine, and 2D demo cannot be waived. OpenVINO GPU execution may fall back to a supported CPU device if the actual Intel GPU/runtime is unsupported. The attempted device, error, and fallback must be documented; do not report unsupported hardware performance.

## Not required for completion

- Physical flight, PX4/Gazebo/AirSim, 3D dynamics.
- Jetson/TensorRT/INT8.
- SLAM, path planning, collision avoidance, RL.
- Production deployment or safety certification.
- A small YOLO comparison model when compute is unavailable.
