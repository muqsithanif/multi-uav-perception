# Multi-UAV Aerial Object Detection, Tracking, and Target Assignment

A portfolio-grade ROS 2 software and 2D simulation prototype that detects and tracks people/vehicles in aerial imagery, prioritizes targets, assigns them to three virtual UAVs, and produces high-level mission states.

> Status: Gate 1 foundation and the Day 2 VisDrone data-validation checkpoint
> were verified on 2026-08-07. Gate 2A and later project gates have not been
> completed.

## Verified Day 1 foundation

The CPU smoke test ran in WSL 2 on Ubuntu 24.04.4 LTS with Python 3.12.3,
Ultralytics 8.4.115, and PyTorch 2.13.0+cpu. It loaded the pretrained
`yolo26n.pt` checkpoint and saved a prediction plus machine-readable records.

The one cold prediction call took 967.907 ms wall time. Ultralytics reported
560.715 ms for its inference stage. This is a one-sample smoke measurement with
no warm-up, not a benchmark or real-time-performance claim. At the configured
640-pixel input size and 0.25 confidence threshold, the run produced zero
detections; that result is retained rather than tuned away.

- [Day 1 verification report](docs/DAY_1_REPORT.md)
- [Immutable config snapshot](experiments/S00_20260807_001/config.yaml)
- [Machine-readable summary](experiments/S00_20260807_001/summary.json)
- [Environment record](experiments/S00_20260807_001/environment.json)
- [Saved prediction](results/smoke/S00_20260807_001/prediction.jpg)
- [Current asset and tool licenses](docs/LICENSES.md)

The exact successful invocation is stored in
`experiments/S00_20260807_001/command.txt`. Experiment directories are
immutable; use a new experiment ID and matching output directories for a
separate run.

## Verified VisDrone data path

Official VisDrone2019-DET train and validation splits were downloaded,
checksummed, converted to the documented five-class YOLO mapping, and validated.
The output contains 6,471 train and 548 validation image/label pairs. Source
sanitization is explicit: three zero-height train boxes were excluded (only one
belonged to a selected training class), and 34 empty trailing fields were
normalized. The converted output contains zero invalid boxes.

Six deterministic validation overlays covering all five project classes passed
visual inspection. This proves the data conversion path, not detector accuracy.

- [Day 2 data report](docs/DAY_2_REPORT.md)
- [VisDrone source, mapping, and conversion policy](docs/VISDRONE_DATA.md)
- [Validation summary](experiments/D01_visdrone_validation/summary.json)
- [Visual audit summary](results/day2/visual_audit/summary.json)
- [Class-distribution analysis](results/day2/dataset_analysis/class_distribution.json)

## Project goals

The project is optimized for:

1. **Completion** — a demonstrable end-to-end path before optional features.
2. **Efficiency** — a small YOLO model, focused experiments, and simple testable modules.
3. **Open resources** — VisDrone and broadly available open-source tooling.

## End-to-end flow

```text
VisDrone / aerial video
  -> YOLO baseline and fine-tuning
  -> evaluation and ONNX/OpenVINO optimization
  -> ByteTrack or BoT-SORT
  -> configurable target priority
  -> ROS 2 messages
  -> Greedy or global linear assignment
  -> mission state machine
  -> three-UAV 2D simulation and benchmark
```

## Required deliverables

- Fine-tuned YOLO nano detector and baseline comparison.
- Precision, recall, mAP, latency, FPS, model-size, and resource measurements.
- ByteTrack default plus BoT-SORT comparison on identical input.
- ONNX FP32 and verified OpenVINO FP16 export/attempt.
- ROS 2 Jazzy perception, assignment, and mission communication.
- Configurable target priority and 2D three-UAV simulation.
- Greedy versus global linear assignment comparison.
- Mission state machine, failure/reassignment scenarios, and a C++ monitoring node.
- Tests, benchmark records, diagrams, limitations, and a 2–4 minute demo.

## Intended repository layout

```text
multi-uav-perception/
├── AGENTS.md
├── README.md
├── configs/
├── data/                 # metadata/sample only; no VisDrone archive in Git
├── docs/
├── experiments/
├── models/               # large generated weights ignored
├── notebooks/
├── results/              # compact reports; large videos ignored or released separately
├── ros2_ws/src/
├── scripts/
├── simulation/
├── src/
│   ├── vision/
│   ├── tracking/
│   ├── priority/
│   ├── assignment/
│   ├── mission/
│   └── reporting/
└── tests/
```

Create implementation files only when their milestone begins; avoid a repository full of empty placeholders.

## Recommended environment

- Windows 11 with WSL2
- Ubuntu 24.04
- Python virtual environment
- ROS 2 Jazzy
- Training on available local hardware or Google Colab; do not assume free GPU availability

Exact package/model versions must be pinned after the first working smoke test. Use the currently supported Ultralytics nano checkpoint available in that pinned version rather than hard-coding an unverified model generation.

## First success path

1. Copy this package into a new `multi-uav-perception` repository.
2. Review [project context](docs/PROJECT_CONTEXT.md), [blueprint](docs/PROJECT_BLUEPRINT.md), and [Definition of Done](docs/DEFINITION_OF_DONE.md).
3. Follow [Week 1](docs/WEEK_1_PLAN.md) from Gate 0; do not jump to ROS 2 before image inference works.
4. Run one pretrained inference on one aerial image.
5. Save the prediction and a machine-readable record containing the actual environment and timing.
6. Commit the verified foundation, then proceed to data validation.

No example metric value in documentation is evidence. Only generated artifacts from actual runs may be reported as results.

## Configuration policy

Keep these choices in YAML:

- dataset paths and class mapping;
- model, resolution, thresholds, and seed;
- tracker and tracker parameters;
- priority rules and score thresholds;
- fleet size, UAV properties, assignment algorithm, and cost weights;
- simulation scenario and visualization settings.

Each experiment copies its effective config to `experiments/<id>/config.yaml` and records outputs in CSV/JSON plus notes.

## Documentation map

- [PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) — audience, constraints, and goals.
- [PROJECT_BLUEPRINT.md](docs/PROJECT_BLUEPRINT.md) — architecture and design decisions.
- [DEFINITION_OF_DONE.md](docs/DEFINITION_OF_DONE.md) — binary acceptance gates.
- [REQUIREMENTS_MAPPING.md](docs/REQUIREMENTS_MAPPING.md) — capability-to-evidence traceability.
- [EXPERIMENT_PLAN.md](docs/EXPERIMENT_PLAN.md) — controlled evaluation plan.
- [WEEK_1_PLAN.md](docs/WEEK_1_PLAN.md) — milestone order and fallback rules.

## Scope boundary

This repository is not a flight controller and does not control physical aircraft. Gazebo/PX4, Jetson/TensorRT, SLAM, RL, INT8, and full 3D dynamics are future work. See the blueprint for the complete boundary.

## Safe portfolio description

> Developed a ROS 2-based multi-UAV perception and mission-planning prototype using a fine-tuned YOLO detector, multi-object tracking, configurable target prioritization, and global target assignment. Benchmarked supported PyTorch, ONNX, and OpenVINO inference paths for accuracy and real-time performance.

Use that wording only after the listed functions and benchmarks actually exist. Never call the result a production-ready autonomous drone swarm.
