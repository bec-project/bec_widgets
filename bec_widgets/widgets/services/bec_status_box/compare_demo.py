"""Side-by-side demo of the QWidget and QML status box views, fed with simulated BEC services.

No BEC server or Redis is needed. Run with:

    python -m bec_widgets.widgets.services.bec_status_box.compare_demo

Both views sit in a BEC dock area (pass ``--plain`` for a simple splitter instead) and receive the
same simulated updates once per second, like the real widget. The control panel on the left sets
the state of every core service, adds or removes clients, and starts scripted scenarios.
"""

from __future__ import annotations

import argparse
import random
import sys
import tempfile
import time
from unittest import mock

from bec_lib.messages import (
    BECStatus,
    ServiceInfo,
    ServiceMetricMessage,
    ServiceVersions,
    StatusMessage,
)
from qtpy.QtCore import QObject, Qt, QTimer, Signal
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import apply_theme, get_theme_name
from bec_widgets.widgets.services.bec_status_box import bec_status_box
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox

STATES = ["Running", "Busy", "Idle", "Error", "Not connected"]
STATE_TO_BEC = {
    "Running": BECStatus.RUNNING,
    "Busy": BECStatus.BUSY,
    "Idle": BECStatus.IDLE,
    "Error": BECStatus.ERROR,
}
CURRENT_VERSION = "3.39.5"
OLD_VERSION = "3.38.1"


class SimulatedServices(QObject):
    """Stands in for BECServiceStatusMixin and emits simulated service updates."""

    services_update = Signal(dict, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.core_states = {name: "Running" for name in BECStatusBox.CORE_SERVICES}
        self.clients = 2
        self.gui_clients = 1
        self.dap_server = True
        self.old_client = False
        self.live_metrics = True
        self.start_times: dict[str, float] = {}
        self._tick = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.emit_update)
        self.timer.start(1000)

    def _info(self, user: str, host: str, version: str) -> ServiceInfo:
        versions = ServiceVersions(
            bec_lib=version,
            bec_server=version,
            bec_ipython_client=version,
            bec_widgets=CURRENT_VERSION,
            ophyd_devices="1.51.0",
        )
        return ServiceInfo(user=user, hostname=host, versions=versions)

    def _metrics(self, name: str, user: str, host: str, index: int) -> dict:
        now = time.time()
        started = self.start_times.setdefault(name, now - random.uniform(600, 3 * 86400))
        jitter = random.uniform(-2, 2) if self.live_metrics else 0
        return {
            "process_name": "python",
            "username": user,
            "hostname": host,
            "cpu_percent": max(0.0, 3.0 + index + jitter),
            "cpu_times": 12.0,
            "cmdline": ["python", name],
            "num_threads": 10 + index,
            "pid": 4100 + index,
            "memory_in_mb": 160.0 + 12 * index + jitter * 3,
            "memory_used_percent": 1.0,
            "create_time": started,
        }

    def snapshot(self) -> tuple[dict, dict]:
        """Build the services_info and services_metric dicts BEC would report now."""
        infos, metrics = {}, {}
        services = [(name, "x12sa", "x12sa-bec-01") for name in BECStatusBox.CORE_SERVICES]
        if self.dap_server:
            services.append(("DAPServer/9f3c2a1b", "x12sa", "x12sa-bec-01"))
        services += [
            (f"CLIBECClient/{i:02x}7a9e5c{i:04x}", "e12345", "x12sa-console-2")
            for i in range(self.clients)
        ]
        services += [
            (f"BECGuiClient/{i:02x}c0ffee{i:04x}", "e12345", "x12sa-console-2")
            for i in range(self.gui_clients)
        ]
        for index, (name, user, host) in enumerate(services):
            state = self.core_states.get(name, "Running")
            if state == "Not connected":
                continue
            version = (
                OLD_VERSION
                if self.old_client and name.startswith("CLIBECClient/00")
                else (CURRENT_VERSION)
            )
            infos[name] = StatusMessage(
                name=name, status=STATE_TO_BEC[state], info=self._info(user, host, version)
            )
            metrics[name] = ServiceMetricMessage(
                name=name, metrics=self._metrics(name, user, host, index)
            )
        return infos, metrics

    def simulate_restart(self, fail: bool = False) -> None:
        """Mimic SciHub restarting the server: core services drop out, then come back one by one.

        Args:
            fail (bool): Keep the scan bundler down, so the restart never finishes.
        """
        saved = dict(self.core_states)
        for name in BECStatusBox.CORE_SERVICES:
            self.core_states[name] = "Not connected"
        self.emit_update()

        def bring_back(index: int):
            name = BECStatusBox.CORE_SERVICES[index]
            if fail and name == "ScanBundler":
                return
            self.start_times[name] = time.time()
            self.core_states[name] = saved[name] if saved[name] != "Not connected" else "Running"
            self.emit_update()

        for index in range(len(BECStatusBox.CORE_SERVICES)):
            QTimer.singleShot(2500 + 900 * index, lambda i=index: bring_back(i))

    def emit_update(self) -> None:
        """Emit one update, like the real mixin does every second."""
        self._tick += 1
        self.services_update.emit(*self.snapshot())

    def cleanup(self):
        """Same interface as BECServiceStatusMixin."""


