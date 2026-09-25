# Day 2 report — VisDrone and training-pipeline validation

Last updated: 7 August 2026 (Asia/Jakarta)

## 1. Objective

Build an official, reproducible, and safe VisDrone2019-DET data path for
five-class YOLO training. This milestone covers download, checksums,
conversion, programmatic validation, measured sanitization of source defects,
class-distribution analysis, and a visual audit.

## Status

**Day 2 data checkpoint: passed with sanitization
(`passed_with_sanitization`).**

**E00 pretrained baseline: passed on the locked validation subset.**

**Colab smoke/resume: passed.** Three-epoch training on the full dataset,
checkpoints persisted to Drive, and resuming from a checkpoint that still holds
the optimizer state were demonstrated on a Tesla T4.

**E01 fine-tuning and locked comparison: passed.** The main run completed
30 epochs, and the best checkpoint was evaluated with the same subset and
protocol as E00.

**Gate 2A overall: passed (`passed`).** The deployment gate and later project
stages were not yet complete at this point.

## 2. Files and configuration

- `configs/visdrone_sources.yaml` locks the official sources and the train/val split.
- `configs/visdrone_conversion.yaml` locks the five-class mapping and the
  input, output, and report locations.
- `scripts/download_visdrone.py` downloads, verifies SHA-256, and safely
  extracts the ZIP files.
- `scripts/visdrone_dataset.py` converts and validates annotations.
- `scripts/prepare_visdrone.py` produces the manifest and the validation report.
- `scripts/render_visdrone_audit.py` selects and renders validation samples
  deterministically.
- `scripts/analyze_visdrone_distribution.py` produces JSON/CSV summaries and
  class-distribution plots.
- `scripts/evaluate_pretrained_baseline.py` locks the subset, class mapping,
  inference, IoU matching, metrics, timing, and curves for both E00 and E01.
- `configs/e00_pretrained_baseline.yaml` stores the actual E00 protocol.
- `configs/e01_finetuned_locked_eval.yaml` uses the E01 checkpoint with the
  native five-class mapping and requires the E00 subset manifest.
- `scripts/compare_detection_experiments.py` refuses comparisons when the subset
  or protocol differs, then writes JSON/CSV deltas.
- `configs/e00_vs_e01_comparison.yaml` locks the accepted pair of summaries and
  the comparison output.
- `scripts/run_visdrone_smoke_training.py` prepares the smoke subset, splits
  training into two phases, keeps the optimizer checkpoint, and verifies that the
  resume actually happened.
- `configs/visdrone_smoke_train.yaml` limits the scope to 256 train images,
  64 val images, and three epochs; `full_fine_tuning` is locked to `false`.
- `notebooks/day2_visdrone_smoke_colab.ipynb` automates Colab setup, dataset
  validation, smoke training, Google Drive persistence, and pushing the compact
  artifacts.
- The test suite covers the parser, conversion, sanitization, validator, sample
  selection, rendering, distribution counts, artifact checksums, baseline
  mapping, bbox conversion, prediction matching, the subset reference lock, and
  rejection of non-comparable comparisons.

The bbox and trailing-comma sanitization policy was committed in `0725378`
(`fix: sanitize measured VisDrone annotation defects`).

## 3. Verification and results

### Source access and integrity

The download manifest records complete image/annotation pairs:

| Split | Images | Annotations | ZIP size | SHA-256 |
|---|---:|---:|---:|---|
| train | 6,471 | 6,471 | 1,549,875,511 bytes | `86a77eba93137bfc16e4993860de9245b0675c0dba0d3ab98fb458699e256f84` |
| val | 548 | 548 | 81,638,851 bytes | `abeea063037e5d20398837deb11084e652402a34ddf4f207bdf541a6f2a35ef9` |

The first download through Google Drive was blocked by the public quota; the
data later became available through the same official, authorized mechanism
and was verified against the source metadata before conversion.

### Conversion and validation

Commands that passed:

```text
.venv/bin/python scripts/prepare_visdrone.py --check-config
.venv/bin/python -m pytest -q tests/test_visdrone_dataset.py tests/test_visdrone_audit.py tests/test_visdrone_distribution.py
.venv/bin/python scripts/prepare_visdrone.py
.venv/bin/python scripts/render_visdrone_audit.py --split val --samples 6
.venv/bin/python scripts/analyze_visdrone_distribution.py
.venv/bin/python scripts/evaluate_pretrained_baseline.py --config configs/e00_pretrained_baseline.yaml
.venv/bin/python scripts/evaluate_pretrained_baseline.py --config configs/e01_finetuned_locked_eval.yaml
.venv/bin/python scripts/compare_detection_experiments.py --config configs/e00_vs_e01_comparison.yaml
```

Final suite result after the E01 error analysis: **37 passed, 0 failed** in
49.47 seconds. At the distribution checkpoint, one test run failed because the
SHA-256 constant for a new fixture was wrong; the constant was corrected to the
fixture's actual digest and the suite then passed.

| Split | Input images/labels | Source annotations | Output objects | Output images/labels |
|---|---:|---:|---:|---:|
| train | 6,471 / 6,471 | 353,550 | 267,960 | 6,471 / 6,471 |
| val | 548 / 548 | 40,169 | 25,884 | 548 / 548 |

