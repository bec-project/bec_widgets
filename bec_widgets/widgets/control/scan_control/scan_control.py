import threading
from collections import defaultdict
from functools import partial
from types import NoneType
from typing import Optional

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.scan_history import ScanHistory
from bec_qthemes import material_icon
from pydantic import BaseModel, Field
from qtpy.QtCore import QSignalBlocker, Qt, QTimer, Signal
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton
from bec_widgets.widgets.control.scan_control.scan_docstring import render_scan_tooltip_html
from bec_widgets.widgets.control.scan_control.scan_group_box import ScanGroupBox
from bec_widgets.widgets.control.scan_control.scan_info_adapter import ScanInfoAdapter
from bec_widgets.widgets.control.scan_control.scan_info_dialog import ScanInfoDialog
from bec_widgets.widgets.control.scan_control.scan_selection_dialog import ScanSelectionDialog
from bec_widgets.widgets.editors.scan_metadata.scan_metadata import ScanMetadata

logger = bec_logger.logger


class ScanParameterConfig(BaseModel):
    name: str
    args: Optional[list] = Field(None)
    kwargs: Optional[dict] = Field(None)


class ScanControlConfig(ConnectionConfig):
    default_scan: Optional[str] = Field(None)
    allowed_scans: Optional[list] = Field(None)
    scans: Optional[dict[str, ScanParameterConfig]] = defaultdict(dict)


