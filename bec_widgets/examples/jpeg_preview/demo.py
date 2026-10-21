"""
JPEG live preview demo: the BEC Image widget and a picture-only view side by side, fed by the
simulated JPEG camera (ophyd_devices.sim.sim_jpeg_camera.SimJpegCamera).

Run against a BEC with the camera loaded:

    python -m bec_widgets.examples.jpeg_preview.demo --device jpeg_cam

The top bar changes the camera stream while it runs (size, JPEG or raw, quality, rate, 8-bit
scaling). The bottom table shows, per view, what each frame costs. "Run benchmark" sweeps sizes,
encodings and views and saves the results as CSV and JSON.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import statistics
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, Qt, QTimer, Signal
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.examples.jpeg_preview.jpeg_view import JpegView
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.plots.image.image import Image

logger = bec_logger.logger

RESOLUTIONS = {
    "512 x 512": (512, 512),
    "1024 x 1024": (1024, 1024),
    "2048 x 2048": (2048, 2048),
    "2068 x 2162 (Eiger 4M)": (2068, 2162),
    "3108 x 3262 (Eiger 9M)": (3108, 3262),
    "4096 x 4096": (4096, 4096),
    "Custom": None,
}
ENCODINGS = {"JPEG gray": "jpeg_gray", "JPEG colour (colormapped)": "jpeg_rgb", "Raw uint16": "raw"}
STAT_COLUMNS = (
    "frames/s shown",
    "frames/s sent",
    "dropped %",
    "frame KB",
    "vs raw",
    "encode ms (device)",
    "decode ms (receiver thread)",
    "GUI ms per frame",
    "GUI busy %",
    "latency ms",
    "GUI stall ms (max)",
)


class TimedImage(Image):
    """Image widget that records how long its update slot takes."""

    frame_timed = Signal(dict, float)

    @SafeSlot(dict, dict)
    def on_image_update_2d(self, msg: dict, metadata: dict):
        t0 = time.perf_counter()
        super().on_image_update_2d(msg, metadata)
        # Paint now, so the measured time is the whole cost of showing this frame
        self.plot_widget.viewport().repaint()
        self.frame_timed.emit(metadata, t0)


@dataclass
class FrameSample:
    """What one displayed frame cost."""

    t_shown: float
    frame_id: int
    transfer_nbytes: int
    raw_nbytes: int
    encode_ms: float
    decode_ms: float
    gui_ms: float
    latency_ms: float


@dataclass
class StatsTracker:
    """Rolling statistics of one view."""

    window_s: float = 3.0
    samples: deque = field(default_factory=lambda: deque(maxlen=2000))

    def add(self, sample: FrameSample) -> None:
        """Add one displayed frame."""
        self.samples.append(sample)

    def clear(self) -> None:
        """Forget all samples."""
        self.samples.clear()

    def summary(self, since: float | None = None) -> dict:
        """
        Summarise the samples of the last window (or since a time).

        Args:
            since (float | None): perf_counter time to start from; default is the rolling window.

        Returns:
            dict: One value per STAT_COLUMNS entry, empty if there are no samples.
        """
        now = time.perf_counter()
        start = since if since is not None else now - self.window_s
        rows = [s for s in self.samples if s.t_shown >= start]
        if len(rows) < 2:
            return {}
        span = max(1e-6, rows[-1].t_shown - rows[0].t_shown)
        ids = [r.frame_id for r in rows]
        sent = max(1, ids[-1] - ids[0])
        med = statistics.median
        transfer = med(r.transfer_nbytes for r in rows)
        raw = med(r.raw_nbytes for r in rows)
        return {
            "frames/s shown": (len(rows) - 1) / span,
            "frames/s sent": sent / span,
            "dropped %": max(0.0, 100.0 * (1 - (len(rows) - 1) / sent)),
            "frame KB": transfer / 1e3,
            "vs raw": raw / transfer if transfer else 0.0,
            "encode ms (device)": med(r.encode_ms for r in rows),
            "decode ms (receiver thread)": med(r.decode_ms for r in rows),
            "GUI ms per frame": med(r.gui_ms for r in rows),
            "latency ms": med(r.latency_ms for r in rows),
            "GUI busy %": 100.0 * sum(r.gui_ms for r in rows[1:]) / 1e3 / span,
        }


class EventLoopProbe(QObject):
    """Measures how late a 20 ms timer fires: how long the GUI thread was blocked."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._interval = 0.02
        self._last = time.perf_counter()
        self.stalls: deque = deque(maxlen=1000)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(int(self._interval * 1000))

    def _tick(self):
        now = time.perf_counter()
        self.stalls.append((now, max(0.0, (now - self._last - self._interval) * 1e3)))
        self._last = now

    def max_stall(self, since: float) -> float:
        """Longest stall since a perf_counter time, in ms."""
        values = [s for t, s in self.stalls if t >= since]
        return max(values) if values else 0.0


