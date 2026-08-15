# Current Asset and Tool Licenses

This record covers assets and tools used by the verified runs in this
repository. It is an engineering inventory, not legal advice.

## VisDrone2019-DET dataset

- Work: VisDrone2019-DET, official train and validation splits
- Source: <https://github.com/VisDrone/VisDrone-Dataset>
- Terms: released for academic and research purposes; redistribution is
  restricted. Review the official terms before any public or commercial use.

**This repository does not redistribute VisDrone images, labels, or any imagery
derived from them.** Training mosaics, validation overlays, and error-analysis
overlays are generated locally and excluded from Git by `.gitignore`. What the
repository does track is metadata, source checksums, converted-label statistics,
metrics, and written analysis — none of which reproduce the dataset content.

To reproduce the visual artefacts, obtain the dataset from its official source
and re-run the documented pipeline; the generation scripts are included.

## Aerial smoke image and derived prediction

- Work: `Wolapark dron.jpg`
- Author: Situus55
- Source: <https://commons.wikimedia.org/wiki/File:Wolapark_dron.jpg>
- License: Creative Commons Attribution-ShareAlike 4.0 International
- License text: <https://creativecommons.org/licenses/by-sa/4.0/>
- Local source SHA-256:
  `5198970f04a8b6ff3bedc63552d3fe5811e9c19250ca1454802b8868d906a0b0`

The saved prediction is a re-encoded derivative and is distributed under the
same CC BY-SA 4.0 license. Its attribution record is stored beside the output.

## Aerial tracking video and derived previews

- Work: Drone Footage of a Traffic in the Road (Pexels asset 3978617)
- Source: <https://www.pexels.com/video/drone-footage-of-a-traffic-in-the-road-3978617/>
- License: <https://www.pexels.com/license/>
- Local source SHA-256:
  `5e257a6a2c2ebd1c9320e595847d4c6e652978e440117c3bb2eab453858be5d4`

Pexels states that its photos and videos are free to download and use, and that
attribution is not required. The downloaded source video and derived annotated
MP4 previews are ignored by Git; the repository tracks only source metadata,
trajectory CSVs, hashes, and selected still previews for the documented
tracking experiment.

## Installed Python components

The following values come from the installed package metadata used by
experiment `S00_20260807_001`:

| Component | Version | Declared package license |
|---|---:|---|
| Ultralytics | 8.4.115 | AGPL-3.0 |
| PyTorch CPU | 2.13.0+cpu | Composite SPDX expression recorded in package metadata |
| torchvision CPU | 0.28.0+cpu | BSD |
| opencv-python | 5.0.0.93 | Apache-2.0 |
| NumPy | 2.4.4 | Composite SPDX expression recorded in package metadata |
| PyYAML | 6.0.3 | MIT |
| lap | 0.5.13 | BSD-3-Clause |
| pytest | 9.1.1 | MIT |

The pretrained `yolo26n.pt` file was downloaded by Ultralytics 8.4.115 from
<https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt>.
The repository does not redistribute that ignored weight file. The installed
Ultralytics package declares AGPL-3.0; public or commercial reuse must comply
with the applicable Ultralytics terms.

## System tool

Ubuntu supplied FFmpeg `6.1.1-3ubuntu5`. The installed build reports
`--enable-gpl` in its configuration. The repository does not redistribute the
FFmpeg binary.
