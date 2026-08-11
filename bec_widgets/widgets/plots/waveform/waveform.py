from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger, messages
from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.lmfit_serializer import serialize_lmfit_params, serialize_param_object
from bec_lib.scan_data_container import ScanDataContainer
from bec_lib.utils.import_utils import lazy_import
from pydantic import Field, ValidationError, field_validator
from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_signal_proxy import BECSignalProxy
from bec_widgets.utils.colors import Colors, apply_theme
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.qt_data_subscription import QtDataSubscription
from bec_widgets.utils.settings_dialog import SettingsDialog
from bec_widgets.utils.side_panel import SidePanel
from bec_widgets.utils.signal_classification import SignalCategory, classify_device_signal
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import MaterialIconAction
from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog import LMFitDialog
from bec_widgets.widgets.plots.plot_base import PlotBase
from bec_widgets.widgets.plots.waveform.curve import Curve, CurveConfig, DeviceSignal
from bec_widgets.widgets.plots.waveform.settings.curve_settings.curve_setting import CurveSetting
from bec_widgets.widgets.plots.waveform.utils.alignment_controller import (
    AlignmentContext,
    WaveformAlignmentController,
)
from bec_widgets.widgets.plots.waveform.utils.alignment_panel import WaveformAlignmentPanel
from bec_widgets.widgets.plots.waveform.utils.roi_manager import WaveformROIManager
from bec_widgets.widgets.services.scan_history_browser.scan_history_browser import (
    ScanHistoryBrowser,
)

logger = bec_logger.logger
_DAP_PARAM = object()

if TYPE_CHECKING:  # pragma: no cover
    import lmfit  # type: ignore
else:
    lmfit = lazy_import("lmfit")


# noinspection PyDataclass
class WaveformConfig(ConnectionConfig):
    color_palette: str | None = Field(
        "plasma", description="The color palette of the figure widget.", validate_default=True
    )
    max_dataset_size_mb: float = Field(
        10,
        description="Maximum dataset size (in MB) permitted when fetching async data from history before prompting the user.",
        validate_default=True,
    )

    model_config: dict = {"validate_assignment": True}
    _validate_color_palette = field_validator("color_palette")(Colors.validate_color_map)


