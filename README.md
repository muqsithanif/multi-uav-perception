# Multi-UAV Aerial Object Detection, Tracking, and Target Assignment

A portfolio-grade ROS 2 software and 2D simulation prototype that detects and tracks people/vehicles in aerial imagery, prioritizes targets, assigns them to three virtual UAVs, and produces high-level mission states.

> Status: Gate 1, Gate 2A, Gate 5 deployment, and Gate 6 tracking were verified by
> 2026-08-09. The official VisDrone data path, E00 baseline, GPU smoke/resume
> proof, 30-epoch E01 fine-tuning, locked E00/E01 comparison, ONNX FP32 export,
> and OpenVINO FP16 CPU export have objective artifacts. Tracking has objective
> ByteTrack and BoT-SORT comparison artifacts. The ROS 2 Jazzy environment and
> standard talker/listener smoke test are verified, but the project ROS graph,
> assignment, simulation, and handoff gates remain incomplete.

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

## Verified E00 pretrained baseline

The COCO-pretrained `yolo26n.pt` baseline was evaluated on a deterministic
128-image subset of the official VisDrone validation split at 640 pixels. The
recorded macro results are precision 0.28923, recall 0.17337, mAP50 0.15419,
and mAP50-95 0.09688. These are subset results, not full-validation claims.

COCO `person`, `car`, `truck`, and `bus` outputs were mapped explicitly. The
project `van` class remains present in the ground truth but has zero baseline
predictions because the pretrained checkpoint has no distinct van class.

- [E00 summary](experiments/E00_20260807_003/summary.json)
- [E00 metrics](results/day2/E00_20260807_003/metrics.csv)
- [Locked subset manifest](experiments/E00_20260807_003/subset_manifest.json)
- [Colab smoke run instructions](docs/COLAB_SMOKE_RUN.md)

## Verified E01 fine-tuning and locked comparison

The five-class nano checkpoint was fine-tuned for 30 epochs on all 6,471
training images using a Tesla T4. The run was interrupted after epoch 11,
resumed from an optimizer-bearing persistent checkpoint, and completed all 30
epochs without early stopping. Its full-validation training summary records
precision 0.53166, recall 0.38044, mAP50 0.38521, and mAP50-95 0.23458.

For the fair detector comparison, `best.pt` was evaluated separately on the
same locked 128-image subset and CPU/FP32 protocol as E00. The selection hash
is identical. E01 produced precision 0.56508, recall 0.38806, mAP50 0.40177,
and mAP50-95 0.25345. Relative to E00, the absolute gains are +0.27585,
+0.21469, +0.24758, and +0.15657 respectively. These are locked-subset
results; they are not full-validation or deployment-speed claims.

- [E01 training summary](experiments/E01_20260807_001/summary.json)
- [Verified handoff receipt](experiments/E01_20260807_001/handoff_receipt.json)
- [Locked E01 evaluation](experiments/E01E_20260807_001/summary.json)
- [E00 versus E01 comparison](results/day2/E00_vs_E01_20260807_001/summary.json)
- [E01 evaluation metrics](results/day2/E01E_20260807_001/metrics.csv)
- [E01 small-object/occlusion error analysis](docs/E01_ERROR_ANALYSIS.md)

## Verified deployment export

The E01 checkpoint was exported and validated against PyTorch on a deterministic
16-image subset using identical 640x640 square-preprocessed inputs. ONNX Runtime
FP32 achieved 100% reference/candidate detection matching. OpenVINO FP16 on the
available WSL CPU achieved 99.598% reference matching and 100% candidate
matching; both formats met their declared IoU and confidence-difference
tolerances.

This local CPU observation measured mean end-to-end wall latency of 79.057 ms
for PyTorch, 69.123 ms for ONNX Runtime, and 118.826 ms for OpenVINO. The
measurement has one timed repetition after two warm-ups and is not a
production-performance claim.

- [Day 3 deployment report](docs/DAY_3_REPORT.md)
- [Deployment config](configs/e01_deployment_export.yaml)
- [Machine-readable deployment summary](experiments/B01_20260809_005/summary.json)
- [Agreement measurements](results/day3/B01_20260809_005/agreement.csv)
- [Benchmark measurements](results/day3/B01_20260809_005/benchmark.csv)

## Verified tracker comparison

ByteTrack and BoT-SORT processed the same 270-frame (11.25-second) aerial
traffic video with the E01 detector, identical CPU/640/threshold settings, and
the same measurement boundary. ByteTrack is the configurable default because
it reached 12.952 FPS with 77.208 ms mean wall latency, compared with
BoT-SORT's 9.001 FPS and 111.093 ms. BoT-SORT retained slightly more
observations per local track, but no identity ground truth exists, so no IDF1,
MOTA, HOTA, or ID-switch claim is made.

- [Tracking report and limitations](docs/TRACKING_REPORT.md)
- [Tracking protocol](configs/e01_tracking_comparison.yaml)
- [Machine-readable summary](experiments/T01_20260809_002/summary.json)
- [ByteTrack trajectories](results/day3/T01_20260809_002/bytetrack/tracks.csv)
- [BoT-SORT trajectories](results/day3/T01_20260809_002/botsort/tracks.csv)

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

The local ROS 2 Jazzy installation and talker/listener smoke evidence are in
[ROS environment verification](docs/ROS_JAZZY_ENVIRONMENT.md). Source
`/opt/ros/jazzy/setup.bash` explicitly in each WSL shell before ROS commands.

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
