"""
Side-by-side comparison of the scan progress bar: today's widget, the QML port and the QWidget
version with the same UX. A simulated scan runs through every state; no BEC server is needed.

Run with: python -m bec_widgets.examples.scan_progress_compare [--light]
"""

import sys
import time
from unittest import mock

from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QApplication, QGridLayout, QLabel, QPushButton, QWidget

from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar import ScanProgressBar
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar_modern import (
    ScanProgressBarModern,
)
from bec_widgets.widgets.progress.scan_progressbar.scan_progressbar_qml import ScanProgressBarQml

POINTS = 60

# (status sent with the progress messages, points to advance, final scan status or None)
SCRIPT = [("open", 0, None)] * 3 + [("open", 1, None)] * 25 + [("paused", 0, None)] * 6
SCRIPT += [("open", 1, None)] * 20 + [("open", 0, "halted")] * 6 + [("open", 1, None)] * POINTS


class Demo(QWidget):
    """Drives all bars with the same simulated scan."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scan progress: today vs QML vs QWidget")
        client = mock.MagicMock()
        grid = QGridLayout(self)
        grid.setHorizontalSpacing(18)
        self.bars = []
        for col, (name, cls) in enumerate(
            [
                ("Today", ScanProgressBar),
                ("QML", ScanProgressBarQml),
                ("QWidget", ScanProgressBarModern),
            ]
        ):
            grid.addWidget(QLabel(f"<b>{name}</b>"), 0, col)
            for row, compact in enumerate((False, True)):
                bar = cls(client=client, one_line_design=compact, rpc_exposed=False)
                bar.setMinimumWidth(320)
                grid.addWidget(bar, row + 1, col)
                self.bars.append(bar)
        restart = QPushButton("Restart scan")
        restart.clicked.connect(self.start)
        grid.addWidget(restart, 3, 0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step)
        self.scan = 0
        self.start()

    def start(self):
        self.scan += 1
        self.value = 0
        self.index = 0
        self.scan_id = f"scan-{self.scan}"
        for bar in self.bars:
            model = getattr(bar, "model", None)
            if model is not None:
                model._on_scan_status(
                    {
                        "scan_id": self.scan_id,
                        "status": "open",
                        "scan_name": "line_scan",
                        "scan_number": self.scan,
                    },
                    {},
                )
        self.timer.start(250)

    def step(self):
        if self.index >= len(SCRIPT):
            self.timer.stop()
            return
        status, advance, final = SCRIPT[self.index]
        self.index += 1
        self.value = min(POINTS, self.value + advance)
        max_value = 0 if self.index <= 3 else POINTS
        done = self.value >= POINTS
        for bar in self.bars:
            if final and getattr(bar, "model", None) is not None:
                bar.model._on_scan_status({"scan_id": self.scan_id, "status": final}, {})
                continue
            bar.progress_tracker.process_progress_message(
                {"value": self.value, "max_value": max_value, "done": done},
                {
                    "scan_id": self.scan_id,
                    "RID": self.scan_id,
                    "status": final or status,
                    "scan_number": self.scan,
                },
            )
        if final:
            self.timer.stop()
            QTimer.singleShot(2000, self.start)
        elif done:
            self.timer.stop()


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    apply_theme("light" if "--light" in sys.argv else "dark")
    demo = Demo()
    demo.show()
    sys.exit(app.exec())
