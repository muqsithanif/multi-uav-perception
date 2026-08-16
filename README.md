# Multi-UAV Aerial Perception

Aerial object detection and tracking, carried from raw dataset through fine-tuning to optimised CPU inference. Every reported number traces back to a versioned experiment artefact.

**Scope:** a software and 2D-simulation prototype. It is not a flight controller, it does not command physical aircraft, and it makes no production-autonomy claim.

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

Every figure below comes from a recorded run rather than a documentation example.

### Detector: baseline vs fine-tuned

Both models were evaluated on the same locked 128-image subset under an identical CPU/FP32 protocol, making the comparison like-for-like.

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

Two agreement failures preceded this result: unnamed OpenVINO output tensors, then a preprocessing mismatch. Both were fixed without loosening the acceptance thresholds, and the failure history remains in `experiments/`.

### Tracker comparison

Same 270-frame aerial clip, same detector, same thresholds and timing boundary.

| Tracker | Mean latency | FPS | Unique tracks |
|---|---:|---:|---:|
| ByteTrack *(default)* | 77.21 ms | 12.95 | 95 |
| BoT-SORT | 111.09 ms | 9.00 | 88 |

No MOTA, IDF1, HOTA, or ID-switch figures are claimed. The source footage carries no identity ground truth.

---

## What the numbers do not say

- Detector metrics are locked-subset results rather than full-validation or deployment benchmarks.
- Latency is a single timed repetition on one local WSL CPU after two warm-ups.
- ROS integration uses synthetic targets over local transport, with no radio, no network-latency claim, and no physical vehicle control.
- Error analysis at confidence 0.25 and IoU 0.50 identified small objects, heavy occlusion, and van-to-car confusion as the dominant failure modes. They are documented rather than tuned away.

---

## Reproducing

Documented environment: Windows 11 with WSL2, Ubuntu 24.04, Python 3.12, ROS 2 Jazzy.

```bash
YOLO_CONFIG_DIR=/tmp .venv/bin/python -m pytest -q
source /opt/ros/jazzy/setup.bash
cd ros2_ws && colcon build --merge-install --symlink-install
source install/setup.bash && cd ..
bash scripts/run_ros_gate7_smoke.sh G02_<new-id>
```

[REPRODUCTION.md](docs/REPRODUCTION.md) records a clean-checkout verification run: source exported with `git archive`, workspace rebuilt, typed messages and C++ monitor receipt captured. 82 project tests and 12 ROS package tests pass.

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

This repository does not redistribute VisDrone2019-DET. It tracks only metadata, checksums, metrics, and reports derived from the dataset. Obtain the data from its official source and review its terms before any public or commercial use.

[LICENSES.md](docs/LICENSES.md) inventories the third-party assets and tool licences, covering the CC BY-SA aerial smoke image, the Pexels tracking clip, and the AGPL-3.0 Ultralytics dependency.

---

Built by [Muqsit Muhammad Hanif](https://github.com/muqsithanif) · muqsithanif29@gmail.com
