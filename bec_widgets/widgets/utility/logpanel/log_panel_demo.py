"""Realistic sample BEC logs for the log panel demo, screenshots and benchmarks.

Run ``python -m bec_widgets.widgets.utility.logpanel.log_panel_demo`` to compare the legacy panel,
the QWidget version and the QML version side by side with a live feed. No BEC server is needed.
"""

from __future__ import annotations

import random
import sys
import time

from bec_widgets.widgets.utility.logpanel.log_ux_common import LogEntry, LogFeedModel

SERVICES = [
    "ScanServer",
    "DeviceServer",
    "ScanBundler",
    "FileWriterManager",
    "SciHub",
    "DAPServer",
    "BECIPythonClient",
]

TRACEBACK = """Traceback (most recent call last):
  File "/opt/bec/bec_server/device_server/device_server.py", line 412, in _set_device
    status = obj.set(value)
  File "/opt/bec/ophyd_devices/sim/sim_positioner.py", line 188, in set
    self._check_limits(value)
  File "/opt/bec/ophyd_devices/sim/sim_positioner.py", line 131, in _check_limits
    raise LimitError(f"position={value} not within limits {self.limits}")
ophyd.utils.errors.LimitError: position=12.5 not within limits (-10, 10)"""

TRACEBACK_TIMEOUT = """Error while reading bpm4i: device did not answer
Traceback (most recent call last):
  File "/opt/bec/bec_server/device_server/devices/device_serializer.py", line 77, in read
    return self.obj.read()
  File "/opt/epics/ophyd/signal.py", line 1204, in read
    raise TimeoutError(f"{self.name} did not respond within {timeout} s")
TimeoutError: bpm4i did not respond within 2.0 s"""

_TEMPLATES = [
    ("INFO", "ScanServer", "Scan {scan} started: line_scan(samx, -5, 5, steps=50, exp_time=0.1)"),
    ("INFO", "ScanServer", "Scan {scan} finished in {dur:.1f} s"),
    ("INFO", "ScanBundler", "Emitting scan segment {point} of scan {scan}"),
    ("INFO", "DeviceServer", "samx moved to {pos:.3f} mm"),
    ("INFO", "DeviceServer", "samy moved to {pos:.3f} mm"),
    ("DEBUG", "DeviceServer", "Readback of bpm4i: {val:.4e}"),
    ("DEBUG", "ScanBundler", "Bundling point {point} for queue primary"),
    ("INFO", "FileWriterManager", "Writing /sls/x01da/data/S{scan:05d}.h5 ({point} points)"),
    ("SUCCESS", "FileWriterManager", "File /sls/x01da/data/S{scan:05d}.h5 written"),
    ("WARNING", "DeviceServer", "Readback of bpm4i is {lag} ms late"),
    ("WARNING", "SciHub", "SciLog is not reachable, retrying in 30 s"),
    ("INFO", "DAPServer", "Fit gaussian on bpm4i: center={pos:.3f}, sigma=0.41"),
    ("INFO", "BECIPythonClient", "User jan started a scan from the console"),
    ("DEBUG", "SciHub", "Heartbeat sent"),
]


def demo_specs(count: int = 400, end: float | None = None, seed: int = 4) -> list[tuple]:
    """Return ``(level, ts, service, message, function)`` tuples ending at ``end``."""
    rng = random.Random(seed)
    end = time.time() if end is None else end
    ts = end - count * 0.9
    scan = 1040
    specs: list[tuple] = []
    for i in range(count):
        ts += rng.uniform(0.2, 1.6)
        roll = rng.random()
        if i % 97 == 60:
            specs.append(("ERROR", ts, "DeviceServer", TRACEBACK, "_set_device"))
            continue
        if i % 131 == 90:
            specs.append(("ERROR", ts, "DeviceServer", TRACEBACK_TIMEOUT, "read"))
            continue
        if i % 173 == 120:
            specs.append(
                (
                    "CRITICAL",
                    ts,
                    "ScanServer",
                    "Scan queue halted: beam lost (ring current 0.0 mA)",
                    "halt",
                )
            )
            continue
        if i % 59 == 30:
            # a burst of identical messages, folded into one row with a counter
            for _ in range(rng.randint(3, 12)):
                ts += 0.2
                specs.append(("WARNING", ts, "DeviceServer", "Waiting for samy to settle", "wait"))
            continue
        if roll < 0.04:
            scan += 1
        level, service, template = _TEMPLATES[int(rng.random() * len(_TEMPLATES))]
        message = template.format(
            scan=scan,
            dur=rng.uniform(20, 300),
            point=rng.randint(0, 50),
            pos=rng.uniform(-5, 5),
            val=rng.uniform(1e3, 9e4),
            lag=rng.randint(150, 900),
        )
        specs.append((level, ts, service, message, "run"))
    return specs


def demo_entries(model: LogFeedModel, count: int = 400, end: float | None = None, seed: int = 4):
    """Build :class:`LogEntry` objects for ``model`` from :func:`demo_specs`."""
    return [
        LogEntry(model.next_seq(), level, ts, service, message, function)
        for level, ts, service, message, function in demo_specs(count, end, seed)
    ]


def main() -> None:  # pragma: no cover
    """Show the QWidget and QML versions side by side with a live feed."""
    # pylint: disable=import-outside-toplevel
    from qtpy.QtCore import QTimer
    from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget

    from bec_widgets.utils.colors import apply_theme
    from bec_widgets.widgets.utility.logpanel.log_panel_qml import LogPanelQml
    from bec_widgets.widgets.utility.logpanel.log_panel_qwidget import LogPanelQWidget
    from bec_widgets.widgets.utility.logpanel.log_ux_common import LogPanelBackend

    app = QApplication(sys.argv)
    apply_theme(sys.argv[1] if len(sys.argv) > 1 else "dark")
    window = QWidget()
    layout = QHBoxLayout(window)
    panels = []
    for cls in (LogPanelQWidget, LogPanelQml):
        backend = LogPanelBackend(use_queue=False)
        backend.ingest(demo_entries(backend.model, 600))
        panel = cls(backend=backend)
        backend.setParent(panel)
        layout.addWidget(panel)
        panels.append(panel)
    rng = random.Random(1)

    def feed():
        for panel in panels:
            spec = demo_specs(rng.randint(1, 4), seed=rng.randint(0, 9999))
            panel.backend.ingest([LogEntry(panel.backend.model.next_seq(), *s) for s in spec])

    timer = QTimer(window, interval=700)
    timer.timeout.connect(feed)
    timer.start()
    window.resize(1800, 700)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