Five-class object distribution after conversion:

| Split | pedestrian | car | van | truck | bus |
|---|---:|---:|---:|---:|---:|
| train | 79,337 | 144,866 | 24,956 | 12,875 | 5,926 |
| val | 8,844 | 14,064 | 1,975 | 750 | 251 |

The dominant class in both splits is `car` (54.062547% of train and 54.334724%
of val), and the minority class is `bus` (2.211524% of train and 0.969711% of
val). The ratio between the largest and smallest class is 24.445832 in train
and 56.031873 in val. The largest shift in proportion is for `pedestrian`:
+4.560049 percentage points in val relative to train.

The output validator found **0 invalid bboxes** and **0 filename overlaps
between splits**, and the object count from re-parsing equals the conversion
count in both splits.

The final report records `source_revision=0725378` and
`tracked_source_dirty=true`. The only dirty tracked files at snapshot time were
the README and milestone documentation being updated; the converter and
validator match that revision.

### Source sanitization

- Three train bboxes have height `0`; there are no such cases in val.
- Two of the invalid bboxes are ignored regions with `score=0`.
- One invalid bbox is source class 4 (`car`) with `score=1`; this row is
  excluded from the training labels and recorded as
  `invalid_selected_source_box_count=1`.
- 34 train rows have a single empty trailing comma and are normalized to eight
  fields. Val has no such cases.
- Sanitization never invents bbox sizes and produces no invalid output bboxes.

### Visual audit

Six validation overlays were inspected at native resolution. The samples cover
all five classes. The boxes show no systematic offset or scale error, stay
inside the frame, and the class mapping matches the visible annotated objects.
Visual audit status: **passed**.

### E00 pretrained baseline

The accepted run is `E00_20260807_003` at revision `9e5727e`. The protocol uses
128 of the 548 validation images (23.36%), selected evenly by filename order.
The selection SHA-256 is
`7e1bd549153bea5fa2d6f1e17a4e7f29f57f11157c6c277441a6d00520c265bd`.
The subset contains 6,090 objects: 1,946 pedestrian, 3,417 car, 487 van,
187 truck, and 53 bus.

The `yolo26n.pt` checkpoint is 5,544,453 bytes with SHA-256
`9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`.
Evaluation ran on CPU/FP32 with image size 640, confidence 0.001, NMS IoU 0.7,
at most 300 detections, batch 4, and evaluation IoU 0.50–0.95.

| Scope | Instances | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|
| macro, 5 classes | 6,090 | 0.289228 | 0.173370 | 0.154190 | 0.096881 |
| pedestrian | 1,946 | 0.392821 | 0.124358 | 0.119576 | 0.049120 |
| car | 3,417 | 0.634277 | 0.379865 | 0.408989 | 0.246381 |
| van | 487 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| truck | 187 | 0.171500 | 0.155080 | 0.095931 | 0.072219 |
| bus | 53 | 0.247544 | 0.207547 | 0.146452 | 0.116683 |

The pretrained output mapping is COCO `person -> pedestrian`, `car -> car`,
`truck -> truck`, and `bus -> bus`. Ground-truth `van` objects are still
counted, but the COCO checkpoint has no separate van class, so the van
prediction count and all van metrics are zero.

Wall time for the evaluation step was 13.223372 seconds, or 103.307593
ms/image. The total inference stage reported by Ultralytics was 8.285059
seconds. This is a single CPU run for pipeline validation, not a performance
benchmark; model loading and manifest creation happen before the evaluation
timer starts.

Two earlier attempts failed before metrics were computed, because the loader
turned a list of path strings into generated names such as `image0.jpg`. Both
are kept as `E00_20260807_001_failed_order` and
`E00_20260807_002_failed_synthetic_names` with `metrics: null`. The third run
used a `.txt` file list, which preserves the filenames.

### GPU smoke run and resume proof

`E01S_20260807_001` ran three epochs on all 6,471 train images and 548
validation images on a Tesla T4, batch 16, image size 640. The run finished in
599.46 seconds. Epoch 3 recorded precision 0.38560, recall 0.31271, mAP50
0.26127, and mAP50-95 0.15114. The `best.pt` and `last.pt` checkpoints were
saved to Google Drive.

`E01R_20260807_001` then genuinely resumed from `epoch1.pt`, which still holds
the optimizer state. The resume produced one additional epoch row and a new
checkpoint in 199.25 seconds. This proves the recovery mechanism; it is not an
accuracy run for comparison.

### E01 main fine-tuning

`E01_20260807_001` used all training data for 30 epochs with AdamW, seed 42,
batch 16, image size 640, AMP, and a Tesla T4. The first session was cut off
after epoch 11; recovery resumed from the checkpoint at epoch index 10,
starting at epoch 12. The run completed all 30 epochs without early stopping.
The estimated combined duration of both sessions is 5,193.53 seconds; this is
not a continuous-training benchmark.

| Full-validation scope | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| best/final epoch 30 | 0.53166 | 0.38044 | 0.38521 | 0.23458 |

