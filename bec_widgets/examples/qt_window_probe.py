"""Probe window visibility from a terminal using only Qt, without starting BEC.

Run this file directly with the affected environment's Python interpreter.
Enter ``cycle`` repeatedly to hide/show a plain QWidget in one event-loop callback.
Compare with separate ``hide`` and ``show`` commands and with ``raise``.
"""

import json
import os
import sys

from qtpy import API_NAME
from qtpy.QtCore import QSocketNotifier, QTimer, qVersion
from qtpy.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget


def main() -> int:
    """Run a plain Qt window controlled through standard input on macOS or Linux."""
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Qt window visibility probe")
    window.resize(800, 600)
    layout = QVBoxLayout(window)
    layout.addWidget(QLabel("Control this plain Qt window from the terminal."))
    window.show()
    handle = window.windowHandle()
    command_number = 0

    print(
        json.dumps(
            {
                "pid": os.getpid(),
                "python": sys.executable,
                "qt_binding": API_NAME,
                "qt_version": qVersion(),
                "qt_platform": app.platformName(),
                "session_type": os.environ.get("XDG_SESSION_TYPE"),
                "desktop": os.environ.get("XDG_CURRENT_DESKTOP"),
            }
        ),
        flush=True,
    )
    print("Commands: cycle, hide, show, raise, state, quit", flush=True)

    def report(stage: str, number: int) -> None:
        print(
            json.dumps(
                {
                    "command": number,
                    "stage": stage,
                    "visible": window.isVisible(),
                    "native_visible": handle.isVisible(),
                    "active": window.isActiveWindow(),
                    "exposed": handle.isExposed(),
                    "minimized": window.isMinimized(),
                }
            ),
            flush=True,
        )

    notifier = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Type.Read, window)

    def read_command() -> None:
        nonlocal command_number
        line = sys.stdin.readline()
        if not line or line.strip() == "quit":
            notifier.setEnabled(False)
            app.quit()
            return
        command = line.strip()
        command_number += 1
        number = command_number
        report(f"before {command}", number)
        if command == "cycle":
            window.hide()
            window.show()
        elif command == "hide":
            window.hide()
        elif command == "show":
            window.show()
        elif command == "raise":
            window.raise_()
            window.activateWindow()
        elif command != "state":
            print(f"Unknown command: {command}", flush=True)
            return
        report(f"after {command}", number)
        # Observe settled state; this timer does not alter the window or delay the operation.
        QTimer.singleShot(250, window, lambda: report(f"250ms after {command}", number))

    notifier.activated.connect(read_command)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
