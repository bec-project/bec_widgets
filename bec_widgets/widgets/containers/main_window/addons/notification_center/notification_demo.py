"""Demo window for the reworked notifications, used for screenshots and side-by-side checks.

Run this module with ``--variant qml`` or ``--variant qwidget`` (``python -m
bec_widgets.widgets.containers.main_window.addons.notification_center.notification_demo``).
No BEC server is needed: the buttons post sample
notifications and raise errors inside ``SafeSlot(popup_error=True)`` slots.
"""

from __future__ import annotations

import argparse
import sys
import traceback

import numpy as np
import pyqtgraph as pg
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_ux_common import (
    NotificationHub,
    Severity,
)

SAMPLE_TRACE = """Traceback (most recent call last):
  File "/opt/bec/bec_server/device_server/devices/devicemanager.py", line 412, in stage
    status = obj.stage()
  File "/opt/bec/ophyd_devices/devices/eiger9m.py", line 233, in on_stage
    self.cam.acquire.set(1).wait(timeout=10)
  File "/opt/bec/ophyd/status.py", line 336, in wait
    raise WaitTimeoutError(f"Status {self!r} has not completed yet.")
ophyd.utils.errors.WaitTimeoutError: Status DeviceStatus(device=eiger9m_cam_acquire) has not completed yet.

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/opt/bec/bec_server/scan_server/scan_worker.py", line 289, in _stage_devices
    self.device_manager.stage(devices, timeout=10)
bec_lib.alarm_handler.DeviceTimeoutError: Device eiger9m did not respond within 10 s while staging."""


def post_samples(hub: NotificationHub) -> None:
    """Fill the hub with a realistic mix of notifications for screenshots."""
    hub.notify(
        "Scan 1042 finished",
        "line_scan over samx, 101 points in 2 min 13 s.",
        Severity.SUCCESS,
        source="Scan queue",
        scan_number=1042,
    )
    hub.notify(
        "Profile saved",
        "Workspace 'alignment' was saved to the beamline profiles.",
        Severity.INFO,
        source="Workspace",
    )
    hub.notify(
        "Ring current low",
        "Ring current dropped to 180 mA (threshold 200 mA). Data may be noisy.",
        Severity.WARNING,
        source="Beamline states",
    )
    trace = ""
    try:
        raise ValueError("Target 12.5 is outside the soft limits [-10, 10] of samx.")
    except ValueError:
        trace = traceback.format_exc()
    for _ in range(3):
        hub.report_exception("Method error", trace, source="PositionerBox.move")
    hub.post_alarm(
        {
            "severity": 2,
            "alarm_type": "DeviceTimeoutError",
            "msg": SAMPLE_TRACE,
            "info": {
                "id": "demo-critical",
                "error_message": SAMPLE_TRACE,
                "compact_error_message": "Device eiger9m did not respond within 10 s while"
                " staging. The scan was aborted.",
                "exception_type": "DeviceTimeoutError",
                "device": "eiger9m",
            },
        },
        {"scan_number": 1043, "scan_id": "4f0d6c1e-7a51-4b0c-9a59-2f9a3d1c2b77"},
    )


class DemoWindow(QMainWindow):
    """Window that looks like the BEC app, with buttons that produce notifications."""

    def __init__(self, variant: str = "qwidget"):
        super().__init__()
        self.setWindowTitle(f"BEC notifications ({variant})")
        self.resize(1180, 720)
        self.menuBar().addMenu("File")
        self.menuBar().addMenu("View")
        self.menuBar().addMenu("Help")
        toolbar = QToolBar("Main", self)
        for label in ("Dock area", "Device manager", "Scan control"):
            toolbar.addAction(label)
        self.addToolBar(toolbar)

        central = QWidget(self)
        layout = QHBoxLayout(central)
        controls = QVBoxLayout()
        self.hub = NotificationHub.instance()
        for label, slot in (
            ("Info", lambda: self.hub.notify("Profile saved", "Workspace saved.", "info")),
            ("Success", lambda: self.hub.notify("Scan finished", "101 points.", "success")),
            ("Warning", lambda: self.hub.notify("Ring current low", "180 mA.", "warning")),
            ("Error in a slot", self.failing_slot),
            ("Critical alarm", self.critical),
            ("Burst of 20 errors", self.burst),
            ("Toggle theme", self.toggle_theme),
        ):
            button = QPushButton(label, central)
            button.clicked.connect(slot)
            controls.addWidget(button)
        controls.addStretch(1)
        layout.addLayout(controls)
        plot = pg.PlotWidget(central)
        x = np.linspace(-5, 5, 400)
        plot.plot(x, np.exp(-(x**2) / 2) + 0.05 * np.sin(9 * x), pen=pg.mkPen("#3b82f6", width=2))
        plot.showGrid(x=True, y=True, alpha=0.2)
        layout.addWidget(plot, 1)
        self.setCentralWidget(central)
        self.statusBar().addWidget(QLabel("Ready · account p12345"))

        if variant == "qml":
            from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_qml import (
                NotificationHostQML as Host,
            )
        else:
            from bec_widgets.widgets.containers.main_window.addons.notification_center.notification_qwidget import (
                NotificationHostQWidget as Host,
            )
        self.notifications = Host(self)

    @SafeSlot(popup_error=True)
    def failing_slot(self):
        """Raise inside a SafeSlot: shows a toast instead of a modal dialog."""
        raise ValueError("Target 12.5 is outside the soft limits [-10, 10] of samx.")

    def critical(self):
        """Post a critical alarm with a long traceback."""
        self.hub.post_alarm(
            {
                "severity": 2,
                "alarm_type": "DeviceTimeoutError",
                "msg": SAMPLE_TRACE,
                "info": {
                    "id": None,
                    "error_message": SAMPLE_TRACE,
                    "compact_error_message": "Device eiger9m did not respond within 10 s.",
                    "exception_type": "DeviceTimeoutError",
                    "device": "eiger9m",
                },
            },
            {"scan_number": 1043},
        )

    def burst(self):
        """Post many different errors at once; the stack shows three and counts the rest."""
        for i in range(20):
            self.hub.notify(f"Readback failed for motor{i}", "Timeout after 2 s.", "error")

    def toggle_theme(self):
        """Switch between the light and dark theme."""
        theme = getattr(QApplication.instance(), "theme", None)
        apply_theme("light" if theme is not None and theme.theme == "dark" else "dark")

    def closeEvent(self, event):  # pylint: disable=invalid-name
        """Detach the notification UI."""
        self.notifications.cleanup()
        super().closeEvent(event)


def main(variant: str | None = None) -> None:  # pragma: no cover
    """Start the demo."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("qml", "qwidget"), default=variant or "qwidget")
    parser.add_argument("--theme", choices=("dark", "light"), default="dark")
    parser.add_argument("--samples", action="store_true", help="start with sample notifications")
    args = parser.parse_args()
    app = QApplication(sys.argv)
    apply_theme(args.theme)
    window = DemoWindow(args.variant)
    window.show()
    if args.samples:
        post_samples(window.hub)
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
