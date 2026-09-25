# Day 3 report — export and deployment agreement

Last updated: 9 August 2026 (Asia/Jakarta)

## Objective and status

This milestone exports the checkpoint E01_20260807_001/best.pt to ONNX FP32 and OpenVINO FP16, then shows that both backends load, run inference on identical inputs, and stay within the agreement tolerances against the PyTorch reference.

**Deployment gate: passed.** Run B01_20260809_005 produced and validated both formats and met every agreement tolerance on 16 deterministically selected validation images.

## Configuration and verification

- Config: configs/e01_deployment_export.yaml
- Checkpoint: models/checkpoints/E01_20260807_001/best.pt (5,363,845 bytes, SHA-256 d5fcbeab43dc5706ea743d834094495be241836da2b25910c1cd1757f84faea5)
- Command: YOLO_CONFIG_DIR=/tmp .venv/bin/python scripts/export_and_validate_detector.py --config configs/e01_deployment_export.yaml
- Environment: WSL2 Ubuntu 24.04, Python 3.12.3, PyTorch 2.13.0+cpu, Ultralytics 8.4.115, ONNX 1.22.0, ONNX Runtime 1.28.0, and OpenVINO 2026.3.0. The final artifacts record source revision ba6be91 with a clean tracked worktree.
- Hardware actually available: Intel Core Ultra 7 155H CPU; OpenVINO was tested on CPU only.
- Protocol: 16 evenly spaced images from the E01 locked subset (128 images), imgsz=640, confidence 0.25, NMS IoU 0.7, max_det=300, square padding (rect=false), two warm-up passes, and one measurement per image and backend.

rect=false is required because the ONNX and OpenVINO exports have a static 640×640 input. With rect=true, PyTorch can use rectangular padding, so the backends would receive different inputs and the agreement check would no longer be a fair test of the export.

## Export and agreement results

| Backend | Format validation | Artifact size | Agreement with PyTorch | Status |
|---|---|---:|---|---|
| ONNX Runtime FP32 | ONNX checker and CPUExecutionProvider pass | 9,760,468 bytes | 498/498 reference and candidate matches; mean box IoU 0.999999; max confidence difference 0.000014 | Passed |
| OpenVINO FP16 | XML/BIN read and compiled on CPU | XML 492,606 + BIN 4,802,358 bytes | 496/498 reference matches (99.598%); 496/496 candidate matches; mean box IoU 0.999026; max confidence difference 0.014266 | Passed |

ONNX tolerance: at least 99.5% matches in both directions, mean box IoU 0.999, and a maximum confidence difference of 0.005. OpenVINO tolerance: at least 98% matches in both directions, mean box IoU 0.99, and a maximum confidence difference of 0.02. All checks passed.

## Local CPU benchmark

| Backend | Mean wall latency | Median | P95 | FPS from mean wall |
|---|---:|---:|---:|---:|
| PyTorch FP32 | 79.057 ms | 71.446 ms | 109.434 ms | 12.649 |
| ONNX Runtime FP32 | 69.123 ms | 69.224 ms | 83.913 ms | 14.467 |
| OpenVINO FP16 | 118.826 ms | 86.693 ms | 285.092 ms | 8.416 |

Timing covers one model.predict call per image, including preprocessing, inference, postprocessing, and the wrapper, after two warm-up passes. This is an observation on a local WSL CPU with a single timed repetition, not a real-time claim or a production-device benchmark.

## Recovery history

- B01_20260807_001 completed the export but stopped because the OpenVINO outputs had no tensor names. The evidence is in experiments/B01_20260807_001_failed_tensor_names/.
- B01_20260807_002 used a tensor-name fallback and loaded both formats, but agreement failed because rect=true made PyTorch preprocessing differ from the static export input. The evidence is in experiments/B01_20260807_002/ and results/day3/B01_20260807_002/.
- B01_20260809_003 used the tensor-name fallback and identical square padding without changing the tolerance thresholds. This run passed.
- B01_20260809_004 confirmed the same result, but the WSL Git dirty-worktree metadata wrongly reported host CRLF files as modified. The runner was then changed to use the host Git when available.
- B01_20260809_005 is the final rerun: source revision ba6be91, clean tracked worktree, and every agreement check still passing.

## Artifacts and limitations

- experiments/B01_20260809_005/config.yaml
- experiments/B01_20260809_005/environment.json
- experiments/B01_20260809_005/sample_manifest.json
- experiments/B01_20260809_005/summary.json
- results/day3/B01_20260809_005/agreement.csv
- results/day3/B01_20260809_005/benchmark.csv
- results/day3/B01_20260809_005/summary.json

Agreement was checked on the final detections at confidence 0.25, not on every raw tensor or on the whole validation split. The benchmark covers only 16 images with one timed repetition. GPU, Jetson, TensorRT, and production hardware have not been tested.

The next milestone is Gate 6: running ByteTrack and BoT-SORT on the same aerial video, then recording the latency/FPS comparison and qualitative failure examples.
