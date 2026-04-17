#!/usr/bin/env bash
# BENCHMARK_TITLE: BEC IPython client without companion app
set -euo pipefail

bec --nogui --post-startup-file tests/benchmarks/hyperfine/utils/exit_bec_startup.py