class TimedStatusBox(BECStatusBox):
    """BECStatusBox that records how long each update takes."""

    timing = Signal(float)

    def update_service_status(self, services_info, services_metric):
        start = time.perf_counter()
        super().update_service_status(services_info, services_metric)
        self.timing.emit((time.perf_counter() - start) * 1000)


class ControlPanel(QWidget):
    """Controls for every state and interaction of the simulated services."""

    def __init__(self, sim: SimulatedServices, boxes: dict[str, BECStatusBox], parent=None):
        super().__init__(parent)
        self.sim = sim
        self.boxes = boxes
        self.combos: dict[str, QComboBox] = {}
        layout = QVBoxLayout(self)

        core = QGroupBox("Core services")
        form = QFormLayout(core)
        for name in BECStatusBox.CORE_SERVICES:
            combo = QComboBox()
            combo.addItems(STATES)
            combo.currentTextChanged.connect(lambda state, n=name: self._set_state(n, state))
            self.combos[name] = combo
            form.addRow(name, combo)
        layout.addWidget(core)

        others = QGroupBox("Clients and other services")
        form = QFormLayout(others)
        self.clients = QSpinBox()
        self.clients.setRange(0, 60)
        self.clients.setValue(sim.clients)
        self.clients.valueChanged.connect(lambda v: self._set("clients", v))
        form.addRow("IPython clients", self.clients)
        self.gui_clients = QSpinBox()
        self.gui_clients.setRange(0, 10)
        self.gui_clients.setValue(sim.gui_clients)
        self.gui_clients.valueChanged.connect(lambda v: self._set("gui_clients", v))
        form.addRow("GUI clients", self.gui_clients)
        self.dap = QCheckBox("Data processing server")
        self.dap.setChecked(True)
        self.dap.toggled.connect(lambda v: self._set("dap_server", v))
        form.addRow(self.dap)
        self.old = QCheckBox("First client runs an old bec_lib")
        self.old.toggled.connect(lambda v: self._set("old_client", v))
        form.addRow(self.old)
        layout.addWidget(others)

        scenarios = QGroupBox("Scenarios")
        grid = QVBoxLayout(scenarios)
        for label, slot in (
            ("All healthy", self.all_healthy),
            ("Scan running (Scan server busy)", self.scan_running),
            ("One core service down", self.one_down),
            ("BEC stopped (all core down)", self.all_down),
            ("Services starting (all idle)", self.all_idle),
            ("Random incident", self.random_incident),
            ("Crowded beamline (40 clients)", self.crowded),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            grid.addWidget(button)
        self.flapping = QCheckBox("Flapping: random changes every 2 s")
        self.flap_timer = QTimer(self)
        self.flap_timer.timeout.connect(self.random_incident)
        self.flapping.toggled.connect(
            lambda on: self.flap_timer.start(2000) if on else self.flap_timer.stop()
        )
        grid.addWidget(self.flapping)
        self.restart_fails = QCheckBox("Server restart fails (Scan bundler stays down)")
        grid.addWidget(self.restart_fails)
        grid.addWidget(QLabel("Restart: use the button in either view's header."))
        layout.addWidget(scenarios)

        view = QGroupBox("Look")
        form = QFormLayout(view)
        self.live = QCheckBox("Live CPU and memory numbers")
        self.live.setChecked(True)
        self.live.toggled.connect(lambda v: self._set("live_metrics", v))
        form.addRow(self.live)
        self.paused = QCheckBox("Pause updates")
        self.paused.toggled.connect(lambda on: sim.timer.stop() if on else sim.timer.start(1000))
        form.addRow(self.paused)
        theme = QPushButton("Toggle dark / light theme")
        theme.clicked.connect(
            lambda: apply_theme("light" if get_theme_name() == "dark" else "dark")
        )
        form.addRow(theme)
        self.compact = QCheckBox("Compact mode (LED + popup button)")
        self.compact.toggled.connect(self._set_compact)
        form.addRow(self.compact)
        layout.addWidget(view)

        timing = QGroupBox("Last update time")
        form = QFormLayout(timing)
        for kind, box in boxes.items():
            label = QLabel("–")
            box.timing.connect(lambda ms, lab=label: lab.setText(f"{ms:.2f} ms"))
            form.addRow(kind, label)
        layout.addWidget(timing)
        layout.addStretch()

    def _push(self):
        self.sim.emit_update()

    def _set(self, attr: str, value):
        setattr(self.sim, attr, value)
        self._push()

    def _set_state(self, name: str, state: str):
        self.sim.core_states[name] = state
        self._push()

    def _apply_states(self, states: dict[str, str]):
        for name, state in states.items():
            combo = self.combos[name]
            combo.blockSignals(True)
            combo.setCurrentText(state)
            combo.blockSignals(False)
            self.sim.core_states[name] = state
        self._push()

    def _set_compact(self, compact: bool):
        for box in self.boxes.values():
            box.compact_view = compact

    def all_healthy(self):
        self._apply_states({name: "Running" for name in BECStatusBox.CORE_SERVICES})

    def scan_running(self):
        states = {name: "Running" for name in BECStatusBox.CORE_SERVICES}
        states["ScanServer"] = "Busy"
        self._apply_states(states)

    def one_down(self):
        states = {name: "Running" for name in BECStatusBox.CORE_SERVICES}
        states["ScanBundler"] = "Not connected"
        self._apply_states(states)

    def all_down(self):
        self._apply_states({name: "Not connected" for name in BECStatusBox.CORE_SERVICES})

    def all_idle(self):
        self._apply_states({name: "Idle" for name in BECStatusBox.CORE_SERVICES})

    def random_incident(self):
        states = {name: "Running" for name in BECStatusBox.CORE_SERVICES}
        for name in random.sample(BECStatusBox.CORE_SERVICES, random.randint(0, 2)):
            states[name] = random.choice(STATES[1:])
        self._apply_states(states)

    def crowded(self):
        self.clients.setValue(40)


class CompareWindow(QMainWindow):
    """Main window with the control panel and both views."""

    def __init__(self, plain: bool = False):
        super().__init__()
        self.setWindowTitle("BEC status box: QWidget vs QML")
        self.sim = SimulatedServices(self)
        client = mock.MagicMock()
        client.connector.send.side_effect = self._on_send
        bec_status_box.RESTART_TIMEOUT_S = 20  # a failed restart shows up quickly in the demo
        self.boxes = {
            "QWidget": TimedStatusBox(
                client=client, bec_service_status_mixin=self.sim, view="widgets"
            ),
            "QML": TimedStatusBox(client=client, bec_service_status_mixin=self.sim, view="qml"),
        }
        controls = ControlPanel(self.sim, self.boxes)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(controls)
        scroll.setMinimumWidth(320)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(scroll)
        if plain:
            for kind, box in self.boxes.items():
                column = QWidget()
                col_layout = QVBoxLayout(column)
                title = QLabel(kind)
                title.setStyleSheet("font-weight: bold;")
                col_layout.addWidget(title)
                col_layout.addWidget(box, 1)
                splitter.addWidget(column)
        else:
            # pylint: disable=import-outside-toplevel
            from bec_widgets.widgets.containers.dock_area import profile_utils
            from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea

            # without a running BEC there is no client config for the profile folder
            profiles = tempfile.mkdtemp(prefix="status_box_demo_profiles_")
            profile_utils._settings_profiles_root = lambda: profiles  # pylint: disable=W0212

            self.dock_area = BECDockArea(
                mode="utils",
                profile_namespace="status_box_compare_demo",
                auto_save_upon_exit=False,
                enable_profile_management=False,
            )
            for box in self.boxes.values():
                self.dock_area.new(box, where="right")
            for dock in self.dock_area.dock_list():
                for kind, box in self.boxes.items():
                    if dock.widget() is box:
                        dock.setWindowTitle(f"{kind} view")
            splitter.addWidget(self.dock_area)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self.resize(1250, 780)
        self.sim.emit_update()

    def _on_send(self, endpoint, msg):
        if getattr(msg, "action", None) == "restart":
            fail = self.findChild(ControlPanel).restart_fails.isChecked()
            self.sim.simulate_restart(fail=fail)

    def closeEvent(self, event):
        self.sim.timer.stop()
        for box in self.boxes.values():
            box.cleanup()
        super().closeEvent(event)


def main():  # pragma: no cover
    """Start the demo."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plain", action="store_true", help="splitter instead of a dock area")
    parser.add_argument("--theme", choices=["dark", "light"], default="dark")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(args.theme)
    window = CompareWindow(plain=args.plain)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
