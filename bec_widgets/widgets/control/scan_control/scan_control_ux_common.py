"""Behaviour shared by the QML and QWidget ports of :class:`ScanControl`.

The ports keep the public API of ``ScanControl`` (signals, Designer properties, ``run_scan``,
``get_scan_parameters``, scan filter, last-scan restore, ...). The form itself is a
:class:`ScanFormModel`; the renderers only draw :meth:`ScanControlPortBase.view_state` and call
back into the methods here.

UX changes compared to ``ScanControl``:

* every field shows its unit, default and a specific error message ("Must be ≥ 0");
* errors appear once a field was edited, or for all fields after an attempt to start;
* argument rows can be removed individually;
* Start names the scan and says what is missing; Stop turns into Emergency Stop for 2 s;
* metadata moves to a dialog opened from the footer, which shows whether it is complete.
"""

from __future__ import annotations

import threading
from functools import partial
from types import NoneType

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.ux_kit import PortedPropertiesMixin
from bec_widgets.widgets.control.scan_control.scan_control import (
    ScanControl,
    ScanControlConfig,
    ScanParameterConfig,
)
from bec_widgets.widgets.control.scan_control.scan_docstring import render_scan_tooltip_html
from bec_widgets.widgets.control.scan_control.scan_form_model import ScanFormModel
from bec_widgets.widgets.control.scan_control.scan_info_adapter import ScanInfoAdapter
from bec_widgets.widgets.control.scan_control.scan_info_dialog import ScanInfoDialog
from bec_widgets.widgets.control.scan_control.scan_selection_dialog import ScanSelectionDialog
from bec_widgets.widgets.editors.scan_metadata.scan_metadata import ScanMetadata

logger = bec_logger.logger


def doc_summary(docstring: str | None) -> str:
    """First paragraph of a scan docstring on one line."""
    if not docstring:
        return ""
    lines = []
    for line in docstring.strip().splitlines():
        if not line.strip():
            if lines:
                break
            continue
        lines.append(line.strip())
    return " ".join(lines)


