# Experiment Plan

## 1. General protocol

Every run receives an ID, copied YAML config, source revision, environment record, dataset manifest/split, seed, start/end time, status, raw metrics, summary, and notes. Failed runs stay in the registry with their cause.

Suggested record:

```text
experiments/<ID>/
  config.yaml
  environment.json
  metrics.csv
  summary.json
  notes.md
```

Never seed documentation with placeholder zeroes that could be mistaken for results. Use `null`/`not_run` until measured.

## 2. Dataset checks

### D00 — conversion smoke test

- Input: a small representative VisDrone sample.
- Check: category mapping, ignored regions, box conversion, clipping, image-label pairing.
- Evidence: validator report and rendered boxes.
- Gate: no systematic offset/class error.

### D01 — selected dataset validation

- Input: the complete chosen training/validation material.
- Check: counts, corrupt/missing files, invalid boxes, per-class distribution, image sizes, occlusion/truncation distribution if retained.
- Evidence: manifest, CSV summary, plots, random/edge-case render set.

## 3. Detection experiments

| ID | Configuration | Purpose | Priority |
|---|---|---|---|
| E00 | Pretrained nano, 640 | Locked baseline | Required |
| E01 | Fine-tuned nano, 640 | Main accuracy model | Required |
| E02 | E01 checkpoint, inference 512 | Accuracy-speed trade-off | Required |
| E03 | E01 checkpoint, inference 416 | Faster trade-off | Required |
| E04 | Fine-tuned small, 640 | Capacity comparison | Optional after all gates |

E02/E03 are inference-resolution evaluations of the selected checkpoint unless a separately justified retraining plan is recorded. Do not imply they were independently trained.

Training starts with a short smoke run. Only after data/config/output checks pass should the main run begin. Checkpoint to persistent storage when using ephemeral compute. Use early stopping where appropriate, but report the real stopping rule and epoch.

Metrics: precision, recall, mAP50, mAP50-95, per-class AP, confusion/error examples, checkpoint size, and evaluation duration. Compare E00/E01 under an identical locked protocol.

## 4. Threshold and resolution study

Use one fixed validation subset/input suite. Vary only the named factor:

- image size: 416, 512, 640;
- confidence thresholds selected before the run;
- optionally IoU/NMS threshold if completion time remains.

Report accuracy and latency together. Select the demo setting from measured trade-offs rather than declaring 640 or the fastest setting automatically best.

## 5. Deployment study

| ID | Backend | Precision | Required device path |
|---|---|---|---|
| B00 | PyTorch | FP32 or framework default stated explicitly | CPU reference |
| B01 | ONNX Runtime | FP32 | CPU |
| B02 | OpenVINO | FP16 model | supported CPU; GPU separately if verified |

Protocol:

1. Same checkpoint, preprocessing, inputs, thresholds, and postprocessing semantics.
2. Record versions and execution provider/device.
3. Warm up consistently, then time a declared number of frames/runs.
4. Record preprocessing, inference-only, postprocessing, and end-to-end timing where possible.
5. Report mean, median, p95, FPS, model size, CPU/RAM, and device-specific data available.
6. Check output agreement on a fixed sample and rerun evaluation when practical.

## 6. Tracking study

| ID | Detector | Tracker | Purpose |
|---|---|---|---|
| T00 | Pretrained baseline | ByteTrack | Pipeline baseline |
| T01 | Fine-tuned selected | ByteTrack | Main tracker |
| T02 | Fine-tuned selected | BoT-SORT | Controlled comparison |
| T03 | Selected optimized backend | ByteTrack | End-to-end speed |
| T04 | Selected optimized backend | BoT-SORT | Optional optimized comparison |

Use identical video segments and detector outputs/settings. Record end-to-end and tracking-stage timing, track counts/duration, visible fragmentation/failure cases, and assignment churn. Quantitative ID metrics require valid identity ground truth; otherwise mark them `not_available`, not zero.

## 7. Assignment study

Compare Greedy and global linear assignment on seeded scenario sets with the same UAVs, targets, cost weights, and constraints.

Scenario sizes should include fewer, equal, and more targets than UAVs plus critical-target, target-loss, and UAV-failure events. Scale tests may add larger synthetic matrices to characterize computation without pretending they represent flight performance.

Metrics:

- objective cost and distance proxy;
- computation time distribution;
- number/percentage of high-priority targets served;
- wait time and queue size;
- assignment success and infeasible pairs;
- reassignment count and switching penalty effects.

Pre-run hypothesis: Greedy may have lower overhead; global assignment may lower total defined cost in multi-target cases. Accept, reject, or qualify this only from results.

## 8. ROS 2 and end-to-end benchmark

Measure at least:

- source timestamp to perception publication;
- perception receipt to assignment publication;
- assignment receipt to mission update;
- end-to-end source-to-command latency;
- message rate, drops/gaps detectable by sequence/timestamps, and C++ monitor status.

State clock source and whether nodes share one machine. WSL2 single-host latency is not networked multi-UAV latency.

## 9. Experiment registry schema

```text
experiment_id,status,git_revision,model,checkpoint,dataset_split,
image_size,backend,device,precision,seed,metrics_path,notes
```

Additional benchmark CSVs should remain tidy (one observation/configuration per row) and include units in column names or metadata.

## 10. Decision gates

- Detector: choose only after E00–E03 and deployment feasibility are known.
- Tracker: choose after T01/T02 on identical input.
- Assignment default: choose after scenario results, while retaining both algorithms.
- Optimization: accept only if export agreement remains within declared tolerance.
- Stop experiments once a defensible required configuration is selected and complete integration/documentation.
