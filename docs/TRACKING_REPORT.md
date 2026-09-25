# Tracking report — ByteTrack vs BoT-SORT

Last updated: 9 August 2026 (Asia/Jakarta)

## Objective and status

The tracking gate passed with comparison T01_20260809_002. ByteTrack and BoT-SORT ran the same E01 checkpoint on every frame of the same aerial video. Both trackers produced a trajectory CSV, an annotated preview video, deterministic key frames, and machine-readable timing metrics.

ByteTrack was chosen as the project's default tracker. The choice applies to this software and 2D-simulation prototype and can be changed in YAML; it is not a claim about general tracking quality or a production guarantee.

## Source video and license

- Provider: Pexels
- Asset: 3978617, drone footage of traffic on a road
- Source page: https://www.pexels.com/video/drone-footage-of-a-traffic-in-the-road-3978617/
- License: https://www.pexels.com/license/
- Local video: data/raw/tracking/pexels_3978617_traffic.mp4
- SHA-256: 5e257a6a2c2ebd1c9320e595847d4c6e652978e440117c3bb2eab453858be5d4
- Size and duration: 7,767,712 bytes, 1920×1080, 24 FPS, 270 frames, 11.25 seconds

Pexels states that the video can be downloaded and used for free, and attribution is not required. The raw file and the preview videos are not committed to Git. The source, hash, and license terms are recorded so the local input can be verified.

## Locked protocol

- Checkpoint: E01_20260807_001/best.pt, SHA-256 d5fcbeab43dc5706ea743d834094495be241836da2b25910c1cd1757f84faea5.
- Input: all 270 frames at stride 1; no warm-up frames are excluded from the measurement.
- Detector: CPU, image size 640, confidence 0.25, NMS IoU 0.7, at most 300 detections, square preprocessing (rect=false).
- ByteTrack and BoT-SORT use their own YAML parameters. BoT-SORT uses sparse optical-flow global motion compensation, with ReID disabled.
- Timing boundary: one model.track call per decoded frame, covering preprocessing, the detector, tracker association, postprocessing, and the wrapper.
- Environment: WSL2 Ubuntu 24.04, Intel Core Ultra 7 155H CPU, Python 3.12.3, PyTorch 2.13.0+cpu, Ultralytics 8.4.115, lap 0.5.13.
- Source revision: 9e01d3f with a clean tracked worktree.

Run T01_20260809_001 was executed earlier but is not used for the timing comparison, because Ultralytics installed lap during the first ByteTrack call. Its execution record and failure review are kept. T01_20260809_002 was run after lap was pinned and available before the first frame.

## Results

| Tracker | Mean wall latency | Median | P95 | FPS | Unique tracks | Track observations | Mean observations per track | Total gap frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ByteTrack | 77.208 ms | 67.205 ms | 94.388 ms | 12.952 | 95 | 2,108 | 22.189 | 663 |
| BoT-SORT | 111.093 ms | 89.044 ms | 218.774 ms | 9.001 | 88 | 2,208 | 25.091 | 839 |

BoT-SORT produces slightly longer tracks on average, but ByteTrack has about 30.5% lower mean latency, a much smaller p95, higher FPS, and fewer total gap frames. Because both use the same detector and input, and no identity ground truth is available, the default was chosen on efficiency and this continuity proxy, not on IDF1 or MOTA.

## Failures and qualitative review

Start, middle, and end frames are saved deterministically for each tracker. In the middle frame, small objects and overlaps around the bus produce dense labels; the preview shows that both trackers keep emitting IDs, but a visual check cannot prove true identity.

The CSVs also show fragmentation that can be audited without treating it as a ground-truth ID switch:

- ByteTrack: local track 119 (truck) has 63 gap frames over a 107-frame span; track 312 (bus) has 49 gap frames.
- BoT-SORT: local track 336 (van) has 69 gap frames over a 110-frame span; track 95 (car) has 63 gap frames.
- Tracks with at most two observations: 18 for ByteTrack and 19 for BoT-SORT.

These IDs are local to each tracker. Without per-frame identity annotations, MOTA, IDF1, HOTA, and the ID-switch count are reported as unavailable, not as zero.

## Artifacts

- Active config: configs/e01_tracking_comparison.yaml
- Tracker configs: configs/tracker_bytetrack.yaml and configs/tracker_botsort.yaml
- Summary: experiments/T01_20260809_002/summary.json
- ByteTrack trajectories: results/day3/T01_20260809_002/bytetrack/tracks.csv
- BoT-SORT trajectories: results/day3/T01_20260809_002/botsort/tracks.csv
- Per-frame timing: results/day3/T01_20260809_002/bytetrack/frames.csv and results/day3/T01_20260809_002/botsort/frames.csv
- Local preview: results/day3/T01_20260809_002/<tracker>/annotated.mp4
- Key frames: results/day3/T01_20260809_002/<tracker>/key_frames/

## Limitations and next steps

The source video is stock footage without tracking ground truth. The result shows that the tracker path works and gives an operational comparison on one clip; it does not generalize to an MOT benchmark or to real-time performance on production hardware.

The next milestone is the priority, assignment, and mission-state software that consumes the internal target schema produced from the tracker trajectories.
