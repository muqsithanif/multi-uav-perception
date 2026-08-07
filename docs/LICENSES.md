# Current Asset and Tool Licenses

This record covers only assets and tools actually used by the verified Day 1
smoke run. It is an engineering inventory, not legal advice.

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
