#!/usr/bin/env bash
set -eo pipefail

run_id="${1:-G01_20260809_001}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workspace="${repo_root}/ros2_ws"
output_dir="${repo_root}/results/day4/${run_id}"
source_revision="$(git -C "${repo_root}" rev-parse HEAD)"
source_tracked_dirty=false
if command -v powershell.exe >/dev/null 2>&1; then
  host_repo_root="$(wslpath -w "${repo_root}")"
  source_revision="$(powershell.exe -NoProfile -Command "git -C '${host_repo_root}' rev-parse HEAD" | tr -d '\r')"
  host_tracked_status="$(powershell.exe -NoProfile -Command "git -C '${host_repo_root}' status --porcelain --untracked-files=no" | tr -d '\r')"
  if [[ -n "${host_tracked_status}" ]]; then
    source_tracked_dirty=true
  fi
elif ! git -C "${repo_root}" diff --quiet || ! git -C "${repo_root}" diff --cached --quiet; then
  source_tracked_dirty=true
fi

if [[ -e "${output_dir}" ]]; then
  echo "refusing to overwrite existing artifact directory: ${output_dir}" >&2
  exit 2
fi
if [[ ! -f /opt/ros/jazzy/setup.bash ]]; then
  echo "ROS 2 Jazzy is not installed at /opt/ros/jazzy" >&2
  exit 2
fi
if [[ ! -f "${workspace}/install/setup.bash" ]]; then
  echo "workspace is not built; run colcon build from ${workspace}" >&2
  exit 2
fi

mkdir -p "${output_dir}"
source /opt/ros/jazzy/setup.bash
source "${workspace}/install/setup.bash"
set -u

launch_log="${output_dir}/launch.log"
status_output="${output_dir}/mission_status.yaml"
targets_output="${output_dir}/targets.yaml"

ros2 launch multi_uav_bringup gate7_bringup.launch.py > "${launch_log}" 2>&1 &
launch_pid=$!

cleanup() {
  kill "${launch_pid}" 2>/dev/null || true
  wait "${launch_pid}" 2>/dev/null || true
}
trap cleanup EXIT

for attempt in 1 2 3 4 5; do
  if timeout 3s ros2 topic echo --once /mission/status > "${status_output}" 2>&1; then
    break
  fi
  sleep 1
done

timeout 5s ros2 topic echo --once /perception/targets > "${targets_output}" 2>&1
grep -q "state: DISPATCHED" "${status_output}"
grep -q "source_id: synthetic_gate7" "${targets_output}"
grep -q "mission_status_count=" "${launch_log}"

printf '{\n  "run_id": "%s",\n  "status": "passed",\n  "source_revision": "%s",\n  "source_tracked_dirty": %s,\n  "source_id": "synthetic_gate7",\n  "launch": "gate7_bringup.launch.py",\n  "checks": ["typed_target_array", "typed_mission_status", "cpp_monitor"]\n}\n' "${run_id}" "${source_revision}" "${source_tracked_dirty}" > "${output_dir}/summary.json"
printf 'Gate 7 smoke passed. Artifacts: %s\n' "${output_dir}"
