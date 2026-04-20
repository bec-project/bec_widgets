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
source ./bin/install_bec_dev.sh
cd ..

python -m pip install -e ./ophyd_devices -e .[dev,pyside6] -e ./bec_testing_plugin

benchmark_tmp_dir="$(mktemp -d)"
export BEC_SERVICE_CONFIG="$benchmark_tmp_dir/services_config.yaml"

# Start Redis
redis-server --daemonize yes --port 6379

# Wait for Redis to be ready
timeout 30 bash -c 'until redis-cli ping > /dev/null 2>&1; do sleep 0.1; done' || {
  echo "Redis failed to start" >&2
  exit 1
}

# Start BEC server
bec-server start --config "$BEC_SERVICE_CONFIG"

# Wait for BEC server to be ready
sleep 5

# Export BEC client configuration
export BEC_CONFIG='{"redis": {"host": "localhost", "port": 6379}}'