class CameraControl(QWidget):
    """Top bar that changes the simulated camera's stream while it runs."""

    settings_received = Signal(dict)
    rpc_failed = Signal(str)

    def __init__(self, dev, device: str, parent=None):
        super().__init__(parent)
        self._dev = dev
        self._device = device
        self._applying = False

        self.live_button = QPushButton("Stop live", self)
        self.live_button.setCheckable(True)
        self.live_button.setChecked(True)
        self.live_button.toggled.connect(self._on_live_toggled)
        self.resolution_box = QComboBox(self)
        self.resolution_box.addItems(RESOLUTIONS)
        self.width_spin = self._spin(16, 8192, 2048, " px")
        self.height_spin = self._spin(16, 8192, 2048, " px")
        self.encoding_box = QComboBox(self)
        self.encoding_box.addItems(ENCODINGS)
        self.quality_spin = self._spin(1, 100, 90, "")
        self.rate_spin = QDoubleSpinBox(self)
        self.rate_spin.setRange(0.1, 100)
        self.rate_spin.setValue(5)
        self.rate_spin.setSuffix(" Hz")
        self.max_counts_spin = self._spin(0, 65535, 0, "")
        self.max_counts_spin.setSpecialValueText("auto")
        self.max_counts_spin.setToolTip("Counts mapped to 255 in JPEG modes; auto = 99.9th pct")
        self.status_label = QLabel("", self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        for label, widget in (
            (None, self.live_button),
            ("Preview size", self.resolution_box),
            (None, self.width_spin),
            ("x", self.height_spin),
            ("Encoding", self.encoding_box),
            ("JPEG quality", self.quality_spin),
            ("Rate", self.rate_spin),
            ("255 =", self.max_counts_spin),
        ):
            if label:
                layout.addWidget(QLabel(label, self))
            layout.addWidget(widget)
        layout.addStretch(1)
        layout.addWidget(self.status_label)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self.apply)
        self.resolution_box.currentTextChanged.connect(self._on_preset)
        for spin in (self.width_spin, self.height_spin, self.quality_spin, self.max_counts_spin):
            spin.valueChanged.connect(self._schedule)
        self.rate_spin.valueChanged.connect(self._schedule)
        self.encoding_box.currentTextChanged.connect(self._schedule)
        self.settings_received.connect(self._show_settings)
        self.rpc_failed.connect(lambda text: self.status_label.setText(f"Error: {text}"))
        self.resolution_box.setCurrentText("2048 x 2048")

    def _spin(self, low: int, high: int, value: int, suffix: str) -> QSpinBox:
        spin = QSpinBox(self)
        spin.setRange(low, high)
        spin.setValue(value)
        spin.setSuffix(suffix)
        spin.setKeyboardTracking(False)
        return spin

    @SafeSlot(str)
    def _on_preset(self, text: str):
        size = RESOLUTIONS.get(text)
        custom = size is None
        self.width_spin.setEnabled(custom)
        self.height_spin.setEnabled(custom)
        if size:
            self._applying = True
            self.width_spin.setValue(size[0])
            self.height_spin.setValue(size[1])
            self._applying = False
        self._schedule()

    def _schedule(self, *_):
        if not self._applying:
            self._debounce.start()

    def current_settings(self) -> dict:
        """The settings shown in the bar."""
        return {
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "encoding": ENCODINGS[self.encoding_box.currentText()],
            "quality": self.quality_spin.value(),
            "frame_rate": self.rate_spin.value(),
            "max_counts": float(self.max_counts_spin.value()),
        }

    def set_settings(self, **settings) -> None:
        """Change the bar (and so the camera) programmatically, e.g. from the benchmark."""
        self._applying = True
        if "width" in settings or "height" in settings:
            self.resolution_box.setCurrentText("Custom")
            self.width_spin.setValue(settings.get("width", self.width_spin.value()))
            self.height_spin.setValue(settings.get("height", self.height_spin.value()))
        if "encoding" in settings:
            label = {v: k for k, v in ENCODINGS.items()}[settings["encoding"]]
            self.encoding_box.setCurrentText(label)
        if "quality" in settings:
            self.quality_spin.setValue(settings["quality"])
        if "frame_rate" in settings:
            self.rate_spin.setValue(settings["frame_rate"])
        self._applying = False
        self.apply()

    def _call_device(self, method: str, **kwargs):
        """Call a device method off the GUI thread; the RPC waits for the device server."""

        def run():
            try:
                result = getattr(self._dev[self._device], method)(**kwargs)
                if isinstance(result, dict):
                    self.settings_received.emit(result)
            except Exception as exc:  # pylint: disable=broad-except
                self.rpc_failed.emit(str(exc))

        threading.Thread(target=run, daemon=True).start()

    @SafeSlot()
    def apply(self):
        """Send the bar's settings to the camera."""
        self.status_label.setText("Applying…")
        self._call_device("configure_stream", **self.current_settings())

    @SafeSlot(bool)
    def _on_live_toggled(self, live: bool):
        self.live_button.setText("Stop live" if live else "Start live")
        self._call_device("start_live" if live else "stop_live")

    @SafeSlot(dict)
    def _show_settings(self, settings: dict):
        self.status_label.setText(
            f"camera: {settings['width']} x {settings['height']}, {settings['encoding']}"
        )


