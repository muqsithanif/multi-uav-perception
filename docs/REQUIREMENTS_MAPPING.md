# Requirements-to-Evidence Mapping

This matrix keeps work aligned with portfolio value. Replace planned artifact paths with final links as implementation progresses.

| Capability / requirement | Implementation evidence | Verification evidence | Claim boundary |
|---|---|---|---|
| Python software engineering | Modular detector, tracking adapters, priority, assignment, mission, reporting | pytest results; lint/type checks if adopted | Tested prototype code, not production service |
| C++ | ROS 2 monitoring/health node | `colcon` build plus subscription/integration test | One operational C++ ROS node, not a C++ flight stack |
| Computer vision / OpenCV | Image/video ingestion, overlays, trajectories, 2D visualization | Saved sample outputs and repeatable command | Image-space analysis unless calibrated |
| Deep learning / YOLO | Pretrained baseline and VisDrone fine-tuned nano checkpoint | Config/logs; precision, recall, mAP50, mAP50-95 | State exact split/checkpoint; no invented gains |
| Dataset engineering | VisDrone downloader instructions, manifest, converter, validator | Validation report and visual sample audit | Do not redistribute data without permission |
| Experiment reproducibility | YAML snapshots, seeds, TensorBoard, CSV/JSON registry | One experiment reproducibility check | Note nondeterminism and compute differences |
| Performance optimization | Resolution/backend comparisons; ONNX/OpenVINO FP16 | Controlled latency/FPS and agreement report | Results apply only to stated hardware/runtime |
| Multi-object tracking | ByteTrack default and BoT-SORT adapter | Same-input comparison; identity metrics only with GT | Visual stability is not a quantitative identity score |
| ROS 2 | Typed perception, assignment, mission/status interfaces; launch file | Topic/interface inspection and integration test | ROS 2 software graph, not airborne network validation |
| Algorithms / optimization | Greedy and global linear assignment; shared cost model | Deterministic unit/scenario benchmark | “Global” means optimal for the defined linear cost matrix |
| Autonomous mission logic | Explicit finite-state machine and high-level commands | Transition tests and scenario logs | High-level simulation control, not certified autonomy |
| Multi-UAV coordination | Configurable fleet, three-UAV demo, queues/reassignment | Balanced, overloaded, critical, failure scenarios | Virtual agents in 2D, not physical swarm flight |
| Reliability / testing | Validators, unit tests, ROS smoke test, scenario regression | Test report from pinned environment | No claim of safety-critical coverage |
| Technical communication | README, architecture, benchmark, limitations, demo | Fresh-user reproduction notes | Documentation reflects current verified status |

## Planned evidence index

```text
docs/
  architecture.md
  benchmark_report.md
  limitations.md
experiments/
  experiment_registry.csv
  <experiment_id>/config.yaml
  <experiment_id>/summary.json
results/
  metrics/detection_evaluation.csv
  metrics/inference_benchmark.csv
  metrics/tracking_comparison.csv
  metrics/assignment_benchmark.csv
  charts/
  final_demo/
tests/
  dataset/
  assignment/
  mission/
  integration/
```

## Portfolio wording gate

Do not use a capability in a CV bullet until its implementation and verification columns have evidence. Replace “optimized,” “real-time,” “improved,” or percentage claims with measured values and the exact platform only after benchmarks are final.

Safe after full completion:

> Built a ROS 2-based software and 2D simulation prototype that fine-tunes an aerial YOLO detector, compares ByteTrack and BoT-SORT, assigns tracked targets across three virtual UAVs using Greedy and global linear assignment, and benchmarks supported PyTorch, ONNX, and OpenVINO inference paths.

Never use:

> Built a production-ready autonomous drone swarm.
