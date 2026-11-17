"""
The HDF5 viewer: browse the scans BEC has written and look into any HDF5 file.

The scans come from the scan history that BEC keeps in memory and their curves are drawn
by the Waveform widget through the Data API. Files are read by
:mod:`~bec_widgets.widgets.services.hdf5_viewer.h5_reader`, which never keeps a file open,
never takes a file lock and never reads more than is shown.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Qt, QTimer
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.plots.waveform.waveform import Waveform
from bec_widgets.widgets.progress.scan_progressbar.scan_ui import ElidedLabel
from bec_widgets.widgets.services.hdf5_viewer import h5_reader
from bec_widgets.widgets.services.hdf5_viewer.h5_preview import H5DetailsPanel, H5Preview, StatePage
from bec_widgets.widgets.services.hdf5_viewer.h5_reader import FileSummary, H5ReadError
from bec_widgets.widgets.services.hdf5_viewer.h5_service import H5Service
from bec_widgets.widgets.services.hdf5_viewer.h5_tree import H5Tree
from bec_widgets.widgets.services.hdf5_viewer.pane_tabs import PaneTabs
from bec_widgets.widgets.services.hdf5_viewer.plot_targets import (
    AddResult,
    CurveSource,
    add_history_curves,
    copy_label,
    dock_area_for,
    has_curve,
    other_plots,
    plot_name,
    shown_signals,
    signal_of_dataset,
)
from bec_widgets.widgets.services.hdf5_viewer.scan_list import ScanEntry, ScanList, series_color
from bec_widgets.widgets.services.hdf5_viewer.signal_list import SignalInfo, SignalList, SourceKey
from bec_widgets.widgets.services.hdf5_viewer.style import control_key_name, mute, remute
from bec_widgets.widgets.services.scan_history_browser.components.scan_history_view import (
    BECHistoryManager,
)

logger = bec_logger.logger

#: Pen styles that tell the signals of one scan apart when scans are compared.
PEN_STYLES = ("solid", "dash", "dot", "dashdot")
#: Pause between two looks at a file that is still being written.
BUSY_RETRY_MS = 2000
#: Text of the button that adds the curves to another plot.
ADD_BUTTON_TEXT = "Add to plot"
#: How long the result of adding curves stays on that button.
ADD_FEEDBACK_MS = 3000
#: Widest the message on an "Add to plot" button gets, in pixels; longer ones are cut.
ADD_FEEDBACK_MAX_WIDTH = 170
#: Largest number of rows a dataset of the File tab may have to be copied to another plot.
COPY_MAX_POINTS = 1_000_000
#: What the File tab's button says about a copy before and after it is made.
COPY_TOOLTIP = "Adds a copy of these values. A copy is not saved with the workspace."
#: Time a scan that ended stays listed as running while its history entry is awaited.
LIVE_LINGER_MS = 20000

CurveKey = tuple[str, str, str]


class HDF5Viewer(BECWidget, QWidget):
    """
    Viewer for the scans BEC has written and for HDF5 files in general.

    The scan list, the signals of a scan and the plot are served from BEC's scan history and
    the Data API. The file view lists a file one group at a time and reads one frame, the
    rows in view or a reduced overview of a dataset. A file is opened for each read and
    closed again, without a file lock, and a file that is still being written is not read.
    """

    PLUGIN = True
    RPC = True
    ICON_NAME = "data_exploration"
    USER_ACCESS = [*BECWidget.USER_ACCESS, "open_file", "show_scan"]

    def __init__(self, parent: QWidget | None = None, client=None, config=None, gui_id=None, **kw):
        super().__init__(parent=parent, client=client, config=config, gui_id=gui_id, **kw)
        self.get_bec_shortcuts()
        self._entry: ScanEntry | None = None
        self._file_path = ""
        self._file_shown = ""
        self._file_sizes: dict[str, int] = {}
        self._keep_file = False
        self._select_when_listed = ""
        self._curves: dict[CurveKey, tuple[object, bool]] = {}
        self._x_applied: SourceKey | None | str = "unset"
        self._plot_note = ""

        self.service = H5Service(self)
        self.history_manager = BECHistoryManager(parent=self, client=self.client)

        # Left: the scans
        self.scan_list = ScanList(self)

        # Middle: the signals of the scan, or the contents of its file
        self.signal_list = SignalList(self)
        self.tree = H5Tree(self.service, self)
        self.details = H5DetailsPanel(self)
        self.file_splitter = QSplitter(Qt.Orientation.Vertical, self)
        self.file_splitter.addWidget(self.tree)
        self.file_splitter.addWidget(self.details)
        self.file_splitter.setStretchFactor(0, 3)
        self.file_splitter.setStretchFactor(1, 2)
        self.file_splitter.setChildrenCollapsible(False)
        self.tabs = PaneTabs(self)
        self.tabs.setMinimumWidth(300)
        self.tabs.add_tab(
            self._padded(self.signal_list), "Signals", "The signals BEC stored for the scan"
        )
        self.tabs.add_tab(
            self._padded(self.file_splitter), "File", "Everything that is in the scan's file"
        )
        self.open_button = QToolButton(self)
        self.open_button.setText("Open file…")
        self.open_button.setIcon(material_icon("folder_open", convert_to_pixmap=False))
        self.open_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.open_button.setAutoRaise(True)
        self.open_button.setToolTip("Look into any HDF5 file")
        self.tabs.set_corner_widget(self.open_button)

        # Right: the plot of the signals, or the preview of a dataset
        self.plot_title = QLabel(self)
        font = self.plot_title.font()
        font.setWeight(QFont.Weight.DemiBold)
        self.plot_title.setFont(font)
        self.plot_subtitle = ElidedLabel(parent=self)
        mute(self.plot_subtitle)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(self.plot_title)
        title_row.addWidget(self.plot_subtitle, 1)
        self.add_button, self.add_menu, self._add_reset_timer = self._make_add_button(
            "Add the curves of this plot to another plot as history curves"
        )
        self.add_menu.aboutToShow.connect(self._fill_add_menu)
        title_row.addWidget(self.add_button)
        self.waveform = Waveform(parent=self, client=self.client)
        self.plot_state = StatePage(self)
        self.plot_stack = QStackedWidget(self)
        self.plot_stack.addWidget(self.plot_state)
        self.plot_stack.addWidget(self.waveform)
        self.plot_page = QWidget(self)
        plot_layout = QVBoxLayout(self.plot_page)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(6)
        plot_layout.addLayout(title_row)
        plot_layout.addWidget(self.plot_stack, 1)
        self.preview = H5Preview(self.service, client=self.client, parent=self)
        # The same button for the dataset shown in the File tab.
        self.file_add_button, self.file_add_menu, self._file_add_reset_timer = (
            self._make_add_button(COPY_TOOLTIP)
        )
        self.file_add_menu.aboutToShow.connect(self._fill_file_add_menu)
        self.file_add_button.hide()
        self._copy_channel = f"viewer-copy-{id(self)}"
        self._copying = False
        self.preview.add_header_widget(self.file_add_button)
        self.preview.shown_changed.connect(self._update_file_add_button)
        self.right_stack = QStackedWidget(self)
        self.right_stack.addWidget(self.plot_page)
        self.right_stack.addWidget(self.preview)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.addWidget(self._padded(self.scan_list))
        self.splitter.addWidget(self.tabs)
        self.splitter.addWidget(self._padded(self.right_stack))
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([270, 400, 730])

        # Bottom: what is being read, and that nothing is locked
        self.status_icon = QLabel(self)
        self.status_icon.setPixmap(material_icon("verified_user", size=(16, 16)))
        self.status_label = ElidedLabel(parent=self)
        mute(self.status_label)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        status_row = QHBoxLayout()
        status_row.setContentsMargins(8, 2, 8, 4)
        status_row.setSpacing(6)
        status_row.addWidget(self.status_icon)
        status_row.addWidget(self.status_label, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.splitter, 1)
        layout.addLayout(status_row)

        self._busy_timer = QTimer(self)
        self._busy_timer.setSingleShot(True)
        self._busy_timer.setInterval(BUSY_RETRY_MS)
        self._busy_timer.timeout.connect(self._reopen_file)

        self.scan_list.scan_selected.connect(self._on_scan_selected)
        self.scan_list.pins_changed.connect(self._refresh_plot)
        self.scan_list.context_menu_requested.connect(self._show_scan_menu)
        self.signal_list.selection_changed.connect(self._refresh_plot)
        self.signal_list.open_requested.connect(self._open_signal_in_file)
        self.tabs.current_changed.connect(self._on_tab_changed)
        self.open_button.clicked.connect(self._choose_file)
        self.tree.node_selected.connect(self.preview.show_node)
        self.tree.file_failed.connect(self._on_file_failed)
        self.tree.file_listed.connect(lambda _path: self._busy_timer.stop())
        self.preview.details_changed.connect(self.details.set_details)
        self.preview.details_changed.connect(lambda _details: self._update_status())
        self.service.bytes_read_changed.connect(lambda _path: self._update_status())
        self.history_manager.scan_history_refreshed.connect(self._on_history_refreshed)
        self.history_manager.scan_history_updated.connect(self._on_history_updated)
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())

        self._on_scan_selected(None)
        self._load_history()

    ################################################################################
    # Public interface
    ################################################################################

    @SafeSlot()
    def open_file(self, file_path: str, dataset: str = "") -> None:
        """
        Show an HDF5 file in the file view.

        The file is opened for each read and closed again, without a file lock. A file that
        is still being written is not read until its writer is done.

        Args:
            file_path (str): Path of the file.
            dataset (str): Path of a dataset or group inside the file to select.
        """
        file_path = str(Path(file_path).expanduser())
        listed = next(
            (entry for entry in self.scan_list.model.entries() if entry.file_path == file_path),
            None,
        )
        if listed is not None and self.scan_list.select(listed.scan_id):
            self.tabs.set_current_index(1)
            self._show_file(dataset)
            return
        self._keep_file = True
        try:
            self.scan_list.clear_selection()
        finally:
            self._keep_file = False
        self._file_path = file_path
        self._file_shown = ""
        self.tabs.set_current_index(1)
        self._show_file(dataset)

    @SafeSlot()
    def show_scan(self, scan: int | str) -> None:
        """
        Select a scan of the scan history.

        Scan numbers can repeat (e.g. after a counter reset): for a number shared by several
        scans the newest of them is selected. A scan id always names one scan.

        Args:
            scan (int | str): Scan number or scan id.

        Raises:
            ValueError: If the scan is not in the scan history.
        """
        # The scans are listed newest first, so the first match of a number is its newest scan.
        for entry in self.scan_list.model.entries():
            if scan in (entry.scan_id, entry.scan_number):
                self.scan_list.search_edit.clear()
                self.scan_list.ending_buttons["all"].click()
                self.scan_list.select(entry.scan_id)
                return
        raise ValueError(f"Scan {scan} is not in the scan history.")

    ################################################################################
    # Scans
    ################################################################################

    @staticmethod
    def _padded(widget: QWidget) -> QWidget:
        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.addWidget(widget)
        return holder

    def _load_history(self) -> None:
        try:
            self.history_manager.refresh_scan_history()
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"HDF5 viewer: the scan history could not be read: {exc}")

    @SafeSlot(list)
    def _on_history_refreshed(self, history: list) -> None:
        live = [entry for entry in self.scan_list.model.entries() if entry.live]
        entries = [ScanEntry.from_history(msg) for msg in history]
        known = {entry.scan_id for entry in entries}
        self.scan_list.set_entries(
            entries + [entry for entry in live if entry.scan_id not in known]
        )

    @SafeSlot(dict)
    def _on_history_updated(self, msg: dict) -> None:
        self.scan_list.add_entry(ScanEntry.from_history(msg))

    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, _meta: dict) -> None:
        """
        List the running scan at the top and let it go when it has ended.

        Args:
            msg (dict): Content of a ``ScanStatusMessage``.
            _meta (dict): Metadata of the message.
        """
        scan_id = msg.get("scan_id")
        if not scan_id:
            return
        existing = self.scan_list.model.entry(scan_id)
        if existing is not None and not existing.live:
            return
        status = msg.get("status") or "open"
        if status not in ("open", "paused"):
            # The history entry replaces this one as soon as the file is written.
            self._call_later(LIVE_LINGER_MS, lambda: self._forget_live(scan_id))
            return
        priority = msg.get("readout_priority") or {}
        stored: dict = {}
        kinds: dict[SourceKey, str] = {}
        for kind in ("monitored", "async"):
            for device in priority.get(kind) or []:
                signal = self._default_entry(device)
                if signal:
                    # The shape is not known before the scan is done.
                    stored[device] = {signal: {"shape": (0,), "dtype": ""}}
                    kinds[(device, signal)] = kind
        entry = ScanEntry(
            scan_id=scan_id,
            scan_number=msg.get("scan_number"),
            scan_name=msg.get("scan_name") or "",
            status=status,
            start_time=float(msg.get("timestamp") or 0.0),
            num_points=msg.get("num_points"),
            motors=tuple(msg.get("scan_report_devices") or ()),
            stored_data_info=stored,
            signal_kinds=kinds,
            live=True,
        )
        self.scan_list.add_entry(entry)

    def _default_entry(self, device: str) -> str:
        """The signal of a device that the plots draw when only the device is named."""
        try:
            return self.waveform.entry_validator.validate_signal(device, None)
        except Exception:  # pylint: disable=broad-except
            return ""

    def _forget_live(self, scan_id: str) -> None:
        entry = self.scan_list.model.entry(scan_id)
        if entry is not None and entry.live:
            self.scan_list.model.remove(scan_id)

    def _signal_kinds(self, entry: ScanEntry) -> dict[SourceKey, str]:
        """Ask the Data API how each stored signal is keyed. Nothing is read for this."""
        if entry.signal_kinds:
            return entry.signal_kinds
        sources = [
            (device, signal)
            for device, signals in (entry.stored_data_info or {}).items()
            for signal in signals
        ]
        if not sources:
            return {}
        try:
            described = self.client.data_api.describe(sources, scan=entry.scan_id)
            return {
                key: str(info.kind)
                for key, info in described.items()
                if getattr(info, "available", False) and getattr(info, "kind", None)
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug(f"HDF5 viewer: the Data API could not describe {entry.scan_id}: {exc}")
            return {}

    def _on_scan_selected(self, entry: ScanEntry | None) -> None:
        self._entry = entry
        self._busy_timer.stop()
        if entry is not None:
            self._file_path = entry.file_path
        elif not self._keep_file:
            self._file_path = ""
        self.signal_list.set_scan(entry, self._signal_kinds(entry) if entry is not None else None)
        if self.tabs.current_index() == 1 and not self._keep_file:
            self._show_file()
        self._update_status()

    ################################################################################
    # Plot of the signals
    ################################################################################

    def _plot_scans(self) -> list[tuple[ScanEntry, int]]:
        """The selected scan in palette slot 0 and the pinned ones in theirs."""
        scans: list[tuple[ScanEntry, int]] = []
        if self._entry is not None:
            scans.append((self._entry, 0))
        for entry, slot in self.scan_list.pinned_entries():
            if self._entry is None or entry.scan_id != self._entry.scan_id:
                scans.append((entry, slot))
        return scans

    @staticmethod
    def _plot_problem(device: str, error: Exception) -> str:
        """Say in plain words why a signal is not on the plot."""
        return f"{device} could not be plotted: {error}"

    @SafeSlot()
    def _refresh_plot(self) -> None:
        """Bring the curves of the plot in line with the chosen scans and signals."""
        scans = self._plot_scans()
        y_keys = self.signal_list.y_signals()
        x_key = self.signal_list.x_signal()
        one_scan = len(scans) <= 1
        wanted: dict[CurveKey, tuple[ScanEntry, str, str]] = {}
        for entry, slot in scans:
            for position, (device, signal) in enumerate(y_keys):
                if signal not in (entry.stored_data_info or {}).get(device, {}):
                    continue
                color = series_color(position) if one_scan else series_color(slot)
                style = "solid" if one_scan else PEN_STYLES[position % len(PEN_STYLES)]
                wanted[(entry.scan_id, device, signal)] = (entry, color, style)

        self.signal_list.set_colors(
            (
                {key: series_color(position) for position, key in enumerate(y_keys)}
                if one_scan
                else {}
            ),
            series_color(0),
        )
        self._update_plot_title(scans)

        for key in list(self._curves):
            curve, live = self._curves[key]
            if key not in wanted or wanted[key][0].live != live:
                self._drop_curve(key)
        self._plot_note = ""
        self._apply_x(x_key)
        for key, (entry, color, style) in wanted.items():
            if key in self._curves:
                curve = self._curves[key][0]
                curve.set_color(color)
                curve.set_pen_style(style)
                continue
            # Errors come back here instead of as a popup: they are explained under the title.
            options = {
                "device_y": key[1],
                "signal_y": key[2],
                "color": color,
                "pen_style": style,
                "pen_width": 2,
                "_override_slot_params": {"popup_error": False, "raise_error": True},
            }
            if not entry.live:
                options["scan_id"] = entry.scan_id
            try:
                curve = self.waveform.plot(**options)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(f"HDF5 viewer: {key[1]}/{key[2]} could not be plotted: {exc}")
                self._plot_note = self._plot_problem(key[1], exc)
                continue
            if curve is None:
                self._plot_note = f"{key[1]} could not be plotted."
                continue
            self._curves[key] = (curve, entry.live)

        if self._curves:
            self.plot_stack.setCurrentWidget(self.waveform)
        elif self._entry is None:
            self.plot_state.show_state(
                "query_stats", "No scan picked", "Pick a scan on the left to plot its signals."
            )
            self.plot_stack.setCurrentWidget(self.plot_state)
        elif not self.signal_list.signals():
            self.plot_state.show_state(
                "data_alert",
                "No signals listed for this scan",
                "Its history entry does not say what was stored. "
                "The File tab shows everything that is in its file.",
                (("Go to the File tab", lambda: self.tabs.set_current_index(1)),),
            )
            self.plot_stack.setCurrentWidget(self.plot_state)
        else:
            self.plot_state.show_state(
                "show_chart",
                "Nothing on the plot",
                self._plot_note or "Press Y on a signal to plot it, and X to choose the x axis.",
            )
            self.plot_stack.setCurrentWidget(self.plot_state)
        if self._plot_note:
            self.plot_subtitle.setText(self._plot_note)

    def _drop_curve(self, key: CurveKey) -> None:
        curve, _live = self._curves.pop(key)
        try:
            self.waveform.remove_curve(curve.name())
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug(f"HDF5 viewer: curve {key} was already gone: {exc}")

    def _apply_x(self, x_key: SourceKey | None) -> None:
        if x_key == self._x_applied:
            return
        try:
            if x_key is None:
                self.waveform.x_mode = "auto"
            else:
                self.waveform.x_mode = x_key[0]
                if self.waveform.signal_x != x_key[1]:
                    self.waveform.signal_x = x_key[1]
            self._x_applied = x_key
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"HDF5 viewer: the x axis could not be set to {x_key}: {exc}")
            self._plot_note = f"{x_key[0] if x_key else 'This'} cannot be the x axis here: {exc}"
            self._x_applied = "unset"

    def _update_plot_title(self, scans: list[tuple[ScanEntry, int]]) -> None:
        if self._entry is None:
            self.plot_title.setText("")
            self.plot_subtitle.setText("")
            return
        self.plot_title.setText(
            f"Scan {self.scan_list.model.scan_label(self._entry)}  {self._entry.scan_name}".rstrip()
        )
        label = self.scan_list.model.scan_label
        others = [label(entry) for entry, _slot in scans[1:]]
        if others:
            self.plot_subtitle.setText(
                f"compared with {', '.join(others)}"
                "  ·  one colour per scan, one line style per signal"
            )
        elif self._entry.live:
            self.plot_subtitle.setText("running  ·  drawn live, its file is not opened")
        else:
            key = control_key_name()
            self.plot_subtitle.setText(
                f"{self._entry.summary()}  ·  pin another scan or {key}-click it to compare"
            )

    ################################################################################
    # File view
    ################################################################################

    def _on_tab_changed(self, index: int) -> None:
        self.right_stack.setCurrentWidget(self.preview if index == 1 else self.plot_page)
        if index == 1:
            self._show_file()
        self._update_status()

    def _choose_file(self) -> None:
        start = str(Path(self._file_path).parent) if self._file_path else ""
        suffixes = " ".join(f"*{suffix}" for suffix in h5_reader.HDF5_SUFFIXES)
        file_path, _filter = QFileDialog.getOpenFileName(
            self, "Open an HDF5 file", start, f"HDF5 files ({suffixes});;All files (*)"
        )
        if file_path:
            self.open_file(file_path)

    def _open_signal_in_file(self, signal: SignalInfo) -> None:
        self.tabs.set_current_index(1)
        self._show_file(signal.dataset_path)

    def _show_file(self, select_path: str = "") -> None:
        """Show the file of the selected scan, or the opened file, in the tree."""
        entry = self._entry
        self._busy_timer.stop()
        if entry is not None and entry.live:
            self._file_shown = ""
            self.tree.set_file(None)
            self.preview.show_message(
                "hourglass_top",
                f"Scan {self.scan_list.model.scan_label(entry)} is still running",
                "Its file is being written and is not opened. The Signals tab shows the scan "
                "while it runs, and the file opens here as soon as the scan is done.",
                (("Go to the Signals tab", lambda: self.tabs.set_current_index(0)),),
            )
            return
        file_path = self._file_path
        if not file_path:
            self._file_shown = ""
            self.tree.set_file(None)
            self.preview.show_message(
                "draft",
                "No file",
                "Pick a scan on the left, or open any HDF5 file.",
                (("Open file…", self._choose_file),),
            )
            return
        if file_path == self._file_shown:
            if select_path and self.tree.file_path == file_path:
                self.tree.select_path(select_path)
            elif select_path:
                # The file is being listed: select once it is there.
                self._select_when_listed = select_path
            return
        self._file_shown = file_path
        self._select_when_listed = select_path
        self.tree.set_file(None)
        self.preview.show_node(None)

        def listed(files: list[FileSummary]):
            if self._file_shown != file_path:
                return
            for summary in files:
                self._file_sizes[summary.file_path] = summary.size_bytes
            neighbours = tuple(summary.file_path for summary in files[1:])
            self.tree.set_file(file_path, neighbours, self._select_when_listed)
            self._select_when_listed = ""
            self._update_status()

        def failed(error: H5ReadError):
            if self._file_shown == file_path:
                self._on_file_failed(error)

        self.service.request(
            f"viewer-{id(self)}-folder",
            "",
            lambda _ctx: h5_reader.scan_folder_files(file_path),
            listed,
            failed,
        )

    def _reopen_file(self) -> None:
        self._file_shown = ""
        if self.tabs.current_index() == 1:
            self._show_file()

    def _on_file_failed(self, error: H5ReadError) -> None:
        """Explain in place why the file is not shown, and keep looking while it is written."""
        file_path = self._file_shown

        def read_anyway():
            self.service.allow_busy_file(file_path)
            self._reopen_file()

        self.preview.show_file_error(error, self._reopen_file, read_anyway, waiting=True)
        if error.kind == "busy":
            self._busy_timer.start()

    def _update_status(self) -> None:
        file_path = self._file_path
        node = self.preview.node
        if self.tabs.current_index() == 1 and node is not None and node.file_path:
            # A link may have led into another file: tell about the file that is read.
            file_path = node.file_path
        self.status_icon.setToolTip(file_path or "")
        if self._entry is not None and self._entry.live:
            self.status_label.setText(
                "The running scan is drawn live from BEC. Its file is not opened."
            )
            return
        if not file_path:
            self.status_label.setText("Read-only. Files are never locked or kept open.")
            return
        parts = [Path(file_path).name]
        size = self._file_sizes.get(file_path)
        if self.tabs.current_index() == 1:
            read = h5_reader.format_bytes(self.service.bytes_read(file_path))
            if size:
                parts.append(f"{read} of {h5_reader.format_bytes(size)} read")
            parts.append("read-only, never locked, closed after every read")
        else:
            if size:
                parts.append(h5_reader.format_bytes(size))
            parts.append("read-only, plotted through BEC's Data API")
        self.status_label.setText("  ·  ".join(parts))

    ################################################################################
    # Other plots
    ################################################################################

    def curve_sources(self) -> list[CurveSource]:
        """
        The curves on the plot that can go to another plot: those of finished scans.

        Returns:
            list[CurveSource]: (scan id, device, signal) of each.
        """
        return [key for key, (_curve, live) in self._curves.items() if not live]

    def _make_add_button(self, tool_tip: str) -> tuple[QToolButton, QMenu, QTimer]:
        """A button "Add to plot" with a menu of the other plots, and the timer of its text."""
        button = QToolButton(self)
        button.setText(ADD_BUTTON_TEXT)
        button.setIcon(material_icon("add_chart", convert_to_pixmap=False))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setAutoRaise(True)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolTip(tool_tip)
        menu = QMenu(button)
        button.setMenu(menu)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(ADD_FEEDBACK_MS)
        timer.timeout.connect(lambda: self._end_saying(button))
        return button, menu, timer

    def _fill_menu(self, menu: QMenu, unavailable: str, add, say) -> None:
        """
        List the other plots in a menu of an "Add to plot" button.

        Args:
            menu (QMenu): The menu.
            unavailable (str): Why there is nothing to add, or empty.
            add: Called with a plot and its name to add to it.
            say: Puts a message on the button.
        """
        menu.clear()
        if unavailable:
            menu.addAction(unavailable).setEnabled(False)
            return
        plots = other_plots(self)
        area = dock_area_for(self)
        for name, plot in plots:
            action = menu.addAction(name)
            action.triggered.connect(lambda _=False, p=plot, n=name: add(p, n))
        if area is not None:
            if plots:
                menu.addSeparator()
            action = menu.addAction("New plot in workspace")
            action.triggered.connect(lambda _=False, a=area: self._add_to_new(a, add, say))
        if not plots and area is None:
            menu.addAction("No other plot is open and there is no workspace").setEnabled(False)

    def _add_to_new(self, dock_area, add, say):
        try:
            plot = dock_area.new("Waveform")
        except Exception as exc:  # pylint: disable=broad-except
            say(f"Could not open a new plot: {exc}")
            return None
        return add(plot, plot_name(plot))

    def _add_sources(self, plot: Waveform, name: str | None, sources, say) -> AddResult:
        """Add history curves to another plot and say how it went on the button."""
        result = add_history_curves(plot, sources)
        say(result.message(name or plot_name(plot)))
        return result

    def _fill_add_menu(self) -> None:
        empty = (
            ""
            if self.curve_sources()
            else "Nothing to add: the plot is empty or shows a running scan"
        )
        self._fill_menu(self.add_menu, empty, self.add_to_plot, self._say_on_add_button)

    def add_to_plot(self, plot: Waveform, name: str | None = None) -> AddResult:
        """
        Add what is on the plot of the viewer to another plot as history curves.

        Args:
            plot (Waveform): The other plot.
            name (str | None): Its name, as shown on the button afterwards.

        Returns:
            AddResult: What happened.
        """
        return self._add_sources(plot, name, self.curve_sources(), self._say_on_add_button)

    def add_to_new_plot(self, dock_area) -> AddResult | None:
        """
        Open a new plot in a dock area and add what is on the plot of the viewer to it.

        Args:
            dock_area (BECDockArea): The dock area.

        Returns:
            AddResult | None: What happened, or None when no plot could be opened.
        """
        return self._add_to_new(dock_area, self.add_to_plot, self._say_on_add_button)

    @staticmethod
    def _say_on(
        button: QToolButton, timer: QTimer, text: str, width: int = ADD_FEEDBACK_MAX_WIDTH
    ) -> None:
        """
        Put a message on an "Add to plot" button for a few seconds. A message wider than
        ``width`` is cut, so the button does not widen its pane, and is given in full in the
        tooltip meanwhile.
        """
        shown = button.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width)
        button.setText(shown)
        button.setProperty("feedback", text)
        if shown != text:
            button.setProperty("tool_tip_before", button.toolTip())
            button.setToolTip(text)
        timer.start()

    @staticmethod
    def _end_saying(button: QToolButton) -> None:
        button.setText(ADD_BUTTON_TEXT)
        button.setProperty("feedback", "")
        before = button.property("tool_tip_before")
        if before:
            button.setToolTip(before)
            button.setProperty("tool_tip_before", "")

    def _say_on_add_button(self, text: str) -> None:
        self._say_on(self.add_button, self._add_reset_timer, text)

    ################################################################################
    # The dataset of the File tab on other plots
    ################################################################################

    def file_history_source(self) -> CurveSource | None:
        """
        The history curve of the dataset the File tab shows, if it is one: the ``value`` of a
        BEC signal, 1D, in the file of a listed scan that stored that signal.

        Returns:
            CurveSource | None: (scan id, device, signal), or None for any other dataset.
        """
        line = self.preview.line_source()
        if line is None or line.node.ndim != 1 or line.index:
            return None
        signal = signal_of_dataset(line.node.path)
        if signal is None:
            return None
        entry = self._scan_of_file(line.node.file_path)
        if entry is None or signal[1] not in (entry.stored_data_info or {}).get(signal[0], {}):
            return None
        return (entry.scan_id, *signal)

    def _scan_of_file(self, file_path: str) -> ScanEntry | None:
        """The listed scan whose file this is, matched by path, newest first."""
        wanted = Path(file_path).resolve()
        for entry in self.scan_list.model.entries():
            if entry.file_path and Path(entry.file_path).resolve() == wanted:
                return entry
        return None

    def _update_file_add_button(self) -> None:
        line = self.preview.line_source()
        button = self.file_add_button
        button.setVisible(line is not None)
        if line is None:
            return
        source = self.file_history_source()
        if source is not None:
            entry = self.scan_list.model.entry(source[0])
            label = self.scan_list.model.scan_label(entry) if entry else "?"
            button.setToolTip(f"Adds {source[1]} {source[2]} of scan {label} as a history curve")
            button.setEnabled(not self._copying)
            return
        rows = int(line.node.shape[-1]) if line.node.shape else 1
        if rows > COPY_MAX_POINTS:
            button.setEnabled(False)
            button.setToolTip(
                f"Too many rows to copy: {rows:,} is more than {COPY_MAX_POINTS:,}. "
                "Only BEC signals of listed scans can go to other plots at any length."
            )
            return
        button.setToolTip(COPY_TOOLTIP)
        button.setEnabled(not self._copying)

    def _fill_file_add_menu(self) -> None:
        empty = "" if self.preview.line_source() is not None else "Show a dataset as a line first"
        self._fill_menu(self.file_add_menu, empty, self.add_file_to_plot, self._say_on_file_button)

    def add_file_to_plot(self, plot: Waveform, name: str | None = None) -> AddResult | None:
        """
        Add the dataset the File tab shows to another plot: a BEC signal of a listed scan as a
        history curve (as from the Signals tab), anything else as a copy of the values shown.

        Args:
            plot (Waveform): The other plot.
            name (str | None): Its name, as shown on the button afterwards.

        Returns:
            AddResult | None: What happened for a history curve; None while a copy is read.
        """
        name = name or plot_name(plot)
        source = self.file_history_source()
        if source is not None:
            return self._add_sources(plot, name, [source], self._say_on_file_button)
        self._copy_to_plot(plot, name)
        return None

    def _copy_to_plot(self, plot: Waveform, name: str) -> None:
        line = self.preview.line_source()
        if line is None:
            return
        node = line.node
        label = copy_label(node.file_path, node.path, line.index)
        if has_curve(plot, label):
            self._say_on_file_button(f"Already on {name}")
            return
        rows = int(node.shape[-1]) if node.shape else 1
        if rows > COPY_MAX_POINTS:
            self._say_on_file_button(f"Too many rows to copy to {name}")
            return
        self._copying = True
        self.file_add_button.setEnabled(False)
        self.file_add_button.setText("Reading…")
        self.file_add_button.setProperty("feedback", "Reading…")
        x_path = line.x_path or None

        def done(curve_data):
            self._copy_finished()
            try:
                plot.plot(
                    x=np.asarray(curve_data.x),
                    y=np.asarray(curve_data.y),
                    label=label,
                    _override_slot_params={"popup_error": False, "raise_error": True},
                )
            except Exception as exc:  # pylint: disable=broad-except
                self._say_on_file_button(f"Could not add to {name}: {exc}")
                return
            self._say_on_file_button(f"Copied to {name}, not saved with the workspace")

        def failed(error: H5ReadError):
            self._copy_finished()
            self._say_on_file_button(f"Could not copy: {error.message}")

        self.service.request(
            self._copy_channel,
            node.file_path,
            lambda ctx: h5_reader.read_curve(
                node.file_path,
                node.path,
                line.index,
                max_points=max(rows, 1),
                cancel=ctx.cancelled,
                x_path=x_path,
            ),
            done,
            failed,
        )

    def _copy_finished(self) -> None:
        self._copying = False
        self._update_file_add_button()

    def _say_on_file_button(self, text: str) -> None:
        # The header of the preview is narrow: use only the room the other parts leave.
        button = self.file_add_button
        others = [self.preview.name_label, *self.preview.view_buttons.values()]
        taken = sum(widget.width() + 8 for widget in others if widget.isVisible())
        chrome = button.sizeHint().width() - button.fontMetrics().horizontalAdvance(button.text())
        room = self.preview.width() - taken - chrome
        least = button.fontMetrics().horizontalAdvance(ADD_BUTTON_TEXT)
        width = max(least, min(room, ADD_FEEDBACK_MAX_WIDTH))
        self._say_on(button, self._file_add_reset_timer, text, width)

    def _show_scan_menu(self, entry: ScanEntry, position) -> None:
        self.scan_menu(entry).popup(position)

    def scan_menu(self, entry: ScanEntry) -> QMenu:
        """
        The context menu of a scan: overlay it on another plot.

        Args:
            entry (ScanEntry): The scan.

        Returns:
            QMenu: The menu, not shown yet.
        """
        menu = QMenu(self)
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        overlay = QMenu("Overlay on", menu)
        menu.addMenu(overlay)
        menu.overlay_menu = overlay
        plots = other_plots(self)
        if entry.live:
            overlay.setEnabled(False)
            overlay.setToolTip("A running scan can be overlaid once it is done")
        for name, plot in plots:
            action = overlay.addAction(name)
            action.triggered.connect(
                lambda _=False, e=entry, p=plot, n=name: self.overlay_scan(e, p, n)
            )
        if not plots:
            note = overlay.addAction("No other plot is open")
            note.setEnabled(False)
        return menu

    def overlay_scan(self, entry: ScanEntry, plot: Waveform, name: str | None = None) -> str:
        """
        Add a scan to another plot with the signals that plot shows, as history curves.

        Args:
            entry (ScanEntry): The scan.
            plot (Waveform): The other plot.
            name (str | None): Its name.

        Returns:
            str: What happened, as said in the note under the scan list.
        """
        name = name or plot_name(plot)
        signals = shown_signals(plot)
        stored = entry.stored_data_info or {}
        sources = [
            (entry.scan_id, device, signal)
            for device, signal in signals
            if signal in stored.get(device, {})
        ]
        if not signals:
            text = f"{name} shows no signal to overlay"
        elif not sources:
            text = f"Scan {self.scan_list.model.scan_label(entry)} did not store what {name} shows"
        else:
            text = add_history_curves(plot, sources).message(name)
            missing = len(signals) - len(sources)
            if missing:
                text += f" ({missing} not stored in scan {self.scan_list.model.scan_label(entry)})"
        self.scan_list.flash_note(text)
        return text

    ################################################################################
    # Housekeeping
    ################################################################################

    def pause(self) -> None:
        """
        Stop reading files while the viewer is not shown, e.g. while another view of the main
        application is open. :meth:`resume` picks up what was cut off.
        """
        self._paused_busy = self._busy_timer.isActive()
        self._busy_timer.stop()
        self.tree.pause()
        self.service.cancel(self._copy_channel)
        self._copy_finished()
        channel = self.preview._channel  # pylint: disable=protected-access
        self._paused_preview = self.service.has_pending(channel)
        self.service.cancel_all(channel)

    def resume(self) -> None:
        """Read again what :meth:`pause` cut off."""
        self.tree.resume()
        if getattr(self, "_paused_busy", False):
            self._paused_busy = False
            self._busy_timer.start()
        if getattr(self, "_paused_preview", False):
            self._paused_preview = False
            self.preview.reload()

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """
        Follow a change of the theme.

        Args:
            theme (str): Name of the theme.
        """
        if not hasattr(self, "scan_list"):
            return
        self.status_icon.setPixmap(material_icon("verified_user", size=(16, 16)))
        remute(self)
        self.scan_list.view.viewport().update()
        # The Waveform recolours its curves when it follows the theme itself; give the curves
        # the colours of the scan list and the signal chips again once it has done so.
        QTimer.singleShot(0, self._refresh_plot)

    def cleanup(self):
        """Stop the reads, release the history and scan status subscriptions."""
        self._busy_timer.stop()
        self._add_reset_timer.stop()
        self._file_add_reset_timer.stop()
        self.service.cancel(self._copy_channel)
        self.scan_list.cleanup()
        self.tree.cleanup()
        self.preview.cleanup()
        self.service.cleanup()
        self.history_manager.cleanup()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("light")
    viewer = HDF5Viewer()
    viewer.setWindowTitle("HDF5 Viewer")
    viewer.resize(1400, 820)
    viewer.show()
    for argument in sys.argv[1:2]:
        viewer.open_file(argument)
    sys.exit(app.exec())
