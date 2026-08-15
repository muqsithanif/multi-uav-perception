# Multi-UAV Aerial Perception

Aerial object detection and tracking, taken from raw dataset through fine-tuning to optimised CPU inference — with every reported number traceable to a versioned experiment artefact.

**Scope:** this is a software and 2D-simulation prototype. It is not a flight controller, does not command physical aircraft, and makes no production-autonomy claim.

---

## Pipeline

```
VisDrone2019-DET
  → five-class YOLO conversion + validation
  → E00 pretrained baseline
  → E01 fine-tuning (30 epochs, Tesla T4)
  → locked-subset comparison
  → ONNX FP32 / OpenVINO FP16 export + agreement check
  → ByteTrack / BoT-SORT comparison
  → target priority + assignment (greedy vs Hungarian)
  → ROS 2 typed message graph
  → three-UAV 2D simulation
```

---

## Results

All figures below come from recorded runs, not from documentation examples.

### Detector: baseline vs fine-tuned

Both evaluated on the **same locked 128-image subset** under identical CPU/FP32 protocol, so the comparison is like-for-like.

| Macro metric | E00 pretrained | E01 fine-tuned | Δ |
|---|---:|---:|---:|
| Precision | 0.2892 | 0.5651 | +0.2759 |
| Recall | 0.1734 | 0.3881 | +0.2147 |
| mAP50 | 0.1542 | 0.4018 | +0.2476 |
| mAP50-95 | 0.0969 | 0.2535 | +0.1566 |

Training was interrupted at epoch 11 and resumed from an optimizer-bearing checkpoint, completing all 30 epochs without early stopping.

### Export agreement and CPU latency

Validated against PyTorch on 16 deterministic images with identical preprocessing.

| Backend | Agreement vs PyTorch | Mean wall latency |
|---|---|---:|
| PyTorch FP32 | reference | 79.06 ms |
| ONNX Runtime FP32 | 498/498 both directions, IoU 0.999999 | 69.12 ms |
| OpenVINO FP16 | 99.598% reference, 100% candidate, IoU 0.999026 | 118.83 ms |

Two agreement failures occurred before this passed — unnamed OpenVINO output tensors, then a preprocessing mismatch. Both were fixed **without loosening the acceptance thresholds**, and the failure history is retained in `experiments/`.

### Tracker comparison

Same 270-frame aerial clip, same detector, same thresholds and timing boundary.

| Tracker | Mean latency | FPS | Unique tracks |
|---|---:|---:|---:|
| ByteTrack *(default)* | 77.21 ms | 12.95 | 95 |
| BoT-SORT | 111.09 ms | 9.00 | 88 |

No MOTA, IDF1, HOTA, or ID-switch figures are claimed — the source footage has no identity ground truth.

---

## What the numbers do not say

- Detector metrics are **locked-subset** results, not full-validation or deployment benchmarks.
- Latency is a single timed repetition on one local WSL CPU after two warm-ups.
- ROS integration uses synthetic targets over local transport — no radio, no network-latency claim, no physical vehicle control.
- Error analysis at confidence 0.25 / IoU 0.50 found the dominant failure modes to be small objects, heavy occlusion, and van→car confusion. These are documented rather than tuned away.

---

## Reproducing

Documented environment: Windows 11 + WSL2, Ubuntu 24.04, Python 3.12, ROS 2 Jazzy.

```bash
YOLO_CONFIG_DIR=/tmp .venv/bin/python -m pytest -q
source /opt/ros/jazzy/setup.bash
cd ros2_ws && colcon build --merge-install --symlink-install
source install/setup.bash && cd ..
bash scripts/run_ros_gate7_smoke.sh G02_<new-id>
```

A clean-checkout verification run is recorded in [REPRODUCTION.md](docs/REPRODUCTION.md): source exported with `git archive`, workspace rebuilt, typed messages and C++ monitor receipt captured. 82 project tests and 12 ROS package tests pass.

---

## Documentation

| Topic | Document |
|---|---|
| Full walkthrough, dataset to ROS | [END_TO_END_PROJECT_REPORT.md](docs/END_TO_END_PROJECT_REPORT.md) |
| Dataset source, mapping, licensing | [VISDRONE_DATA.md](docs/VISDRONE_DATA.md) |
| Detector failure analysis | [E01_ERROR_ANALYSIS.md](docs/E01_ERROR_ANALYSIS.md) |
| Export and agreement | [DAY_3_REPORT.md](docs/DAY_3_REPORT.md) |
| Tracking protocol and limits | [TRACKING_REPORT.md](docs/TRACKING_REPORT.md) |
| Assignment policy | [ASSIGNMENT_REPORT.md](docs/ASSIGNMENT_REPORT.md) |
| ROS topic contract | [ROS_GRAPH.md](docs/ROS_GRAPH.md) |
| Simulation and demo | [SIMULATION_REPORT.md](docs/SIMULATION_REPORT.md) |
| Final status and evidence | [FINAL_REPORT.md](docs/FINAL_REPORT.md) |

---

## Data and licensing

**VisDrone2019-DET is not redistributed by this repository.** Only metadata, checksums, metrics, and reports derived from it are tracked. Obtain the dataset from its official source and review its terms before any public or commercial use.

Third-party assets and tool licenses — including the CC BY-SA aerial smoke image, the Pexels tracking clip, and the AGPL-3.0 Ultralytics dependency — are inventoried in [LICENSES.md](docs/LICENSES.md).

---

Built by [Muqsit Muhammad Hanif](https://github.com/muqsithanif) · muqsithanif29@gmail.com
