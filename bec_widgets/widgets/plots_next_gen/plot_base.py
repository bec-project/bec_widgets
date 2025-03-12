from __future__ import annotations

from enum import Enum

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger
from qtpy.QtCore import QPoint, QPointF, Qt, Signal
from qtpy.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.qt_utils.round_frame import RoundedFrame
from bec_widgets.qt_utils.settings_dialog import SettingsDialog
from bec_widgets.qt_utils.side_panel import SidePanel
from bec_widgets.qt_utils.toolbar import MaterialIconAction, ModularToolBar, ToolbarBundle
from bec_widgets.utils import ConnectionConfig, Crosshair, EntryValidator
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.fps_counter import FPSCounter
from bec_widgets.utils.widget_state_manager import WidgetStateManager
from bec_widgets.widgets.containers.layout_manager.layout_manager import LayoutManagerWidget
from bec_widgets.widgets.plots_next_gen.setting_menus.axis_settings import AxisSettings
from bec_widgets.widgets.plots_next_gen.toolbar_bundles.mouse_interactions import (
    MouseInteractionToolbarBundle,
)
from bec_widgets.widgets.plots_next_gen.toolbar_bundles.plot_export import PlotExportBundle
from bec_widgets.widgets.plots_next_gen.toolbar_bundles.roi_bundle import ROIBundle

logger = bec_logger.logger


class BECViewBox(pg.ViewBox):
    sigPaint = Signal()

    def paint(self, painter, opt, widget):
        super().paint(painter, opt, widget)
        self.sigPaint.emit()

    def itemBoundsChanged(self, item):
        self._itemBoundsCache.pop(item, None)
        if (self.state["autoRange"][0] is not False) or (self.state["autoRange"][1] is not False):
            # check if the call is coming from a mouse-move event
            if hasattr(item, "skip_auto_range") and item.skip_auto_range:
                return
            self._autoRangeNeedsUpdate = True
            self.update()


class UIMode(Enum):
    NONE = 0
    POPUP = 1
    SIDE = 2


