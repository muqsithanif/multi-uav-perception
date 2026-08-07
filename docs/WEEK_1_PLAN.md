# Week 1 Execution Plan

This is a gate-based sequence, not a promise that every task fits one calendar day. If a gate fails, debug it before starting the next layer. Protect completion by dropping optional comparisons first.

## Day 1 — Foundation and smoke test

### Objective

Create the repository foundation and prove one-image YOLO inference.

### Work

- Review and commit this migration package.
- Set up WSL2 Ubuntu 24.04, Git, Python virtual environment, OpenCV, FFmpeg, and the pinned Ultralytics stack.
- Create only the folders needed for the first milestone.
- Add ignore rules for datasets, models, environments, ROS build output, secrets, and large media.
- Run a pretrained nano detector on one legally usable aerial image.
- Save prediction, environment/version metadata, detector settings, and actual timing.

### Gate 1

- Repository and docs are committed.
- Environment imports succeed.
- One-image prediction and machine-readable smoke record exist.

### Fallback

Use CPU and a single image. Do not install ROS 2 or download the full dataset until this works.

## Day 2 — VisDrone and fine-tuning

### Objective

Create a trustworthy data path and at least one real fine-tuned checkpoint.

### Work

- Obtain the selected VisDrone release from an official/authorized source and record license/source/checksum metadata.
- Implement conversion and validation; inspect rendered labels.
- Run E00 baseline.
- Run a short smoke training, then E01 main nano training with persistent checkpoints/logs.
- Keep E04 small-model training optional.

### Gate 2

- Dataset validation report and visual audit pass.
- E00 result is recorded.
- Fine-tuned checkpoint, effective config, log, and curves exist.

### Fallback

Use a documented subset and fewer epochs to prove the pipeline. Label all resulting claims as subset/smoke results and schedule a longer run later.

## Day 3 — Evaluation and deployment

### Objective

Select a defensible accuracy-speed configuration.

### Work

- Evaluate baseline versus fine-tuned under identical settings.
- Perform per-class/error analysis.
- Run 416/512/640 inference study.
- Export and validate ONNX FP32.
- Export and validate OpenVINO FP16 on a supported device.
- Run controlled backend benchmarks and create the first accuracy-speed table.

### Gate 3

- Raw detection/evaluation records and comparison chart exist.
- ONNX runs.
- OpenVINO runs or a reproducible limitation plus supported fallback is documented.
- Selected demo model/resolution/backend has a written rationale.

### Fallback

Keep PyTorch CPU as the integration baseline. Never block tracking on an unsupported accelerator.

## Day 4 — Tracking and target features

### Objective

Turn detections into stable target records with rule-based priority.

### Work

- Integrate ByteTrack, trajectory history, velocity/heading estimates, and video overlay.
- Run BoT-SORT on the same clip and settings.
- Implement zone manager, simple motion rules, and YAML priority policy.
- Record valid comparison metrics and failure examples.

### Gate 4

- Same video can run through both trackers.
- Default tracker is selected from evidence.
- Output shows IDs, trajectories, priority, and explicit image-space units.
- Priority unit tests pass.

### Fallback

Keep ByteTrack as the operational path. A documented BoT-SORT comparison may be narrower, but it must actually run.

## Day 5 — ROS 2 Jazzy and C++ monitor

### Objective

Create a typed, observable ROS 2 data path.

### Work

- Install/verify ROS 2 Jazzy on Ubuntu 24.04 and run a standard talker/listener smoke test.
- Create messages and perception/source, assignment, and mission nodes.
- Add timestamps, sequence/source identifiers, units, and appropriate QoS.
- Implement a C++ status/latency monitoring subscriber.
- Add build/test commands and launch file.

### Gate 5

- Workspace builds cleanly.
- At least three functional nodes exchange valid messages.
- C++ monitor receives useful status.
- One launch command starts the graph; smoke test passes.

### Fallback

Use a prerecorded/synthetic source node so ROS integration is independent of real-time detector availability.

## Day 6 — Assignment, mission, and 3-UAV integration

### Objective

Complete the end-to-end multi-UAV software simulation.

### Work

- Implement shared assignment interface, Greedy, cost matrix, and global linear assignment.
- Implement configurable three-UAV 2D dynamics and mission state machine.
- Run fewer/equal/more target scenarios, critical arrival, UAV unavailable, and lost/reacquired target.
- Compare algorithms and record assignment/ROS/end-to-end metrics.
- Connect video or normalized synthetic targets through ROS 2 to commands and visualization.

### Gate 6

- Assignment and FSM tests pass.
- Required scenarios are repeatable from configs.
- One launch/config produces end-to-end commands, visualization, and raw metrics.

### Fallback

Use seeded synthetic target records for deterministic scenario coverage; keep the video path as a separate verified adapter if live integration is unstable.

## Day 7 — Hardening and portfolio handoff

### Objective

Make results reproducible, reviewable, and professionally honest.

### Work

- Run tests and the final benchmark suite from a clean state.
- Fix blocking defects; freeze optional feature work.
- Complete architecture, benchmark, setup, troubleshooting, limitations, and license notes.
- Produce charts, screenshots, and a reproducible 2–4 minute demo.
- Audit every README/CV statement against evidence.
- Perform a clean-environment or second-user reproduction check.

### Gate 7

- Every required Definition of Done item links to evidence.
- Final demo and README commands work.
- Raw metrics support charts and claims.
- Future work is clearly separated from completed work.

## Daily checkpoint format

```text
Objective:
Verified result:
Commands/tests run:
Artifacts:
Failure/limitation:
Decision:
Next gate:
```

## Scope-cut order if time is constrained

1. Drop E04 small-model training.
2. Reduce optional threshold sweeps and large synthetic scale studies.
3. Reduce cosmetic dashboard work.
4. Shorten nonessential tracker/backend variants while preserving required comparisons.
5. Never drop the core fine-tuned model, honest evaluation, ByteTrack + BoT-SORT run, ROS 2 graph, both assignment algorithms, three-UAV scenario, FSM, C++ monitor, tests, or documentation.
