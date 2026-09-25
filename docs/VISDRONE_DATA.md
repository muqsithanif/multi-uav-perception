# VisDrone2019-DET data

## Day 2 scope

The project uses only the **object detection in images** task of
VisDrone2019-DET. The official `train` and `val` splits are kept as they are;
test-dev and test-challenge are not used for Gate 2A.

Official sources:

- Dataset repository: <https://github.com/VisDrone/VisDrone-Dataset>
- AISKYEYE download page: <https://aiskyeye.com/download/>
- DET annotation and evaluation toolkit:
  <https://github.com/VisDrone/VisDrone2018-DET-toolkit>

The Google Drive links and file IDs in `configs/visdrone_sources.yaml` come
from the official repository. The raw dataset, ZIP archives, converted output,
and checkpoints must not be committed to Git. Only source code, configuration,
checksum manifests, reports, and small audit samples are kept.

## Usage and redistribution status

When checked on 2026-08-07, the official repository did not include an
explicit dataset license file. The official toolkit states that its code is
for research purposes. This repository therefore does not claim that VisDrone
is openly licensed for commercial use, and it does not redistribute the
dataset. Public or commercial use should check the latest terms and, where
needed, ask the dataset owners for permission.

## Expected source layout

```text
data/raw/visdrone2019_det/
  VisDrone2019-DET-train.zip
  VisDrone2019-DET-val.zip
  VisDrone2019-DET-train/
    images/*.jpg
    annotations/*.txt
  VisDrone2019-DET-val/
    images/*.jpg
    annotations/*.txt
```

Access:

```bash
.venv/bin/python -m pip install -r requirements-day2.txt
.venv/bin/python scripts/download_visdrone.py --plan
.venv/bin/python scripts/download_visdrone.py --splits train val
```

The downloader records the SHA-256, archive size, image and annotation counts,
and the actual access time in `data/metadata/visdrone2019_det_download_manifest.json`.
Extraction rejects ZIP paths that escape the target directory.

## Conversion and validation

The conversion policy is in `configs/visdrone_conversion.yaml`, and the
portable Ultralytics dataset configuration is in `configs/visdrone_5class.yaml`.
Run the configuration check without data, then the D00 fixture tests, then the
actual conversion, in this order:

```bash
.venv/bin/python scripts/prepare_visdrone.py --check-config
.venv/bin/python -m pytest -q tests/test_visdrone_dataset.py tests/test_visdrone_audit.py tests/test_visdrone_distribution.py
.venv/bin/python scripts/prepare_visdrone.py
.venv/bin/python scripts/render_visdrone_audit.py --split val --samples 6
.venv/bin/python scripts/analyze_visdrone_distribution.py
```

The local output, ignored by Git, uses this layout:

```text
data/processed/visdrone5/
  images/train/*.jpg
  images/val/*.jpg
  labels/train/*.txt
  labels/val/*.txt
```

By default, images are hardlinked so dataset bytes are not duplicated on the
same volume, with an automatic fallback to copying when the filesystem does not
support hardlinks. YOLO labels are always written separately. The converter
keeps the official split, and the validator checks the eight-field format,
categorical field values, positive bbox sizes, clipping and normalization,
corrupt files, image-label pairing, YOLO class range, bbox bounds, and filename
overlap between splits.

Source bboxes with a non-positive width or height are never given an invented
size. Those rows are excluded from the YOLO labels and must be recorded per
split and class, with example file and line, in the validation report. The
report status becomes `passed_with_sanitization`, while the output validator
still requires zero invalid bboxes. This policy keeps source annotation defects
visible without producing invalid training labels.

A single trailing comma is accepted only when it produces exactly one empty
ninth field; the eight data fields are still parsed according to the
specification. Every such normalization is counted and given an example file
and line in the report. A non-empty ninth field is treated as ambiguous and
rejected.

The visual audit selects samples deterministically, first covering every
project class and then spreading evenly by filename. Overlays and the checksum
manifest are written to `results/day2/visual_audit/`. The manifest starts with
the status `rendered_pending_manual_visual_review`; the gate status may only be
changed after the artifacts have actually been reviewed visually.

The distribution analysis reads the same validation report and writes JSON,
CSV, plots, and artifact checksums to `results/day2/dataset_analysis/`. The
numbers in the Day 2 report come from this output, not from estimates.

## Official annotation format

Each row has eight fields:

```text
bbox_left,bbox_top,bbox_width,bbox_height,score,object_category,truncation,occlusion
```

- `score=0` marks an ignored region; `score=1` marks an evaluated instance.
- Original categories: ignored region (0), pedestrian (1), people (2),
  bicycle (3), car (4), van (5), truck (6), tricycle (7), awning-tricycle (8),
  bus (9), motor (10), and others (11).
- Truncation: 0 not truncated, 1 partially truncated.
- Occlusion: 0 none, 1 partial, 2 heavy.
- The official toolkit states that ignored regions and `others` are not counted
  in evaluation.

## Project class mapping

Gate 2A uses the five classes locked in the project blueprint:

| YOLO ID | Project name | Original VisDrone ID |
|---:|---|---:|
| 0 | pedestrian | 1 |
| 1 | car | 4 |
| 2 | van | 5 |
| 3 | truck | 6 |
| 4 | bus | 9 |

Categories 0 and 11 are always ignored. Categories 2, 3, 7, 8, and 10 are
outside the scope of the five-class model and are recorded as
`excluded_unselected_class`, rather than silently dropped as missing negatives.