class PlotBase(BECWidget, QWidget):
    PLUGIN = False
    RPC = False

    # Custom Signals
    property_changed = Signal(str, object)
    crosshair_position_changed = Signal(tuple)
    crosshair_position_clicked = Signal(tuple)
    crosshair_coordinates_changed = Signal(tuple)
    crosshair_coordinates_clicked = Signal(tuple)

    def __init__(
        self,
        parent: QWidget | None = None,
        config: ConnectionConfig | None = None,
        client=None,
        gui_id: str | None = None,
        popups: bool = False,
        **kwargs,
    ) -> None:
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(client=client, gui_id=gui_id, config=config, **kwargs)
        QWidget.__init__(self, parent=parent)

        # For PropertyManager identification
        self.setObjectName("PlotBase")
        self.get_bec_shortcuts()

        # Layout Management
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout_manager = LayoutManagerWidget(parent=self)
        self.layout_manager.layout.setContentsMargins(0, 0, 0, 0)
        self.layout_manager.layout.setSpacing(0)

        # Property Manager
        self.state_manager = WidgetStateManager(self)

        # Entry Validator
        self.entry_validator = EntryValidator(self.dev)

        # Base widgets elements
        self._popups = popups
        self._ui_mode = UIMode.POPUP if popups else UIMode.SIDE
        self.axis_settings_dialog = None
        self.plot_widget = pg.GraphicsLayoutWidget(parent=self)
        self.plot_item = pg.PlotItem(viewBox=BECViewBox(enableMenu=True))
        self.plot_widget.addItem(self.plot_item)
        self.side_panel = SidePanel(self, orientation="left", panel_max_width=280)
        self.toolbar = ModularToolBar(target_widget=self, orientation="horizontal")
        self._init_toolbar()

        # PlotItem Addons
        self.plot_item.addLegend()
        self.crosshair = None
        self.fps_monitor = None
        self.fps_label = QLabel(alignment=Qt.AlignmentFlag.AlignRight)
        self._user_x_label = ""
        self._x_label_suffix = ""
        self._user_y_label = ""
        self._y_label_suffix = ""

        self._init_ui()

        self._connect_to_theme_change()
        self._update_theme()

    def apply_theme(self, theme: str):
        self.round_plot_widget.apply_theme(theme)

    def _init_ui(self):
        self.layout.addWidget(self.layout_manager)
        self.round_plot_widget = RoundedFrame(content_widget=self.plot_widget, theme_update=True)

        self.layout_manager.add_widget(self.round_plot_widget)
        self.layout_manager.add_widget_relative(self.fps_label, self.round_plot_widget, "top")
        self.fps_label.hide()
        self.layout_manager.add_widget_relative(self.side_panel, self.round_plot_widget, "left")
        self.layout_manager.add_widget_relative(self.toolbar, self.fps_label, "top")

        self.ui_mode = self._ui_mode  # to initiate the first time

        # PlotItem ViewBox Signals
        self.plot_item.vb.sigStateChanged.connect(self.viewbox_state_changed)

    def _init_toolbar(self):
        self.popup_bundle = None
        self.performance_bundle = ToolbarBundle("performance")
        self.plot_export_bundle = PlotExportBundle("plot_export", target_widget=self)
        self.mouse_bundle = MouseInteractionToolbarBundle("mouse_interaction", target_widget=self)
        # self.state_export_bundle = SaveStateBundle("state_export", target_widget=self) #TODO ATM disabled, cannot be used in DockArea, which is exposed to the user
        self.roi_bundle = ROIBundle("roi", target_widget=self)

        # Add elements to toolbar
        self.toolbar.add_bundle(self.plot_export_bundle, target_widget=self)
        # self.toolbar.add_bundle(self.state_export_bundle, target_widget=self) #TODO ATM disabled, cannot be used in DockArea, which is exposed to the user
        self.toolbar.add_bundle(self.mouse_bundle, target_widget=self)
        self.toolbar.add_bundle(self.roi_bundle, target_widget=self)

        self.performance_bundle.add_action(
            "fps_monitor",
            MaterialIconAction(
                icon_name="speed", tooltip="Show FPS Monitor", checkable=True, parent=self
            ),
        )
        self.toolbar.add_bundle(self.performance_bundle, target_widget=self)

        self.toolbar.widgets["fps_monitor"].action.toggled.connect(
            lambda checked: setattr(self, "enable_fps_monitor", checked)
        )

        # hide some options by default
        self.toolbar.toggle_action_visibility("fps_monitor", False)

    def add_side_menus(self):
        """Adds multiple menus to the side panel."""
        # Setting Axis Widget
        try:
            axis_setting = AxisSettings(target_widget=self)
            self.side_panel.add_menu(
                action_id="axis",
                icon_name="settings",
                tooltip="Show Axis Settings",
                widget=axis_setting,
                title="Axis Settings",
            )
        except ValueError:
            return

    def add_popups(self):
        """
        Add popups to the toolbar.
        """
        self.popup_bundle = ToolbarBundle("popup_bundle")
        settings = MaterialIconAction(
            icon_name="settings", tooltip="Show Axis Settings", checkable=True, parent=self
        )
        self.popup_bundle.add_action("axis", settings)
        self.toolbar.add_bundle(self.popup_bundle, target_widget=self)
        self.toolbar.widgets["axis"].action.triggered.connect(self.show_axis_settings_popup)

    def show_axis_settings_popup(self):
        """
        Show the axis settings dialog.
        """
        settings_action = self.toolbar.widgets["axis"].action
        if self.axis_settings_dialog is None or not self.axis_settings_dialog.isVisible():
            axis_setting = AxisSettings(target_widget=self, popup=True)
            self.axis_settings_dialog = SettingsDialog(
                self, settings_widget=axis_setting, window_title="Axis Settings", modal=False
            )
            # When the dialog is closed, update the toolbar icon and clear the reference
            self.axis_settings_dialog.finished.connect(self._axis_settings_closed)
            self.axis_settings_dialog.show()
            settings_action.setChecked(True)
        else:
            # If already open, bring it to the front
            self.axis_settings_dialog.raise_()
            self.axis_settings_dialog.activateWindow()
            settings_action.setChecked(True)  # keep it toggled

    def _axis_settings_closed(self):
        """
        Slot for when the axis settings dialog is closed.
        """
        self.axis_settings_dialog = None
        self.toolbar.widgets["axis"].action.setChecked(False)

    def reset_legend(self):
        """In the case that the legend is not visible, reset it to be visible to top left corner"""
        self.plot_item.legend.autoAnchor(50)

    ################################################################################
    # Toggle UI Elements
    ################################################################################
    @property
    def ui_mode(self) -> UIMode:
        """
        Get the UI mode.
        """
        return self._ui_mode

    @ui_mode.setter
    def ui_mode(self, mode: UIMode):
        """
        Set the UI mode.

        Args:
            mode(UIMode): The UI mode to set.
        """
        if not isinstance(mode, UIMode):
            raise ValueError("ui_mode must be an instance of UIMode")
        self._ui_mode = mode

        # First, clear both UI elements:
        if self.popup_bundle is not None:
            for action_id in self.toolbar.bundles["popup_bundle"]:
                self.toolbar.widgets[action_id].action.setVisible(False)
            if self.axis_settings_dialog is not None and self.axis_settings_dialog.isVisible():
                self.axis_settings_dialog.close()
        self.side_panel.hide()

        # Now, apply the new mode:
        if mode == UIMode.POPUP:
            if self.popup_bundle is None:
                self.add_popups()
            else:
                for action_id in self.toolbar.bundles["popup_bundle"]:
                    self.toolbar.widgets[action_id].action.setVisible(True)
        elif mode == UIMode.SIDE:
            self.add_side_menus()
            self.side_panel.show()

    @SafeProperty(bool, doc="Enable popups setting dialogs for the plot widget.")
    def enable_popups(self):
        """
        Enable popups setting dialogs for the plot widget.
        """
        return self.ui_mode == UIMode.POPUP

    @enable_popups.setter
    def enable_popups(self, value: bool):
        """
        Set the popups setting dialogs for the plot widget.

        Args:
            value(bool): The value to set.
        """
        if value:
            self.ui_mode = UIMode.POPUP
        else:
            if self.ui_mode == UIMode.POPUP:
                self.ui_mode = UIMode.NONE

    @SafeProperty(bool, doc="Show Side Panel")
    def enable_side_panel(self) -> bool:
        """
        Show Side Panel
        """
        return self.ui_mode == UIMode.SIDE

    @enable_side_panel.setter
    def enable_side_panel(self, value: bool):
        """
        Show Side Panel

        Args:
            value(bool): The value to set.
        """
        if value:
            self.ui_mode = UIMode.SIDE
        else:
            if self.ui_mode == UIMode.SIDE:
                self.ui_mode = UIMode.NONE

    @SafeProperty(bool, doc="Show Toolbar")
    def enable_toolbar(self) -> bool:
        """
        Show Toolbar.
        """
        return self.toolbar.isVisible()

    @enable_toolbar.setter
    def enable_toolbar(self, value: bool):
        """
        Show Toolbar.

        Args:
            value(bool): The value to set.
        """
        self.toolbar.setVisible(value)

    @SafeProperty(bool, doc="Enable the FPS monitor.")
    def enable_fps_monitor(self) -> bool:
        """
        Enable the FPS monitor.
        """
        return self.fps_label.isVisible()

    @enable_fps_monitor.setter
    def enable_fps_monitor(self, value: bool):
        """
        Enable the FPS monitor.

        Args:
            value(bool): The value to set.
        """
        if value and self.fps_monitor is None:
            self.hook_fps_monitor()
        elif not value and self.fps_monitor is not None:
            self.unhook_fps_monitor()

    ################################################################################
    # ViewBox State Signals
    ################################################################################

    def viewbox_state_changed(self):
        """
        Emit a signal when the state of the viewbox has changed.
        Merges the default pyqtgraphs signal states and also CTRL menu toggles.
        """

        viewbox_state = self.plot_item.vb.getState()
        # Range Limits
        x_min, x_max = viewbox_state["targetRange"][0]
        y_min, y_max = viewbox_state["targetRange"][1]
        self.property_changed.emit("x_min", x_min)
        self.property_changed.emit("x_max", x_max)
        self.property_changed.emit("y_min", y_min)
        self.property_changed.emit("y_max", y_max)

        # Grid Toggles

    ################################################################################
    # Plot Properties
    ################################################################################

    def set(self, **kwargs):
        """
        Set the properties of the plot widget.

        Args:
            **kwargs: Keyword arguments for the properties to be set.

        Possible properties:

        """
        property_map = {
            "title": self.title,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "x_limits": self.x_limits,
            "y_limits": self.y_limits,
            "x_grid": self.x_grid,
            "y_grid": self.y_grid,
            "inner_axes": self.inner_axes,
            "outer_axes": self.outer_axes,
            "lock_aspect_ratio": self.lock_aspect_ratio,
            "auto_range_x": self.auto_range_x,
            "auto_range_y": self.auto_range_y,
            "x_log": self.x_log,
            "y_log": self.y_log,
            "legend_label_size": self.legend_label_size,
        }

        for key, value in kwargs.items():
            if key in property_map:
                setattr(self, key, value)
            else:
                logger.warning(f"Property {key} not found.")

    @SafeProperty(str, doc="The title of the axes.")
    def title(self) -> str:
        """
        Set title of the plot.
        """
        return self.plot_item.titleLabel.text

    @title.setter
    def title(self, value: str):
        """
        Set title of the plot.

        Args:
            value(str): The title to set.
        """
        self.plot_item.setTitle(value)
        self.property_changed.emit("title", value)

    @SafeProperty(str, doc="The text of the x label")
    def x_label(self) -> str:
        """
        The set label for the x-axis.
        """
        return self._user_x_label

    @x_label.setter
    def x_label(self, value: str):
        """
        The set label for the x-axis.

        Args:
            value(str): The label to set.
        """
        self._user_x_label = value
        self._apply_x_label()
        self.property_changed.emit("x_label", self._user_x_label)

    @property
    def x_label_suffix(self) -> str:
        """
        A read-only (or internal) suffix automatically appended to the user label.
        Not settable by the user directly from the UI.
        """
        return self._x_label_suffix

    def set_x_label_suffix(self, suffix: str):
        """
        Public or protected method to update the suffix.
        The user code or subclass (Waveform) can call this
        when x_mode changes, but the AxisSettings won't show it.
        """
        self._x_label_suffix = suffix
        self._apply_x_label()

    @property
    def x_label_combined(self) -> str:
        """
        The final label shown on the axis = user portion + suffix.
        """
        return self._user_x_label + self._x_label_suffix

    def _apply_x_label(self):
        """
        Actually updates the pyqtgraph axis label text to
        the combined label. Called whenever user label or suffix changes.
        """
        final_label = self.x_label_combined
        self.plot_item.setLabel("bottom", text=final_label)

    @SafeProperty(str, doc="The text of the y label")
    def y_label(self) -> str:
        """
        The set label for the y-axis.
        """
        return self._user_y_label

    @y_label.setter
    def y_label(self, value: str):
        """
        The set label for the y-axis.
        Args:
            value(str): The label to set.
        """
        self._user_y_label = value
        self._apply_y_label()
        self.property_changed.emit("y_label", value)

    @property
    def y_label_suffix(self) -> str:
        """
        A read-only suffix automatically appended to the y label.
        """
        return self._y_label_suffix

    def set_y_label_suffix(self, suffix: str):
        """
        Public method to update the y label suffix.
        """
        self._y_label_suffix = suffix
        self._apply_y_label()

    @property
    def y_label_combined(self) -> str:
        """
        The final y label shown on the axis = user portion + suffix.
        """
        return self._user_y_label + self._y_label_suffix

    def _apply_y_label(self):
        """
        Actually updates the pyqtgraph y axis label text to
        the combined y label. Called whenever y label or suffix changes.
        """
        final_label = self.y_label_combined
        self.plot_item.setLabel("left", text=final_label)

    def _tuple_to_qpointf(self, tuple: tuple | list):
        """
        Helper function to convert a tuple to a QPointF.

        Args:
            tuple(tuple|list): Tuple or list of two numbers.

        Returns:
            QPointF: The tuple converted to a QPointF.
        """
        if len(tuple) != 2:
            raise ValueError("Limits must be a tuple or list of two numbers.")
        min_val, max_val = tuple
        if not isinstance(min_val, (int, float)) or not isinstance(max_val, (int, float)):
            raise TypeError("Limits must be numbers.")
        if min_val > max_val:
            raise ValueError("Minimum limit cannot be greater than maximum limit.")
        return QPoint(*tuple)

    ################################################################################
    # X limits, has to be SaveProperty("QPointF") because of the tuple conversion for designer,
    # the python properties are used for CLI and API for context dialog settings.

    @SafeProperty("QPointF")
    def x_limits(self) -> QPointF:
        """
        Get the x limits of the plot.
        """
        current_lim = self.plot_item.vb.viewRange()[0]
        return QPointF(current_lim[0], current_lim[1])

    @x_limits.setter
    def x_limits(self, value):
        """
        Set the x limits of the plot.

        Args:
            value(QPointF|tuple|list): The x limits to set.
        """
        if isinstance(value, (tuple, list)):
            value = self._tuple_to_qpointf(value)
        self.plot_item.vb.setXRange(value.x(), value.y(), padding=0)

    @property
    def x_lim(self) -> tuple:
        """
        Get the x limits of the plot.
        """
        return (self.x_limits.x(), self.x_limits.y())

    @x_lim.setter
    def x_lim(self, value):
        """
        Set the x limits of the plot.

        Args:
            value(tuple): The x limits to set.
        """
        self.x_limits = value

    @property
    def x_min(self) -> float:
        """
        Get the minimum x limit of the plot.

        """
        return self.x_limits.x()

    @x_min.setter
    def x_min(self, value: float):
        """
        Set the minimum x limit of the plot.

        Args:
            value(float): The minimum x limit to set.
        """
        self.x_limits = (value, self.x_lim[1])

    @property
    def x_max(self) -> float:
        """
        Get the maximum x limit of the plot.
        """
        return self.x_limits.y()

    @x_max.setter
    def x_max(self, value: float):
        """
        Set the maximum x limit of the plot.

        Args:
            value(float): The maximum x limit to set.
        """
        self.x_limits = (self.x_lim[0], value)

    ################################################################################
    # Y limits, has to be SaveProperty("QPointF") because of the tuple conversion for designer,
    # the python properties are used for CLI and API for context dialog settings.

    @SafeProperty("QPointF")
    def y_limits(self) -> QPointF:
        """
        Get the y limits of the plot.
        """
        current_lim = self.plot_item.vb.viewRange()[1]
        return QPointF(current_lim[0], current_lim[1])

    @y_limits.setter
    def y_limits(self, value):
        """
        Set the y limits of the plot.

        Args:
            value(QPointF|tuple|list): The y limits to set.
        """
        if isinstance(value, (tuple, list)):
            value = self._tuple_to_qpointf(value)
        self.plot_item.vb.setYRange(value.x(), value.y(), padding=0)

    @property
    def y_lim(self) -> tuple:
        """
        Get the y limits of the plot.
        """
        return (self.y_limits.x(), self.y_limits.y())

    @y_lim.setter
    def y_lim(self, value):
        """
        Set the y limits of the plot.

        Args:
            value(tuple): The y limits to set.
        """
        self.y_limits = value

    @property
    def y_min(self) -> float:
        """
        Get the minimum y limit of the plot.
        """
        return self.y_limits.x()

    @y_min.setter
    def y_min(self, value: float):
        """
        Set the minimum y limit of the plot.

        Args:
            value(float): The minimum y limit to set.
        """
        self.y_limits = (value, self.y_lim[1])

    @property
    def y_max(self) -> float:
        """
        Get the maximum y limit of the plot.
        """
        return self.y_limits.y()

    @y_max.setter
    def y_max(self, value: float):
        """
        Set the maximum y limit of the plot.

        Args:
            value(float): The maximum y limit to set.
        """
        self.y_limits = (self.y_lim[0], value)

    @SafeProperty(bool, doc="Show grid on the x-axis.")
    def x_grid(self) -> bool:
        """
        Show grid on the x-axis.
        """
        return self.plot_item.ctrl.xGridCheck.isChecked()

    @x_grid.setter
    def x_grid(self, value: bool):
        """
        Show grid on the x-axis.

        Args:
            value(bool): The value to set.
        """
        self.plot_item.showGrid(x=value)
        self.property_changed.emit("x_grid", value)

    @SafeProperty(bool, doc="Show grid on the y-axis.")
    def y_grid(self) -> bool:
        """
        Show grid on the y-axis.
        """
        return self.plot_item.ctrl.yGridCheck.isChecked()

    @y_grid.setter
    def y_grid(self, value: bool):
        """
        Show grid on the y-axis.

        Args:
            value(bool): The value to set.
        """
        self.plot_item.showGrid(y=value)
        self.property_changed.emit("y_grid", value)

    @SafeProperty(bool, doc="Set X-axis to log scale if True, linear if False.")
    def x_log(self) -> bool:
        """
        Set X-axis to log scale if True, linear if False.
        """
        return bool(self.plot_item.vb.state.get("logMode", [False, False])[0])

    @x_log.setter
    def x_log(self, value: bool):
        """
        Set X-axis to log scale if True, linear if False.

        Args:
            value(bool): The value to set.
        """
        self.plot_item.setLogMode(x=value)
        self.property_changed.emit("x_log", value)

    @SafeProperty(bool, doc="Set Y-axis to log scale if True, linear if False.")
    def y_log(self) -> bool:
        """
        Set Y-axis to log scale if True, linear if False.
        """
        return bool(self.plot_item.vb.state.get("logMode", [False, False])[1])

    @y_log.setter
    def y_log(self, value: bool):
        """
        Set Y-axis to log scale if True, linear if False.

        Args:
            value(bool): The value to set.
        """
        self.plot_item.setLogMode(y=value)
        self.property_changed.emit("y_log", value)

    @SafeProperty(bool, doc="Show the outer axes of the plot widget.")
    def outer_axes(self) -> bool:
        """
        Show the outer axes of the plot widget.
        """
        return self.plot_item.getAxis("top").isVisible()

    @outer_axes.setter
    def outer_axes(self, value: bool):
        """
        Show the outer axes of the plot widget.

        Args:
            value(bool): The value to set.
        """
        self.plot_item.showAxis("top", value)
        self.plot_item.showAxis("right", value)
        self.property_changed.emit("outer_axes", value)

    @SafeProperty(bool, doc="Show inner axes of the plot widget.")
    def inner_axes(self) -> bool:
        """
        Show inner axes of the plot widget.
        """
        return self.plot_item.getAxis("bottom").isVisible()

    @inner_axes.setter
    def inner_axes(self, value: bool):
        """
        Show inner axes of the plot widget.

        Args:
            value(bool): The value to set.
        """
        self.plot_item.showAxis("bottom", value)
        self.plot_item.showAxis("left", value)
        self.property_changed.emit("inner_axes", value)

    @SafeProperty(bool, doc="Lock aspect ratio of the plot widget.")
    def lock_aspect_ratio(self) -> bool:
        """
        Lock aspect ratio of the plot widget.
        """
        return bool(self.plot_item.vb.getState()["aspectLocked"])

    @lock_aspect_ratio.setter
    def lock_aspect_ratio(self, value: bool):
        """
        Lock aspect ratio of the plot widget.

        Args:
            value(bool): The value to set.
        """
        self.plot_item.setAspectLocked(value)

    @SafeProperty(bool, doc="Set auto range for the x-axis.")
    def auto_range_x(self) -> bool:
        """
        Set auto range for the x-axis.
        """
        return bool(self.plot_item.vb.getState()["autoRange"][0])

    @auto_range_x.setter
    def auto_range_x(self, value: bool):
        """
        Set auto range for the x-axis.

        Args:
            value(bool): The value to set.
        """
        self.plot_item.enableAutoRange(x=value)

    @SafeProperty(bool, doc="Set auto range for the y-axis.")
    def auto_range_y(self) -> bool:
        """
        Set auto range for the y-axis.
        """
        return bool(self.plot_item.vb.getState()["autoRange"][1])

    @auto_range_y.setter
    def auto_range_y(self, value: bool):
        """
        Set auto range for the y-axis.

        Args:
            value(bool): The value to set.
        """
        self.plot_item.enableAutoRange(y=value)

    @SafeProperty(int, doc="The font size of the legend font.")
    def legend_label_size(self) -> int:
        """
        The font size of the legend font.
        """
        if not self.plot_item.legend:
            return
        scale = self.plot_item.legend.scale() * 9
        return scale

    @legend_label_size.setter
    def legend_label_size(self, value: int):
        """
        The font size of the legend font.

        Args:
            value(int): The font size to set.
        """
        if not self.plot_item.legend:
            return
        scale = (
            value / 9
        )  # 9 is the default font size of the legend, so we always scale it against 9
        self.plot_item.legend.setScale(scale)

    ################################################################################
    # FPS Counter
    ################################################################################

    def update_fps_label(self, fps: float) -> None:
        """
        Update the FPS label.

        Args:
            fps(float): The frames per second.
        """
        if self.fps_label:
            self.fps_label.setText(f"FPS: {fps:.2f}")

    def hook_fps_monitor(self):
        """Hook the FPS monitor to the plot."""
        if self.fps_monitor is None:
            self.fps_monitor = FPSCounter(self.plot_item.vb)
            self.fps_label.show()

            self.fps_monitor.sigFpsUpdate.connect(self.update_fps_label)
            self.update_fps_label(0)

    def unhook_fps_monitor(self, delete_label=True):
        """Unhook the FPS monitor from the plot."""
        if self.fps_monitor is not None and delete_label:
            # Remove Monitor
            self.fps_monitor.cleanup()
            self.fps_monitor.deleteLater()
            self.fps_monitor = None
        if self.fps_label is not None:
            # Hide Label
            self.fps_label.hide()

    ################################################################################
    # Crosshair
    ################################################################################

    def hook_crosshair(self) -> None:
        """Hook the crosshair to all plots."""
        if self.crosshair is None:
            self.crosshair = Crosshair(self.plot_item, precision=3)
            self.crosshair.crosshairChanged.connect(self.crosshair_position_changed)
            self.crosshair.crosshairClicked.connect(self.crosshair_position_clicked)
            self.crosshair.coordinatesChanged1D.connect(self.crosshair_coordinates_changed)
            self.crosshair.coordinatesClicked1D.connect(self.crosshair_coordinates_clicked)
            self.crosshair.coordinatesChanged2D.connect(self.crosshair_coordinates_changed)
            self.crosshair.coordinatesClicked2D.connect(self.crosshair_coordinates_clicked)

    def unhook_crosshair(self) -> None:
        """Unhook the crosshair from all plots."""
        if self.crosshair is not None:
            self.crosshair.crosshairChanged.disconnect(self.crosshair_position_changed)
            self.crosshair.crosshairClicked.disconnect(self.crosshair_position_clicked)
            self.crosshair.coordinatesChanged1D.disconnect(self.crosshair_coordinates_changed)
            self.crosshair.coordinatesClicked1D.disconnect(self.crosshair_coordinates_clicked)
            self.crosshair.coordinatesChanged2D.disconnect(self.crosshair_coordinates_changed)
            self.crosshair.coordinatesClicked2D.disconnect(self.crosshair_coordinates_clicked)
            self.crosshair.cleanup()
            self.crosshair.deleteLater()
            self.crosshair = None

    def toggle_crosshair(self) -> None:
        """Toggle the crosshair on all plots."""
        if self.crosshair is None:
            return self.hook_crosshair()

        self.unhook_crosshair()

    @SafeSlot()
    def reset(self) -> None:
        """Reset the plot widget."""
        if self.crosshair is not None:
            self.crosshair.clear_markers()
            self.crosshair.update_markers()

    def cleanup(self):
        self.unhook_crosshair()
        self.unhook_fps_monitor(delete_label=True)
        if self.axis_settings_dialog is not None:
            self.axis_settings_dialog.close()
            self.axis_settings_dialog = None
        self.cleanup_pyqtgraph()
        super().cleanup()

    def cleanup_pyqtgraph(self, item: pg.PlotItem | None = None):
        """Cleanup pyqtgraph items."""
        if item is None:
            item = self.plot_item
        item.vb.menu.close()
        item.vb.menu.deleteLater()
        item.ctrlMenu.close()
        item.ctrlMenu.deleteLater()


class DemoPlotBase(QMainWindow):  # pragma: no cover:
    def __init__(self):
        super().__init__()
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_widget.layout = QHBoxLayout(self.main_widget)

        self.plot_popup = PlotBase(popups=True)
        self.plot_popup.title = "PlotBase with popups"
        self.plot_side_panels = PlotBase(popups=False)
        self.plot_side_panels.title = "PlotBase with side panels"

        self.plot_popup.plot_item.plot(np.random.rand(100), pen=(255, 0, 0))
        self.plot_side_panels.plot_item.plot(np.random.rand(100), pen=(0, 255, 0))

        self.main_widget.layout.addWidget(self.plot_side_panels)
        self.main_widget.layout.addWidget(self.plot_popup)

        self.resize(1400, 600)


if __name__ == "__main__":  # pragma: no cover:
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = DemoPlotBase()
    window.show()

    sys.exit(app.exec_())
