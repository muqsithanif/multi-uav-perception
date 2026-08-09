# ROS 2 Jazzy environment verification

## Objective

Record the local ROS 2 installation that unblocks the project ROS workspace.
This is an environment smoke check, not Gate 7: the project has not yet
implemented its three-node graph or launch file.

## Verified host

- Date: 2026-08-09
- Guest OS: Ubuntu 24.04.4 LTS (Noble) in WSL 2
- ROS installation: `ros-jazzy-ros-base`
- Development tools: `ros-dev-tools` and `python3-colcon-core`
- Demo package: `ros-jazzy-demo-nodes-cpp`
- C++ compiler: g++ 13.3.0

The ROS repository was installed through the official
[ROS 2 Jazzy Ubuntu binary-installation guide](https://docs.ros.org/en/jazzy/Installation/Alternatives/Ubuntu-Install-Binary.html).
The lightweight `ros-base` variant was selected deliberately: this project does
not require the ROS desktop GUI stack.

## Package snapshot

These are the package versions installed during this check. They are a
reproduction record, not a promise that future APT installs will select the
same versions.

```text
ros-jazzy-ros-base 0.11.0-1noble.20260616.084325
ros-dev-tools 1.0.1
ros-jazzy-demo-nodes-cpp 0.33.11-1noble.20260615.142146
python3-colcon-core 0.21.0+upstream-1
```

## Use in a new WSL shell

Source Jazzy before invoking ROS commands:

```bash
source /opt/ros/jazzy/setup.bash
ros2 --help
colcon --help
```

The setup file was not added automatically to a shell profile. Keeping the
source command explicit avoids changing unrelated WSL shells and makes each
ROS invocation reproducible.

## Smoke-test evidence

The standard C++ demo publisher and listener ran locally. After the publisher
had started, the listener received consecutive messages:

```text
[listener]: I heard: [Hello World: 3]
[listener]: I heard: [Hello World: 4]
[listener]: I heard: [Hello World: 5]
```

This verifies the local Jazzy runtime, discovery, publisher, and subscriber
path. It does **not** verify the project data model, QoS choices, custom
messages, C++ monitor, three-node graph, or a one-command project launch.

## Next gate

Create the project ROS workspace with typed perception/source, assignment, and
mission interfaces; then verify those nodes exchange valid messages through a
single launch command for Gate 7.