class ScanControl(BECWidget, QWidget):
    """
    Widget to submit new scans to the queue.
    """

    USER_ACCESS = ["attach", "detach", "screenshot"]
    PLUGIN = True
    ICON_NAME = "tune"
    ARG_BOX_POSITION: int = 2
    SUPPORTED_SCAN_BASE_CLASSES = {"ScanBase", "SyncFlyScanBase", "AsyncFlyScanBase", "ScanBaseV4"}
    RECENT_SCAN_HISTORY_COUNT = 50
    MAX_HISTORY_LOOKBACK = 500
    LAST_SCAN_FETCH_TIMEOUT_MS = 30_000

    scan_started = Signal()
    scan_selected = Signal(str)
    device_selected = Signal(str)
    scan_args = Signal(list)
    _last_scan_parameters_received = Signal(int, str, object)

    def __init__(
        self,
        parent=None,
        client=None,
        config: ScanControlConfig | dict | None = None,
        gui_id: str | None = None,
        allowed_scans: list | None = None,
        default_scan: str | None = None,
        **kwargs,
    ):
        if config is None:
            config = ScanControlConfig(
                widget_class=self.__class__.__name__, allowed_scans=allowed_scans
            )
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        self._hide_add_remove_buttons = False

        # Client from BEC + shortcuts to device manager and scans
        self.get_bec_shortcuts()

        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setAlignment(Qt.AlignTop)
        self.arg_box = None
        self.kwarg_boxes = []
        self.expert_mode = False  # TODO implement in the future versions
        self.previous_scan = None

        # Widget Default Parameters
        if default_scan is not None:
            self.config.default_scan = default_scan
        if allowed_scans is not None:
            # Same normalization as the property setter: an empty filter means "no filter",
            # so no construction argument can produce a selector without a runnable scan.
            self.config.allowed_scans = list(dict.fromkeys(allowed_scans)) or None

        self._scan_metadata: dict | None = None
        self._metadata_form = ScanMetadata(parent=self)
        self._hide_arg_box = False
        self._hide_kwarg_boxes = False
        self._hide_scan_control_buttons = False
        self._hide_metadata = False
        self._hide_scan_selection_combobox = False
        self._hide_scan_selector_settings_button = False
        self._scan_info_adapter = ScanInfoAdapter()
        self._scan_info_dialog: ScanInfoDialog | None = None
        self._last_scan_parameters_received.connect(self._apply_last_scan_parameters)
        # Window-lookup results memoized per scan name, valid while the stream tip is
        # unchanged. Fetch workers can overlap - the watchdog re-enables the button while a
        # hung worker is still running - so the memo is guarded by its own lock.
        self._last_scan_lookup_memo: dict[str, tuple[str | None, tuple[list, dict] | None]] = {}
        self._last_scan_lookup_lock = threading.Lock()
        # Generation counter to discard results of superseded or timed-out fetches
        self._last_scan_fetch_generation = 0
        self._last_scan_fetch_watchdog = QTimer(self)
        self._last_scan_fetch_watchdog.setSingleShot(True)
        self._last_scan_fetch_watchdog.setInterval(self.LAST_SCAN_FETCH_TIMEOUT_MS)
        self._last_scan_fetch_watchdog.timeout.connect(self._on_last_scan_parameters_timeout)

        # Create and set main layout
        self._init_UI()

    def _init_UI(self):
        """
        Initializes the UI of the scan control widget. Create the top box for scan selection and populate scans to main combobox.
        """
        # Scan selection box
        self.scan_selection_group = QWidget(self)
        QVBoxLayout(self.scan_selection_group)
        scan_selection_layout = QHBoxLayout()
        self.comboBox_scan_selection_label = QLabel("Scan:", self.scan_selection_group)
        self.comboBox_scan_selection = QComboBox(self.scan_selection_group)
        self.scan_info_button = QToolButton(self.scan_selection_group)
        self.scan_info_button.setIcon(material_icon("info", size=(20, 20), convert_to_pixmap=False))
        self.scan_info_button.setAutoRaise(True)
        self.scan_info_button.setToolTip("Show information about the selected scan")
        self.scan_info_button.setAccessibleName("Scan information")
        self.scan_selector_settings_button = QToolButton(self.scan_selection_group)
        self.scan_selector_settings_button.setAutoRaise(True)
        self.scan_selector_settings_button.setIcon(
            material_icon("filter_list", size=(20, 20), convert_to_pixmap=False)
        )
        self.scan_selector_settings_button.setToolTip("Choose scans shown in the selector")
        self.scan_selector_settings_button.setAccessibleName("Scan selector settings")
        scan_selection_layout.addWidget(self.comboBox_scan_selection_label, 0)
        scan_selection_layout.addWidget(self.comboBox_scan_selection, 1)
        scan_selection_layout.addWidget(self.scan_info_button, 0)
        scan_selection_layout.addWidget(self.scan_selector_settings_button, 0)
        self.scan_selection_group.layout().addLayout(scan_selection_layout)

        # Button to reload the last scan parameters on demand.
        self.last_scan_button = QPushButton(
            "Restore last scan parameters", self.scan_selection_group
        )
        self.last_scan_button.clicked.connect(self.request_last_executed_scan_parameters)
        self.scan_selection_group.layout().addWidget(self.last_scan_button)
        self.scan_selection_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.layout.addWidget(self.scan_selection_group)

        # Scan control (Run/Stop) buttons
        self.scan_control_group = QWidget(self)
        self.scan_control_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.button_layout = QHBoxLayout(self.scan_control_group)
        self.button_run_scan = QPushButton("Start", self.scan_control_group)
        self.button_run_scan.setProperty("variant", "success")
        self.button_stop_scan = StopButton(parent=self.scan_control_group)
        self.button_layout.addWidget(self.button_run_scan)
        self.button_layout.addWidget(self.button_stop_scan)
        self.layout.addWidget(self.scan_control_group)

        # Connect signals
        self.comboBox_scan_selection.view().pressed.connect(self.save_current_scan_parameters)
        self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selection_changed)
        self.scan_info_button.clicked.connect(self.show_selected_scan_info)
        self.scan_selector_settings_button.clicked.connect(self.show_scan_selector_settings)
        self.button_run_scan.clicked.connect(self.run_scan)

        self.scan_selected.connect(self.scan_select)

        # Initialize scan selection
        self.populate_scans()

        # Default scan from config; applied after population so the entry exists
        if self.config.default_scan is not None:
            self.comboBox_scan_selection.setCurrentText(self.config.default_scan)

        # Append metadata form
        self._add_metadata_form()

    def _add_metadata_form(self):
        # Wrap metadata form in a group box
        self._metadata_group = QGroupBox("Scan Metadata", self)
        self._metadata_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        metadata_layout = QVBoxLayout(self._metadata_group)
        metadata_layout.addWidget(self._metadata_form)

        self.layout.addWidget(self._metadata_group)
        self._metadata_form.update_with_new_scan(self.comboBox_scan_selection.currentText())
        self.scan_selected.connect(self._metadata_form.update_with_new_scan)
        self._metadata_form.form_data_updated.connect(self.update_scan_metadata)
        self._metadata_form.form_data_cleared.connect(self.update_scan_metadata)
        self._metadata_form.validate_form()

    def _scan_docstring(self, scan_name: str) -> str | None:
        scan_info = self.available_scans.get(scan_name, {})
        docstring = scan_info.get("doc") if isinstance(scan_info, dict) else None
        return docstring if isinstance(docstring, str) else None

    @SafeSlot()
    @SafeSlot(bool)
    def show_selected_scan_info(self, *_args) -> None:
        """Show documentation for the currently selected scan without blocking the GUI."""
        self.show_scan_info(self.comboBox_scan_selection.currentText())

    @SafeSlot(str)
    def show_scan_info(self, scan_name: str) -> None:
        """Show documentation for a specific scan."""
        if self._scan_info_dialog is None:
            self._scan_info_dialog = ScanInfoDialog(self)
        self._scan_info_dialog.show_scan(scan_name, self._scan_docstring(scan_name))

    def populate_scans(self):
        """Populates the scan selection combo box with available scans from BEC session."""
        self.available_scans = self.client.connector.get(
            MessageEndpoints.available_scans()
        ).resource
        self._update_scan_selector()

    def _supported_scan_names(self) -> list[str]:
        """Return available scans that can be rendered by this widget."""
        return [
            scan_name
            for scan_name, scan_info in getattr(self, "available_scans", {}).items()
            if scan_info.get("base_class") in self.SUPPORTED_SCAN_BASE_CLASSES
            and self._scan_info_adapter.has_scan_ui_config(scan_info)
            and not scan_name.startswith("_")
        ]

    def _update_scan_selector(self) -> None:
        """Apply the configured scan filter while preserving the current selection."""
        current_scan = self.comboBox_scan_selection.currentText()
        if current_scan:
            self.save_current_scan_parameters()
        # Read the raw filter: ``None`` means "unset", which the property never reports.
        allowed_scans = self.config.allowed_scans
        if allowed_scans is None:
            visible_scans = self._supported_scan_names()
        else:
            # An explicit filter overrides the support filter and keeps the caller's order;
            # entries not currently available stay in the filter and reappear once published.
            visible_scans = [scan for scan in allowed_scans if scan in self.available_scans]

        with QSignalBlocker(self.comboBox_scan_selection):
            self.comboBox_scan_selection.clear()
            self.comboBox_scan_selection.addItems(visible_scans)
            for index, scan_name in enumerate(visible_scans):
                self.comboBox_scan_selection.setItemData(
                    index,
                    render_scan_tooltip_html(scan_name, self._scan_docstring(scan_name)),
                    Qt.ItemDataRole.ToolTipRole,
                )
            if current_scan in visible_scans:
                self.comboBox_scan_selection.setCurrentText(current_scan)

        self.scan_info_button.setEnabled(bool(visible_scans))
        self._update_run_button_state()
        self._update_selected_scan_tooltip()
        if self.comboBox_scan_selection.currentText() != current_scan:
            self.on_scan_selection_changed(self.comboBox_scan_selection.currentIndex())

    def _update_run_button_state(self) -> None:
        """Start requires a selected scan and valid metadata."""
        has_scan = bool(self.comboBox_scan_selection.currentText())
        self.button_run_scan.setEnabled(has_scan and self._scan_metadata is not None)

    def _update_selected_scan_tooltip(self) -> None:
        """Mirror the selected item's documentation tooltip on the closed combo box."""
        index = self.comboBox_scan_selection.currentIndex()
        tooltip = self.comboBox_scan_selection.itemData(index, Qt.ItemDataRole.ToolTipRole)
        self.comboBox_scan_selection.setToolTip(tooltip or "")

    @SafeSlot()
    @SafeSlot(bool)
    def show_scan_selector_settings(self, *_):
        """Open the scan filter dialog and apply accepted changes."""
        scan_names = self._supported_scan_names()
        allowed_scans = self.config.allowed_scans
        if allowed_scans is not None:
            # Keep configured entries visible in the dialog even when currently unsupported.
            scan_names += [scan for scan in allowed_scans if scan not in scan_names]
        dialog = ScanSelectionDialog(
            scan_names=scan_names,
            selected_scans=scan_names if allowed_scans is None else allowed_scans,
            scan_docs={scan_name: self._scan_docstring(scan_name) for scan_name in scan_names},
            parent=self,
        )
        try:
            selected_scans = (
                dialog.selected_scans() if dialog.exec() == QDialog.DialogCode.Accepted else None
            )
        finally:
            dialog.deleteLater()
        if selected_scans is not None:
            # Everything checked means "no filter", so scans added later show up as well.
            self.allowed_scans = None if selected_scans == scan_names else selected_scans

    @SafeProperty("QStringList")
    def allowed_scans(self) -> list[str]:
        """Scans configured for the selector.

        Reports the configured filter when one is set - entries that are not currently
        available are kept, so a filter survives a scan disappearing and reappearing -
        and every supported scan when no filter is set. It never reports ``None``: Qt
        cannot convert that to a list property, so an unset filter would surface as
        ``[]`` and, once stored in a profile and restored, would filter every scan away.
        """
        allowed_scans = getattr(self.config, "allowed_scans", None)
        return self._supported_scan_names() if allowed_scans is None else list(allowed_scans)

    @allowed_scans.setter
    def allowed_scans(self, scan_names: list[str] | str | None):
        """Set the scans displayed in the selector.

        ``None``, an empty list, or a list holding exactly the currently supported scans
        in their listed order all clear the filter, so no configuration can leave the
        selector without a single runnable scan. A reordered full list is kept as an
        explicit filter, preserving the caller's ordering in the selector.

        Note that "no filter" and "every scan selected" are the same plain list once
        stored: a profile saved before further scans became available is restored as an
        explicit filter and does not pick those scans up until the selection is cleared
        again (for example by checking everything in the scan filter dialog).
        """
        if isinstance(scan_names, str):
            scan_names = [scan_names]
        if scan_names is not None:
            scan_names = list(dict.fromkeys(scan_names))
            if not scan_names or scan_names == self._supported_scan_names():
                scan_names = None
        self.config.allowed_scans = scan_names
        self._update_scan_selector()

    @SafeProperty(bool)
    def hide_scan_selector_settings_button(self) -> bool:
        """Whether the button for configuring visible scans is hidden."""
        return self._hide_scan_selector_settings_button

    @hide_scan_selector_settings_button.setter
    def hide_scan_selector_settings_button(self, hide: bool):
        self._hide_scan_selector_settings_button = bool(hide)
        self.scan_selector_settings_button.setVisible(not self._hide_scan_selector_settings_button)

    def on_scan_selection_changed(self, index: int):
        """Callback for scan selection combo box"""
        selected_scan_name = self.comboBox_scan_selection.currentText()
        self._update_selected_scan_tooltip()
        self.scan_selected.emit(selected_scan_name)
        self.restore_scan_parameters(selected_scan_name)

    @SafeSlot()
    @SafeSlot(bool)
    def request_last_executed_scan_parameters(self, *_):
        """
        Requests the last executed scan parameters from BEC and restores them to the scan control widget.
        """
        if not self.last_scan_button.isEnabled():
            return
        current_scan = self.comboBox_scan_selection.currentText()
        if not current_scan:
            # e.g. an empty selector after a filter change - nothing to restore
            return
        self.last_scan_button.setEnabled(False)
        self._last_scan_fetch_generation += 1
        generation = self._last_scan_fetch_generation
        self._last_scan_fetch_watchdog.start()
        try:
            # ``completed`` is success-only; ``failed`` carries a traceback string, which
            # _on_last_scan_parameters_finished does not take, so bind the generation instead.
            self.submit_task(
                self._fetch_last_executed_scan_parameters,
                generation,
                current_scan,
                on_complete=partial(self._on_last_scan_parameters_finished, generation),
                on_failed=lambda _msg, gen=generation: self._on_last_scan_parameters_finished(gen),
            )
        except Exception:
            self._on_last_scan_parameters_finished(generation)
            raise

    def _fetch_last_executed_scan_parameters(self, generation: int, scan_name: str):
        """Fetch the latest parameters for ``scan_name`` without touching the Qt UI."""
        try:
            parameters = self._lookup_last_scan_parameters(scan_name)
        except Exception:
            logger.exception(f"Failed to fetch parameters for scan {scan_name}")
            return
        if parameters is None:
            return
        try:
            self._last_scan_parameters_received.emit(generation, scan_name, parameters)
        except RuntimeError:
            # the widget was deleted while the fetch was in flight - nothing to deliver to
            logger.debug(f"ScanControl deleted before parameters for {scan_name} arrived")

    def _lookup_last_scan_parameters(self, scan_name: str) -> tuple[list, dict] | None:
        """
        Find the newest parameters for ``scan_name`` in the client-side scan-history cache or
        in a strictly bounded window of the scan-history stream.

        There is deliberately no full-stream path: decoding an entry allocates hundreds of
        GC-tracked objects, and the resulting stop-the-world collections stall the Qt event
        loop from any thread.
        """
        endpoint = MessageEndpoints.scan_history()
        # Single one-entry probe of the stream tip. The stream is append-only, so the tip
        # both proves the in-memory cache is caught up (it lags when the newest scan's file
        # is not readable yet, e.g. over NFS) and keys the memo: repeat lookups with an
        # unchanged tip are answered for the cost of this one decode.
        tip = self._read_history_window(endpoint, 1)
        tip_id = getattr(tip[0].get("data"), "scan_id", None) if tip else None

        parameters = self._find_parameters_in_history_cache(scan_name, tip_id)
        if parameters is not None:
            return parameters

        # The lock is held only around the dict access, never across a redis read: a hung
        # fetch must not block the worker that the watchdog let the user start.
        with self._last_scan_lookup_lock:
            memo = self._last_scan_lookup_memo.get(scan_name)
        if memo is not None and memo[0] == tip_id:
            logger.debug(f"Scan history unchanged; reusing memoized lookup for {scan_name}")
            return memo[1]

        parameters = self._search_history_windows(endpoint, scan_name)
        with self._last_scan_lookup_lock:
            # Overlapping workers race to write here; the loser stores a result for an
            # older tip, which the tip comparison above discards on the next lookup.
            self._last_scan_lookup_memo[scan_name] = (tip_id, parameters)
        return parameters

    def _search_history_windows(self, endpoint, scan_name: str) -> tuple[list, dict] | None:
        """Search the recent, then the deep, stream window for ``scan_name``."""
        history = self._read_history_window(endpoint, self.RECENT_SCAN_HISTORY_COUNT)
        parameters = self._find_last_scan_parameters(scan_name, history)
        if parameters is not None or len(history) < self.RECENT_SCAN_HISTORY_COUNT:
            # fewer entries than requested means the whole stream was already searched
            return parameters
        if self.MAX_HISTORY_LOOKBACK <= self.RECENT_SCAN_HISTORY_COUNT:
            return None

        history = self._read_history_window(endpoint, self.MAX_HISTORY_LOOKBACK)
        parameters = self._find_last_scan_parameters(scan_name, history)
        if parameters is None and len(history) >= self.MAX_HISTORY_LOOKBACK:
            logger.warning(
                f"No execution of {scan_name} found within the last "
                f"{self.MAX_HISTORY_LOOKBACK} scans; older history is not searched."
            )
        return parameters

    def _read_history_window(self, endpoint, count: int) -> list[dict]:
        """Read at most ``count`` newest scan-history entries, oldest-first."""
        history = self.client.connector.get_last(endpoint, count=count)
        if isinstance(history, dict):
            # get_last returns a single message dict instead of a list for count == 1
            history = [history]
        return history or []

    def _find_parameters_in_history_cache(
        self, scan_name: str, tip_id: str | None
    ) -> tuple[list, dict] | None:
        """Search the in-memory scan history (newest first) for ``scan_name``.

        The cache is only trusted when its newest entry matches the stream tip: it skips
        scans whose file is not readable yet, so a lagging cache could otherwise return an
        older execution than the stream holds.
        """
        history = getattr(self.client, "history", None)
        if not isinstance(history, ScanHistory):
            # not available before the client services are started (e.g. in Qt Designer)
            return None
        length = len(history)
        if length == 0:
            return None
        newest = getattr(history[length - 1], "_msg", None)
        if newest is None or newest.scan_id != tip_id:
            return None
        # iterate by index from the end instead of slicing to avoid copying the whole cache
        for index in range(length - 1, -1, -1):
            msg = getattr(history[index], "_msg", None)
            if msg is not None and msg.scan_name == scan_name:
                return self._parameters_from_request_inputs(msg.request_inputs)
        return None

    @staticmethod
    def _parameters_from_request_inputs(request_inputs: dict | None) -> tuple[list, dict]:
        """Split ``request_inputs`` into the argument bundle and merged keyword arguments."""
        ri = request_inputs or {}
        return ri.get("arg_bundle", []), {**ri.get("inputs", {}), **ri.get("kwargs", {})}

    @staticmethod
    def _find_last_scan_parameters(scan_name: str, history: list[dict]) -> tuple[list, dict] | None:
        """Return the newest matching argument and keyword bundles from ``history``."""
        for scan in reversed(history):
            scan_data = scan.get("data")
            if not scan_data:
                continue

            if scan_data.scan_name != scan_name:
                continue

            return ScanControl._parameters_from_request_inputs(
                getattr(scan_data, "request_inputs", None)
            )
        return None

    @SafeSlot(int, str, object)
    def _apply_last_scan_parameters(
        self, generation: int, scan_name: str, parameters: tuple[list, dict]
    ):
        """Apply asynchronously fetched parameters on the GUI thread."""
        if generation != self._last_scan_fetch_generation:
            # result of a timed-out or superseded fetch
            return
        if self.comboBox_scan_selection.currentText() != scan_name:
            logger.debug(f"Discarding fetched parameters for {scan_name}: scan selection changed")
            return

        args_list, kwargs = parameters
        if args_list and self.arg_box:
            self.arg_box.set_parameters(args_list)

        if kwargs and self.kwarg_boxes:
            for box in self.kwarg_boxes:
                box.set_parameters(kwargs)

    @SafeSlot()
    def _on_last_scan_parameters_finished(self, generation: int | None = None):
        """Re-enable parameter restoration after the background request finishes."""
        if generation is not None and generation != self._last_scan_fetch_generation:
            # a stale fetch finished after a timeout or a newer request; leave the UI state alone
            return
        self._last_scan_fetch_watchdog.stop()
        self.last_scan_button.setEnabled(True)

    @SafeSlot()
    def _on_last_scan_parameters_timeout(self):
        """Recover the UI if the background fetch hangs (e.g. unreachable Redis)."""
        logger.warning("Timed out while fetching the last executed scan parameters")
        # invalidate the in-flight fetch so a late result is not applied
        self._last_scan_fetch_generation += 1
        self.last_scan_button.setEnabled(True)

    @SafeProperty(str)
    def current_scan(self):
        """Returns the scan name for the currently selected scan."""
        return self.comboBox_scan_selection.currentText()

    @current_scan.setter
    def current_scan(self, scan_name: str):
        """Sets the current scan to the given scan name.

        Args:
            scan_name(str): Name of the scan to set as current.
        """
        if scan_name not in self.available_scans:
            return
        self.comboBox_scan_selection.setCurrentText(scan_name)

    @SafeSlot(str)
    def set_current_scan(self, scan_name: str):
        """Slot for setting the current scan to the given scan name.

        Args:
            scan_name(str): Name of the scan to set as current.
        """
        self.current_scan = scan_name

    @SafeProperty(bool)
    def hide_arg_box(self):
        """Property to hide the argument box."""
        return self._hide_arg_box

    @hide_arg_box.setter
    def hide_arg_box(self, hide: bool):
        """Setter for the hide_arg_box property.

        Args:
            hide(bool): Hide or show the argument box.
        """
        self._hide_arg_box = hide
        if self.arg_box is not None:
            self.arg_box.setVisible(not hide)

    @SafeProperty(bool)
    def hide_kwarg_boxes(self):
        """Property to hide the keyword argument boxes."""
        return self._hide_kwarg_boxes

    @hide_kwarg_boxes.setter
    def hide_kwarg_boxes(self, hide: bool):
        """Setter for the hide_kwarg_boxes property.

        Args:
            hide(bool): Hide or show the keyword argument boxes.
        """
        self._hide_kwarg_boxes = hide
        if len(self.kwarg_boxes) > 0:
            for box in self.kwarg_boxes:
                box.setVisible(not hide)

    @SafeProperty(bool)
    def hide_scan_control_buttons(self):
        """Property to hide the scan control buttons."""
        return self._hide_scan_control_buttons

    @hide_scan_control_buttons.setter
    def hide_scan_control_buttons(self, hide: bool):
        """Setter for the hide_scan_control_buttons property.

        Args:
            hide(bool): Hide or show the scan control buttons.
        """
        self._hide_scan_control_buttons = hide
        self.show_scan_control_buttons(not hide)

    @SafeProperty(bool)
    def hide_metadata(self):
        """Property to hide the metadata form."""
        return self._hide_metadata

    @hide_metadata.setter
    def hide_metadata(self, hide: bool):
        """Setter for the hide_metadata property.

        Args:
            hide(bool): Hide or show the metadata form.
        """
        self._hide_metadata = hide
        self._metadata_form.setVisible(not hide)

    @SafeProperty(bool)
    def hide_optional_metadata(self):
        """Property to hide the optional metadata form."""
        return self._metadata_form.hide_optional_metadata

    @hide_optional_metadata.setter
    def hide_optional_metadata(self, hide: bool):
        """Setter for the hide_optional_metadata property.

        Args:
            hide(bool): Hide or show the optional metadata form.
        """
        self._metadata_form.hide_optional_metadata = hide

    @SafeSlot(bool)
    def show_scan_control_buttons(self, show: bool):
        """Shows or hides the scan control buttons."""
        self._hide_scan_control_buttons = not show
        self.scan_control_group.setVisible(show)

    @SafeProperty(bool)
    def hide_scan_selection_combobox(self):
        """Property to hide the scan selection combobox."""
        return self._hide_scan_selection_combobox

    @hide_scan_selection_combobox.setter
    def hide_scan_selection_combobox(self, hide: bool):
        """Setter for the hide_scan_selection_combobox property.

        Args:
            hide(bool): Hide or show the scan selection combobox.
        """
        self._hide_scan_selection_combobox = hide
        self.show_scan_selection_combobox(not hide)

    @SafeSlot(bool)
    def show_scan_selection_combobox(self, show: bool):
        """Shows or hides the scan selection combobox."""
        self._hide_scan_selection_combobox = not show
        self.scan_selection_group.setVisible(show)

    @SafeSlot(str)
    def scan_select(self, scan_name: str):
        """
        Slot for scan selection. Updates the scan control layout based on the selected scan.

        Args:
            scan_name(str): Name of the selected scan.
        """
        self.reset_layout()
        selected_scan_info = self.available_scans.get(scan_name, {})

        gui_config = self._scan_info_adapter.build_scan_ui_config(selected_scan_info)
        arg_group = gui_config.get("arg_group", None)
        kwarg_groups = gui_config.get("kwarg_groups", [])

        if arg_group and bool(arg_group.get("arg_inputs")):
            self.add_arg_group(arg_group)
        if kwarg_groups:
            self.add_kwargs_boxes(kwarg_groups)

        self.update()
        self.adjustSize()

    @SafeProperty(bool)
    def hide_add_remove_buttons(self):
        """Property to hide the add_remove buttons."""
        return self._hide_add_remove_buttons

    @hide_add_remove_buttons.setter
    def hide_add_remove_buttons(self, hide: bool):
        """Setter for the hide_add_remove_buttons property.

        Args:
            hide(bool): Hide or show the add_remove buttons.
        """
        self._hide_add_remove_buttons = hide
        if self.arg_box is not None:
            self.arg_box.hide_add_remove_buttons = hide

    def add_kwargs_boxes(self, groups: list):
        """
        Adds the given gui_groups to the scan control layout.

        Args:
            groups(list): List of dictionaries containing the gui_group information.
        """
        position = self.ARG_BOX_POSITION + (1 if self.arg_box is not None else 0)
        for group in groups:
            box = ScanGroupBox(box_type="kwargs", config=group)
            box.reference_units_changed.connect(self._apply_reference_units_to_other_boxes)
            self.layout.insertWidget(position + len(self.kwarg_boxes), box)
            self.kwarg_boxes.append(box)
            box.setVisible(not self._hide_kwarg_boxes)

    def add_arg_group(self, group: dict):
        """
        Adds the given gui_groups to the scan control layout.

        Args:
        """
        self.arg_box = ScanGroupBox(box_type="args", config=group)
        self.arg_box.device_selected.connect(self.emit_device_selected)
        self.arg_box.reference_units_changed.connect(self._apply_reference_units_to_other_boxes)
        self.arg_box.hide_add_remove_buttons = self._hide_add_remove_buttons
        self.layout.insertWidget(self.ARG_BOX_POSITION, self.arg_box)
        self.arg_box.setVisible(not self._hide_arg_box)

    def _scan_group_boxes(self) -> list[ScanGroupBox]:
        boxes = []
        if self.arg_box is not None:
            boxes.append(self.arg_box)
        boxes.extend(self.kwarg_boxes)
        return boxes

    def _apply_reference_units_to_other_boxes(
        self, source_box: ScanGroupBox, reference_name: str, units: str | None
    ) -> None:
        """
        Propagate device-derived units to scan fields that reference a device in another group.
        """
        for box in self._scan_group_boxes():
            if box is source_box:
                continue
            box.apply_reference_units(reference_name, units)

    @SafeSlot(str)
    def emit_device_selected(self, dev_names):
        """
        Emit the signal to inform about selected device(s)

        "dev_names" is a string separated by space, in case of multiple devices
        """
        self._selected_devices = dev_names
        self.device_selected.emit(dev_names)

    def reset_layout(self):
        """Clears the scan control layout from GuiGroups and ArgGroups boxes."""
        if self.arg_box is not None:
            self.layout.removeWidget(self.arg_box)
            self.arg_box.close()
            self.arg_box.deleteLater()
            self.arg_box = None
        if self.kwarg_boxes != []:
            self.remove_kwarg_boxes()

    def remove_kwarg_boxes(self):
        for box in self.kwarg_boxes:
            self.layout.removeWidget(box)
            box.close()
            box.deleteLater()
        self.kwarg_boxes = []

    def get_scan_parameters(self, bec_object: bool = True):
        """
        Returns the scan parameters for the selected scan.

        Args:
            bec_object(bool): If True, returns the BEC object for the scan parameters such as device objects.
        """
        args = []
        kwargs = {}
        if self.arg_box is not None:
            args = self.arg_box.get_parameters(bec_object)
        for box in self.kwarg_boxes:
            box_kwargs = box.get_parameters(bec_object)
            kwargs.update(box_kwargs)
        if self._scan_metadata is not None:
            kwargs["metadata"] = self._scan_metadata
        return args, kwargs

    def restore_scan_parameters(self, scan_name: str):
        """
        Restores the scan parameters for the given scan name

        Args:
            scan_name(str): Name of the scan to restore the parameters for.
        """
        scan_params = self.config.scans.get(scan_name, None)
        if scan_params is None and self.previous_scan is None:
            return

        if scan_params is None and self.previous_scan is not None:
            previous_scan_params = self.config.scans.get(self.previous_scan, None)
            self._restore_kwargs(previous_scan_params.kwargs)
            return

        if scan_params.args is not None and self.arg_box is not None:
            self.arg_box.set_parameters(scan_params.args)

        self._restore_kwargs(scan_params.kwargs)

    def _restore_kwargs(self, scan_kwargs: dict):
        """Restores the kwargs for the given scan parameters."""
        if scan_kwargs is not None and self.kwarg_boxes is not None:
            for box in self.kwarg_boxes:
                box.set_parameters(scan_kwargs)

    def save_current_scan_parameters(self):
        """Saves the current scan parameters to the scan control config for further use."""
        scan_name = self.comboBox_scan_selection.currentText()
        self.previous_scan = scan_name
        args, kwargs = self.get_scan_parameters(False)
        scan_params = ScanParameterConfig(name=scan_name, args=args, kwargs=kwargs)
        self.config.scans[scan_name] = scan_params

    @SafeSlot(dict)
    @SafeSlot(NoneType)
    def update_scan_metadata(self, md: dict | None):
        self._scan_metadata = md
        self._update_run_button_state()

    @SafeSlot(popup_error=True)
    def run_scan(self):
        """Starts the selected scan with the given parameters."""
        scan_name = self.comboBox_scan_selection.currentText()
        if not scan_name:
            return
        args, kwargs = self.get_scan_parameters()
        self.scan_args.emit(args)
        scan_function = getattr(self.scans, scan_name)
        if callable(scan_function):
            self.scan_started.emit()
            scan_function(*args, **kwargs)

    def cleanup(self):
        """Cleanup the scan control widget."""
        # Invalidate any in-flight fetch so a late result is dropped instead of being
        # applied to (or logged against) a widget that is going away.
        self._last_scan_fetch_generation += 1
        self._last_scan_fetch_watchdog.stop()
        if self._scan_info_dialog is not None:
            self._scan_info_dialog.close()
            self._scan_info_dialog.deleteLater()
            self._scan_info_dialog = None
        super().cleanup()


# Application example
if __name__ == "__main__":  # pragma: no cover
    app = QApplication([])
    scan_control = ScanControl()

    apply_theme("dark")
    window = scan_control
    window.show()
    app.exec()
