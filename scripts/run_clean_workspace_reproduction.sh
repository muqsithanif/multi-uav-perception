#!/usr/bin/env bash
set -euo pipefail

run_id="${1:-R01_20260809_001}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_dir="${repo_root}/results/day7/${run_id}"
source_revision="$(git -C "${repo_root}" rev-parse HEAD)"
repro_root="$(mktemp -d /tmp/multi-uav-perception-repro.XXXXXX)"

cleanup() {
  if [[ "${repro_root}" == /tmp/multi-uav-perception-repro.* && -d "${repro_root}" ]]; then
    rm -rf -- "${repro_root}"
  fi
}
trap cleanup EXIT

if [[ -e "${output_dir}" ]]; then
  echo "refusing to overwrite existing artifact directory: ${output_dir}" >&2
  exit 2
fi
if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo "ROS 2 Jazzy is not installed at /opt/ros/jazzy" >&2
  exit 2
fi
if [[ ! -x "${repo_root}/.venv/bin/python" ]]; then
  echo "project virtual environment is missing at ${repo_root}/.venv" >&2
  exit 2
fi

mkdir -p "${output_dir}"
git -C "${repo_root}" archive --format=tar HEAD | tar -x -C "${repro_root}"

PYTHONPATH="${repro_root}/src" "${repo_root}/.venv/bin/python" -m pytest -q \
  "${repro_root}/tests/test_mission.py" "${repro_root}/tests/test_simulation.py" \
  > "${output_dir}/python_tests.log" 2>&1

set +u
source /opt/ros/jazzy/setup.bash
set -u
cd "${repro_root}/ros2_ws"
colcon build --merge-install --symlink-install > "${output_dir}/colcon_build.log" 2>&1
set +u
source install/setup.bash
set -u
PYTHONPATH="${repro_root}/src:${repro_root}/ros2_ws/src/multi_uav_bringup" python3 -m pytest -q \
  "${repro_root}/ros2_ws/src/multi_uav_bringup/test/test_assignment_logic.py" \
  > "${output_dir}/ros_adapter_test.log" 2>&1

export MULTI_UAV_PROJECT_ROOT="${repro_root}"
ros2 launch multi_uav_bringup gate7_bringup.launch.py > "${output_dir}/launch.log" 2>&1 &
launch_pid=$!

stop_launch() {
  kill "${launch_pid}" 2>/dev/null || true
  wait "${launch_pid}" 2>/dev/null || true
}
trap 'stop_launch; cleanup' EXIT

timeout 5s ros2 topic echo --once /mission/commands > "${output_dir}/mission_commands.yaml" 2>&1
timeout 5s ros2 topic echo --once /mission/status > "${output_dir}/mission_status.yaml" 2>&1
grep -q "command: MOVE_TO_TARGET" "${output_dir}/mission_commands.yaml"
grep -q "state: DISPATCHED" "${output_dir}/mission_status.yaml"
grep -q "algorithm=hungarian" "${output_dir}/launch.log"
grep -q "mission_status_count=" "${output_dir}/launch.log"

printf '{\n  "run_id": "%s",\n  "status": "passed",\n  "source_revision": "%s",\n  "source_tree": "git archive HEAD in temporary directory",\n  "environment_note": "same installed WSL dependencies; not a fresh OS image",\n  "checks": ["python_mission_simulation_tests", "fresh_workspace_colcon_build", "ros_assignment_adapter_test", "typed_mission_command", "typed_mission_status", "cpp_monitor"]\n}\n' \
  "${run_id}" "${source_revision}" > "${output_dir}/summary.json"
printf 'Clean-checkout reproduction passed. Artifacts: %s\n' "${output_dir}"
