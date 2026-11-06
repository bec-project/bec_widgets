#!/usr/bin/env bash
# Launch the error dialog demo with sample errors already raised.
#
# Usage: launch_error_dialog_demo.sh [qwidget|qml|legacy|all] [dark|light]
#   all      opens the QWidget, QML and old (legacy) versions side by side
#   PYTHON   environment variable to pick the interpreter (default: python)
#
# Run it from an environment where this bec_widgets checkout is installed (pip install -e .).
set -euo pipefail

ui="${1:-qwidget}"
theme="${2:-dark}"
python="${PYTHON:-python}"
module="bec_widgets.utils.error_dialog.error_dialog_demo"

case "$ui" in
  qwidget|qml|legacy)
    exec "$python" -m "$module" "$ui" --theme "$theme" --fire
    ;;
  all)
    pids=()
    for variant in legacy qwidget qml; do
      "$python" -m "$module" "$variant" --theme "$theme" --fire &
      pids+=("$!")
    done
    trap 'kill "${pids[@]}" 2>/dev/null' INT TERM
    wait
    ;;
  *)
    echo "usage: $0 [qwidget|qml|legacy|all] [dark|light]" >&2
    exit 2
    ;;
esac