class JpegPreviewDemo(QMainWindow):
    """Main window of the demo."""

    def __init__(self, device: str, signal: str = "preview", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"JPEG live preview: {device}.{signal}")
        self.device = device

        self.image = TimedImage(parent=self, popups=False)
        self.image.enable_colorbar(enabled=True, style="full")
        self.jpeg_view = JpegView(parent=self)
        self.control = CameraControl(self.image.dev, device, parent=self)
        self.probe = EventLoopProbe(self)
        self.trackers = {"Image widget": StatsTracker(), "Picture view": StatsTracker()}

        self.image_check = QCheckBox("BEC Image widget (JPEG decoded to numpy)", self)
        self.view_check = QCheckBox("Picture view (Qt decodes JPEG, no data)", self)
        for check in (self.image_check, self.view_check):
            check.setChecked(True)
        self.image_check.toggled.connect(lambda on: self.enable_view("Image widget", on))
        self.fast_check = QCheckBox("Fast 8-bit path", self)
        self.fast_check.setToolTip(
            "On: JPEG frames are drawn as 8-bit images with a fixed 0-255 range and no per-frame"
            " statistics.\nOff: the normal Image widget path (statistics and mean +/- 2 std"
            " autorange on every frame)."
        )
        self.fast_check.setChecked(self.image.fast_8bit_preview)
        self.fast_check.toggled.connect(self.set_fast_path)
        self.view_check.toggled.connect(lambda on: self.enable_view("Picture view", on))

        left, right = QWidget(self), QWidget(self)
        for holder, check, view in (
            (left, self.image_check, self.image),
            (right, self.view_check, self.jpeg_view),
        ):
            column = QVBoxLayout(holder)
            column.setContentsMargins(0, 0, 0, 0)
            header = QHBoxLayout()
            header.addWidget(check)
            if view is self.image:
                header.addWidget(self.fast_check)
            header.addStretch(1)
            column.addLayout(header)
            column.addWidget(view)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([1, 1])

        self.stats_table = QTableWidget(len(self.trackers), len(STAT_COLUMNS), self)
        self.stats_table.setHorizontalHeaderLabels(STAT_COLUMNS)
        self.stats_table.setVerticalHeaderLabels(list(self.trackers))
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setMaximumHeight(100)
        self.benchmark_button = QPushButton("Run benchmark", self)
        self.benchmark_button.clicked.connect(lambda: self.run_benchmark())  # clicked passes a bool
        self.benchmark_label = QLabel("", self)
        bottom = QHBoxLayout()
        bottom.addWidget(self.benchmark_button)
        bottom.addWidget(self.benchmark_label, 1)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addWidget(self.control)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.stats_table)
        layout.addLayout(bottom)
        self.setCentralWidget(central)

        self.image.frame_timed.connect(lambda md, t0: self._frame_done("Image widget", md, t0))
        self.jpeg_view.frame_shown.connect(self._on_view_frame)
        self.image.device = device
        self.image.signal = signal
        self.jpeg_view.set_source(device, signal)

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_stats)
        self._stats_timer.start(500)
        self.benchmark: BenchmarkRunner | None = None

    def enable_view(self, name: str, enabled: bool) -> None:
        """Show or hide one view; a hidden view stops receiving frames."""
        if name == "Image widget":
            self.image_check.setChecked(enabled)
            self.image.setVisible(enabled)
            if enabled:
                self.image.device = self.device
                self.image.signal = "preview"
            else:
                self.image.signal = ""
        else:
            self.view_check.setChecked(enabled)
            self.jpeg_view.setVisible(enabled)
            if enabled:
                self.jpeg_view.set_source(self.device, "preview")
            else:
                self.jpeg_view.bec_dispatcher.disconnect_slot(self.jpeg_view.on_frame)
        self.trackers[name].clear()

    @SafeSlot(bool)
    def set_fast_path(self, enabled: bool) -> None:
        """Switch the Image widget between its normal and its fast 8-bit path."""
        self.fast_check.setChecked(enabled)
        self.image.fast_8bit_preview = enabled
        self.image.autorange = True
        self.trackers["Image widget"].clear()

    @SafeSlot()
    def _on_view_frame(self):
        md = self.jpeg_view.last_frame_metadata
        t0 = time.perf_counter()
        # Paint now, so the measured time is the whole cost of showing this frame
        self.jpeg_view.view.viewport().repaint()
        t0 -= self.jpeg_view.last_update_ms / 1e3
        self._frame_done("Picture view", md, t0)

    def _frame_done(self, name: str, metadata: dict, t_slot_start: float):
        now = time.perf_counter()
        capture = metadata.get("timestamp_capture")
        self.trackers[name].add(
            FrameSample(
                t_shown=now,
                frame_id=int(metadata.get("frame_id", 0)),
                transfer_nbytes=int(metadata.get("transfer_nbytes", metadata.get("raw_nbytes", 0))),
                raw_nbytes=int(metadata.get("raw_nbytes", 0)),
                encode_ms=float(metadata.get("encode_ms", 0.0)),
                decode_ms=float(metadata.get("decode_ms", 0.0)),
                gui_ms=(now - t_slot_start) * 1e3,
                latency_ms=(time.time() - capture) * 1e3 if capture else 0.0,
            )
        )

    def summaries(self, since: float | None = None) -> dict[str, dict]:
        """Current statistics of both views."""
        start = since if since is not None else time.perf_counter() - 3.0
        result = {}
        for name, tracker in self.trackers.items():
            summary = tracker.summary(since)
            if summary:
                summary["GUI stall ms (max)"] = self.probe.max_stall(start)
            result[name] = summary
        return result

    @SafeSlot()
    def _refresh_stats(self):
        for row, summary in enumerate(self.summaries().values()):
            for col, key in enumerate(STAT_COLUMNS):
                value = summary.get(key)
                text = "" if value is None else f"{value:.1f}"
                if key == "vs raw" and value:
                    text = f"{value:.1f}x"
                self.stats_table.setItem(row, col, QTableWidgetItem(text))

    def run_benchmark(
        self,
        sizes=(512, 1024, 2048, 4096),
        encodings=("raw", "jpeg_gray", "jpeg_rgb"),
        frame_rate: float = 10.0,
        settle_s: float = 2.0,
        measure_s: float = 4.0,
        out_dir: Path | None = None,
        on_done=None,
    ):
        """Sweep sizes x encodings x views; see BenchmarkRunner."""
        self.benchmark = BenchmarkRunner(
            self, sizes, encodings, frame_rate, settle_s, measure_s, out_dir, on_done
        )
        self.benchmark.start()


