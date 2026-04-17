#!/usr/bin/env bash
# BENCHMARK_TITLE: BEC IPython client with companion app
set -euo pipefail

bec --post-startup-file tests/benchmarks/hyperfine/utils/exit_bec_startup.py
