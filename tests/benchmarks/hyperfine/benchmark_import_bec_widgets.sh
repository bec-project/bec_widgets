#!/usr/bin/env bash
# BENCHMARK_TITLE: Import bec_widgets
set -euo pipefail

python -c 'import bec_widgets; print(bec_widgets.__file__)'
