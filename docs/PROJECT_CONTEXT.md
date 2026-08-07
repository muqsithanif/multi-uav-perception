# Project Context

## Purpose

This project is a focused portfolio bridge from industrial automation/robotics and Python/C++ experience toward Software & AI Engineering work involving computer vision, ROS 2, real-time inference, and autonomous-system architecture.

It must produce credible engineering evidence, not merely a notebook or architecture proposal. The central outcome is one reproducible path from aerial video to high-level commands for multiple virtual UAVs.

## Starting context

- Primary host: Windows 11.
- Linux/robotics environment: WSL2 with Ubuntu 24.04.
- Expected ROS distribution: ROS 2 Jazzy.
- Compute may include an Intel-based laptop and time-limited Google Colab resources.
- Prior exposure includes Python/C++ and YOLO; ROS 2 and UAV systems are learning areas.
- No physical UAV, NVIDIA Jetson, flight controller, or production flight-test environment is assumed.

These are planning assumptions and should be corrected in this document when the actual environment is known.

## Decision principles

### 1. Completion

The required vertical slice wins over breadth. A smaller system that runs end to end, has tests, and reports honest metrics is more valuable than a partially connected collection of advanced components.

### 2. Efficiency

Start with a nano detector, a single primary dataset, ByteTrack, 2D dynamics, and simple ROS 2 messages. Add the comparison experiments only after the baseline works. Optimize the measured bottleneck, not an assumed one.

### 3. Open resources

Prefer resources that are publicly obtainable and reproducible. Record the exact source, version, license, and access date for datasets, weights, code, and sample media. “Openly accessible” does not automatically mean unrestricted commercial use.

## Intended audience

- The project owner implementing the system step by step.
- Codex or another coding agent working inside the repository.
- Recruiters and interviewers reviewing engineering evidence.
- Developers attempting to reproduce the demo.

## Success narrative

The strongest honest story is: a developer designed and integrated a modular ROS 2 perception/mission prototype, fine-tuned and evaluated an aerial detector, compared tracking and assignment choices, optimized inference for Intel-capable tooling, and documented measured trade-offs and limitations.

The project does not establish avionics safety, real-world localization, collision avoidance, radio reliability, flight-control stability, or swarm behavior on physical aircraft.

## Constraints and risks

- Free Colab GPU access and session duration are not guaranteed.
- VisDrone contains small, dense, and occluded objects; annotation conversion must be validated visually and programmatically.
- Detection data does not automatically provide tracking ground truth. Tracking metrics requiring identity annotations must use an appropriate annotated sequence or be marked unavailable.
- WSL2 is useful for development but does not represent a production UAV computer.
- Intel GPU support varies by device/driver/runtime. CPU must remain a valid benchmark path.
- Tool and model licenses may affect reuse; licensing must be reviewed before distribution or commercial claims.
- A seven-day plan is an execution sequence, not a promise that training or troubleshooting will fit fixed clock time.

## Non-negotiable evidence standards

- Raw logs and machine-readable metrics accompany headline charts.
- Every benchmark states device, backend, precision, input size, sample count, warm-up, and timing boundary.
- Every model result identifies the checkpoint and dataset split.
- Hypotheses are labeled before measurement; conclusions are written after measurement.
- Screenshots and videos support, but do not replace, tests or metrics.