class Waveform(PlotBase):
    #: 15 Hz: above typical device message rates while leaving paint headroom
    #: for multi-million-point async curves (benchmarked).
    DEFAULT_UPDATE_RATE = 15.0
    """
    Widget for plotting waveforms.
    """

    PLUGIN = True
    RPC = True
    ICON_NAME = "show_chart"
    USER_ACCESS = [
        *PlotBase.USER_ACCESS,
        "_config_dict",
        # Waveform Specific RPC Access
        "curves",
        "x_mode",
        "x_mode.setter",
        "signal_x",
        "signal_x.setter",
        "color_palette",
        "color_palette.setter",
        "skip_large_dataset_warning",
        "skip_large_dataset_warning.setter",
        "skip_large_dataset_check",
        "skip_large_dataset_check.setter",
        "max_dataset_size_mb",
        "max_dataset_size_mb.setter",
        "plot",
        "add_dap_curve",
        "remove_curve",
        "update_with_scan_history",
        "get_dap_params",
        "get_dap_summary",
        "get_all_data",
        "get_curve",
        "select_roi",
        "clear_all",
    ]

    request_dap_update = Signal()
    unblock_dap_proxy = Signal()
    dap_params_update = Signal(dict, dict)
    dap_summary_update = Signal(dict, dict)
    new_scan = Signal()
    new_scan_id = Signal(str)

    roi_changed = Signal(tuple)
    roi_active = Signal(bool)
    roi_enable = Signal(bool)  # enable toolbar icon

    def __init__(
        self,
        parent: QWidget | None = None,
        config: WaveformConfig | None = None,
        client=None,
        gui_id: str | None = None,
        popups: bool = True,
        **kwargs,
    ):
        if config is None:
            config = WaveformConfig(widget_class=self.__class__.__name__)
        super().__init__(
            parent=parent, config=config, client=client, gui_id=gui_id, popups=popups, **kwargs
        )

        # Curve data
        self._sync_curves = []
        self._async_curves = []
        self._history_curves = []
        self._dap_curves = []
        self._mode = None

        # Data delivery through the DataAPI: one bridge follows the widget's
        # scan (live or a history scan pinned via update_with_scan_history),
        # plus one bridge per scan pinned by individual history curves.
        self._data_bridge: QtDataSubscription | None = None
        self._data_api_scan: str = "live"
        self._history_bridges: dict[str, QtDataSubscription] = {}
        self._history_x_keys: dict[str, tuple[str, str] | None] = {}
        self._shutting_down = False

        # Scan data
        self.old_scan_id = None
        self.scan_id = None
        self.scan_item = None
        self.x_axis_mode = {
            "name": "auto",
            "entry": None,
            "readout_priority": None,
            "label_suffix": "",
        }
        self._current_x_device: tuple[str, str] | None = None
        self._alignment_panel_visible = False
        self._alignment_side_panel: SidePanel | None = None
        self._alignment_panel_index: int | None = None
        self._alignment_panel: WaveformAlignmentPanel | None = None
        self._alignment_controller: WaveformAlignmentController | None = None
        self._alignment_positioner_name: str | None = None

        # Specific GUI elements
        self._init_roi_manager()
        self.dap_summary = None
        self.dap_summary_dialog = None
        self.scan_history_dialog = None
        self._add_waveform_specific_popup()
        self._enable_roi_toolbar_action(False)  # default state where are no dap curves
        self._init_curve_dialog()
        self._init_alignment_mode()
        self.curve_settings_dialog = None

        # Large-dataset guard
        self._skip_large_dataset_warning = False  # session flag
        self._size_confirmed_sources: set = set()  # (scan_id, source) confirm memo
        self._skip_large_dataset_check = False  # per-plot flag, to skip the warning for this plot

        # Scan status is only used for per-scan bookkeeping (reset, scan_id,
        # categorisation, DAP triggering); the data flows through the DataAPI.
        self.bec_dispatcher.connect_slot(self.on_scan_status, MessageEndpoints.scan_status())

        # DAP update loop
        self.proxy_dap_request = BECSignalProxy(
            self.request_dap_update, rateLimit=25, slot=self.request_dap, timeout=10.0
        )
        self.unblock_dap_proxy.connect(self.proxy_dap_request.unblock_proxy)
        self.roi_enable.connect(self._enable_roi_toolbar_action)

        self.update_with_scan_history(-1)

        # To fix the ViewAll action with clipToView activated
        self._connect_viewbox_menu_actions()

        self.toolbar.show_bundles(
            ["plot_export", "mouse_interaction", "roi", "alignment_mode", "axis_popup"]
        )

    def _connect_viewbox_menu_actions(self):
        """Connect the viewbox menu action ViewAll to the custom reset_view method."""
        menu = self.plot_item.vb.menu
        # Find and replace "View All" action
        for action in menu.actions():
            if action.text() == "View All":
                # Disconnect the default autoRange action
                action.triggered.disconnect()
                # Connect to the custom reset_view method
                action.triggered.connect(self._reset_view)
                break

    ################################################################################
    # Widget Specific GUI interactions
    ################################################################################
    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """
        Apply the theme to the widget.

        Args:
            theme(str, optional): The theme to be applied.
        """
        self._refresh_colors()
        alignment_panel = getattr(self, "_alignment_panel", None)
        alignment_controller = getattr(self, "_alignment_controller", None)
        if alignment_panel is not None:
            alignment_panel.refresh_theme_colors()
        if alignment_controller is not None:
            alignment_controller.refresh_theme_colors()
        super().apply_theme(theme)

    def add_side_menus(self):
        """
        Add side menus to the Waveform widget.
        """
        super().add_side_menus()
        self._add_dap_summary_side_menu()

    def _init_alignment_mode(self):
        """
        Initialize the top alignment panel.
        """
        self.toolbar.components.add_safe(
            "alignment_mode",
            MaterialIconAction(
                icon_name="align_horizontal_center",
                tooltip="Show Alignment Mode",
                checkable=True,
                parent=self,
            ),
        )
        bundle = ToolbarBundle("alignment_mode", self.toolbar.components)
        bundle.add_action("alignment_mode")
        self.toolbar.add_bundle(bundle)
        shown_bundles = list(self.toolbar.shown_bundles)
        if "alignment_mode" not in shown_bundles:
            shown_bundles.append("alignment_mode")
            self.toolbar.show_bundles(shown_bundles)

        self._alignment_side_panel = SidePanel(
            parent=self, orientation="top", panel_max_width=320, show_toolbar=False
        )
        self.layout_manager.add_widget_relative(
            self._alignment_side_panel,
            self.round_plot_widget,
            position="top",
            shift_direction="down",
        )

        self._alignment_panel = WaveformAlignmentPanel(parent=self, client=self.client)
        self._alignment_controller = WaveformAlignmentController(
            self.plot_item, self._alignment_panel, parent=self
        )
        self._alignment_panel_index = self._alignment_side_panel.add_menu(
            widget=self._alignment_panel
        )
        self._alignment_controller.move_absolute_requested.connect(self._move_alignment_positioner)
        self._alignment_controller.autoscale_requested.connect(self._autoscale_alignment_indicators)
        self.dap_summary_update.connect(self._alignment_controller.update_dap_summary)
        self.toolbar.components.get_action("alignment_mode").action.toggled.connect(
            self.toggle_alignment_mode
        )

        self._refresh_alignment_state()

    @SafeSlot(bool)
    def toggle_alignment_mode(self, checked: bool):
        """
        Show or hide the alignment panel.

        Args:
            checked(bool): Whether the panel should be visible.
        """
        if self._alignment_side_panel is None or self._alignment_panel_index is None:
            return

        self._alignment_panel_visible = checked
        if checked:
            self._alignment_side_panel.show_panel(self._alignment_panel_index)
            self._refresh_alignment_state(force_readback=True)
            self._refresh_dap_signals()
        else:
            self._alignment_side_panel.hide_panel()
            self._refresh_alignment_state()

    def _refresh_alignment_state(self, force_readback: bool = False):
        """
        Refresh the alignment panel state after waveform changes.

        Args:
            force_readback(bool): Force a positioner readback refresh.
        """
        if self._alignment_controller is None:
            return

        context = self._build_alignment_context(force_readback=force_readback)
        self._alignment_positioner_name = context.positioner_name
        self._alignment_controller.update_context(context)

    def _resolve_alignment_positioner(self) -> str | None:
        """
        Resolve the active x-axis positioner for alignment mode.
        """
        if self.x_axis_mode["name"] in {"index", "timestamp"}:
            return None

        if self.x_axis_mode["name"] == "auto":
            device_name = self._current_x_device[0] if self._current_x_device is not None else None
        else:
            device_name = self.x_axis_mode["name"]

        if not device_name or device_name not in self.dev:
            return None
        if not isinstance(self.dev[device_name], Positioner):
            return None
        return device_name

    def _build_alignment_context(self, force_readback: bool = False) -> AlignmentContext:
        """Build controller-facing alignment context from waveform/device state."""
        positioner_name = self._resolve_alignment_positioner()
        if positioner_name is None:
            return AlignmentContext(
                visible=self._alignment_panel_visible,
                positioner_name=None,
                has_dap_curves=bool(self._dap_curves),
                force_readback=force_readback,
            )

        precision = getattr(self.dev[positioner_name], "precision", 3)
        try:
            precision = int(precision)
        except (TypeError, ValueError):
            precision = 3

        limits = getattr(self.dev[positioner_name], "limits", None)
        parsed_limits: tuple[float, float] | None = None
        if limits is not None and len(limits) == 2:
            low, high = float(limits[0]), float(limits[1])
            if low != 0 or high != 0:
                if low > high:
                    low, high = high, low
                parsed_limits = (low, high)

        data = self.dev[positioner_name].read(cached=True)
        value = data.get(positioner_name, {}).get("value")
        readback = None if value is None else float(value)

        return AlignmentContext(
            visible=self._alignment_panel_visible,
            positioner_name=positioner_name,
            precision=precision,
            limits=parsed_limits,
            readback=readback,
            has_dap_curves=bool(self._dap_curves),
            force_readback=force_readback,
        )

    @SafeSlot(float)
    def _move_alignment_positioner(self, value: float):
        """
        Move the active alignment positioner to an absolute value requested by the controller.
        """
        if self._alignment_positioner_name is None:
            return
        self.dev[self._alignment_positioner_name].move(float(value), relative=False)

    @SafeSlot()
    def _autoscale_alignment_indicators(self):
        """Autoscale the waveform view after alignment indicator updates."""
        self._reset_view()

    def _add_waveform_specific_popup(self):
        """
        Add popups to the Waveform widget.
        """
        self.toolbar.components.add_safe(
            "fit_params",
            MaterialIconAction(
                icon_name="monitoring", tooltip="Open Fit Parameters", checkable=True, parent=self
            ),
        )
        self.toolbar.components.add_safe(
            "scan_history",
            MaterialIconAction(
                icon_name="manage_search",
                tooltip="Open Scan History browser",
                checkable=True,
                parent=self,
            ),
        )
        self.toolbar.get_bundle("axis_popup").add_action("fit_params")
        self.toolbar.get_bundle("axis_popup").add_action("scan_history")

        self.toolbar.components.get_action("fit_params").action.triggered.connect(
            self.show_dap_summary_popup
        )
        self.toolbar.components.get_action("scan_history").action.triggered.connect(
            self.show_scan_history_popup
        )

    @SafeSlot()
    def _reset_view(self):
        """
        Custom _reset_view method to fix ViewAll action in toolbar.
        Due to setting clipToView to True on the curves, the autoRange() method
        of the ViewBox does no longer work as expected. This method deactivates the
        setClipToView for all curves, calls autoRange() to circumvent that issue.
        Afterward, it re-enables the setClipToView for all curves again.

        It is hooked to the ViewAll action in the right-click menu of the pg.PlotItem ViewBox.
        """
        for curve in self._async_curves + self._sync_curves:
            curve.setClipToView(False)
        self.plot_item.vb.autoRange()
        self.auto_range_x = True
        self.auto_range_y = True
        for curve in self._async_curves + self._sync_curves:
            curve.setClipToView(True)

    ################################################################################
    # Roi manager

    def _init_roi_manager(self):
        """
        Initialize the ROI manager for the Waveform widget.
        """
        # Add toolbar icon
        self.toolbar.components.add_safe(
            "roi_linear",
            MaterialIconAction(
                icon_name="align_justify_space_between",
                tooltip="Add ROI region for DAP",
                checkable=True,
                parent=self,
            ),
        )
        self.toolbar.get_bundle("roi").add_action("roi_linear")

        self._roi_manager = WaveformROIManager(self.plot_item, parent=self)

        # Connect manager signals -> forward them via Waveform's own signals
        self._roi_manager.roi_changed.connect(self.roi_changed)
        self._roi_manager.roi_active.connect(self.roi_active)

        # Example: connect ROI changed to re-request DAP
        self.roi_changed.connect(self._on_roi_changed_for_dap)
        self._roi_manager.roi_active.connect(self.request_dap_update)
        self.toolbar.components.get_action("roi_linear").action.toggled.connect(
            self._roi_manager.toggle_roi
        )

    def _init_curve_dialog(self):
        """
        Initializes the Curve dialog within the toolbar.
        """
        self.toolbar.components.add_safe(
            "curve",
            MaterialIconAction(
                icon_name="timeline", tooltip="Show Curve dialog.", checkable=True, parent=self
            ),
        )
        self.toolbar.get_bundle("axis_popup").add_action("curve")
        self.toolbar.components.get_action("curve").action.triggered.connect(
            self.show_curve_settings_popup
        )

    def show_curve_settings_popup(self):
        """
        Displays the curve settings popup to allow users to modify curve-related configurations.
        """
        curve_action = self.toolbar.components.get_action("curve").action

        if self.curve_settings_dialog is None or not self.curve_settings_dialog.isVisible():
            curve_setting = CurveSetting(parent=self, target_widget=self)
            self.curve_settings_dialog = SettingsDialog(
                self, settings_widget=curve_setting, window_title="Curve Settings", modal=False
            )
            # When the dialog is closed, update the toolbar icon and clear the reference
            self.curve_settings_dialog.finished.connect(self._curve_settings_closed)
            self.curve_settings_dialog.show()
            curve_action.setChecked(True)
        else:
            # If already open, bring it to the front
            self.curve_settings_dialog.raise_()
            self.curve_settings_dialog.activateWindow()
            curve_action.setChecked(True)  # keep it toggled

    def _curve_settings_closed(self):
        """
        Slot for when the axis settings dialog is closed.
        """
        self.curve_settings_dialog.close()
        self.curve_settings_dialog.deleteLater()
        self.curve_settings_dialog = None
        self.toolbar.components.get_action("curve").action.setChecked(False)

    @property
    def roi_region(self) -> tuple[float, float] | None:
        """
        Allows external code to get/set the ROI region easily via Waveform.
        """
        return self._roi_manager.roi_region

    @roi_region.setter
    def roi_region(self, value: tuple[float, float] | None):
        """
        Set the ROI region limits.

        Args:
            value(tuple[float, float] | None): The new ROI region limits.
        """
        self._roi_manager.roi_region = value

    def select_roi(self, region: tuple[float, float]):
        """
        Public method if you want the old `select_roi` style.
        """
        self._roi_manager.select_roi(region)

    def toggle_roi(self, enabled: bool):
        """
        Toggle the ROI on or off.

        Args:
            enabled(bool): Whether to enable or disable the ROI.
        """
        self._roi_manager.toggle_roi(enabled)

    def _on_roi_changed_for_dap(self):
        """
        Whenever the ROI changes, you might want to re-request DAP with the new x_min, x_max.
        """
        self.request_dap_update.emit()

    def _enable_roi_toolbar_action(self, enable: bool):
        """
        Enable or disable the ROI toolbar action.

        Args:
            enable(bool): Enable or disable the ROI toolbar action.
        """
        self.toolbar.components.get_action("roi_linear").action.setEnabled(enable)
        if enable is False:
            self.toolbar.components.get_action("roi_linear").action.setChecked(False)
            self._roi_manager.toggle_roi(False)

    ################################################################################
    # Scan History browser popup
    # TODO this is so far quick implementation just as popup, we should make scan history also standalone widget later
    def show_scan_history_popup(self):
        """
        Show the scan history popup.
        """
        scan_history_action = self.toolbar.components.get_action("scan_history").action
        if self.scan_history_dialog is None or not self.scan_history_dialog.isVisible():
            self.scan_history_widget = ScanHistoryBrowser(parent=self)
            self.scan_history_dialog = QDialog(modal=False)
            self.scan_history_dialog.setWindowTitle(f"{self.object_name} - Scan History Browser")
            self.scan_history_dialog.layout = QVBoxLayout(self.scan_history_dialog)
            self.scan_history_dialog.layout.addWidget(self.scan_history_widget)
            self.scan_history_widget.scan_history_device_viewer.request_history_plot.connect(
                lambda scan_id, device_name, signal_name: self.plot(
                    device_y=device_name, signal_y=signal_name, scan_id=scan_id
                )
            )
            self.scan_history_dialog.finished.connect(self._scan_history_closed)
            self.scan_history_dialog.show()
            self.scan_history_dialog.resize(780, 320)
            scan_history_action.setChecked(True)
        else:
            # If already open, bring it to the front
            self.scan_history_dialog.raise_()
            self.scan_history_dialog.activateWindow()
            scan_history_action.setChecked(True)  # keep it toggle

    def _scan_history_closed(self):
        """
        Slot for when the scan history dialog is closed.
        """
        if self.scan_history_dialog is None:
            return
        self.scan_history_widget.close()
        self.scan_history_widget.deleteLater()
        self.scan_history_dialog.deleteLater()
        self.scan_history_dialog = None
        self.toolbar.components.get_action("scan_history").action.setChecked(False)

    ################################################################################
    # Dap Summary

    def _add_dap_summary_side_menu(self):
        """
        Add the DAP summary to the side panel.
        """
        self.dap_summary = LMFitDialog(parent=self)
        self.side_panel.add_menu(
            action_id="fit_params",
            icon_name="monitoring",
            tooltip="Open Fit Parameters",
            widget=self.dap_summary,
            title="Fit Parameters",
        )
        self.dap_summary_update.connect(self.dap_summary.update_summary_tree)

    def show_dap_summary_popup(self):
        """
        Show the DAP summary popup.
        """
        fit_action = self.toolbar.components.get_action("fit_params").action
        if self.dap_summary_dialog is None or not self.dap_summary_dialog.isVisible():
            self.dap_summary = LMFitDialog(parent=self)
            self.dap_summary_dialog = QDialog(modal=False)
            self.dap_summary_dialog.layout = QVBoxLayout(self.dap_summary_dialog)
            self.dap_summary_dialog.layout.addWidget(self.dap_summary)
            self.dap_summary_update.connect(self.dap_summary.update_summary_tree)
            self.dap_summary_dialog.finished.connect(self._dap_summary_closed)
            self.dap_summary_dialog.show()
            self._refresh_dap_signals()  # Get current dap data
            self.dap_summary_dialog.resize(300, 300)
            fit_action.setChecked(True)
        else:
            # If already open, bring it to the front
            self.dap_summary_dialog.raise_()
            self.dap_summary_dialog.activateWindow()
            fit_action.setChecked(True)  # keep it toggle

    def _dap_summary_closed(self):
        """
        Slot for when the axis settings dialog is closed.
        """
        self.dap_summary.close()
        self.dap_summary.deleteLater()
        self.dap_summary_dialog.deleteLater()
        self.dap_summary_dialog = None
        self.toolbar.components.get_action("fit_params").action.setChecked(False)

    def _get_dap_from_target_widget(self) -> None:
        """Get the DAP data from the target widget and update the DAP dialog manually on creation."""
        dap_summary = self.get_dap_summary()
        for curve_id, data in dap_summary.items():
            md = {"curve_id": curve_id}
            self.dap_summary.update_summary_tree(data=data, metadata=md)

    @SafeSlot()
    def get_dap_params(self) -> dict[str, dict]:
        """
        Get the DAP parameters of all DAP curves.

        Returns:
            dict[str, dict]: DAP parameters of all DAP curves.
        """
        return {curve.name(): curve.dap_params for curve in self._dap_curves}

    @SafeSlot()
    def get_dap_summary(self) -> dict[str, dict]:
        """
        Get the DAP summary of all DAP curves.

        Returns:
            dict[str, dict]: DAP summary of all DAP curves.
        """
        return {curve.name(): curve.dap_summary for curve in self._dap_curves}

    ################################################################################
    # Widget Specific Properties
    ################################################################################

    @SafeProperty(str)
    def x_mode(self) -> str:
        return self.x_axis_mode["name"]

    @x_mode.setter
    def x_mode(self, value: str):
        self.x_axis_mode["name"] = value
        if value not in ["timestamp", "index", "auto"]:
            self.x_axis_mode["entry"] = self.entry_validator.validate_signal(value, None)
            self._current_x_device = (value, self.x_axis_mode["entry"])
        self._switch_x_axis_item(mode=value)
        self._current_x_device = None
        self._refresh_history_curves()
        self._update_curve_visibility()
        # Rebuild the DataAPI subscription so the x source follows the new mode.
        self._setup_data_api_subscription(scan=self._data_api_scan)
        self.plot_item.enableAutoRange(x=True)
        self.round_plot_widget.apply_plot_widget_style()  # To keep the correct theme
        self._refresh_alignment_state(force_readback=True)

    @SafeProperty(str)
    def signal_x(self) -> str | None:
        """
        The x signal name.
        """
        return self.x_axis_mode["entry"]

    @signal_x.setter
    def signal_x(self, value: str | None):
        """
        Set the x signal name.

        Args:
            value(str|None): The x signal name to set.
        """
        if value is None:
            return
        if self.x_axis_mode["name"] in ["auto", "index", "timestamp"]:
            logger.warning("Cannot set signal_x when x_mode is not 'device'.")
            return
        self.x_axis_mode["entry"] = self.entry_validator.validate_signal(self.x_mode, value)
        self._switch_x_axis_item(mode="device")
        self._refresh_history_curves()
        self._update_curve_visibility()
        # Rebuild the DataAPI subscription so the x source follows the new signal.
        self._setup_data_api_subscription(scan=self._data_api_scan)
        self.plot_item.enableAutoRange(x=True)
        self.round_plot_widget.apply_plot_widget_style()
        self._refresh_alignment_state(force_readback=True)

    @SafeProperty(str)
    def color_palette(self) -> str:
        """
        The color palette of the figure widget.
        """
        return self.config.color_palette

    @color_palette.setter
    def color_palette(self, value: str):
        """
        Set the color palette of the figure widget.

        Args:
            value(str): The color palette to set.
        """
        try:
            self.config.color_palette = value
        except ValidationError:
            return

        colors = Colors.golden_angle_color(
            colormap=self.config.color_palette, num=max(10, len(self.curves) + 1), format="HEX"
        )
        for i, curve in enumerate(self.curves):
            curve.set_color(colors[i])

    @SafeProperty(str, designable=False, popup_error=True)
    def curve_json(self) -> str:
        """
        A JSON string property that serializes all curves' pydantic configs.
        """
        raw_list = []
        for c in self.curves:
            if c.config.source == "custom":  # Do not serialize custom curves
                continue
            cfg_dict = c.config.model_dump()
            raw_list.append(cfg_dict)
        return json.dumps(raw_list, indent=2)

    @curve_json.setter
    def curve_json(self, json_data: str):
        """
        Load curves from a JSON string and add them to the plot, omitting custom source curves.
        """
        try:
            curve_configs = json.loads(json_data)
            self.clear_all()
            for cfg_dict in curve_configs:
                if cfg_dict.get("source") == "custom":
                    logger.warning(f"Custom source curve '{cfg_dict['label']}' not loaded.")
                    continue
                config = CurveConfig(**cfg_dict)
                self._add_curve(config=config)
            self._refresh_alignment_state(force_readback=self._alignment_panel_visible)
            self._refresh_dap_signals()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")

    @property
    def curves(self) -> list[Curve]:
        """
        Get the curves of the plot widget as a list.

        Returns:
            list: List of curves.
        """
        return [item for item in self.plot_item.curves if isinstance(item, Curve)]

    @SafeProperty(bool)
    def skip_large_dataset_check(self) -> bool:
        """
        Whether to skip the large dataset warning when fetching async data.
        """
        return self._skip_large_dataset_check

    @skip_large_dataset_check.setter
    def skip_large_dataset_check(self, value: bool):
        """
        Set whether to skip the large dataset warning when fetching async data.

        Args:
            value(bool): Whether to skip the large dataset warning.
        """
        self._skip_large_dataset_check = value

    @SafeProperty(bool)
    def skip_large_dataset_warning(self) -> bool:
        """
        Whether to skip the large dataset warning when fetching async data.
        """
        return self._skip_large_dataset_warning

    @skip_large_dataset_warning.setter
    def skip_large_dataset_warning(self, value: bool):
        """
        Set whether to skip the large dataset warning when fetching async data.

        Args:
            value(bool): Whether to skip the large dataset warning.
        """
        self._skip_large_dataset_warning = value

    @SafeProperty(float)
    def max_dataset_size_mb(self) -> float:
        """
        The maximum dataset size (in MB) permitted when fetching async data from history before prompting the user.
        """
        return self.config.max_dataset_size_mb

    @max_dataset_size_mb.setter
    def max_dataset_size_mb(self, value: float):
        """
        Set the maximum dataset size (in MB) permitted when fetching async data from history before prompting the user.

        Args:
            value(float): The maximum dataset size in MB.
        """
        if value <= 0:
            raise ValueError("Maximum dataset size must be greater than 0.")
        self.config.max_dataset_size_mb = value

    ################################################################################
    # High Level methods for API
    ################################################################################
    @SafeSlot(popup_error=True)
    def plot(
        self,
        arg1: list | np.ndarray | str | None = None,
        y: list | np.ndarray | None = None,
        x: list | np.ndarray | None = None,
        device_x: str | None = None,
        device_y: str | None = None,
        signal_x: str | None = None,
        signal_y: str | None = None,
        color: str | None = None,
        label: str | None = None,
        dap: str | list[str] | None = None,
        dap_parameters: dict | list | lmfit.Parameters | None | object = None,
        scan_id: str | None = None,
        scan_number: int | None = None,
        **kwargs,
    ) -> Curve:
        """
        Plot a curve to the plot widget.

        Args:
            arg1(list | np.ndarray | str | None): First argument, which can be x data, y data, or device_y.
            y(list | np.ndarray): Custom y data to plot.
            x(list | np.ndarray): Custom y data to plot.
            device_x(str): Name of the x signal.
                - "auto": Use the best effort signal.
                - "timestamp": Use the timestamp signal.
                - "index": Use the index signal.
                - Custom signal name of a device from BEC.
            device_y(str): The name of the device for the y-axis.
            signal_x(str): The name of the entry for the x-axis.
            signal_y(str): The name of the entry for the y-axis.
            color(str): The color of the curve.
            label(str): The label of the curve.
            dap(str | list[str]): The dap model to use for the curve. When provided, a DAP curve is
                attached automatically for device, history, or custom data sources. Use
                the same string as the LMFit model name, or a list of model names to build a composite.
            dap_parameters(dict | list | lmfit.Parameters | None): Optional lmfit parameter overrides sent to
                the DAP server. For a single model: values can be numeric (interpreted as fixed parameters)
                or dicts like `{"value": 1.0, "vary": False}`. For composite models (dap is list), use either
                a list aligned to the model list (each item is a param dict), or a dict of
                `{ "ModelName": { "param": {...} } }` when model names are unique.
            scan_id(str):  Optional scan ID. When provided, the curve is treated as a **history** curve and
                the y‑data (and optional x‑data) are fetched from that historical scan. Such curves are
                never cleared by live‑scan resets.
            scan_number(int): Optional scan index. When provided, the curve is treated as a **history** curve and

        Returns:
            Curve: The curve object.
        """
        # 0) preallocate
        source = "custom"
        x_data = None
        y_data = None
        if dap_parameters is _DAP_PARAM:
            dap_parameters = kwargs.pop("dap_parameters", None) or kwargs.pop("parameters", None)

        # 1. Custom curve logic
        if x is not None and y is not None:
            source = "custom"
            x_data = np.asarray(x)
            y_data = np.asarray(y)

        if isinstance(arg1, str):
            device_y = arg1
        elif isinstance(arg1, list):
            if isinstance(y, list):
                source = "custom"
                x_data = np.asarray(arg1)
                y_data = np.asarray(y)
            if y is None:
                source = "custom"
                arr = np.asarray(arg1)
                x_data = np.arange(len(arr))
                y_data = arr
        elif isinstance(arg1, np.ndarray) and y is None:
            if arg1.ndim == 1:
                source = "custom"
                x_data = np.arange(len(arg1))
                y_data = arg1
            if arg1.ndim == 2 and arg1.shape[1] == 2:
                source = "custom"
                x_data = arg1[:, 0]
                y_data = arg1[:, 1]

        # If device_y is set => device data
        if device_y is not None and x_data is None and y_data is None:
            source = "device"
            # Validate or obtain entry
            signal_y = self.entry_validator.validate_signal(device_y, signal_y)

        # If user gave device_x => store in x_axis_mode, but do not set data here
        if device_x is not None:
            self.x_mode = device_x
            if device_x not in ["timestamp", "index", "auto"]:
                self.x_axis_mode["entry"] = self.entry_validator.validate_signal(device_x, signal_x)

        # Decide label if not provided
        if label is None:
            if source == "custom":
                label = WidgetContainerUtils.generate_unique_name(
                    "Curve", [c.object_name for c in self.curves]
                )
            else:
                label = f"{device_y}-{signal_y}"

        # If color not provided, generate from palette
        if color is None:
            color = self._generate_color_from_palette()

        # Build the config
        config = CurveConfig(
            widget_class="Curve",
            parent_id=self.gui_id,
            label=label,
            color=color,
            source=source,
            scan_id=scan_id,
            scan_number=scan_number,
            **kwargs,
        )

        # If it's device-based, attach DeviceSignal
        if source == "device":
            config.signal = DeviceSignal(device=device_y, signal=signal_y)

        if scan_id is not None or scan_number is not None:
            config.source = "history"

        # CREATE THE CURVE
        curve = self._add_curve(config=config, x_data=x_data, y_data=y_data)

        if dap is not None and curve.config.source in ("device", "history", "custom"):
            self.add_dap_curve(
                device_label=curve.name(), dap_name=dap, dap_parameters=dap_parameters, **kwargs
            )

        return curve

    ################################################################################
    # Curve Management Methods
    @SafeSlot()
    def add_dap_curve(
        self,
        device_label: str,
        dap_name: str | list[str],
        color: str | None = None,
        dap_oversample: int = 1,
        dap_parameters: dict | list | lmfit.Parameters | None = None,
        **kwargs,
    ) -> Curve:
        """
        Create a new DAP curve referencing the existing curve `device_label`, with the
        data processing model `dap_name`. DAP curves can be attached to curves that
        originate from live devices, history, or fully custom data sources.

        Args:
            device_label(str): The label of the source curve to add DAP to.
            dap_name(str | list[str]): The name of the DAP model to use, or a list of model
                names to build a composite model.
            color(str): The color of the curve.
            dap_oversample(int): The oversampling factor for the DAP curve.
            dap_parameters(dict | list | lmfit.Parameters | None): Optional lmfit parameter overrides sent to the DAP server.
            **kwargs

        Returns:
            Curve: The new DAP curve.
        """

        # 1) Find the existing curve by label
        device_curve = self._find_curve_by_label(device_label)
        if not device_curve:
            raise ValueError(f"No existing curve found with label '{device_label}'.")
        if device_curve.config.source not in ("device", "history", "custom"):
            raise ValueError(
                f"Curve '{device_label}' is not compatible with DAP. "
                f"Only device, history, or custom curves support fitting."
            )

        dev_name = getattr(getattr(device_curve.config, "signal", None), "device", None)
        dev_entry = getattr(getattr(device_curve.config, "signal", None), "signal", None)
        if dev_name is None:
            dev_name = device_label
        if dev_entry is None:
            dev_entry = "custom"

        # 2) Build a label for the new DAP curve
        dap_label = f"{device_label}-{self._format_dap_label(dap_name)}"

        # 3) Possibly raise if the DAP curve already exists
        if self._check_curve_id(dap_label):
            raise ValueError(f"DAP curve '{dap_label}' already exists.")

        if color is None:
            color = self._generate_color_from_palette()

        # Build config for DAP
        config = CurveConfig(
            widget_class="Curve",
            parent_id=self.gui_id,
            label=dap_label,
            color=color,
            source="dap",
            parent_label=device_label,
            symbol="star",
            **kwargs,
        )

        # Attach device signal with DAP
        config.signal = DeviceSignal(
            device=dev_name,
            signal=dev_entry,
            dap=dap_name,
            dap_oversample=dap_oversample,
            dap_parameters=self._normalize_dap_parameters(dap_parameters, dap_name=dap_name),
        )

        # 4) Create the DAP curve config using `_add_curve(...)`
        dap_curve = self._add_curve(config=config)

        return dap_curve

    def _add_curve(
        self,
        config: CurveConfig,
        x_data: np.ndarray | None = None,
        y_data: np.ndarray | None = None,
    ) -> Curve:
        """
        Private method to finalize the creation of a new Curve in this Waveform widget
        based on an already-built `CurveConfig`.

        Args:
            config (CurveConfig): A fully populated pydantic model describing how to create and style the curve.
            x_data (np.ndarray | None): If this is a custom curve (config.source == "custom"), optional x data array.
            y_data (np.ndarray | None): If this is a custom curve (config.source == "custom"), optional y data array.

        Returns:
            Curve: The newly created curve object.

        Raises:
            ValueError: If a duplicate curve label/config is found, or if
                        custom data is missing for `source='custom'`.
        """
        scan_item: ScanDataContainer | None = None
        if config.source == "history":
            scan_item = self.get_history_scan_item(
                scan_id=config.scan_id, scan_index=config.scan_number
            )
            if scan_item is None:
                raise ValueError(
                    f"Could not find scan item for history curve '{config.label}' with scan_id='{config.scan_id}' and scan_number='{config.scan_number}'."
                )

            config.scan_id = scan_item.metadata["bec"]["scan_id"]
            config.scan_number = scan_item.metadata["bec"]["scan_number"]

        label = config.label
        if config.source == "history":
            label = f"{config.signal.device}-{config.signal.signal}-scan-{config.scan_number}"
            config.label = label
        if not label:
            # Fallback label
            label = WidgetContainerUtils.generate_unique_name(
                "Curve", [c.object_name for c in self.curves]
            )
            config.label = label

        # Check for duplicates
        if self._check_curve_id(label):
            raise ValueError(f"Curve with ID '{label}' already exists in widget '{self.gui_id}'.")

        # If a user did not provide color in config, pick from palette
        if not config.color:
            config.color = self._generate_color_from_palette()

        # For custom data, ensure x_data, y_data
        if config.source == "custom":
            if x_data is None or y_data is None:
                raise ValueError("For 'custom' curves, x_data and y_data must be provided.")

        # Actually create the Curve item
        curve = self._add_curve_object(name=label, config=config)

        # If custom => set initial data
        if config.source == "custom" and x_data is not None and y_data is not None:
            curve.setData(x_data, y_data)

        # If device => let the DataAPI subscription deliver the data
        if config.source == "device":
            if self.scan_item is None:
                self.update_with_scan_history(-1)
            self._setup_data_api_subscription(scan=self._data_api_scan)
        if config.source == "dap":
            self._dap_curves.append(curve)
            self.setup_dap_for_scan()
            self.roi_enable.emit(True)  # Enable the ROI toolbar action
            self.request_dap()  # Request DAP update directly without blocking proxy
        if config.source == "history":
            self._validate_history_curve(curve, scan_item)
            self._history_curves.append(curve)
            self._sync_history_curve_state(curve)
            self._setup_history_curve_subscriptions()

        QTimer.singleShot(
            150, self.auto_range
        )  # autorange with a delay to ensure the plot is updated
        self._refresh_alignment_state()

        return curve

    def _add_curve_object(self, name: str, config: CurveConfig) -> Curve:
        """
        Low-level creation of the PlotDataItem (Curve) from a `CurveConfig`.

        Args:
            name (str): The name/label of the curve.
            config (CurveConfig): Configuration model describing the curve.

        Returns:
            Curve: The newly created curve object, added to the plot.
        """
        curve = Curve(config=config, name=name, parent_item=self)
        self.plot_item.addItem(curve)
        self._categorise_device_curves()
        curve.visibleChanged.connect(self._refresh_crosshair_markers)
        curve.visibleChanged.connect(self.auto_range)
        return curve

    def _validate_history_curve(self, curve: Curve, scan_item: ScanDataContainer) -> None:
        """
        Metadata-level validation of a new history curve (no file I/O).

        Args:
            curve(Curve): The freshly created history curve.
            scan_item(ScanDataContainer): The resolved scan item.

        Raises:
            ValueError: If the scan item carries no stored-data info or the
                requested device/entry is not part of the scan. The curve is
                removed from the plot before raising.
        """
        stored_data_info = getattr(
            getattr(scan_item, "_msg", None), "stored_data_info", None
        ) or getattr(scan_item, "stored_data_info", None)
        device = curve.config.signal.device
        entry = curve.config.signal.signal
        if stored_data_info is None:
            curve.remove()
            raise ValueError(
                f"No stored data info found in scan item ID:{curve.config.scan_id} for curve '{curve.name()}'. "
                f"Upgrade BEC to the latest version."
            )
        if device not in stored_data_info:
            curve.remove()
            raise ValueError(f"Device '{device}' not found in scan item ID:{curve.config.scan_id}.")
        if entry not in stored_data_info[device]:
            curve.remove()
            raise ValueError(
                f"Entry '{entry}' not found in device '{device}' in scan item ID:{curve.config.scan_id}."
            )

    @staticmethod
    def _history_num_points(scan_item) -> int | None:
        """Number of monitored readouts of a history scan, if known."""
        msg = getattr(scan_item, "_msg", None)
        return getattr(msg, "num_monitored_readouts", None) or getattr(msg, "num_points", None)

    def _is_monitored_shaped(self, scan_item, info) -> bool:
        """
        Whether a stored dataset holds exactly one value per scan point.

        Only such datasets can be plotted against a monitored x device; every
        other shape is detector data plotted against its sample index.
        """
        shape = tuple(getattr(info, "shape", None) or ())
        num_points = self._history_num_points(scan_item)
        return len(shape) == 1 and num_points is not None and shape[0] == num_points

    def _history_curve_compatible(self, curve: Curve) -> bool:
        """
        Whether a history curve can be shown with the current x-axis mode.

        Answered from the scan's stored-data info (no file data reads): the
        x device/entry must exist in the scan and match the y shape. Index and
        timestamp modes are always compatible; auto falls back to index when
        no x device can be resolved.

        Args:
            curve(Curve): The history curve to check.

        Returns:
            bool: True if the curve is compatible with the current x mode.
        """
        mode = self.x_axis_mode.get("name") or "auto"
        if mode in ("index", "timestamp"):
            return True
        scan_item = self.get_history_scan_item(
            scan_id=curve.config.scan_id, scan_index=curve.config.scan_number
        )
        if scan_item is None:
            logger.warning(f"Scan item for curve {curve.name()} not found.")
            return False
        stored_data_info = getattr(
            getattr(scan_item, "_msg", None), "stored_data_info", None
        ) or getattr(scan_item, "stored_data_info", None)
        if not stored_data_info:
            return True  # cannot verify; let the delivered data decide
        signal = curve.config.signal
        y_info = stored_data_info.get(signal.device, {}).get(signal.signal) if signal else None
        if y_info is None:
            return False
        if not self._is_monitored_shaped(scan_item, y_info):
            # Detector/async data: one row per acquisition, not per scan point.
            # It is rendered against the sample index (with an index fallback
            # when an x device has a different length), so an x/y row-count
            # difference is expected and must not hide the curve.
            return True
        x_key = self._history_x_source_key(scan_item)
        if x_key is None:
            # Auto mode falls back to index plotting; an unresolvable custom
            # device hides the curve (mirrors the legacy behaviour).
            return mode == "auto"
        x_info = stored_data_info.get(x_key[0], {}).get(x_key[1])
        if x_info is None:
            logger.warning(
                f"X device '{x_key[0]}-{x_key[1]}' not found in scan item of history curve "
                f"'{curve.name()}'; scan ID: {curve.config.scan_id}."
            )
            return False
        try:
            if tuple(x_info.shape)[0] != tuple(y_info.shape)[0]:
                logger.warning(
                    f"Shape mismatch for x data '{x_info.shape[0]}' and y data '{y_info.shape[0]}' "
                    f"in history curve '{curve.name()}'; scan ID: {curve.config.scan_id}."
                )
                return False
        except (TypeError, IndexError):
            return True
        return True

    def _sync_history_curve_state(self, curve: Curve) -> None:
        """
        Sync visibility and the recorded x mode of one history curve with the
        current x-axis mode.

        Args:
            curve(Curve): The history curve to sync.
        """
        compatible = self._history_curve_compatible(curve)
        curve.setVisible(compatible)
        if compatible:
            curve.config.current_x_mode = self.x_axis_mode["name"]

    def _refresh_history_curves(self):
        """
        Re-sync history curves after an x-mode change: visibility comes from
        the stored-data metadata, the data itself is re-delivered through
        fresh scan-bound DataAPI subscriptions.
        """
        for curve in self._history_curves:
            self._sync_history_curve_state(curve)
        self._setup_history_curve_subscriptions()

    def _refresh_crosshair_markers(self):
        """
        Refresh the crosshair markers when a curve visibility changes.
        """
        if self.crosshair is not None:
            self.crosshair.clear_markers()

    def _generate_color_from_palette(self) -> str:
        """
        Generate a color for the next new curve, based on the current number of curves.
        """
        current_count = len(self.curves)
        color_list = Colors.golden_angle_color(
            colormap=self.config.color_palette, num=max(10, current_count + 1), format="HEX"
        )
        return color_list[current_count]

    def _refresh_colors(self):
        """
        Re-assign colors to all existing curves so they match the new count-based distribution.
        """
        all_curves = self.curves
        # Generate enough colors for the new total
        color_list = Colors.golden_angle_color(
            colormap=self.config.color_palette, num=max(10, len(all_curves)), format="HEX"
        )
        for i, curve in enumerate(all_curves):
            curve.set_color(color_list[i])

    def clear_data(self):
        """
        Clear all data from the plot widget, but keep the curve references.
        """
        for c in self.curves:
            if c.config.source != "history":
                c.clear_data()

    # X-axis compatibility helpers
    def _is_curve_compatible(self, curve: Curve) -> bool:
        """
        Return True when *curve* can be shown with the current x-axis mode.

        - ‘index’, ‘timestamp’ are always compatible.
        - History curves are checked against their scan's stored-data info.
        - DAP is done by checking if the parent curve is visible.
        - Device curves are rendered from the DataAPI updates, which resolve
          the compatibility (index fallback) there.
        """
        mode = self.x_axis_mode.get("name", "index")
        if mode in ("index", "timestamp"):  # always compatible - wild west mode
            return True
        if curve.config.source == "history":
            return self._history_curve_compatible(curve)
        if curve.config.source == "dap":
            parent_curve = self._find_curve_by_label(curve.config.parent_label)
            return bool(parent_curve is not None and parent_curve.isVisible())
        return True

    def _update_curve_visibility(self) -> None:
        """Show or hide curves according to `_is_curve_compatible`."""
        for c in self.curves:
            c.setVisible(self._is_curve_compatible(c))

    def clear_all(self):
        """
        Clear all curves from the plot widget.
        """
        curve_list = self.curves
        self._dap_curves = []
        self._sync_curves = []
        self._async_curves = []
        self._history_curves = []
        for curve in curve_list:
            self.remove_curve(curve.name())
        if self.crosshair is not None:
            self.crosshair.clear_markers()
        self._refresh_alignment_state()

    def get_curve(self, curve: int | str) -> Curve | None:
        """
        Get a curve from the plot widget.

        Args:
            curve(int|str): The curve to get. It Can be the order of the curve or the name of the curve.

        Return(Curve|None): The curve object if found, None otherwise.
        """
        if isinstance(curve, int):
            if curve < len(self.curves):
                return self.curves[curve]
        elif isinstance(curve, str):
            for c in self.curves:
                if c.name() == curve:
                    return c
        return None

    @SafeSlot(int, popup_error=True)
    @SafeSlot(str, popup_error=True)
    def remove_curve(self, curve: int | str):
        """
        Remove a curve from the plot widget.

        Args:
            curve(int|str): The curve to remove. It Can be the order of the curve or the name of the curve.
        """
        if isinstance(curve, int):
            self._remove_curve_by_order(curve)
        elif isinstance(curve, str):
            self._remove_curve_by_name(curve)

        self._refresh_colors()
        self._categorise_device_curves()
        self._refresh_data_subscriptions()
        self._refresh_alignment_state()

    def _remove_curve_by_name(self, name: str):
        """
        Remove a curve by its name from the plot widget.

        Args:
            name(str): Name of the curve to be removed.
        """
        for curve in self.curves:
            if curve.name() == name:
                self.plot_item.removeItem(curve)
                self._curve_clean_up(curve)
                return

    def _remove_curve_by_order(self, N: int):
        """
        Remove a curve by its order from the plot widget.

        Args:
            N(int): Order of the curve to be removed.
        """
        if N < len(self.curves):
            curve = self.curves[N]
            self.plot_item.removeItem(curve)
            self._curve_clean_up(curve)

        else:
            logger.error(f"Curve order {N} out of range.")
            raise IndexError(f"Curve order {N} out of range.")

    def _curve_clean_up(self, curve: Curve):
        """
        Clean up the curve bookkeeping and RPC registration.

        Args:
            curve(Curve): The curve to clean up.
        """
        if curve in self._history_curves:
            self._history_curves.remove(curve)
        curve.rpc_register.remove_rpc(curve)

        # Remove itself from the DAP summary only for side panels
        if (
            curve.config.source == "dap"
            and self.dap_summary is not None
            and self.enable_side_panel is True
        ):
            self.dap_summary.remove_dap_data(curve.name())
        if curve.config.source == "dap" and self._alignment_controller is not None:
            self._alignment_controller.remove_dap_curve(curve.name())

        # find a corresponding dap curve and remove it
        for c in self.curves:
            if c.config.parent_label == curve.name():
                self.plot_item.removeItem(c)
                self._curve_clean_up(c)

    def _check_curve_id(self, curve_id: str) -> bool:
        """
        Check if a curve ID exists in the plot widget.

        Args:
            curve_id(str): The ID of the curve to check.

        Returns:
            bool: True if the curve ID exists, False otherwise.
        """
        curve_ids = [curve.name() for curve in self.curves]
        if curve_id in curve_ids:
            return True
        return False

    def _find_curve_by_label(self, label: str) -> Curve | None:
        """
        Find a curve by its label.

        Args:
            label(str): The label of the curve to find.

        Returns:
            Curve|None: The curve object if found, None otherwise.
        """
        for c in self.curves:
            if c.name() == label:
                return c
        return None

    ################################################################################
    # BEC Update Methods
    ################################################################################
    @SafeSlot(dict, dict)
    def on_scan_status(self, msg: dict, meta: dict):
        """
        Initial scan status message handler, which is triggered at the begging and end of scan.
        Used only for per-scan bookkeeping (reset, scan id tracking, curve
        categorisation, DAP triggering); the data flows through the DataAPI.

        Args:
            msg(dict): The message content.
            meta(dict): The message metadata.
        """
        current_scan_id = msg.get("scan_id", None)
        if current_scan_id is None:
            return

        if self.curves and not any(curve.config.source == "device" for curve in self.curves):
            return

        if current_scan_id != self.scan_id:
            self.reset()
            self.new_scan.emit()
            self.new_scan_id.emit(current_scan_id)
            self.auto_range_x = True
            self.auto_range_y = True
            self.old_scan_id = self.scan_id
            self.scan_id = current_scan_id
            self.scan_item = self.queue.scan_storage.find_scan_by_ID(self.scan_id)  # live scan
            self._update_curve_visibility()
            self._mode = self._categorise_device_curves()
            # Rebuild the subscription so the per-scan source resolution
            # (e.g. the auto x device) follows the new scan.
            self._setup_data_api_subscription(scan="live")
        self.setup_dap_for_scan()

    ################################################################################
    # DataAPI subscription handling
    ################################################################################

    def _config_sources(self) -> list[tuple[str, str]] | None:
        """
        Return the deduplicated (device, entry) sources of all device curves,
        including the device supplying the x axis (custom device mode, or the
        device the auto mode resolves to).

        Returns:
            list[tuple[str, str]] | None: The source list, or None if no
                device curve is configured.
        """
        sources: list[tuple[str, str]] = []
        for curve in self.curves:
            if curve.config.source != "device" or curve.config.signal is None:
                continue
            sources.append((curve.config.signal.device, curve.config.signal.signal))
        if not sources:
            return None
        x_key = self._x_source_key()
        if x_key is not None:
            sources.append(x_key)
        return list(dict.fromkeys(sources))

    def _report_devices_no_file_io(self, scan_item) -> list[str]:
        """
        Resolve the scan report devices without touching the data file.

        ``ScanDataContainer.metadata`` is lazy: reading it opens the HDF5 file
        synchronously, which must not happen on the GUI thread (and would even
        precede the large-dataset gate). Live scans carry the report devices on
        their status message, finished scans carry the scan request in the
        (Redis-backed) scan history message.

        Args:
            scan_item: Live scan item or history data container.

        Returns:
            list[str]: Report device names, empty when only the file knows.
        """
        status_message = getattr(scan_item, "status_message", None)
        if status_message is not None:
            raw = getattr(status_message, "scan_report_devices", None)
            devices = (
                self._ensure_str_list(raw) if isinstance(raw, (list, tuple, np.ndarray)) else []
            )
            if devices:
                return devices
            info = getattr(status_message, "info", None)
            raw = info.get("scan_report_devices") if isinstance(info, dict) else None
            devices = (
                self._ensure_str_list(raw) if isinstance(raw, (list, tuple, np.ndarray)) else []
            )
            if devices:
                return devices

        # History: the scan request of the scan history message names the
        # scanned devices; its first entry is the first report device.
        history_msg = getattr(scan_item, "_msg", None)
        request_inputs = getattr(history_msg, "request_inputs", None)
        arg_bundle = request_inputs.get("arg_bundle") if isinstance(request_inputs, dict) else None
        if isinstance(arg_bundle, (list, tuple)):
            devices = [item for item in arg_bundle if isinstance(item, str)]
            if devices:
                return devices[:1]
        return []

    def _x_source_key(self) -> tuple[str, str] | None:
        """
        Resolve the (device, entry) supplying the x axis for the current
        x-axis mode; None for index/timestamp or when auto resolves to index.

        Returns:
            tuple[str, str] | None: The x source key, or None.
        """
        mode = self.x_axis_mode["name"] or "auto"
        if mode in ("timestamp", "index"):
            return None
        if mode != "auto":  # custom device mode
            entry = self.x_axis_mode.get("entry")
            if entry is None:
                try:
                    entry = self.entry_validator.validate_signal(mode, None)
                except Exception:
                    return None
            return (mode, entry)
        # Auto mode: index when async curves are present, otherwise the first
        # device from the scan report.
        if self._async_curves:
            return None
        if self.scan_item is None:
            return None
        report_devices = self._report_devices_no_file_io(self.scan_item)
        if not report_devices:
            # Last resort only: this opens the data file synchronously.
            try:
                report_devices = self._ensure_str_list(
                    self.scan_item.metadata["bec"]["scan_report_devices"]
                )
            except Exception:
                return None
        if not report_devices:
            return None
        device_x = report_devices[0]
        try:
            signal_x = self.entry_validator.validate_signal(device_x, None)
        except Exception:
            return None
        return (device_x, signal_x)

    def _history_x_source_key(self, scan_item) -> tuple[str, str] | None:
        """
        Resolve the x source key for a pinned history scan.

        Auto mode prefers the widget's current x device (set by live scans)
        and falls back to the scan's first report device.

        Args:
            scan_item: The scan item of the pinned history scan.

        Returns:
            tuple[str, str] | None: The x source key, or None for index-like
                modes.
        """
        mode = self.x_axis_mode["name"] or "auto"
        if mode in ("timestamp", "index"):
            return None
        if mode != "auto":  # custom device mode
            entry = self.x_axis_mode.get("entry")
            if entry is None:
                try:
                    entry = self.entry_validator.validate_signal(mode, None)
                except Exception:
                    return None
            return (mode, entry)
        if self._current_x_device is not None:
            return self._current_x_device
        report_devices = self._report_devices_no_file_io(scan_item)
        if not report_devices:
            # Last resort only: this opens the data file synchronously.
            try:
                report_devices = self._ensure_str_list(
                    scan_item.metadata.get("bec", {}).get("scan_report_devices") or []
                )
            except Exception:
                return None
        if not report_devices:
            return None
        device_x = report_devices[0]
        try:
            signal_x = self.entry_validator.validate_signal(device_x, None)
        except Exception:
            return None
        return (device_x, signal_x)

    def _setup_data_api_subscription(self, scan: str = "live"):
        """
        (Re)create the DataAPI subscription for the configured device curves.

        Args:
            scan(str): "live" to follow the active scan, or a terminal scan id.
        """
        self._cleanup_data_api_subscription()
        self._data_api_scan = scan
        if self._shutting_down:
            return
        sources = self._config_sources()
        if sources is None:
            return
        sources = self._filter_oversized_sources(sources, scan)
        if not sources:
            return
        try:
            self._data_bridge = QtDataSubscription(
                self.client,
                sources=sources,
                scan=scan,
                parent=self,
                min_emit_interval=self.update_interval_s,
            )
            self._data_bridge.updated.connect(self._on_data_update)
        except Exception as exc:
            logger.warning(f"Failed to configure waveform data subscription: {exc}")
            self._cleanup_data_api_subscription()

    def _cleanup_data_api_subscription(self):
        if self._data_bridge is None:
            return
        try:
            self._data_bridge.close()
        finally:
            self._data_bridge = None

    def _setup_history_curve_subscriptions(self):
        """
        (Re)create one DataAPI subscription per scan pinned by history curves.
        """
        self._cleanup_history_subscriptions()
        if self._shutting_down:
            return
        sources_by_scan: dict[str, list[tuple[str, str]]] = {}
        for curve in self._history_curves:
            scan_id = curve.config.scan_id
            signal = curve.config.signal
            if not scan_id or signal is None:
                continue
            sources_by_scan.setdefault(scan_id, []).append((signal.device, signal.signal))
        for scan_id, sources in sources_by_scan.items():
            sources = self._filter_oversized_sources(sources, scan_id)
            if not sources:
                continue
            scan_item = self.get_history_scan_item(scan_id=scan_id)
            x_key = self._history_x_source_key(scan_item) if scan_item is not None else None
            if x_key is not None:
                sources.append(x_key)
            self._history_x_keys[scan_id] = x_key
            try:
                bridge = QtDataSubscription(
                    self.client,
                    sources=list(dict.fromkeys(sources)),
                    scan=scan_id,
                    parent=self,
                    min_emit_interval=self.update_interval_s,
                )
                bridge.updated.connect(self._on_data_update)
                self._history_bridges[scan_id] = bridge
            except Exception as exc:
                logger.warning(
                    f"Failed to configure history data subscription for scan {scan_id}: {exc}"
                )

    def _cleanup_history_subscriptions(self):
        for bridge in self._history_bridges.values():
            try:
                bridge.close()
            except Exception:  # pylint: disable=broad-except
                pass
        self._history_bridges = {}
        self._history_x_keys = {}

    def _estimate_source_bytes(self, scan: str, source: tuple[str, str]) -> int | None:
        """
        Estimated stored size of one source, from the scan-history metadata.

        The estimate costs no file I/O — the decision to load is taken before
        anything is read.

        Args:
            scan(str): The scan id the source belongs to.
            source(tuple[str, str]): (device, entry).

        Returns:
            int | None: Size in bytes, or None when it cannot be estimated.
        """
        try:
            estimate = self.client.data_api.estimate_bytes([source], scan)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(f"Could not estimate the size of {source[0]}-{source[1]}: {exc}")
            return None
        return estimate if isinstance(estimate, int) else None

    def _stored_shape(self, scan: str, device: str, entry: str) -> tuple[int, ...] | None:
        """Stored dataset shape of one source, for the confirmation dialog."""
        scan_item = self.get_history_scan_item(scan_id=scan)
        stored = getattr(getattr(scan_item, "_msg", None), "stored_data_info", None)
        if not stored:
            return None
        device_info = stored.get(device) or {}
        info = device_info.get(entry)
        if info is None:
            prefix = f"{device}_"
            if entry.startswith(prefix):
                # Async datasets are stored under the signal's storage name.
                info = device_info.get(entry[len(prefix) :])
        shape = getattr(info, "shape", None) if info is not None else None
        return tuple(shape) if shape else None

    def _filter_oversized_sources(self, sources: list, scan: str | None) -> list:
        """
        Drop sources the user does not want to load, asking per dataset.

        Mirrors the pre-DataAPI guard: each oversized dataset is offered
        individually, a declined dataset is simply not loaded (its curve stays
        visible but empty), and a confirmed dataset is remembered for the rest
        of the session so subscription rebuilds do not re-prompt.

        Args:
            sources(list): Candidate (device, entry) sources.
            scan(str | None): The scan the subscription binds to.

        Returns:
            list: The sources that may be loaded.
        """
        if scan is None or scan == "live" or self._skip_large_dataset_check:
            return list(sources)
        limit_mb = self.config.max_dataset_size_mb
        limit_bytes = int(limit_mb * 1024 * 1024)
        kept = []
        for source in sources:
            if (scan, tuple(source)) in self._size_confirmed_sources:
                kept.append(source)
                continue
            size = self._estimate_source_bytes(scan, tuple(source))
            if size is None or size <= limit_bytes:
                kept.append(source)
                continue
            size_mb = size / (1024 * 1024)
            logger.warning(
                f"Attempt to load large dataset {source[0]}-{source[1]}: {size_mb:.1f} MB "
                f"(limit {limit_mb} MB)"
            )
            if self._skip_large_dataset_warning:
                logger.info("Skipping large dataset warning dialog; dataset not loaded.")
                continue
            if not self._confirm_large_dataset(
                size_mb, source=tuple(source), shape=self._stored_shape(scan, *source)
            ):
                continue
            self._size_confirmed_sources.add((scan, tuple(source)))
            kept.append(source)
        return kept

    def _refresh_data_subscriptions(self):
        """Rebuild all DataAPI subscriptions after a source-set change."""
        if self._shutting_down:
            return
        self._setup_data_api_subscription(scan=self._data_api_scan)
        self._setup_history_curve_subscriptions()

    def _resolve_x_axis(self) -> tuple[str, str] | None:
        """
        Resolve the device x source for the current x mode and sync the label
        suffix, the current-x-device bookkeeping and the alignment state.

        Returns:
            tuple[str, str] | None: The x source key for device/auto modes,
                None when the x axis is index- or timestamp-based.
        """
        mode = self.x_axis_mode["name"] or "auto"
        previous_x_device = self._current_x_device
        x_key = None
        if mode == "timestamp":
            new_suffix = " (timestamp)"
            self._current_x_device = None
        elif mode == "index":
            new_suffix = " (index)"
            self._current_x_device = None
        elif mode == "auto":
            x_key = self._x_source_key()
            if x_key is None:
                new_suffix = " (auto: index)"
                self._current_x_device = None
            else:
                new_suffix = f" (auto: {x_key[0]}-{x_key[1]})"
                self._current_x_device = x_key
        else:  # custom device mode
            x_key = self._x_source_key()
            if x_key is None:
                new_suffix = " (index)"
                self._current_x_device = None
            else:
                new_suffix = f" (custom: {x_key[0]}-{x_key[1]})"
                self._current_x_device = x_key
        self._update_x_label_suffix(new_suffix)
        if previous_x_device != self._current_x_device:
            self._refresh_alignment_state(force_readback=True)
        return x_key

    @SafeSlot(object)
    def _on_data_update(self, update) -> None:
        """
        Render one columnar DataAPI update (live, backfill or history).

        Monitored sources are drawn from the aligned columns; async sources
        are reconstructed from their columnar fragments according to the
        async update type. History curves are routed by their pinned scan id.

        Args:
            update (SubscriptionUpdate): Full-state columnar snapshot.
        """
        updated_any = False

        if self.scan_id is None or update.scan_id == self.scan_id:
            x_key = self._resolve_x_axis()
            aligned_columns = update.aligned()
            for curve in self.curves:
                if curve.config.source != "device":
                    continue
                if self._render_curve_from_update(curve, update, aligned_columns, x_key):
                    updated_any = True

        history_curves = [c for c in self._history_curves if c.config.scan_id == update.scan_id]
        if history_curves:
            x_key = self._history_x_keys.get(update.scan_id)
            aligned_columns = update.aligned()
            for curve in history_curves:
                if self._render_curve_from_update(curve, update, aligned_columns, x_key):
                    updated_any = True

        if updated_any:
            self.request_dap_update.emit()

    def _render_curve_from_update(
        self, curve: Curve, update, aligned_columns: dict, x_key: tuple[str, str] | None
    ) -> bool:
        """
        Render one curve from a DataAPI update.

        Args:
            curve(Curve): The curve to render.
            update(SubscriptionUpdate): The update snapshot.
            aligned_columns(dict): Cached `update.aligned()` columns.
            x_key(tuple[str, str] | None): The resolved x source key.

        Returns:
            bool: True if the curve data was set.
        """
        signal = curve.config.signal
        if signal is None:
            return False
        key = (signal.device, signal.signal)
        source = update.sources.get(key)
        if source is None:
            return False
        if source.kind == "monitored":
            return self._render_monitored_curve(curve, update, key, aligned_columns, x_key)
        return self._render_async_curve(curve, update, source, x_key)

    def _render_monitored_curve(
        self,
        curve: Curve,
        update,
        key: tuple[str, str],
        aligned_columns: dict,
        x_key: tuple[str, str] | None,
    ) -> bool:
        """
        Render a monitored (sync) curve from the aligned columns of an update.

        The x column follows the x-axis mode: aligned ordinals for index, the
        source timestamps for timestamp mode, and the aligned values of the x
        device for device/auto modes with an index fallback when the x source
        is not part of the update.
        """
        y_data = aligned_columns.get(key)
        if y_data is None or len(y_data) == 0:
            return False
        mode = self.x_axis_mode["name"] or "auto"
        x_data = None
        if mode == "timestamp":
            x_data = update.axis("timestamp", key)
        elif mode != "index" and x_key is not None and x_key in update.sources:
            x_data = update.axis("device", x_key)
        if x_data is None:
            x_data = update.aligned_ordinals
        curve.setData(np.asarray(x_data), np.asarray(y_data))
        return True

    def _render_async_curve(
        self, curve: Curve, update, source, x_key: tuple[str, str] | None
    ) -> bool:
        """
        Render an async (or unindexed legacy) curve from its columnar source.

        The y data is reconstructed according to the async update type; x is
        the sample index, the source timestamps (timestamp mode, matching
        lengths only) or a same-length x device column, with an index
        fallback on any length mismatch.
        """
        y_data = self._async_display_values_cached(curve, update, source)
        if y_data is None or len(y_data) == 0:
            return False
        mode = self.x_axis_mode["name"] or "auto"
        x_data = None
        if mode == "timestamp":
            timestamps = source.timestamps
            if timestamps is not None and len(timestamps) == len(y_data):
                try:
                    x_data = np.asarray(timestamps, dtype=float)
                except (TypeError, ValueError):
                    x_data = None
        elif mode not in ("index", "auto") and x_key is not None:
            x_source = update.sources.get(x_key)
            if x_source is not None:
                if x_source.kind == "monitored":
                    x_candidate = np.asarray(x_source.values)
                else:
                    x_candidate = self._async_display_values(x_source)
                if x_candidate is not None and len(x_candidate) == len(y_data):
                    x_data = x_candidate
            if x_data is None:
                logger.warning(
                    f"Async data for curve {curve.name()} and x_axis {x_key} is not of equal "
                    "length. Falling back to 'index' plotting."
                )
        if x_data is None:
            x_data = np.arange(len(y_data))
        self._auto_adjust_async_curve_settings(curve, len(y_data))
        curve.setData(x_data, np.asarray(y_data))
        return True

    @staticmethod
    def _async_display_values(source) -> np.ndarray | None:
        """
        Reconstruct the displayed y data of an async source from its columnar
        fragments.

        - 'add' with a 2-D max_shape displays the latest waveform (last row);
          1-D 'add' concatenates all fragments.
        - 'add_slice' displays the last accumulated row.
        - 'replace' (and unindexed legacy sources without further metadata)
          display the current full state, i.e. the last element.
        - Without an update type (history reads), scalar rows form the full
          series and array rows mirror the legacy "display the last row".

        Args:
            source(SourceData): The async source snapshot.

        Returns:
            np.ndarray | None: The displayed y data.
        """
        values = source.values
        if values is None or len(values) == 0:
            return None
        update_type = source.metadata.get("async_update_type")
        max_shape = source.metadata.get("max_shape") or []
        if update_type == "add":
            if len(max_shape) > 1:
                y_data = np.asarray(values[-1])
                if y_data.ndim > 1:
                    y_data = y_data[-1, :]
                return np.atleast_1d(y_data)
            return np.concatenate([np.atleast_1d(np.asarray(value)) for value in values])
        if update_type in ("add_slice", "replace"):
            return np.atleast_1d(np.asarray(values[-1]))
        # No async-update metadata (e.g. history file reads): rows are the
        # dataset rows.
        first = np.asarray(values[0])
        if first.ndim == 0:
            return np.asarray(values)
        return np.atleast_1d(np.asarray(values[-1]))

    def _async_display_values_cached(self, curve: Curve, update, source) -> np.ndarray | None:
        """
        Incremental variant of :meth:`_async_display_values` for the one
        display mode whose from-scratch cost grows with the scan — 1-D 'add'
        concatenation. The concatenated buffer and the consumed ordinal
        frontier are cached on the curve; per emission only the fragments
        beyond the frontier are appended, keeping the per-message cost
        O(new data) instead of O(total).

        The cache is dropped and the series rebuilt from all fragments when
        the emission cannot be a pure append: a non-live reason (backfill,
        history, rebind), a scan change, a source-key change, or new data at
        or below the frontier (late hole-fills, retention drops). Every full
        rebuild reseeds the cache, so a live stream resumes incrementally
        after it. All other display modes are already O(new data) and are
        delegated unchanged.

        Args:
            curve(Curve): The rendered curve (cache carrier).
            update(SubscriptionUpdate): The update snapshot.
            source(SourceData): The async source snapshot.

        Returns:
            np.ndarray | None: The displayed y data (identical to
                :meth:`_async_display_values`).
        """
        values = source.values
        if values is None or len(values) == 0:
            return None
        update_type = source.metadata.get("async_update_type")
        max_shape = source.metadata.get("max_shape") or []
        if update_type != "add" or len(max_shape) > 1:
            # Last-fragment / last-row display modes: O(new data) already.
            curve._data_api_async_cache = None
            return self._async_display_values(source)
        ordinals = source.ordinals
        if ordinals is None or len(ordinals) == 0:
            return self._async_display_values(source)
        cache = getattr(curve, "_data_api_async_cache", None)
        if (
            cache is not None
            and update.reason == "live"
            and cache["scan_id"] == update.scan_id
            and cache["source_key"] == source.key
        ):
            n_seen = cache["n_seen"]
            frontier_intact = (
                len(ordinals) >= n_seen and ordinals[n_seen - 1] == cache["last_ordinal"]
            )
            if frontier_intact and len(ordinals) == n_seen:
                # Unchanged snapshot (the backend reuses source snapshots).
                return cache["buffer"]
            if frontier_intact and ordinals[n_seen] > cache["last_ordinal"]:
                new_fragments = [np.atleast_1d(np.asarray(value)) for value in values[n_seen:]]
                buffer = np.concatenate([cache["buffer"], *new_fragments])
                cache["buffer"] = buffer
                cache["n_seen"] = len(ordinals)
                cache["last_ordinal"] = ordinals[-1]
                return buffer
        buffer = self._async_display_values(source)
        curve._data_api_async_cache = {
            "scan_id": update.scan_id,
            "source_key": source.key,
            "n_seen": len(ordinals),
            "last_ordinal": ordinals[-1],
            "buffer": buffer,
        }
        return buffer

    def _auto_adjust_async_curve_settings(
        self,
        curve: Curve,
        data_length: int,
        limit: int = 1000,
        method: Literal["subsample", "mean", "peak"] | None = "peak",
    ) -> None:
        """
        Based on the length of the data this method will adjust the plotting settings of
        Curve items, by deactivating the symbol and activating downsampling auto, method='mean',
        if the data length exceeds N points. If the data length is less than N points, the
        symbol will be activated and downsampling will be deactivated. Maximum points will be
        5x the limit.

        Args:
            curve(Curve): The curve to adjust.
            data_length(int): The length of the data.
            limit(int): The limit of the data length to activate the downsampling.

        """
        if limit <= 1:
            logger.warning("Limit must be greater than 1.")
            return
        if data_length > limit:
            if curve.config.symbol is not None:
                curve.set_symbol(None)
            if curve.config.pen_width > 3:
                curve.set_pen_width(3)
            curve.setDownsampling(ds=None, auto=True, method=method)
            curve.setClipToView(True)
        elif data_length <= limit:
            curve.set_symbol("o")
            curve.set_pen_width(4)
            curve.setDownsampling(ds=1, auto=None, method=method)
            curve.setClipToView(True)

    def setup_dap_for_scan(self):
        """Setup DAP updates for the new scan."""
        self.bec_dispatcher.disconnect_slot(
            self.update_dap_curves,
            MessageEndpoints.dap_response(f"{self.old_scan_id}-{self.gui_id}"),
        )
        if len(self._dap_curves) > 0:
            self.bec_dispatcher.connect_slot(
                self.update_dap_curves,
                MessageEndpoints.dap_response(f"{self.scan_id}-{self.gui_id}"),
            )

    @SafeSlot()
    def request_dap(self, _=None):
        """Request new fit for data"""

        published = False
        for dap_curve in self._dap_curves:
            parent_label = getattr(dap_curve.config, "parent_label", None)
            if not parent_label:
                continue
            # find the device curve
            parent_curve = self._find_curve_by_label(parent_label)
            if parent_curve is None:
                logger.warning(
                    f"No device curve found for DAP curve '{dap_curve.name()}'!"
                )  # TODO triggered when DAP curve is removed from the curve dialog, why?
                continue

            x_data, y_data = parent_curve.get_data()
            model_name = dap_curve.config.signal.dap
            model = None
            if not isinstance(model_name, (list, tuple)):
                model = getattr(self.dap, model_name)
            try:
                x_min, x_max = self.roi_region
                x_data, y_data = self._crop_data(x_data, y_data, x_min, x_max)
            except TypeError:
                x_min = None
                x_max = None

            dap_parameters = getattr(dap_curve.config.signal, "dap_parameters", None)

            if parent_curve.config.source != "device":
                fingerprint = self._dap_request_fingerprint(
                    dap_curve, parent_curve, model_name, dap_parameters
                )
                if fingerprint == dap_curve._last_dap_request_fingerprint:
                    continue
                dap_curve._last_dap_request_fingerprint = fingerprint

            dap_kwargs = {
                "data_x": x_data,
                "data_y": y_data,
                "oversample": dap_curve.dap_oversample,
            }
            if dap_parameters:
                dap_kwargs["parameters"] = dap_parameters

            if model is not None:
                class_args = model._plugin_info["class_args"]
                class_kwargs = model._plugin_info["class_kwargs"]
            else:
                class_args = []
                class_kwargs = {"model": model_name}

            msg = messages.DAPRequestMessage(
                dap_cls="LmfitService1D",
                dap_type="on_demand",
                config={
                    "args": [],
                    "kwargs": dap_kwargs,
                    "class_args": class_args,
                    "class_kwargs": class_kwargs,
                    "curve_label": dap_curve.name(),
                },
                metadata={"RID": f"{self.scan_id}-{self.gui_id}"},
            )
            self.client.connector.set_and_publish(MessageEndpoints.dap_request(), msg)
            published = True

        if not published:
            self.unblock_dap_proxy.emit()

    def _dap_request_fingerprint(
        self,
        dap_curve: Curve,
        parent_curve: Curve,
        model_name: str | list[str],
        dap_parameters: dict | list | None,
    ) -> tuple:
        """
        Fingerprint of everything that determines the outcome of a DAP request for a
        curve with a static (custom/history) parent. Two identical fingerprints mean
        the request can be skipped. scan_id is included because it keys the request
        RID and the response subscription, so a new scan re-issues the fit once under
        the current subscription.

        Args:
            dap_curve(Curve): The DAP curve the request would be issued for.
            parent_curve(Curve): The static source curve providing the fit data.
            model_name(str | list[str]): The DAP model name(s).
            dap_parameters(dict | list | None): Optional lmfit parameter overrides.

        Returns:
            tuple: The fingerprint.
        """
        return (
            self.scan_id,
            str(model_name),
            dap_curve.dap_oversample,
            dap_parameters,
            parent_curve.data_version,
            self.roi_region,
        )

    @staticmethod
    def _normalize_dap_parameters(
        parameters: dict | list | lmfit.Parameters | None, dap_name: str | list[str] | None = None
    ) -> dict | list | None:
        """
        Normalize user-provided lmfit parameters into a JSON-serializable dict suitable for the DAP server.

        Supports:
        - `lmfit.Parameters` (single-model only)
        - `dict[name -> number]` (treated as fixed parameter with `vary=False`)
        - `dict[name -> dict]` (lmfit.Parameter fields; defaults to `vary=False` if unspecified)
        - `dict[name -> lmfit.Parameter]`
        - composite: `list[dict[param_name -> spec]]` aligned to model list
        - composite: `dict[model_name -> dict[param_name -> spec]]` (unique model names only)
        """
        if parameters is None:
            return None
        if isinstance(dap_name, (list, tuple)):
            if lmfit is not None and isinstance(parameters, lmfit.Parameters):
                raise TypeError("dap_parameters must be a dict when using composite dap models.")
            if isinstance(parameters, (list, tuple)):
                normalized_list: list[dict | None] = []
                for idx, item in enumerate(parameters):
                    if item is None:
                        normalized_list.append(None)
                        continue
                    if not isinstance(item, dict):
                        raise TypeError(
                            f"dap_parameters list item {idx} must be a dict of parameter overrides."
                        )
                    normalized_list.append(Waveform._normalize_param_overrides(item))
                return normalized_list or None
            if not isinstance(parameters, dict):
                raise TypeError(
                    "dap_parameters must be a dict of model->params when using composite dap models."
                )
            model_names = set(dap_name)
            invalid_models = set(parameters.keys()) - model_names
            if invalid_models:
                raise TypeError(
                    f"Invalid dap_parameters keys for composite model: {sorted(invalid_models)}"
                )
            normalized_composite: dict[str, dict] = {}
            for model_name in dap_name:
                model_params = parameters.get(model_name)
                if model_params is None:
                    continue
                if not isinstance(model_params, dict):
                    raise TypeError(
                        f"dap_parameters for '{model_name}' must be a dict of parameter overrides."
                    )
                normalized = Waveform._normalize_param_overrides(model_params)
                if normalized:
                    normalized_composite[model_name] = normalized
            return normalized_composite or None

        if lmfit is not None and isinstance(parameters, lmfit.Parameters):
            return serialize_lmfit_params(parameters)
        if not isinstance(parameters, dict):
            if lmfit is None:
                raise TypeError(
                    "dap_parameters must be a dict when lmfit is not installed on the client."
                )
            raise TypeError("dap_parameters must be a dict or lmfit.Parameters (or omitted).")

        return Waveform._normalize_param_overrides(parameters)

    @staticmethod
    def _normalize_param_overrides(parameters: dict) -> dict | None:
        normalized: dict[str, dict] = {}
        for name, spec in parameters.items():
            if spec is None:
                continue
            if isinstance(spec, (int, float, np.number)):
                normalized[name] = {"name": name, "value": float(spec), "vary": False}
                continue
            if lmfit is not None and isinstance(spec, lmfit.Parameter):
                normalized[name] = serialize_param_object(spec)
                continue
            if isinstance(spec, dict):
                normalized[name] = {"name": name, **spec}
                if "vary" not in normalized[name]:
                    normalized[name]["vary"] = False
                continue
            raise TypeError(
                f"Invalid dap_parameters entry for '{name}': expected number, dict, or lmfit.Parameter."
            )

        return normalized or None

    @staticmethod
    def _format_dap_label(dap_name: str | list[str]) -> str:
        if isinstance(dap_name, (list, tuple)):
            return "+".join(dap_name)
        return dap_name

    @SafeSlot(dict, dict)
    def update_dap_curves(self, msg, metadata):
        """
        Update the DAP curves with the new data.

        Args:
            msg(dict): Message with the DAP data.
            metadata(dict): Metadata of the message.
        """
        self.unblock_dap_proxy.emit()
        # Extract configuration from the message
        msg_config = msg.get("dap_request", None).content.get("config", {})
        curve_id = msg_config.get("curve_label", None)
        curve = self._find_curve_by_label(curve_id)
        if not curve:
            return

        # Retrieve and store the fit parameters and summary from the DAP server response
        try:
            curve.dap_params = msg["data"][1]["fit_parameters"]
            curve.dap_summary = msg["data"][1]["fit_summary"]
        except TypeError:
            logger.warning(f"Failed to retrieve DAP data for curve '{curve.name()}'")
            return

        # Plot the fitted curve using the server-provided output to avoid requiring lmfit on the client.
        try:
            fit_data = msg["data"][0]
            curve.setData(np.asarray(fit_data["x"]), np.asarray(fit_data["y"]))
        except Exception as e:
            logger.exception(f"Failed to plot DAP result for curve '{curve.name()}', error: {e}")
            return

        metadata.update({"curve_id": curve_id})
        self.dap_params_update.emit(curve.dap_params, metadata)
        self.dap_summary_update.emit(curve.dap_summary, metadata)

    def _refresh_dap_signals(self):
        """
        Refresh the DAP signals for all curves.
        """
        for curve in self._dap_curves:
            self.dap_params_update.emit(curve.dap_params, {"curve_id": curve.name()})
            self.dap_summary_update.emit(curve.dap_summary, {"curve_id": curve.name()})

    def _update_x_label_suffix(self, new_suffix: str):
        """
        Update x_label so it ends with `new_suffix`, removing any old suffix.

        Args:
            new_suffix(str): The new suffix to add to the x_label.
        """
        if new_suffix == self.x_axis_mode["label_suffix"]:
            return

        self.x_axis_mode["label_suffix"] = new_suffix
        self.set_x_label_suffix(new_suffix)

    def _switch_x_axis_item(self, mode: str):
        """
        Switch the x-axis mode between timestamp, index, the best effort and custom signal.

        Args:
            mode(str): Mode of the x-axis.
                - "timestamp": Use the timestamp signal.
                - "index": Use the index signal.
                - "best_effort": Use the best effort signal.
                - Custom signal name of a device from BEC.
        """
        logger.info(f'Switching x-axis mode to "{mode}"')
        current_axis = self.plot_item.axes["bottom"]["item"]
        # Only update the axis if the mode change requires it.
        if mode == "timestamp":
            # Only update if the current axis is not a DateAxisItem.
            if not isinstance(current_axis, pg.graphicsItems.DateAxisItem.DateAxisItem):
                date_axis = pg.graphicsItems.DateAxisItem.DateAxisItem(orientation="bottom")
                self.plot_item.setAxisItems({"bottom": date_axis})
        else:
            # For non-timestamp modes, only update if the current axis is a DateAxisItem.
            if isinstance(current_axis, pg.graphicsItems.DateAxisItem.DateAxisItem):
                default_axis = pg.AxisItem(orientation="bottom")
                self.plot_item.setAxisItems({"bottom": default_axis})

        self.set_x_label_suffix(self.x_axis_mode["label_suffix"])

    def _categorise_device_curves(self) -> str:
        """
        Categorize the device curves into sync and async based on the readout priority.
        """
        if self.scan_item is None:
            self.update_with_scan_history(-1)
            if self.scan_item is None:
                logger.info("No scan executed so far; skipping device curves categorisation.")
                return None

        if hasattr(self.scan_item, "live_data"):
            readout_priority = self.scan_item.status_message.info.get(
                "readout_priority"
            )  # live data
        else:
            readout_priority = self.scan_item.metadata["bec"].get("readout_priority")  # history

        if readout_priority is None:
            return None

        # Reset sync/async curve lists
        self._async_curves.clear()
        self._sync_curves.clear()
        found_async = False
        found_sync = False
        mode = "sync"

        readout_priority_async = self._ensure_str_list(readout_priority.get("async", []))
        readout_priority_sync = self._ensure_str_list(readout_priority.get("monitored", []))

        for curve in self.curves:
            if curve.config.source != "device":
                continue
            dev_name = curve.config.signal.device
            entry = curve.config.signal.signal
            category = classify_device_signal(self.dev.get(dev_name), entry)
            if category == SignalCategory.ASYNC or dev_name in readout_priority_async:
                self._async_curves.append(curve)
                found_async = True
            elif category == SignalCategory.SYNC or dev_name in readout_priority_sync:
                self._sync_curves.append(curve)
                found_sync = True
            else:
                logger.warning(
                    f"Cannot classify signal {dev_name}.{entry}: no signal info and "
                    "device not found in readout priority list."
                )
                continue
        # Determine the mode of the scan
        if found_async and found_sync:
            mode = "mixed"
            logger.warning(
                f"Found both async and sync devices in the scan. X-axis integrity cannot be guaranteed."
            )
        elif found_async:
            mode = "async"
        elif found_sync:
            mode = "sync"

        logger.info(f"Scan {self.scan_id} => mode={self._mode}")
        return mode

    def get_history_scan_item(
        self, scan_index: int = None, scan_id: str = None
    ) -> ScanDataContainer | None:
        """
        Get scan item from history based on scan_id or scan_index.
        If both are provided, scan_id takes precedence and the resolved scan_number
        will be read from the fetched item.

        Args:
            scan_id (str, optional): ScanID of the scan to fetch. Defaults to None.
            scan_index (int, optional): Index (scan number) of the scan to fetch. Defaults to None.

        Returns:
            ScanDataContainer | None: The fetched scan item or None if no item was found.
        """
        if scan_index is not None and scan_id is not None:
            scan_index = None  # Prefer scan_id when both are given

        if scan_index is None and scan_id is None:
            logger.warning("Neither scan_id or scan_number was provided, fetching the latest scan")
            scan_index = -1

        if scan_index is None:
            return self.client.history.get_by_scan_id(scan_id)

        if scan_index == -1:
            scan_item = self.client.queue.scan_storage.current_scan
            if scan_item is not None:
                if scan_item.status_message is None:
                    logger.warning(f"Scan item with {scan_item.scan_id} has no status message.")
                    return None
                return scan_item

        if len(self.client.history) == 0:
            logger.info("No scans executed so far. Cannot fetch scan history.")
            return None

        # check if scan_index is negative, then fetch it just from the list from the end
        if int(scan_index) < 0:
            return self.client.history[scan_index]
        scan_item = self.client.history.get_by_scan_number(scan_index)
        if scan_item is None:
            logger.warning(f"Scan with scan_number {scan_index} not found in history.")
            return None
        if isinstance(scan_item, list):
            if len(scan_item) > 1:
                logger.warning(
                    f"Multiple scans found with scan_number {scan_index}. Returning the latest one."
                )
            scan_item = scan_item[-1]
        return scan_item

    @SafeSlot(int)
    @SafeSlot(str)
    @SafeSlot()
    def update_with_scan_history(self, scan_index: int = None, scan_id: str = None):
        """
        Update the scan curves with the data from the scan storage.
        If both arguments are provided, scan_id takes precedence and scan_index is ignored.

        Args:
            scan_id(str, optional): ScanID of the scan to be updated. Defaults to None.
            scan_index(int, optional): Index (scan number) of the scan to be updated. Defaults to None.
        """
        self.scan_item = self.get_history_scan_item(scan_index=scan_index, scan_id=scan_id)

        if self.scan_item is None:
            return

        if scan_id is not None:
            self.scan_id = scan_id
        else:
            # If scan_number was used, set the scan_id from the fetched item
            if hasattr(self.scan_item, "metadata"):
                self.scan_id = self.scan_item.metadata["bec"]["scan_id"]
            else:
                self.scan_id = self.scan_item.scan_id

        self._mode = self._categorise_device_curves()
        self.setup_dap_for_scan()
        # The data flows through the DataAPI: a still-running scan is followed
        # live, a terminal scan is served by the history plugin.
        if hasattr(self.scan_item, "live_data"):
            self._setup_data_api_subscription(scan="live")
        else:
            self._setup_data_api_subscription(scan=self.scan_id)

    ################################################################################
    # Utility Methods
    ################################################################################

    # Large dataset handling helpers
    @staticmethod
    def _describe_dataset(source: tuple[str, str] | None, shape: tuple[int, ...] | None) -> str:
        """
        Human-readable identity and extent of a dataset for the dialog.

        Args:
            source(tuple[str, str] | None): (device, entry) of the dataset.
            shape(tuple[int, ...] | None): Stored dataset shape.

        Returns:
            str: A sentence naming the dataset and its number of points.
        """
        name = f"'{source[0]}-{source[1]}'" if source else "The selected dataset"
        if not shape:
            return f"{name} (size unknown)"
        if len(shape) == 1:
            return f"{name} holds {shape[0]:,} points"
        per_point = int(np.prod(shape[1:]))
        return (
            f"{name} holds {shape[0]:,} points x {per_point:,} samples "
            f"({int(np.prod(shape)):,} values, shape {tuple(shape)})"
        )

    def _confirm_large_dataset(
        self,
        size_mb: float,
        source: tuple[str, str] | None = None,
        shape: tuple[int, ...] | None = None,
    ) -> bool:
        """
        Confirm with the user whether to load a large dataset with dialog popup.
        Also allows the user to adjust the maximum dataset size limit and if user
        wants to see this popup again during session.

        Args:
            size_mb(float): Size of the dataset in MB.
            source(tuple[str, str] | None): (device, entry) of the dataset, shown
                in the dialog so the user knows which curve is affected.
            shape(tuple[int, ...] | None): Stored shape, shown as a point count.

        Returns:
            bool: True if the user confirmed to load the dataset, False otherwise.
        """
        if self._skip_large_dataset_warning:
            return True

        dialog = QDialog(self)
        dialog.setWindowTitle("Large dataset detected")
        main_dialog_layout = QVBoxLayout(dialog)

        # Limit adjustment widgets
        limit_adjustment_layout = QHBoxLayout()
        limit_adjustment_layout.addWidget(QLabel("New limit (MB):"))
        spin = QDoubleSpinBox()
        spin.setRange(0.001, 4096)
        spin.setDecimals(3)
        spin.setSingleStep(0.01)
        spin.setValue(self.config.max_dataset_size_mb)
        spin.valueChanged.connect(lambda value: setattr(self.config, "max_dataset_size_mb", value))
        limit_adjustment_layout.addWidget(spin)

        # Don't show again checkbox
        checkbox = QCheckBox("Don't show this again for this session")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Yes | QDialogButtonBox.No, Qt.Horizontal, dialog
        )
        buttons.accepted.connect(dialog.accept)  # Yes
        buttons.rejected.connect(dialog.reject)  # No

        # widget layout
        main_dialog_layout.addWidget(
            QLabel(
                f"{self._describe_dataset(source, shape)} and is {size_mb:.1f} MB, "
                f"which exceeds the current limit of {self.config.max_dataset_size_mb} MB.\n"
            )
        )
        main_dialog_layout.addLayout(limit_adjustment_layout)
        main_dialog_layout.addWidget(checkbox)
        main_dialog_layout.addWidget(QLabel("Would you like to display dataset anyway?"))
        main_dialog_layout.addWidget(buttons)

        result = dialog.exec()  # modal; waits for user choice

        # Respect the “don't show again” checkbox for *either* choice
        if checkbox.isChecked():
            self._skip_large_dataset_warning = True

        if result == QDialog.Accepted:
            self.config.max_dataset_size_mb = spin.value()
            return True
        return False

    def _ensure_str_list(self, entries: list | tuple | np.ndarray):
        """
        Convert a variety of possible inputs (string, bytes, list/tuple/ndarray of either)
        into a list of Python strings.

        Args:
            entries:

        Returns:
            list[str]: A list of Python strings.
        """

        if isinstance(entries, (list, tuple, np.ndarray)):
            return [self._to_str(e) for e in entries]
        else:
            return [self._to_str(entries)]

    @staticmethod
    def _to_str(x):
        """
        Convert a single object x (which may be a Python string, bytes, or something else)
        into a plain Python string.
        """
        if isinstance(x, bytes):
            return x.decode("utf-8", errors="replace")
        return str(x)

    @staticmethod
    def _crop_data(x_data, y_data, x_min=None, x_max=None):
        """
        Utility function to crop x_data and y_data based on x_min and x_max.

        Args:
            x_data (np.ndarray): The array of x-values.
            y_data (np.ndarray): The array of y-values corresponding to x_data.
            x_min (float, optional): The lower bound for cropping. Defaults to None.
            x_max (float, optional): The upper bound for cropping. Defaults to None.

        Returns:
            tuple: (cropped_x_data, cropped_y_data)
        """
        # If either bound is None, skip cropping
        if x_min is None or x_max is None:
            return x_data, y_data

        # Create a boolean mask to select only those points within [x_min, x_max]
        mask = (x_data >= x_min) & (x_data <= x_max)

        return x_data[mask], y_data[mask]

    ################################################################################
    # Export Methods
    ################################################################################
    def get_all_data(self, output: Literal["dict", "pandas"] = "dict") -> dict:  # | pd.DataFrame:
        """
        Extract all curve data into a dictionary or a pandas DataFrame.

        Args:
            output (Literal["dict", "pandas"]): Format of the output data.

        Returns:
            dict | pd.DataFrame: Data of all curves in the specified format.
        """
        data = {}
        if output == "pandas":  # pragma: no cover
            try:
                import pandas as pd
            except ModuleNotFoundError:
                raise ModuleNotFoundError(
                    "Pandas is not installed. Please install pandas using 'pip install pandas'."
                )

        for curve in self.curves:
            x_data, y_data = curve.get_data()
            if x_data is not None or y_data is not None:
                if output == "dict":
                    data[curve.name()] = {"x": x_data.tolist(), "y": y_data.tolist()}
                elif output == "pandas" and pd is not None:
                    data[curve.name()] = pd.DataFrame({"x": x_data, "y": y_data})

        if output == "pandas" and pd is not None:  # pragma: no cover
            combined_data = pd.concat(
                [data[curve.name()] for curve in self.curves],
                axis=1,
                keys=[curve.name() for curve in self.curves],
            )
            return combined_data
        return data

    def export_to_matplotlib(self):  # pragma: no cover
        """
        Export current waveform to matplotlib gui. Available only if matplotlib is installed in the environment.

        """
        try:
            import matplotlib as mpl
            from pyqtgraph.exporters import MatplotlibExporter

            MatplotlibExporter(self.plot_item).export()
        except ModuleNotFoundError:
            logger.error("Matplotlib is not installed in the environment.")

    ################################################################################
    # Cleanup
    ################################################################################
    def cleanup(self):
        """
        Cleanup the widget by disconnecting signals and closing dialogs.
        """
        self._shutting_down = True
        self._cleanup_data_api_subscription()
        self._cleanup_history_subscriptions()
        self.proxy_dap_request.cleanup()
        if self._alignment_controller is not None:
            self._alignment_controller.cleanup()
        self.clear_all()
        if self.curve_settings_dialog is not None:
            self.curve_settings_dialog.reject()
            self.curve_settings_dialog = None
        if self.dap_summary_dialog is not None:
            self.dap_summary_dialog.reject()
            self.dap_summary_dialog = None
        if self.scan_history_dialog is not None:
            self.scan_history_dialog.reject()
            self.scan_history_dialog = None
        super().cleanup()


