"""Shared behaviour and public API of the modernized scan control widgets.

``ScanControlQml`` and ``ScanControlModern`` derive from ``ModernScanControlBase`` and only add
a view. The public API mirrors the classic ``ScanControl`` so either can replace it.
"""

from __future__ import annotations

from types import NoneType

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.metadata_schema import get_metadata_schema_for_scan
from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import QDialog, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.scan_arg_metadata import device_units
from bec_widgets.widgets.control.scan_control.modern.form_core import (
    MetadataFormState,
    ScanFormSpec,
    ScanFormState,
    device_names_for_scans,
    lookup_last_scan_parameters,
)
from bec_widgets.widgets.control.scan_control.scan_control import (
    ScanControlConfig,
    ScanParameterConfig,
)
from bec_widgets.widgets.control.scan_control.scan_info_adapter import ScanInfoAdapter
from bec_widgets.widgets.control.scan_control.scan_info_dialog import ScanInfoDialog
from bec_widgets.widgets.control.scan_control.scan_selection_dialog import ScanSelectionDialog

logger = bec_logger.logger


class ModernScanControlBase(BECWidget, QWidget):
    """Scan submission form with the same public API as ``ScanControl``.

    Subclasses provide the view by overriding ``_build_view`` and reacting to the signals of
    ``form``, ``metadata`` and ``status_changed``.
    """

    USER_ACCESS = ["attach", "detach", "screenshot"]
    RPC = False
    PLUGIN = False
    LAST_SCAN_FETCH_TIMEOUT_MS = 30_000
    EMERGENCY_STOP_WINDOW_MS = 3_000

    scan_started = Signal()
    scan_selected = Signal(str)
    device_selected = Signal(str)
    scan_args = Signal(list)
    #: The scan list, a ``hide_*`` option, or the start/restore availability changed.
    status_changed = Signal()
    #: Short feedback for the footer, e.g. after submitting or restoring.
    notice = Signal(str)
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
        self.get_bec_shortcuts()
        if default_scan is not None:
            self.config.default_scan = default_scan
        if allowed_scans is not None:
            self.config.allowed_scans = list(dict.fromkeys(allowed_scans)) or None

        self._adapter = ScanInfoAdapter()
        self.available_scans: dict = {}
        self.visible_scans: list[str] = []
        self._selected_scan = ""
        self.previous_scan: str | None = None
        self._scan_info_dialog: ScanInfoDialog | None = None
        self._options = {
            "hide_arg_box": False,
            "hide_kwarg_boxes": False,
            "hide_scan_control_buttons": False,
            "hide_metadata": False,
            "hide_optional_metadata": False,
            "hide_scan_selection_combobox": False,
            "hide_scan_selector_settings_button": False,
            "hide_add_remove_buttons": False,
        }

        self.form = ScanFormState(self)
        self.form.units_resolver = self._device_units
        self.form.values_changed.connect(self._on_form_values_changed)
        self.metadata = MetadataFormState(self)
        self.metadata.values_changed.connect(self.status_changed)

        self._restoring = False
        self._fetch_generation = 0
        self._fetch_watchdog = QTimer(self)
        self._fetch_watchdog.setSingleShot(True)
        self._fetch_watchdog.setInterval(self.LAST_SCAN_FETCH_TIMEOUT_MS)
        self._fetch_watchdog.timeout.connect(self._on_fetch_timeout)
        self._last_scan_parameters_received.connect(self._apply_last_scan_parameters)
        self._stop_armed = False
        self._stop_timer = QTimer(self)
        self._stop_timer.setSingleShot(True)
        self._stop_timer.setInterval(self.EMERGENCY_STOP_WINDOW_MS)
        self._stop_timer.timeout.connect(self._disarm_stop)
        self._last_devices = ""

        self._build_view()
        self.refresh_devices()
        self.populate_scans()
        if self.config.default_scan is not None:
            self.current_scan = self.config.default_scan

    def _build_view(self) -> None:
        """Create the view. Implemented by subclasses."""
        raise NotImplementedError

    # ------------------------------------------------------------------ scans

    def populate_scans(self) -> None:
        """Read the available scans from BEC and refresh the selector."""
        msg = self.client.connector.get(MessageEndpoints.available_scans())
        self.available_scans = msg.resource if msg is not None else {}
        self._update_scan_selector()

    def _supported_scan_names(self) -> list[str]:
        return [
            name
            for name, info in self.available_scans.items()
            if self._adapter.has_scan_ui_config(info) and not name.startswith("_")
        ]

    def _update_scan_selector(self) -> None:
        if self._selected_scan:
            self.save_current_scan_parameters()
        allowed = self.config.allowed_scans
        if allowed is None:
            self.visible_scans = self._supported_scan_names()
        else:
            self.visible_scans = [s for s in allowed if s in self.available_scans]
        self.status_changed.emit()
        if not self.visible_scans:
            self._selected_scan = ""
            self.form.load(ScanFormSpec())
        elif self._selected_scan not in self.visible_scans:
            self._select(self.visible_scans[0])

    def scan_docstring(self, scan_name: str) -> str | None:
        """Docstring of ``scan_name`` as published by BEC."""
        info = self.available_scans.get(scan_name, {})
        doc = info.get("doc") if isinstance(info, dict) else None
        return doc if isinstance(doc, str) else None

    def is_valid_scan(self, scan_name: str) -> bool:
        """Whether ``scan_name`` is listed in the selector (case-insensitive)."""
        return self._resolve_scan_name(scan_name) is not None

    def _resolve_scan_name(self, scan_name: str) -> str | None:
        lowered = (scan_name or "").lower()
        return next((s for s in self.visible_scans if s.lower() == lowered), None)

    def _select(self, scan_name: str) -> None:
        resolved = self._resolve_scan_name(scan_name)
        if resolved is None or resolved == self._selected_scan:
            return
        if self._selected_scan:
            self._save_scan_parameters(self._selected_scan)
        self._selected_scan = resolved
        info = self.available_scans.get(resolved, {})
        ui_config = self._adapter.build_scan_ui_config(info)
        self.form.load(
            ScanFormSpec.from_ui_config(resolved, self.scan_docstring(resolved), ui_config)
        )
        self.metadata.load(get_metadata_schema_for_scan(resolved), resolved)
        self.restore_scan_parameters(resolved)
        self.scan_selected.emit(resolved)
        self.status_changed.emit()

    @SafeProperty(str)
    def current_scan(self) -> str:
        """Name of the selected scan."""
        return self._selected_scan

    @current_scan.setter
    def current_scan(self, scan_name: str):
        self._select(scan_name)

    @SafeSlot(str)
    def set_current_scan(self, scan_name: str):
        """Select ``scan_name`` if it is listed."""
        self._select(scan_name)

    @SafeProperty("QStringList")
    def allowed_scans(self) -> list[str]:
        """Scans shown in the selector; every supported scan when no filter is set."""
        allowed = self.config.allowed_scans
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
    def show_selected_scan_info(self, *_args) -> None:
        """Show the documentation of the selected scan."""
        self.show_scan_info(self._selected_scan)

    @SafeSlot(str)
    def show_scan_info(self, scan_name: str) -> None:
        """Show the documentation of ``scan_name`` in a non-blocking dialog."""
        if self._scan_info_dialog is None:
            self._scan_info_dialog = ScanInfoDialog(self)
        self._scan_info_dialog.show_scan(scan_name, self.scan_docstring(scan_name))

    @SafeSlot()
    def show_scan_selector_settings(self, *_args) -> None:
        """Let the user choose which scans the selector offers."""
        scan_names = self._supported_scan_names()
        allowed = self.config.allowed_scans
        if allowed is not None:
            scan_names += [s for s in allowed if s not in scan_names]
        dialog = ScanSelectionDialog(
            scan_names=scan_names,
            selected_scans=scan_names if allowed is None else allowed,
            scan_docs={name: self.scan_docstring(name) for name in scan_names},
            parent=self,
        )
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
            selected = dialog.selected_scans() if accepted else None
        finally:
            dialog.deleteLater()
        if selected is not None:
            self.allowed_scans = None if selected == scan_names else selected

    # ------------------------------------------------------------------ devices

    @SafeSlot()
    def refresh_devices(self) -> None:
        """Reload the device names offered by device fields."""
        self.form.device_names = device_names_for_scans(self.dev)

    def _device_units(self, device_name: str) -> str | None:
        device = getattr(self.dev, device_name, None)
        return device_units(device) if device is not None else None

    def _on_form_values_changed(self) -> None:
        devices = " ".join(d for d in self.form.selected_devices() if d in self.form.device_names)
        if devices != self._last_devices:
            self._last_devices = devices
            self.device_selected.emit(devices)
        self.status_changed.emit()

    # ------------------------------------------------------------------ parameters

    def get_scan_parameters(self, bec_object: bool = True) -> tuple[list, dict]:
        """Positional and keyword arguments of the scan as entered in the form.

        Args:
            bec_object(bool): If True, device fields are returned as device objects.
        """
        args = self.form.args_list(self.dev if bec_object else None)
        kwargs = self.form.kwargs_dict()
        if self.metadata.data is not None:
            kwargs["metadata"] = self.metadata.data
        return args, kwargs

    def save_current_scan_parameters(self) -> None:
        """Remember the values of the selected scan in the widget config."""
        if self._selected_scan:
            self._save_scan_parameters(self._selected_scan)

    def _save_scan_parameters(self, scan_name: str) -> None:
        self.previous_scan = scan_name
        self.config.scans[scan_name] = ScanParameterConfig(
            name=scan_name, args=self.form.args_list(), kwargs=self.form.kwargs_dict()
        )

    def restore_scan_parameters(self, scan_name: str) -> None:
        """Restore remembered values of ``scan_name``; shared keywords carry over between scans."""
        params = self.config.scans.get(scan_name)
        if params is None and self.previous_scan is not None:
            previous = self.config.scans.get(self.previous_scan)
            if previous is not None and previous.kwargs:
                self.form.set_kwargs(previous.kwargs)
            return
        if params is None:
            return
        if params.args:
            self.form.set_args(params.args)
        if params.kwargs:
            self.form.set_kwargs(params.kwargs)

    # ------------------------------------------------------------------ status

    def problems(self) -> list[str]:
        """Reasons why Start is disabled, most important first."""
        if not self._selected_scan:
            return ["No scan selected"]
        return self.form.problems() + self.metadata.problems()

    def can_start(self) -> bool:
        """Whether the form is complete and valid."""
        return not self.problems()

    @property
    def is_restoring(self) -> bool:
        """Whether the last scan parameters are being fetched."""
        return self._restoring

    def option(self, name: str) -> bool:
        """Current value of a ``hide_*`` option."""
        return self._options[name]

    def _set_option(self, name: str, value: bool) -> None:
        self._options[name] = bool(value)
        self.status_changed.emit()

    # ------------------------------------------------------------------ actions

    @SafeSlot(popup_error=True)
    def run_scan(self, *_args) -> None:
        """Submit the selected scan with the entered parameters."""
        if not self.can_start():
            self.notice.emit(self.problems()[0])
            return
        args, kwargs = self.get_scan_parameters()
        self.scan_args.emit(args)
        scan_function = getattr(self.scans, self._selected_scan)
        if callable(scan_function):
            self.scan_started.emit()
            scan_function(*args, **kwargs)
            self.notice.emit(f"Submitted {self._selected_scan}")

    @SafeSlot()
    def stop_scan(self, *_args) -> None:
        """Abort the running scan; a second click within a few seconds halts it."""
        if self._stop_armed:
            self.queue.request_scan_halt()
            self.notice.emit("Halt requested")
        else:
            self.queue.request_scan_abortion()
            self.notice.emit("Abort requested. Click Stop again to halt immediately.")
        self._stop_armed = True
        self._stop_timer.start()
        self.status_changed.emit()

    @property
    def stop_armed(self) -> bool:
        """Whether the next Stop click requests a halt."""
        return self._stop_armed

    def _disarm_stop(self) -> None:
        self._stop_armed = False
        self.status_changed.emit()

    @SafeSlot()
    def request_last_executed_scan_parameters(self, *_args) -> None:
        """Fill the form with the parameters of the last run of the selected scan."""
        if self._restoring or not self._selected_scan:
            return
        self._restoring = True
        self._fetch_generation += 1
        generation = self._fetch_generation
        self._fetch_watchdog.start()
        self.status_changed.emit()
        self.submit_task(
            self._fetch_last_parameters,
            generation,
            self._selected_scan,
            on_complete=lambda *_: self._on_fetch_finished(generation),
            on_failed=lambda *_: self._on_fetch_finished(generation),
        )

    def _fetch_last_parameters(self, generation: int, scan_name: str) -> None:
        try:
            parameters = lookup_last_scan_parameters(self.client, scan_name)
        except Exception:  # pylint: disable=broad-except
            logger.exception(f"Failed to fetch parameters for scan {scan_name}")
            return
        try:
            self._last_scan_parameters_received.emit(generation, scan_name, parameters)
        except RuntimeError:
            logger.debug("Scan control deleted before the last scan parameters arrived")

    @SafeSlot(int, str, object)
    def _apply_last_scan_parameters(self, generation: int, scan_name: str, parameters) -> None:
        if generation != self._fetch_generation or scan_name != self._selected_scan:
            return
        if parameters is None:
            self.notice.emit(f"No earlier run of {scan_name} found")
            return
        args, kwargs = parameters
        if args:
            self.form.set_args(args)
        if kwargs:
            self.form.set_kwargs(kwargs)
        self.notice.emit(f"Restored the last {scan_name} parameters")

    def _on_fetch_finished(self, generation: int) -> None:
        if generation != self._fetch_generation:
            return
        self._fetch_watchdog.stop()
        self._restoring = False
        self.status_changed.emit()

    def _on_fetch_timeout(self) -> None:
        logger.warning("Timed out while fetching the last executed scan parameters")
        self._fetch_generation += 1
        self._restoring = False
        self.notice.emit("Could not reach the scan history")
        self.status_changed.emit()

    @SafeSlot(dict)
    @SafeSlot(NoneType)
    def update_scan_metadata(self, md: dict | None) -> None:
        """Replace the free metadata entries with ``md``."""
        self.metadata.set_extras(list((md or {}).items()))

    # ------------------------------------------------------------------ hide_* options

    @SafeProperty(bool)
    def hide_arg_box(self) -> bool:
        """Hide the argument rows."""
        return self._options["hide_arg_box"]

    @hide_arg_box.setter
    def hide_arg_box(self, hide: bool):
        self._set_option("hide_arg_box", hide)

    @SafeProperty(bool)
    def hide_kwarg_boxes(self) -> bool:
        """Hide the keyword argument groups."""
        return self._options["hide_kwarg_boxes"]

    @hide_kwarg_boxes.setter
    def hide_kwarg_boxes(self, hide: bool):
        self._set_option("hide_kwarg_boxes", hide)

    @SafeProperty(bool)
    def hide_scan_control_buttons(self) -> bool:
        """Hide the Start/Stop footer."""
        return self._options["hide_scan_control_buttons"]

    @hide_scan_control_buttons.setter
    def hide_scan_control_buttons(self, hide: bool):
        self._set_option("hide_scan_control_buttons", hide)

    @SafeSlot(bool)
    def show_scan_control_buttons(self, show: bool):
        """Show or hide the Start/Stop footer."""
        self._set_option("hide_scan_control_buttons", not show)

    @SafeProperty(bool)
    def hide_metadata(self) -> bool:
        """Hide the metadata section."""
        return self._options["hide_metadata"]

    @hide_metadata.setter
    def hide_metadata(self, hide: bool):
        self._set_option("hide_metadata", hide)

    @SafeProperty(bool)
    def hide_optional_metadata(self) -> bool:
        """Hide the free key/value metadata."""
        return self._options["hide_optional_metadata"]

    @hide_optional_metadata.setter
    def hide_optional_metadata(self, hide: bool):
        self._set_option("hide_optional_metadata", hide)

    @SafeProperty(bool)
    def hide_scan_selection_combobox(self) -> bool:
        """Hide the scan selector."""
        return self._options["hide_scan_selection_combobox"]

    @hide_scan_selection_combobox.setter
    def hide_scan_selection_combobox(self, hide: bool):
        self._set_option("hide_scan_selection_combobox", hide)

    @SafeSlot(bool)
    def show_scan_selection_combobox(self, show: bool):
        """Show or hide the scan selector."""
        self._set_option("hide_scan_selection_combobox", not show)

    @SafeProperty(bool)
    def hide_scan_selector_settings_button(self) -> bool:
        """Hide the button that filters the scan list."""
        return self._options["hide_scan_selector_settings_button"]

    @hide_scan_selector_settings_button.setter
    def hide_scan_selector_settings_button(self, hide: bool):
        self._set_option("hide_scan_selector_settings_button", hide)

    @SafeProperty(bool)
    def hide_add_remove_buttons(self) -> bool:
        """Hide adding and removing argument rows."""
        return self._options["hide_add_remove_buttons"]

    @hide_add_remove_buttons.setter
    def hide_add_remove_buttons(self, hide: bool):
        self._set_option("hide_add_remove_buttons", hide)

    def cleanup(self):
        """Stop timers and close dialogs."""
        self._fetch_generation += 1
        self._fetch_watchdog.stop()
        self._stop_timer.stop()
        if self._scan_info_dialog is not None:
            self._scan_info_dialog.close()
            self._scan_info_dialog.deleteLater()
            self._scan_info_dialog = None
        super().cleanup()
