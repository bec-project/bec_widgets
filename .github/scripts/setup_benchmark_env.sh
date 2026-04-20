#!/usr/bin/env bash
set -euo pipefail

bec_core_branch="${BEC_CORE_BRANCH:-main}"
ophyd_devices_branch="${OPHYD_DEVICES_BRANCH:-main}"
plugin_repo_branch="${PLUGIN_REPO_BRANCH:-main}"
python_version="${PYTHON_VERSION:-3.11}"

if command -v conda >/dev/null 2>&1; then
  conda_base="$(conda info --base)"
  source "$conda_base/etc/profile.d/conda.sh"
fi

echo "Using branch ${bec_core_branch} of BEC CORE"
git clone --branch "$bec_core_branch" https://github.com/bec-project/bec.git

echo "Using branch ${ophyd_devices_branch} of OPHYD_DEVICES"
git clone --branch "$ophyd_devices_branch" https://github.com/bec-project/ophyd_devices.git

echo "Using branch ${plugin_repo_branch} of bec_testing_plugin"
git clone --branch "$plugin_repo_branch" https://github.com/bec-project/bec_testing_plugin.git

conda create -q -n test-environment "python=${python_version}"
conda activate test-environment

cd bec
source ./bin/install_bec_dev.sh -t
cd ..

python -m pip install -e ./ophyd_devices -e .[dev,pyside6] -e ./bec_testing_plugin

benchmark_tmp_dir="$(mktemp -d)"
export BEC_SERVICE_CONFIG="$benchmark_tmp_dir/services_config.yaml"
ready_file="$benchmark_tmp_dir/ready"
supervisor_log="$benchmark_tmp_dir/bec-benchmark-services.log"

python .github/scripts/start_bec_benchmark_services.py \
  --files-path "$benchmark_tmp_dir" \
  --services-config "$BEC_SERVICE_CONFIG" \
  --ready-file "$ready_file" \
  > "$supervisor_log" 2>&1 &
supervisor_pid=$!

cleanup_benchmark_services() {
  if kill -0 "$supervisor_pid" >/dev/null 2>&1; then
    kill "$supervisor_pid"
    wait "$supervisor_pid" || true
  fi
  rm -rf "$benchmark_tmp_dir"
}
trap cleanup_benchmark_services EXIT

deadline=$((SECONDS + 30))
while [ ! -f "$ready_file" ]; do
  if ! kill -0 "$supervisor_pid" >/dev/null 2>&1; then
    cat "$supervisor_log" >&2 || true
    echo "BEC benchmark service supervisor exited before becoming ready" >&2
    exit 1
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    cat "$supervisor_log" >&2 || true
    echo "Timed out waiting for BEC benchmark services" >&2
    exit 1
  fi
  sleep 0.2
done

cat "$supervisor_log"
echo "BEC_SERVICE_CONFIG=$BEC_SERVICE_CONFIG" >> "$GITHUB_ENV"