class DemoApp(QMainWindow):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Waveform Demo")
        self.resize(1600, 600)
        self.main_widget = QWidget(self)
        self.layout = QHBoxLayout(self.main_widget)
        self.setCentralWidget(self.main_widget)

        self.custom_waveform = Waveform(popups=True)
        self._populate_custom_curve_demo()

        self.sine_waveform = Waveform(popups=True)
        self.sine_waveform.dap_params_update.connect(self._log_sine_dap_params)
        self._populate_sine_curve_demo()

        self.layout.addWidget(self.custom_waveform)
        self.layout.addWidget(self.sine_waveform)

    def _populate_custom_curve_demo(self):
        """
        Showcase how to attach a DAP fit to a fully custom curve.

        The example generates a noisy Gaussian trace, plots it as custom data, and
        immediately adds a Gaussian model fit. When the widget is plugged into a
        running BEC instance, the fit curve will be requested like any other device
        signal. This keeps the example minimal while demonstrating the new workflow.
        """
        x = np.linspace(-4, 4, 600)
        rng = np.random.default_rng(42)
        noise = rng.normal(loc=0, scale=0.05, size=x.size)
        amplitude = 3.5
        center = 0.5
        sigma = 0.8
        y = amplitude * np.exp(-((x - center) ** 2) / (2 * sigma**2)) + noise

        # 1) No explicit parameters: server will use lmfit defaults/guesses.
        self.custom_waveform.plot(x=x, y=y, label="custom-gaussian", dap="GaussianModel")

        # 2) Easy dict: numbers mean "fix this parameter to value" (vary=False).
        self.custom_waveform.plot(
            x=x,
            y=y,
            label="custom-gaussian-fixed-easy",
            dap="GaussianModel",
            dap_parameters={"amplitude": 1.0},
            dap_oversample=5,
        )

        # 3) Partial parameter override: this should still trigger guessing on the server
        #    because not all Gaussian parameters are explicitly specified.
        self.custom_waveform.plot(
            x=x,
            y=y,
            label="custom-gaussian-partial-guess",
            dap="GaussianModel",
            dap_parameters={
                "center": {"value": 1.2, "vary": True},
                "sigma": {"value": sigma, "vary": False, "min": 0.0},
            },
        )

        # 4) Complete parameter override: this should skip guessing on the server.
        if lmfit is not None:
            params_gauss = lmfit.models.GaussianModel().make_params()
            params_gauss["amplitude"].set(value=amplitude, vary=False)
            params_gauss["center"].set(value=center, vary=False)
            params_gauss["sigma"].set(value=sigma, vary=False, min=0.0)
            self.custom_waveform.plot(
                x=x,
                y=y,
                label="custom-gaussian-complete-no-guess",
                dap="GaussianModel",
                dap_parameters=params_gauss,
            )
        else:
            logger.info("Skipping lmfit.Parameters demo (lmfit not installed on client).")

        # Composite example: spectrum with three Gaussians (DAP-only)
        x_spec = np.linspace(-5, 5, 800)
        rng_spec = np.random.default_rng(123)
        centers = [-2.0, 0.6, 2.4]
        amplitudes = [2.5, 3.2, 1.8]
        sigmas = [0.35, 0.5, 0.3]
        y_spec = (
            amplitudes[0] * np.exp(-((x_spec - centers[0]) ** 2) / (2 * sigmas[0] ** 2))
            + amplitudes[1] * np.exp(-((x_spec - centers[1]) ** 2) / (2 * sigmas[1] ** 2))
            + amplitudes[2] * np.exp(-((x_spec - centers[2]) ** 2) / (2 * sigmas[2] ** 2))
            + rng_spec.normal(loc=0, scale=0.06, size=x_spec.size)
        )

        # 5) Composite model with partial overrides only: this should still trigger guessing.
        self.custom_waveform.plot(
            x=x_spec,
            y=y_spec,
            label="custom-gaussian-spectrum-partial-guess",
            dap=["GaussianModel", "GaussianModel", "GaussianModel"],
            dap_parameters=[
                {"center": {"value": centers[0], "vary": False}},
                {"center": {"value": centers[1], "vary": False}},
                {"center": {"value": centers[2], "vary": False}},
            ],
        )

        # 6) Composite model with all component parameters specified: this should skip guessing.
        self.custom_waveform.plot(
            x=x_spec,
            y=y_spec,
            label="custom-gaussian-spectrum-complete-no-guess",
            dap=["GaussianModel", "GaussianModel", "GaussianModel"],
            dap_parameters=[
                {
                    "amplitude": {"value": amplitudes[0], "vary": False},
                    "center": {"value": centers[0], "vary": False},
                    "sigma": {"value": sigmas[0], "vary": False, "min": 0.0},
                },
                {
                    "amplitude": {"value": amplitudes[1], "vary": False},
                    "center": {"value": centers[1], "vary": False},
                    "sigma": {"value": sigmas[1], "vary": False, "min": 0.0},
                },
                {
                    "amplitude": {"value": amplitudes[2], "vary": False},
                    "center": {"value": centers[2], "vary": False},
                    "sigma": {"value": sigmas[2], "vary": False, "min": 0.0},
                },
            ],
        )

    def _populate_sine_curve_demo(self):
        """
        Showcase how lmfit's base SineModel can struggle with a drifting baseline.
        """
        x = np.linspace(0, 6 * np.pi, 600)
        rng = np.random.default_rng(7)
        amplitude = 1.6
        frequency = 0.75
        phase = 0.4
        offset = 0.8
        slope = 0.08
        noise = rng.normal(loc=0, scale=0.12, size=x.size)
        y = offset + slope * x + amplitude * np.sin(2 * np.pi * frequency * x + phase) + noise

        # Base SineModel (no offset support) to show the mismatch
        self.sine_waveform.plot(x=x, y=y, label="custom-sine-data", dap="SineModel")

        # Composite model: Sine + Linear baseline (offset + slope)
        self.sine_waveform.plot(
            x=x,
            y=y,
            label="custom-sine-composite",
            dap=["SineModel", "LinearModel"],
            dap_oversample=4,
        )

        if lmfit is None:
            logger.info("Skipping sine lmfit demo (lmfit not installed on client).")
            return

        return

    @staticmethod
    def _log_sine_dap_params(params: dict, metadata: dict):
        curve_id = metadata.get("curve_id")
        if curve_id not in {
            "custom-sine-data-SineModel",
            "custom-sine-composite-SineModel+LinearModel",
        }:
            return
        logger.info(f"SineModel DAP fit params ({curve_id}): {params}")


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = DemoApp()
    widget.show()
    widget.resize(1400, 600)
    sys.exit(app.exec_())