# view name in the results -> (panel, Image widget fast 8-bit path)
BENCHMARK_VIEWS = {
    "Image widget": ("Image widget", False),
    "Image widget (fast)": ("Image widget", True),
    "Picture view": ("Picture view", False),
}


class BenchmarkRunner(QObject):
    """
    Steps through every size, encoding and view without blocking the GUI.

    For each step only one view is enabled, the camera is reconfigured, the stream settles,
    and the view's statistics over the measuring window become one result row.
    """

    def __init__(
        self, demo, sizes, encodings, frame_rate, settle_s, measure_s, out_dir, on_done=None
    ):
        super().__init__(demo)
        self.demo = demo
        self.steps = list(itertools.product(sizes, encodings, BENCHMARK_VIEWS))
        self.frame_rate = frame_rate
        self.settle_s = settle_s
        self.measure_s = measure_s
        self.out_dir = Path(out_dir) if out_dir else Path.cwd()
        self.on_done = on_done
        self.rows: list[dict] = []
        self._index = -1
        self._measure_start = 0.0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._previous_views = (demo.image_check.isChecked(), demo.view_check.isChecked())
        self._previous_fast = demo.fast_check.isChecked()

    def start(self):
        """Run the first step."""
        self.demo.benchmark_button.setEnabled(False)
        self._next_step()

    def _next_step(self):
        self._index += 1
        if self._index >= len(self.steps):
            self._finish()
            return
        size, encoding, view = self.steps[self._index]
        self.demo.benchmark_label.setText(
            f"Benchmark {self._index + 1}/{len(self.steps)}: {view}, {size} x {size}, {encoding}"
        )
        panel, fast = BENCHMARK_VIEWS[view]
        self.demo.set_fast_path(fast)
        self.demo.enable_view("Image widget", panel == "Image widget")
        self.demo.enable_view("Picture view", panel == "Picture view")
        self.demo.control.set_settings(
            width=size, height=size, encoding=encoding, frame_rate=self.frame_rate
        )
        self._timer.timeout.connect(self._start_measuring)
        # big frames take the simulated camera a few seconds to prepare
        self._timer.start(int(self.settle_s * max(1.0, size / 2048) * 1000))

    def _start_measuring(self):
        self._timer.timeout.disconnect(self._start_measuring)
        self._measure_start = time.perf_counter()
        self._timer.timeout.connect(self._record)
        self._timer.start(int(self.measure_s * 1000))

    def _record(self):
        self._timer.timeout.disconnect(self._record)
        size, encoding, view = self.steps[self._index]
        panel = BENCHMARK_VIEWS[view][0]
        summary = self.demo.summaries(since=self._measure_start).get(panel, {})
        row = {"view": view, "size": f"{size}x{size}", "encoding": encoding}
        row.update({key: round(summary.get(key, float("nan")), 2) for key in STAT_COLUMNS})
        self.rows.append(row)
        print(f"Benchmark row: {row}", flush=True)
        self._next_step()

    def _finish(self):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = self.out_dir / f"jpeg_preview_benchmark_{stamp}.csv"
        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(self.rows[0]))
            writer.writeheader()
            writer.writerows(self.rows)
        csv_path.with_suffix(".json").write_text(json.dumps(self.rows, indent=1))
        self.demo.benchmark_label.setText(f"Benchmark saved to {csv_path}")
        self.demo.benchmark_button.setEnabled(True)
        self.demo.set_fast_path(self._previous_fast)
        self.demo.enable_view("Image widget", self._previous_views[0])
        self.demo.enable_view("Picture view", self._previous_views[1])
        print(f"Benchmark saved to {csv_path}")
        if self.on_done is not None:
            self.on_done(self.rows, csv_path)
        else:
            show_results(self.demo, self.rows)


