# Multi-UAV Aerial Perception

Finding and following vehicles in drone footage, carried from a raw public dataset all the way to a detector that runs at a measured speed on an ordinary CPU.

Every number reported below comes from a recorded experiment run, and each one can be traced back to the artefact that produced it.

**Scope.** This is a software and 2D-simulation prototype. It is not a flight controller, it does not command physical aircraft, and it makes no claim about production autonomy.

---

## What the pipeline does, in order

Each stage depends on the one before it, so they are listed the way they run.

```
VisDrone2019-DET
  → convert to five classes and validate the conversion
  → E00: measure the pretrained model as a baseline
  → E01: fine-tune for 30 epochs on a Tesla T4
  → compare both on the same locked subset
  → export to ONNX and OpenVINO, then check they still agree
  → compare two tracking algorithms
  → prioritise targets and assign them to vehicles
  → publish over a typed ROS 2 message graph
  → drive a three-UAV 2D simulation
```

The two checks in the middle are the ones that carry the weight. Comparing on a **locked subset** means both models saw exactly the same images under exactly the same settings, so the improvement cannot be an artefact of an easier evaluation set. Checking that the exports **still agree** means confirming the converted model produces the same detections as the original, before anyone measures how fast it runs. A faster model that quietly detects different things is not an optimisation.

---

## Results

### The detector, before and after fine-tuning

A general-purpose detector trained on everyday photographs performs poorly on aerial imagery, because objects seen from above are small, densely packed, and viewed from an angle it rarely encountered. Fine-tuning adapts it to that.

Both models were evaluated on the same locked 128-image subset, on CPU, at full precision.

| Metric | Pretrained | Fine-tuned | Change |
|---|---:|---:|---:|
| Precision | 0.2892 | 0.5651 | +0.2759 |
| Recall | 0.1734 | 0.3881 | +0.2147 |
| mAP50 | 0.1542 | 0.4018 | +0.2476 |
| mAP50-95 | 0.0969 | 0.2535 | +0.1566 |

Precision is the share of detections that were real. Recall is the share of real objects that were found. mAP combines both across confidence levels, and the 50-95 variant additionally demands that boxes line up tightly with the object rather than merely overlapping it.

Training was interrupted at epoch 11 and resumed from a checkpoint that carried the optimiser state, completing all 30 epochs without early stopping.

### Export agreement, and speed

A trained model is usually converted into a portable runtime format before deployment. Two were tested here, and both were checked for agreement before either was timed.

| Backend | Agreement with the original | Mean latency |
|---|---|---:|
| PyTorch, full precision | reference | 79.06 ms |
| ONNX Runtime, full precision | 498 of 498 detections matched both ways, box overlap 0.999999 | 69.12 ms |
| OpenVINO, half precision | 99.598 % of reference detections matched, box overlap 0.999026 | 118.83 ms |

Half precision stores numbers with fewer bits, which is why OpenVINO agrees closely rather than exactly. The small disagreement is expected and was accepted only because it was measured.

Two agreement checks failed before this passed. The first came from output tensors arriving without names after conversion, the second from a mismatch in how images were prepared before being fed in. Both were fixed without loosening the acceptance thresholds, which would have been the easy way out, and the failure history remains in `experiments/`.

### Two trackers compared

Detection finds objects in a single frame. **Tracking** links those detections across frames so that the same vehicle keeps the same identity as it moves.

Same 270-frame clip, same detector, same thresholds, same timing boundary.

| Tracker | Mean latency | Frames per second | Unique tracks |
|---|---:|---:|---:|
| ByteTrack *(default)* | 77.21 ms | 12.95 | 95 |
| BoT-SORT | 111.09 ms | 9.00 | 88 |

No tracking accuracy scores are claimed here, and the reason is specific. Measuring tracking quality requires ground truth that says which object is which across every frame, and the source footage has none. Reporting numbers without it would mean inventing the thing being measured.

---

## What these numbers do not say

Stating this plainly is part of the result.

- The detector metrics come from a locked subset. They are not full-validation figures and not deployment benchmarks.
- Latency is a single timed repetition on one local CPU after two warm-up passes.
- The ROS integration uses synthetic targets over local transport. No radio, no network latency claim, no physical vehicle control.
- Error analysis found the dominant failure modes to be small objects, heavy occlusion, and vans being confused with cars. They are documented rather than tuned away, because tuning against the evaluation set is how a number stops meaning anything.

---

## Reproducing it

Environment: Windows 11 with WSL2, Ubuntu 24.04, Python 3.12, ROS 2 Jazzy.

```bash
YOLO_CONFIG_DIR=/tmp .venv/bin/python -m pytest -q
source /opt/ros/jazzy/setup.bash
cd ros2_ws && colcon build --merge-install --symlink-install
source install/setup.bash && cd ..
bash scripts/run_ros_gate7_smoke.sh G02_<new-id>
```

[REPRODUCTION.md](docs/REPRODUCTION.md) records a verification run from a clean checkout: source exported with `git archive`, workspace rebuilt from nothing, typed messages and monitor output captured. 82 project tests and 12 ROS package tests pass.

---

## Documentation

| Topic | Document |
|---|---|
| Full walkthrough, dataset through to ROS | [END_TO_END_PROJECT_REPORT.md](docs/END_TO_END_PROJECT_REPORT.md) |
| Dataset source, class mapping, licensing | [VISDRONE_DATA.md](docs/VISDRONE_DATA.md) |
| Where the detector fails, and why | [E01_ERROR_ANALYSIS.md](docs/E01_ERROR_ANALYSIS.md) |
| Export and agreement checking | [DAY_3_REPORT.md](docs/DAY_3_REPORT.md) |
| Tracking protocol and its limits | [TRACKING_REPORT.md](docs/TRACKING_REPORT.md) |
| Target assignment policy | [ASSIGNMENT_REPORT.md](docs/ASSIGNMENT_REPORT.md) |
| ROS topic contract | [ROS_GRAPH.md](docs/ROS_GRAPH.md) |
| Simulation and demo | [SIMULATION_REPORT.md](docs/SIMULATION_REPORT.md) |
| Final status and evidence index | [FINAL_REPORT.md](docs/FINAL_REPORT.md) |

---

## Data and licensing

This repository does not redistribute the VisDrone dataset. It tracks only metadata, checksums, metrics, and reports derived from it. Obtain the data from its official source and read its terms before any public or commercial use.

[LICENSES.md](docs/LICENSES.md) inventories the third-party assets and tool licences involved, including the aerial demonstration image, the tracking test clip, and the AGPL-licensed training library.

---

Built by [Muqsit Muhammad Hanif](https://github.com/muqsithanif) · muqsithanif29@gmail.com
