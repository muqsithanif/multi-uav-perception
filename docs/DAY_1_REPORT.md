# Day 1 Verification Report

## Objective

Create the repository foundation and prove one-image pretrained YOLO inference
on the CPU fallback path.

## Files and configuration changed

- `.gitignore` excludes environments, datasets, weights, secrets, large media,
  experiment bulk output, and ROS 2 build products.
- `requirements.txt` pins the directly used Python stack and selects the
  PyTorch CPU wheel index.
- `configs/smoke_pretrained.yaml` defines immutable experiment
  `S00_20260807_001`.
- `data/samples/wolapark_dron.jpg` and its YAML record provide a licensed aerial
  smoke input with checksum and attribution.
- `scripts/smoke_inference.py` validates input provenance, runs inference, and
  saves the effective config, environment, detections, timing, and prediction.

## Verification run and actual result

Repository:

```text
branch: main
migration package commit: a7442be3e6521df9446f14f990773cf22b2d0bd0
smoke source commit: 23f8ff0716d4dee4451231e7ce3ba1a5bc1e3dbd
tracked worktree clean at smoke start: true
```

Environment:

```text
WSL: 2.7.11.0
kernel: 6.18.33.2-microsoft-standard-WSL2
guest: Ubuntu 24.04.4 LTS
CPU: Intel(R) Core(TM) Ultra 7 155H
logical CPUs visible to WSL: 22
memory visible to WSL: 7,927,980 KiB
Python: 3.12.3
PyTorch: 2.13.0+cpu
torchvision: 0.28.0+cpu
Ultralytics: 8.4.115
OpenCV: 5.0.0
NumPy: 2.4.4
PyYAML: 6.0.3
pytest: 9.1.1
FFmpeg: 6.1.1-3ubuntu5
CUDA available: false
```

Dependency verification:

```text
python -m pip check
No broken requirements found.

python -m pip install --dry-run --requirement requirements.txt
All seven pinned direct requirements were already satisfied at the exact versions.
```

Successful inference command:

```bash
YOLO_CONFIG_DIR=/tmp .venv/bin/python scripts/smoke_inference.py \
  --config configs/smoke_pretrained.yaml
```

Actual smoke result:

```text
status: success
model: yolo26n.pt
model SHA-256: 9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef
model size: 5,544,453 bytes
input: 1920 x 1080 JPEG
device: CPU
image size: 640
confidence threshold: 0.25
IoU threshold: 0.7
warm-up runs: 0
sample count: 1
model load wall time: 5,412.497 ms
prediction wall time: 967.907 ms
Ultralytics preprocess: 44.210 ms
Ultralytics inference: 560.715 ms
Ultralytics postprocess: 14.511 ms
render and save wall time: 183.300 ms
total recorded wall time: 7,281.560 ms
detections: 0
```

These timings are smoke-only cold-run observations. They are not a controlled
benchmark and do not support an FPS or real-time claim.

## Artifacts created

- `experiments/S00_20260807_001/config.yaml`
- `experiments/S00_20260807_001/environment.json`
- `experiments/S00_20260807_001/summary.json`
- `experiments/S00_20260807_001/command.txt`
- `results/smoke/S00_20260807_001/detections.json`
- `results/smoke/S00_20260807_001/prediction.jpg`
- `results/smoke/S00_20260807_001/ATTRIBUTION.md`

Prediction SHA-256:
`85bd5068750741e32e16f626e70e921e91048a548b3d25d1d1e190cefe03994b`.

## Failures and limitations observed

- WSL was absent initially. The elevated bootstrap installed an additional
  Ubuntu 26.04 distro; it was stopped and was not used. `Ubuntu-24.04` was
  installed separately and set as the project default.
- Creating `.venv` exceeded a 124-second command wrapper limit, but direct
  checks confirmed Python 3.12.3 and pip 26.2.1 were created successfully.
- The first PyTorch CPU installation attempt exceeded a 304-second wrapper
  limit; an import check confirmed `torch` was still absent. A retry using the
  same official CPU index completed successfully.
- A cold `torch` plus `torchvision` import from the Windows-mounted venv took
  49.64 seconds.
- The pretrained COCO nano model returned zero detections for this dense aerial
  image at the locked smoke settings. No accuracy conclusion is drawn.
- CPU-only execution was used; CUDA was unavailable.

## Gate 1 result

- Repository and documentation committed: verified.
- Environment imports: verified.
- One-image prediction and machine-readable smoke record: verified.

Gate 1 is verified. No later gate was started.
