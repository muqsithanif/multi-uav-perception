# E01 locked-subset error analysis

Run date: 7 August 2026

Experiment: `E01A_20260807_001`

Status: **passed**

## Main findings

At the operating point `confidence=0.25` with class-aware matching at
`IoU=0.50`, the E01 checkpoint is weakest on small and heavily occluded
objects. Small-object recall is 0.325061, compared with 0.731993 for medium and
0.836735 for large objects. Recall for heavily occluded objects is only
0.174004, compared with 0.622742 for objects with no occlusion.

These numbers are not AP and do not replace the E00/E01 evaluation. The purpose
is to diagnose failure patterns at one explicit operating point.

## Protocol

- Model: `E01_20260807_001/best.pt`, SHA-256
  `d5fcbeab43dc5706ea743d834094495be241836da2b25910c1cd1757f84faea5`.
- Data: the same 128 validation images as E00/E01E; selection SHA-256
  `7e1bd549153bea5fa2d6f1e17a4e7f29f57f11157c6c277441a6d00520c265bd`.
- Backend: PyTorch CPU/FP32, image size 640, batch 4, rect mode.
- Predictions: confidence 0.25, NMS IoU 0.7, at most 300 detections.
- Error matching: class-aware, one-to-one, minimum IoU 0.50.
- Size uses bbox area at the original image resolution: small `<1024 px²`,
  medium `1024–<9216 px²`, large `>=9216 px²`.
- Occlusion (`none`, `partial`, `heavy`) and truncation come directly from the
  official VisDrone annotations. The order and geometry of every object were
  re-checked against the converted YOLO labels.

Reproduction command:

```text
YOLO_CONFIG_DIR=/tmp .venv/bin/python scripts/analyze_detection_errors.py --config configs/e01_error_analysis.yaml
```

## Totals at the operating point

| Ground truth | Predictions | TP | FN | FP | Precision | Recall |
|---:|---:|---:|---:|---:|---:|---:|
| 6,090 | 4,218 | 2,975 | 3,115 | 1,243 | 0.705311 | 0.488506 |

## Recall by condition

### Object size

| Size | GT | Matched | Missed | Recall |
|---|---:|---:|---:|---:|
| Small | 3,707 | 1,205 | 2,502 | 0.325061 |
| Medium | 2,138 | 1,565 | 573 | 0.731993 |
| Large | 245 | 205 | 40 | 0.836735 |

### Occlusion

| Occlusion | GT | Matched | Missed | Recall |
|---|---:|---:|---:|---:|
| None | 2,990 | 1,862 | 1,128 | 0.622742 |
| Partial | 2,623 | 1,030 | 1,593 | 0.392680 |
| Heavy | 477 | 83 | 394 | 0.174004 |

### Class

| Class | GT | Matched | Missed | Recall |
|---|---:|---:|---:|---:|
| Pedestrian | 1,946 | 484 | 1,462 | 0.248715 |
| Car | 3,417 | 2,315 | 1,102 | 0.677495 |
| Van | 487 | 119 | 368 | 0.244353 |
| Truck | 187 | 37 | 150 | 0.197861 |
| Bus | 53 | 20 | 33 | 0.377358 |

Truncated objects have a recall of 0.662116 (194/293), against 0.479731
(2,781/5,797) for objects that are not truncated. This difference does not show
that truncation helps detection, because size, class, scene, and sample count
are not controlled. The consistent, large bottlenecks in this run are size and
occlusion.

## Class confusion and false positives

There are 237 class-confusion pairs: the prediction and the ground truth
overlap by at least 0.50 but the classes differ. The largest confusion is
`van -> car` with 155 cases (65.4% of all class confusions), followed by
`truck -> car` with 31 and `car -> van` with 29. Separating similar vehicle
classes from an aerial viewpoint is still weak.

Of the 1,243 false positives, 850 are labelled car, 278 pedestrian, 84 van,
19 truck, and 12 bus. These counts come from the 0.25 threshold and should not
be read as the false-positive distribution at every threshold.

## Selected failure examples

Overlays are selected deterministically by failure category. Red marks false
negatives, orange false positives, and magenta class confusions. Because
VisDrone scenes are dense, only class confusions carry a text label; the full
metadata is in the raw CSV files.

The overlay images are produced locally by the analysis script and are not
published in this repository, because they are derived from VisDrone imagery.
The table identifies each source image so the overlays can be regenerated.

| Reason | Source image | TP | FN | FP | Main detail |
|---|---|---:|---:|---:|---|
| Small FN | `0000291_03201_d_0000884` | 54 | 120 | 36 | 102 small FN |
| Heavy-occlusion FN | `0000280_01601_d_0000620` | 41 | 50 | 11 | 22 heavy-occlusion FN |
| Truncated FN | `0000301_00001_d_0000156` | 16 | 34 | 10 | 7 truncated FN |
| Class confusion | `0000277_01801_d_0000548` | 24 | 59 | 20 | 9 confusions |
| False positive | `0000295_01600_d_0000029` | 66 | 49 | 37 | most FP |
| Total errors | `0000295_02900_d_0000034` | 79 | 85 | 21 | 106 total errors |

## Implications and next steps

1. Deployment and tracking should be tested on dense scenes with small objects;
   temporal tracking can help continuity but cannot recover detector false
   negatives.
2. Higher-resolution or tiled inference is worth testing later, since
   small-object recall is far below medium and large. There is no claim yet
   that either method will improve the result.
3. The `van/car/truck` confusion should be monitored in the demo and the
   benchmarks. Possible fixes are hard-example sampling or class balancing, but
   each needs a new experiment ID.
4. The 0.25 threshold is a single operating point for diagnosis. The final
   threshold should be chosen from the precision/recall trade-off the demo
   needs.

## Audit artifacts

- [Summary JSON](../experiments/E01A_20260807_001/summary.json)
- [Ground-truth outcomes](../results/day2/E01A_20260807_001/ground_truth_outcomes.csv)
- [False positives](../results/day2/E01A_20260807_001/false_positives.csv)
- [Classification confusions](../results/day2/E01A_20260807_001/classification_confusions.csv)
- [Per-image summary](../results/day2/E01A_20260807_001/image_summary.csv)

Every headline number in this document comes from these summary and CSV files.
The overlays are selected qualitative evidence only, not a manual review of all
128 images.
