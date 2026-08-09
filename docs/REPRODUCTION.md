# Reproduction guide

## Supported environment

The verified host is WSL 2 Ubuntu 24.04.4 with ROS 2 Jazzy. The local package
snapshot and explicit ROS setup command are recorded in
[ROS_JAZZY_ENVIRONMENT.md](ROS_JAZZY_ENVIRONMENT.md). Python requirements are
pinned in `requirements.txt`, `requirements-deployment.txt`, and
`requirements-tracking.txt`; ROS assignment additionally uses Ubuntu packages
`python3-scipy` and `python3-yaml`.

This guide reproduces the software/2D evidence only. It does not install a
fresh OS image, download private data, or control a vehicle.

## Current workspace verification

```bash
YOLO_CONFIG_DIR=/tmp .venv/bin/python -m pytest -q
source /opt/ros/jazzy/setup.bash
cd ros2_ws
colcon build --merge-install --symlink-install
source install/setup.bash
colcon test --merge-install --packages-select multi_uav_bringup
colcon test-result --verbose
```

The verified functional checkpoint produced `82 passed` project tests, the
standalone ROS assignment-adapter test passed, and the ROS package test report
recorded `12 tests, 0 errors, 0 failures, 1 skipped`. The ament output includes
a known cppcheck slow-version skip; it is not presented as a static-analysis
result.

## Clean-checkout check

Run:

```bash
bash scripts/run_clean_workspace_reproduction.sh R01_<new-id>
```

The script creates a temporary directory with `git archive HEAD`, runs the
mission/simulation tests with the project virtual environment, builds the full
ROS workspace in that clean source tree, runs the ROS adapter test, and starts
the graph until it captures typed mission command/status messages and a C++
monitor receipt. It removes only its validated `mktemp` directory on exit.

[R01_20260809_005](../results/day7/R01_20260809_005/summary.json) passed this
check from source revision `449e02f352565134dbe65914a847084ba6c449ec`: 24
mission/simulation tests and one adapter test passed, and the fresh workspace
launch log recorded Hungarian assignment plus C++ monitor status receipts. It
uses the same already-installed WSL dependencies, so it is a clean-source
checkout reproduction—not a fresh operating-system image.

Earlier `R01_20260809_001` through `R01_20260809_004` directories retain the
initial source/setup/build/discovery failures that the runner fixes.