def show_results(parent, rows: list[dict]) -> None:
    """Show benchmark rows in a dialog."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("JPEG preview benchmark")
    table = QTableWidget(len(rows), len(rows[0]), dialog)
    table.setHorizontalHeaderLabels(list(rows[0]))
    for r, row in enumerate(rows):
        for c, value in enumerate(row.values()):
            table.setItem(r, c, QTableWidgetItem(str(value)))
    table.resizeColumnsToContents()
    layout = QVBoxLayout(dialog)
    layout.addWidget(table)
    dialog.resize(1400, 600)
    dialog.show()


def main(argv=None):  # pragma: no cover
    """Start the demo."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--device", default="jpeg_cam", help="Simulated JPEG camera device")
    parser.add_argument("--signal", default="preview", help="Preview signal name")
    parser.add_argument("--theme", default="dark", choices=("dark", "light"))
    parser.add_argument(
        "--benchmark", action="store_true", help="Run the benchmark sweep at start, then quit"
    )
    parser.add_argument("--sizes", default="512,1024,2048,4096", help="Benchmark frame edges")
    parser.add_argument("--encodings", default="raw,jpeg_gray,jpeg_rgb")
    parser.add_argument("--rate", type=float, default=10.0, help="Benchmark frame rate (Hz)")
    parser.add_argument("--measure", type=float, default=4.0, help="Seconds measured per step")
    parser.add_argument("--out", default=".", help="Folder for the benchmark CSV/JSON")
    parser.add_argument("--screenshot", default="", help="Save a window screenshot and quit")
    args = parser.parse_args(argv)

    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(args.theme)
    window = JpegPreviewDemo(args.device, args.signal)
    window.resize(1800, 1000)
    window.show()
    if args.benchmark:
        QTimer.singleShot(
            3000,
            lambda: window.run_benchmark(
                sizes=[int(s) for s in args.sizes.split(",")],
                encodings=args.encodings.split(","),
                frame_rate=args.rate,
                measure_s=args.measure,
                out_dir=Path(args.out),
                on_done=lambda rows, path: app.quit(),
            ),
        )
    if args.screenshot:

        def grab():
            window.grab().save(args.screenshot)
            app.quit()

        QTimer.singleShot(6000, grab)
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