class ScanControlPortBase(PortedPropertiesMixin, BECWidget, QWidget):
    """Shared implementation of the ScanControl ports.

    Subclasses create the renderer in :meth:`_init_view` and redraw it in :meth:`_sync_view`;
    ``structure`` is True when fields were added or removed, False for value-only changes.
    """

    PLUGIN = False
    RPC = False
    rpc_widget_class = "ScanControl"
    USER_ACCESS = ["attach", "detach", "screenshot"]
    ICON_NAME = "tune"
    RECENT_SCAN_HISTORY_COUNT = ScanControl.RECENT_SCAN_HISTORY_COUNT
    MAX_HISTORY_LOOKBACK = ScanControl.MAX_HISTORY_LOOKBACK
    LAST_SCAN_FETCH_TIMEOUT_MS = ScanControl.LAST_SCAN_FETCH_TIMEOUT_MS
    EMERGENCY_STOP_TIMEOUT_MS = 2000

    scan_started = Signal()
    scan_selected = Signal(str)
    device_selected = Signal(str)
    scan_args = Signal(list)
    _last_scan_parameters_received = Signal(int, str, object)

    # The last-scan lookup is reused unchanged from ScanControl.
    _fetch_last_executed_scan_parameters = ScanControl._fetch_last_executed_scan_parameters
    _lookup_last_scan_parameters = ScanControl._lookup_last_scan_parameters
    _search_history_windows = ScanControl._search_history_windows
    _read_history_window = ScanControl._read_history_window
    _find_parameters_in_history_cache = ScanControl._find_parameters_in_history_cache
    _parameters_from_request_inputs = staticmethod(ScanControl._parameters_from_request_inputs)
    _find_last_scan_parameters = staticmethod(ScanControl._find_last_scan_parameters)

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
        self.get_bec_shortcuts()
        if default_scan is not None:
            self.config.default_scan = default_scan
        if allowed_scans is not None:
            self.config.allowed_scans = list(dict.fromkeys(allowed_scans)) or None

        self.available_scans: dict = {}
        self.previous_scan = None
        self._selected_scan = ""
        self._visible_scans: list[str] = []
        self._touched: set[str] = set()
        self._show_all_errors = False
        self._hide_arg_box = False
        self._hide_kwarg_boxes = False
        self._hide_scan_control_buttons = False
        self._hide_metadata = False
        self._hide_scan_selection_combobox = False
        self._hide_scan_selector_settings_button = False
        self._hide_add_remove_buttons = False
        self._scan_info_adapter = ScanInfoAdapter()
        self._scan_info_dialog: ScanInfoDialog | None = None
        self._device_name_cache: list[str] | None = None

        self.form = ScanFormModel(self._device_names, self._device_object, self)
        self.form.structure_changed.connect(lambda: self._sync_view(True))
        self.form.values_changed.connect(lambda: self._sync_view(False))
        self.form.device_selected.connect(self.emit_device_selected)

        # metadata form lives in a dialog opened from the footer
        self._scan_metadata: dict | None = None
        self._metadata_form = ScanMetadata(parent=self)
        self._metadata_form.hide()
        self._metadata_dialog: QDialog | None = None
        self._metadata_form.form_data_updated.connect(self.update_scan_metadata)
        self._metadata_form.form_data_cleared.connect(self.update_scan_metadata)
        self.scan_selected.connect(self._metadata_form.update_with_new_scan)

        # two-stage stop like StopButton: abort first, then offer an emergency halt
        self._emergency_stop = False
        self._emergency_timer = QTimer(self)
        self._emergency_timer.setSingleShot(True)
        self._emergency_timer.timeout.connect(self._reset_emergency_stop)

        # background fetch of the last executed parameters (see ScanControl)
        self._restore_busy = False
        self._last_scan_parameters_received.connect(self._apply_last_scan_parameters)
        self._last_scan_lookup_memo: dict = {}
        self._last_scan_lookup_lock = threading.Lock()
        self._last_scan_fetch_generation = 0
        self._last_scan_fetch_watchdog = QTimer(self)
        self._last_scan_fetch_watchdog.setSingleShot(True)
        self._last_scan_fetch_watchdog.setInterval(self.LAST_SCAN_FETCH_TIMEOUT_MS)
        self._last_scan_fetch_watchdog.timeout.connect(self._on_last_scan_parameters_timeout)

        self._init_view()
        self.populate_scans()
        if self.config.default_scan is not None:
            self.current_scan = self.config.default_scan
        self._metadata_form.update_with_new_scan(self._selected_scan)
        self._metadata_form.validate_form()
        self._sync_view(True)

    # ---- devices ---------------------------------------------------------------------------

    def _device_names(self) -> list[str]:
        if self._device_name_cache is None:
            try:
                self._device_name_cache = sorted(self.dev.keys())
            except Exception:  # pylint: disable=broad-except
                self._device_name_cache = []
        return self._device_name_cache

    def _device_object(self, name: str):
        return self.dev[name]

    # ---- scan list -----------------------------------------------------------------------

    def populate_scans(self):
        """Load the available scans from BEC and apply the scan filter."""
        message = self.client.connector.get(MessageEndpoints.available_scans())
        self.available_scans = getattr(message, "resource", None) or {}
        self._device_name_cache = None
        self._update_scan_selector()

    def _scan_docstring(self, scan_name: str) -> str | None:
        scan_info = self.available_scans.get(scan_name, {})
        docstring = scan_info.get("doc") if isinstance(scan_info, dict) else None
        return docstring if isinstance(docstring, str) else None

    def _supported_scan_names(self) -> list[str]:
        return [
            scan_name
            for scan_name, scan_info in self.available_scans.items()
            if self._scan_info_adapter.has_scan_ui_config(scan_info)
            and not scan_name.startswith("_")
        ]

    def _update_scan_selector(self) -> None:
        if self._selected_scan:
            self.save_current_scan_parameters()
        allowed = self.config.allowed_scans
        if allowed is None:
            visible = self._supported_scan_names()
        else:
            visible = [scan for scan in allowed if scan in self.available_scans]
        self._visible_scans = visible
        if not visible:
            if self._selected_scan:
                self._selected_scan = ""
                self.form.load(None)
            self._sync_view(True)
            return
        if self._selected_scan not in visible:
            self.on_scan_selection_changed(visible[0])
        else:
            self._sync_view(True)

    def visible_scans(self) -> list[str]:
        """Scans offered by the selector, in order."""
        return list(self._visible_scans)

    def scan_tooltip(self, scan_name: str) -> str:
        """Rich tooltip with the documentation of a scan."""
        return render_scan_tooltip_html(scan_name, self._scan_docstring(scan_name))

    def is_valid_scan(self, scan_name: str) -> bool:
        """Whether ``scan_name`` is offered by the selector (case-insensitive)."""
        return self._resolve_scan_name(scan_name) is not None

    def _resolve_scan_name(self, scan_name: str) -> str | None:
        if not scan_name:
            return None
        lowered = scan_name.lower()
        for name in self._visible_scans:
            if name.lower() == lowered:
                return name
        return None

    def on_scan_selection_changed(self, scan_name: str):
        """Switch to ``scan_name``; unknown names are ignored."""
        resolved = self._resolve_scan_name(scan_name)
        if resolved is None or resolved == self._selected_scan:
            return
        if self._selected_scan:
            self._save_scan_parameters(self._selected_scan)
        self._selected_scan = resolved
        self._touched.clear()
        self._show_all_errors = False
        gui_config = self._scan_info_adapter.build_scan_ui_config(
            self.available_scans.get(resolved, {})
        )
        self.form.load(gui_config)
        self.scan_selected.emit(resolved)
        self.restore_scan_parameters(resolved)
        self._sync_view(True)

    @SafeProperty(str)
    def current_scan(self) -> str:
        """Name of the selected scan."""
        return self._selected_scan

    @current_scan.setter
    def current_scan(self, scan_name: str):
        self.on_scan_selection_changed(scan_name)

    @SafeSlot(str)
    def set_current_scan(self, scan_name: str):
        """Slot for setting the current scan to the given scan name."""
        self.current_scan = scan_name

    @SafeProperty("QStringList")
    def allowed_scans(self) -> list[str]:
        """Scans configured for the selector; see :attr:`ScanControl.allowed_scans`."""
        allowed = getattr(self.config, "allowed_scans", None)
        return self._supported_scan_names() if allowed is None else list(allowed)

    @allowed_scans.setter
    def allowed_scans(self, scan_names: list[str] | str | None):
        if isinstance(scan_names, str):
            scan_names = [scan_names]
        if scan_names is not None:
            scan_names = list(dict.fromkeys(scan_names))
            if not scan_names or scan_names == self._supported_scan_names():
                scan_names = None
        self.config.allowed_scans = scan_names
        self._update_scan_selector()

    @SafeSlot()
    @SafeSlot(bool)
    def show_scan_selector_settings(self, *_):
        """Open the scan filter dialog and apply accepted changes."""
        scan_names = self._supported_scan_names()
        allowed = self.config.allowed_scans
        if allowed is not None:
            scan_names += [scan for scan in allowed if scan not in scan_names]
        dialog = ScanSelectionDialog(
            scan_names=scan_names,
            selected_scans=scan_names if allowed is None else allowed,
            scan_docs={name: self._scan_docstring(name) for name in scan_names},
            parent=self,
        )
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
            selected = dialog.selected_scans() if accepted else None
        finally:
            dialog.deleteLater()
        if selected is not None:
            self.allowed_scans = None if selected == scan_names else selected

    @SafeSlot()
    @SafeSlot(bool)
    def show_selected_scan_info(self, *_args) -> None:
        """Show the documentation of the selected scan."""
        self.show_scan_info(self._selected_scan)

    @SafeSlot(str)
    def show_scan_info(self, scan_name: str) -> None:
        """Show documentation for a specific scan."""
        if self._scan_info_dialog is None:
            self._scan_info_dialog = ScanInfoDialog(self)
        self._scan_info_dialog.show_scan(scan_name, self._scan_docstring(scan_name))

    # ---- form editing --------------------------------------------------------------------

    def set_field(self, key: str, value) -> None:
        """Set a field from the renderer; marks it as edited so its error becomes visible."""
        self._touched.add(key)
        self.form.set_value(key, value)

    def add_row(self) -> None:
        """Add an argument row."""
        self.form.add_bundle()

    def remove_row(self, index: int) -> None:
        """Remove argument row ``index``."""
        self.form.remove_bundle(index)
        self._touched = {key for key in self._touched if not key.startswith("args:")}

    @SafeSlot(str)
    def emit_device_selected(self, dev_names: str):
        """Forward the devices chosen in the argument rows."""
        self._selected_devices = dev_names
        self.device_selected.emit(dev_names)

    # ---- parameters ----------------------------------------------------------------------

    def get_scan_parameters(self, bec_object: bool = True):
        """Return ``(args, kwargs)`` for the selected scan, including metadata.

        Args:
            bec_object(bool): Return device objects for device arguments.
        """
        args = self.form.args(bec_object)
        kwargs = self.form.kwargs()
        if self._scan_metadata is not None:
            kwargs["metadata"] = self._scan_metadata
        return args, kwargs

    def save_current_scan_parameters(self):
        """Remember the parameters of the selected scan."""
        self._save_scan_parameters(self._selected_scan)

    def _save_scan_parameters(self, scan_name: str):
        if not scan_name:
            return
        self.previous_scan = scan_name
        args = self.form.args(bec_object=False)
        kwargs = self.form.kwargs()
        self.config.scans[scan_name] = ScanParameterConfig(name=scan_name, args=args, kwargs=kwargs)

    def restore_scan_parameters(self, scan_name: str):
        """Restore remembered parameters of ``scan_name``, else shared ones of the last scan."""
        params = self.config.scans.get(scan_name)
        if params is None:
            previous = self.config.scans.get(self.previous_scan) if self.previous_scan else None
            if previous is not None and previous.kwargs:
                self.form.set_kwargs(
                    {key: value for key, value in previous.kwargs.items() if value is not None}
                )
            return
        if params.args:
            self.form.set_args(params.args)
        if params.kwargs:
            self.form.set_kwargs(params.kwargs)

    @SafeSlot()
    @SafeSlot(bool)
    def request_last_executed_scan_parameters(self, *_):
        """Fetch the parameters of the last run of the selected scan in the background."""
        if self._restore_busy or not self._selected_scan:
            return
        self._set_restore_busy(True)
        self._last_scan_fetch_generation += 1
        generation = self._last_scan_fetch_generation
        self._last_scan_fetch_watchdog.start()
        try:
            self.submit_task(
                self._fetch_last_executed_scan_parameters,
                generation,
                self._selected_scan,
                on_complete=partial(self._on_last_scan_parameters_finished, generation),
                on_failed=lambda _msg, gen=generation: self._on_last_scan_parameters_finished(gen),
            )
        except Exception:
            self._on_last_scan_parameters_finished(generation)
            raise

    @SafeSlot(int, str, object)
    def _apply_last_scan_parameters(self, generation: int, scan_name: str, parameters):
        if generation != self._last_scan_fetch_generation or scan_name != self._selected_scan:
            return
        args, kwargs = parameters
        if args:
            self.form.set_args(args)
        if kwargs:
            self.form.set_kwargs(kwargs)

    @SafeSlot()
    def _on_last_scan_parameters_finished(self, generation: int | None = None):
        if generation is not None and generation != self._last_scan_fetch_generation:
            return
        self._last_scan_fetch_watchdog.stop()
        self._set_restore_busy(False)

    @SafeSlot()
    def _on_last_scan_parameters_timeout(self):
        logger.warning("Timed out while fetching the last executed scan parameters")
        self._last_scan_fetch_generation += 1
        self._set_restore_busy(False)

    def _set_restore_busy(self, busy: bool) -> None:
        self._restore_busy = busy
        self._sync_view(False)

    # ---- metadata ------------------------------------------------------------------------

    @SafeSlot(dict)
    @SafeSlot(NoneType)
    def update_scan_metadata(self, md: dict | None):
        """Receive validated metadata (or None when the form is invalid)."""
        self._scan_metadata = md
        self._sync_view(False)

    @SafeSlot()
    def show_metadata_dialog(self) -> None:
        """Open the metadata form in a dialog."""
        if self._metadata_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle(f"Scan metadata · {self._selected_scan}")
            layout = QVBoxLayout(dialog)
            self._metadata_form.setParent(dialog)
            self._metadata_form.show()
            layout.addWidget(self._metadata_form)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
            buttons.rejected.connect(dialog.close)
            layout.addWidget(buttons)
            dialog.resize(420, 360)
            self._metadata_dialog = dialog
        self._metadata_dialog.setWindowTitle(f"Scan metadata · {self._selected_scan}")
        self._metadata_dialog.show()
        self._metadata_dialog.raise_()

    # ---- run / stop ----------------------------------------------------------------------

    @SafeSlot(popup_error=True)
    def run_scan(self):
        """Start the selected scan; if fields are invalid, reveal every error instead."""
        scan_name = self._selected_scan
        if not scan_name or self._scan_metadata is None:
            return
        if not self.form.is_valid():
            self._show_all_errors = True
            self._sync_view(False)
            return
        args, kwargs = self.get_scan_parameters()
        self.scan_args.emit(args)
        scan_function = getattr(self.scans, scan_name)
        if callable(scan_function):
            self.scan_started.emit()
            scan_function(*args, **kwargs)

    @SafeSlot()
    def stop_scan(self) -> None:
        """Abort the running scan; a second press within 2 s halts it (emergency stop)."""
        if self._emergency_stop:
            self.queue.request_scan_halt()
        else:
            self.queue.request_scan_abortion()
        self._emergency_stop = True
        self._emergency_timer.start(self.EMERGENCY_STOP_TIMEOUT_MS)
        self._sync_view(False)

    def _reset_emergency_stop(self) -> None:
        self._emergency_stop = False
        self._sync_view(False)

    # ---- view state ----------------------------------------------------------------------

    def view_state(self) -> dict:
        """Display-ready state shared by both renderers (values excluded from ``groups``)."""
        errors = self.form.errors()
        visible_errors = {
            key: message
            for key, message in errors.items()
            if self._show_all_errors or key in self._touched
        }
        scan = self._selected_scan
        if not scan:
            hint = "No scan available" if not self._visible_scans else "Choose a scan"
        elif self._scan_metadata is None:
            hint = "Complete the metadata to start"
        elif errors and self._show_all_errors:
            count = len(errors)
            hint = (
                f"{count} field{'s' if count != 1 else ''} need{'s' if count == 1 else ''} a value"
            )
        else:
            hint = ""
        return {
            "scans": self._visible_scans,
            "current": scan,
            "summary": doc_summary(self._scan_docstring(scan)) if scan else "",
            "errors": visible_errors,
            "canStart": bool(scan) and self._scan_metadata is not None,
            "startLabel": f"Start {scan}" if scan else "Start",
            "hint": hint,
            "metadataValid": self._scan_metadata is not None,
            "restoreBusy": self._restore_busy,
            "stopLabel": "Emergency Stop" if self._emergency_stop else "Stop",
            "emergency": self._emergency_stop,
            "showSelector": not self._hide_scan_selection_combobox,
            "showFilter": not self._hide_scan_selector_settings_button,
            "showArgs": not self._hide_arg_box,
            "showKwargs": not self._hide_kwarg_boxes,
            "showButtons": not self._hide_scan_control_buttons,
            "showMetadata": not self._hide_metadata,
            "showRowButtons": not self._hide_add_remove_buttons,
        }

    # ---- Designer properties (same as ScanControl) ------------------------------------------

    def _set_flag(self, name: str, value: bool) -> None:
        setattr(self, name, bool(value))
        self._sync_view(True)

    @SafeProperty(bool)
    def hide_arg_box(self) -> bool:
        """Hide the argument rows."""
        return self._hide_arg_box

    @hide_arg_box.setter
    def hide_arg_box(self, hide: bool):
        self._set_flag("_hide_arg_box", hide)

    @SafeProperty(bool)
    def hide_kwarg_boxes(self) -> bool:
        """Hide the keyword parameter groups."""
        return self._hide_kwarg_boxes

    @hide_kwarg_boxes.setter
    def hide_kwarg_boxes(self, hide: bool):
        self._set_flag("_hide_kwarg_boxes", hide)

    @SafeProperty(bool)
    def hide_scan_control_buttons(self) -> bool:
        """Hide Start and Stop."""
        return self._hide_scan_control_buttons

    @hide_scan_control_buttons.setter
    def hide_scan_control_buttons(self, hide: bool):
        self._set_flag("_hide_scan_control_buttons", hide)

    @SafeSlot(bool)
    def show_scan_control_buttons(self, show: bool):
        """Shows or hides the scan control buttons."""
        self.hide_scan_control_buttons = not show

    @SafeProperty(bool)
    def hide_metadata(self) -> bool:
        """Hide the metadata button."""
        return self._hide_metadata

    @hide_metadata.setter
    def hide_metadata(self, hide: bool):
        self._set_flag("_hide_metadata", hide)

    @SafeProperty(bool)
    def hide_optional_metadata(self) -> bool:
        """Hide optional metadata fields in the metadata form."""
        return self._metadata_form.hide_optional_metadata

    @hide_optional_metadata.setter
    def hide_optional_metadata(self, hide: bool):
        self._metadata_form.hide_optional_metadata = hide

    @SafeProperty(bool)
    def hide_scan_selection_combobox(self) -> bool:
        """Hide the scan selector."""
        return self._hide_scan_selection_combobox

    @hide_scan_selection_combobox.setter
    def hide_scan_selection_combobox(self, hide: bool):
        self._set_flag("_hide_scan_selection_combobox", hide)

    @SafeSlot(bool)
    def show_scan_selection_combobox(self, show: bool):
        """Shows or hides the scan selection combobox."""
        self.hide_scan_selection_combobox = not show

    @SafeProperty(bool)
    def hide_scan_selector_settings_button(self) -> bool:
        """Hide the scan filter button."""
        return self._hide_scan_selector_settings_button

    @hide_scan_selector_settings_button.setter
    def hide_scan_selector_settings_button(self, hide: bool):
        self._set_flag("_hide_scan_selector_settings_button", hide)

    @SafeProperty(bool)
    def hide_add_remove_buttons(self) -> bool:
        """Hide the buttons that add and remove argument rows."""
        return self._hide_add_remove_buttons

    @hide_add_remove_buttons.setter
    def hide_add_remove_buttons(self, hide: bool):
        self._set_flag("_hide_add_remove_buttons", hide)

    # ---- lifecycle -----------------------------------------------------------------------

    def cleanup(self):
        """Stop timers, close dialogs and release the renderer."""
        self._last_scan_fetch_generation += 1
        self._last_scan_fetch_watchdog.stop()
        self._emergency_timer.stop()
        for dialog in (self._scan_info_dialog, self._metadata_dialog):
            if dialog is not None:
                dialog.close()
                dialog.deleteLater()
        self._scan_info_dialog = None
        self._metadata_dialog = None
        super().cleanup()

    # ---- renderer hooks ------------------------------------------------------------------

    def _init_view(self) -> None:
        """Create the renderer."""
        raise NotImplementedError

    def _sync_view(self, structure: bool) -> None:
        """Redraw the renderer; ``structure`` is True when fields were added or removed."""
        raise NotImplementedError


ScanControlPortBase.PORTED_FROM = ScanControlPortBase