The best checkpoint is 5,363,845 bytes with SHA-256
`d5fcbeab43dc5706ea743d834094495be241836da2b25910c1cd1757f84faea5`.
The transfer archive (`handoff_receipt.json`) was verified against 37 manifest
entries with no failures; the weights are stored locally on a path that Git
ignores.

### Identical E00 versus E01 comparison

`E01E_20260807_001` ran the best checkpoint on the same 128 images as E00. The
selection SHA-256 of both runs is
`7e1bd549153bea5fa2d6f1e17a4e7f29f57f11157c6c277441a6d00520c265bd`.
Both used CPU/FP32, image size 640, confidence 0.001, NMS IoU 0.7, max-det 300,
batch 4, rect mode, and the same evaluator.

| Macro metric | E00 | E01 | Absolute delta |
|---|---:|---:|---:|
| Precision | 0.289228 | 0.565079 | +0.275850 |
| Recall | 0.173370 | 0.388065 | +0.214695 |
| mAP50 | 0.154190 | 0.401769 | +0.247580 |
| mAP50-95 | 0.096881 | 0.253452 | +0.156572 |

E01 also raises mAP50-95 for every class: pedestrian 0.049120 -> 0.129983,
car 0.246381 -> 0.462920, van 0 -> 0.214271, truck 0.072219 -> 0.186587,
and bus 0.116683 -> 0.273501. A relative gain for van is deliberately not
computed, because the baseline is zero and the COCO checkpoint has no separate
van class.

E01 evaluation wall time was 16.774275 seconds (131.049020 ms/image), against
13.223372 seconds (103.307593 ms/image) for E00. Both are single CPU runs for
pipeline validation and do not meet the latency/FPS benchmark protocol.

### E01 error analysis

`E01A_20260807_001` analyzed the same subset at an operating point of
confidence 0.25 and matching IoU 0.50. Of 6,090 ground-truth objects there are
2,975 TP, 3,115 FN, and 1,243 FP. Small-object recall is 0.325061, far below
medium (0.731993) and large (0.836735). Recall for heavily occluded objects is
0.174004, compared with 0.392680 for partial occlusion and 0.622742 for none.

There are 237 class confusions, 155 of them `van -> car`. Six deterministic
overlays were inspected. Method details, per-class tables, examples, and
limitations are in `docs/E01_ERROR_ANALYSIS.md`. These numbers diagnose one
operating point; they are not AP or a deployment benchmark.

## 4. Artifacts

- `data/metadata/visdrone2019_det_download_manifest.json`
- `data/metadata/visdrone5_manifest.json`
- `experiments/D01_visdrone_validation/summary.json`
- `experiments/D02_visdrone_dataset_audit/summary.json`
- `experiments/E00_20260807_003/summary.json`
- `experiments/E00_20260807_003/subset_manifest.json`
- `experiments/E01_20260807_001/summary.json`
- `experiments/E01_20260807_001/handoff_receipt.json`
- `experiments/E01E_20260807_001/summary.json`
- `experiments/E01A_20260807_001/summary.json`
- `results/day2/dataset_analysis/class_distribution.json`
- `results/day2/dataset_analysis/class_distribution.csv`
- `results/day2/dataset_analysis/class_distribution.png`
- `results/day2/visual_audit/summary.json`
- `results/day2/E00_20260807_003/metrics.csv`
- four E00 curves in `results/day2/E00_20260807_003/curves/`
- `results/day2/E01_20260807_001/training/` for training plots and logs
- `results/day2/E01E_20260807_001/metrics.csv` and four evaluation curves
- `results/day2/E00_vs_E01_20260807_001/summary.json`
- `results/day2/E00_vs_E01_20260807_001/comparison.csv`
- four raw CSV files in `results/day2/E01A_20260807_001/`
- `results/day2/gate_2a_status.json`
- `notebooks/day2_visdrone_smoke_colab.ipynb`

The raw dataset, ZIP files, and converted output are ignored by Git. The
visual-audit overlays, error-analysis overlays, and training mosaics are
generated locally but not published, because they are derived from VisDrone
imagery; the manifests, reports, and metrics that describe them are tracked.

## 5. Known limitations

- The official repository does not include an explicit dataset license; this
  project claims no right to redistribute the data or to use it commercially.
- The six-image visual audit is a sample check, not a manual review of all
  7,019 images. Dense scenes make overlay text overlap, and some distant or
  occluded annotations remain ambiguous.
- The fair comparison uses a 128-image subset; it does not replace the E01
  full-validation metrics and should not be generalized without evaluating the
  whole split under the same protocol.
- The van class does not exist in the COCO labels of the pretrained checkpoint
  and is not mapped heuristically to car or truck.
- E00/E01 timings are each a single CPU pipeline-validation run without warm-up
  or latency sampling; no FPS or real-time claim is made.
- Checkpoints are not committed to Git. Reproducing inference requires fetching
  the weights by the path and SHA-256 recorded in the receipt and summary.
- Running the Colab notebook still requires the account owner to authorize
  Google Drive access.
- The error analysis measures one confidence/IoU operating point; deployment
  threshold selection and small-object mitigation experiments have not been done.
