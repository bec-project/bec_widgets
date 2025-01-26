from __future__ import annotations

import pyqtgraph as pg
from bec_lib import bec_logger
from qtpy.QtCore import QPoint, QPointF, Qt, Signal
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.qt_utils.round_frame import RoundedFrame
from bec_widgets.qt_utils.side_panel import SidePanel
from bec_widgets.qt_utils.toolbar import MaterialIconAction, ModularToolBar, SeparatorAction
from bec_widgets.utils import ConnectionConfig, Crosshair, EntryValidator
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import set_theme
from bec_widgets.utils.fps_counter import FPSCounter
from bec_widgets.utils.widget_state_manager import WidgetStateManager
from bec_widgets.widgets.containers.layout_manager.layout_manager import LayoutManagerWidget
from bec_widgets.widgets.plots_next_gen.setting_menus.axis_settings import AxisSettings
from bec_widgets.widgets.plots_next_gen.toolbar_bundles.mouse_interactions import (
    MouseInteractionToolbarBundle,
)
from bec_widgets.widgets.plots_next_gen.toolbar_bundles.plot_export import PlotExportBundle
from bec_widgets.widgets.plots_next_gen.toolbar_bundles.roi_bundle import ROIBundle
from bec_widgets.widgets.plots_next_gen.toolbar_bundles.save_state import SaveStateBundle
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

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
    ) -> None:
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(client=client, gui_id=gui_id, config=config)
        QWidget.__init__(self, parent=parent)

        # For PropertyManager identification
        self.setObjectName("PlotBase")
        self.get_bec_shortcuts()

        # Layout Management
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout_manager = LayoutManagerWidget(parent=self)

        # Property Manager
        self.state_manager = WidgetStateManager(self)

        # Entry Validator
        self.entry_validator = EntryValidator(self.dev)

        # Base widgets elements
        self.plot_item = pg.PlotItem(viewBox=BECViewBox(enableMenu=True))
        self.plot_widget = pg.PlotWidget(plotItem=self.plot_item)
        self.side_panel = SidePanel(self, orientation="left", panel_max_width=280)
        self.toolbar = ModularToolBar(target_widget=self, orientation="horizontal")
        self.init_toolbar()

        # PlotItem Addons
        self.plot_item.addLegend()
        self.crosshair = None
        self.fps_monitor = None
        self.fps_label = QLabel(alignment=Qt.AlignmentFlag.AlignRight)

        self._init_ui()

    def _init_ui(self):
        self.layout.addWidget(self.layout_manager)
        self.round_plot_widget = RoundedFrame(content_widget=self.plot_widget, theme_update=True)
        self.round_plot_widget.apply_theme("dark")

        self.layout_manager.add_widget(self.round_plot_widget)
        self.layout_manager.add_widget_relative(self.fps_label, self.round_plot_widget, "top")
        self.fps_label.hide()
        self.layout_manager.add_widget_relative(self.side_panel, self.round_plot_widget, "left")
        self.layout_manager.add_widget_relative(self.toolbar, self.fps_label, "top")

        self.add_side_menus()

        # PlotItem ViewBox Signals
        self.plot_item.vb.sigStateChanged.connect(self.viewbox_state_changed)

    def init_toolbar(self):

        self.plot_export_bundle = PlotExportBundle("plot_export", target_widget=self)
        self.mouse_bundle = MouseInteractionToolbarBundle("mouse_interaction", target_widget=self)
        self.state_export_bundle = SaveStateBundle("state_export", target_widget=self)
        self.roi_bundle = ROIBundle("roi", target_widget=self)

        # Add elements to toolbar
        self.toolbar.add_bundle(self.plot_export_bundle, target_widget=self)
        self.toolbar.add_bundle(self.state_export_bundle, target_widget=self)
        self.toolbar.add_bundle(self.mouse_bundle, target_widget=self)
        self.toolbar.add_bundle(self.roi_bundle, target_widget=self)

        self.toolbar.add_action("separator_1", SeparatorAction(), target_widget=self)
        self.toolbar.add_action(
            "fps_monitor",
            MaterialIconAction(icon_name="speed", tooltip="Show FPS Monitor", checkable=True),
            target_widget=self,
        )
        self.toolbar.addWidget(DarkModeButton(toolbar=True))

        self.toolbar.widgets["fps_monitor"].action.toggled.connect(
            lambda checked: setattr(self, "enable_fps_monitor", checked)
        )

    def add_side_menus(self):
        """Adds multiple menus to the side panel."""
        # Setting Axis Widget
        axis_setting = AxisSettings(target_widget=self)
        self.side_panel.add_menu(
            action_id="axis",
            icon_name="settings",
            tooltip="Show Axis Settings",
            widget=axis_setting,
            title="Axis Settings",
        )

    ################################################################################
    # Toggle UI Elements
    ################################################################################

    @SafeProperty(bool, doc="Show Toolbar")
    def enable_toolbar(self) -> bool:
        return self.toolbar.isVisible()

    @enable_toolbar.setter
    def enable_toolbar(self, value: bool):
        self.toolbar.setVisible(value)

    @SafeProperty(bool, doc="Show Side Panel")
    def enable_side_panel(self) -> bool:
        return self.side_panel.isVisible()

    @enable_side_panel.setter
    def enable_side_panel(self, value: bool):
        self.side_panel.setVisible(value)

    @SafeProperty(bool, doc="Enable the FPS monitor.")
    def enable_fps_monitor(self) -> bool:
        return self.fps_label.isVisible()

    @enable_fps_monitor.setter
    def enable_fps_monitor(self, value: bool):
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
        return self.plot_item.titleLabel.text

    @title.setter
    def title(self, value: str):
        self.plot_item.setTitle(value)
        self.property_changed.emit("title", value)

    @SafeProperty(str, doc="The text of the x label")
    def x_label(self) -> str:
        return self.plot_item.getAxis("bottom").labelText

    @x_label.setter
    def x_label(self, value: str):
        self.plot_item.setLabel("bottom", text=value)
        self.property_changed.emit("x_label", value)

    @SafeProperty(str, doc="The text of the y label")
    def y_label(self) -> str:
        return self.plot_item.getAxis("left").labelText

    @y_label.setter
    def y_label(self, value: str):
        self.plot_item.setLabel("left", text=value)
        self.property_changed.emit("y_label", value)

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
        current_lim = self.plot_item.vb.viewRange()[0]
        return QPointF(current_lim[0], current_lim[1])

    @x_limits.setter
    def x_limits(self, value):
        if isinstance(value, (tuple, list)):
            value = self._tuple_to_qpointf(value)
        self.plot_item.vb.setXRange(value.x(), value.y(), padding=0)

    @property
    def x_lim(self) -> tuple:
        return (self.x_limits.x(), self.x_limits.y())

    @x_lim.setter
    def x_lim(self, value):
        self.x_limits = value

    @property
    def x_min(self) -> float:
        return self.x_limits.x()

    @x_min.setter
    def x_min(self, value: float):
        self.x_limits = (value, self.x_lim[1])

    @property
    def x_max(self) -> float:
        return self.x_limits.y()

    @x_max.setter
    def x_max(self, value: float):
        self.x_limits = (self.x_lim[0], value)

    ################################################################################
    # Y limits, has to be SaveProperty("QPointF") because of the tuple conversion for designer,
    # the python properties are used for CLI and API for context dialog settings.

    @SafeProperty("QPointF")
    def y_limits(self) -> QPointF:
        current_lim = self.plot_item.vb.viewRange()[1]
        return QPointF(current_lim[0], current_lim[1])

    @y_limits.setter
    def y_limits(self, value):
        if isinstance(value, (tuple, list)):
            value = self._tuple_to_qpointf(value)
        self.plot_item.vb.setYRange(value.x(), value.y(), padding=0)

    @property
    def y_lim(self) -> tuple:
        return (self.y_limits.x(), self.y_limits.y())

    @y_lim.setter
    def y_lim(self, value):
        self.y_limits = value

    @property
    def y_min(self) -> float:
        return self.y_limits.x()

    @y_min.setter
    def y_min(self, value: float):
        self.y_limits = (value, self.y_lim[1])

    @property
    def y_max(self) -> float:
        return self.y_limits.y()

    @y_max.setter
    def y_max(self, value: float):
        self.y_limits = (self.y_lim[0], value)

    @SafeProperty(bool, doc="Show grid on the x-axis.")
    def x_grid(self) -> bool:
        return self.plot_item.ctrl.xGridCheck.isChecked()

    @x_grid.setter
    def x_grid(self, value: bool):
        self.plot_item.showGrid(x=value)
        self.property_changed.emit("x_grid", value)

    @SafeProperty(bool, doc="Show grid on the y-axis.")
    def y_grid(self) -> bool:
        return self.plot_item.ctrl.yGridCheck.isChecked()

    @y_grid.setter
    def y_grid(self, value: bool):
        self.plot_item.showGrid(y=value)
        self.property_changed.emit("y_grid", value)

    @SafeProperty(bool, doc="Set X-axis to log scale if True, linear if False.")
    def x_log(self) -> bool:
        return bool(self.plot_item.vb.state.get("logMode", [False, False])[0])

    @x_log.setter
    def x_log(self, value: bool):
        self.plot_item.setLogMode(x=value)
        self.property_changed.emit("x_log", value)

    @SafeProperty(bool, doc="Set Y-axis to log scale if True, linear if False.")
    def y_log(self) -> bool:
        return bool(self.plot_item.vb.state.get("logMode", [False, False])[1])

    @y_log.setter
    def y_log(self, value: bool):
        self.plot_item.setLogMode(y=value)
        self.property_changed.emit("y_log", value)

    @SafeProperty(bool, doc="Show the outer axes of the plot widget.")
    def outer_axes(self) -> bool:
        return self.plot_item.getAxis("top").isVisible()

    @outer_axes.setter
    def outer_axes(self, value: bool):
        self.plot_item.showAxis("top", value)
        self.plot_item.showAxis("right", value)
        self.property_changed.emit("outer_axes", value)

    @SafeProperty(bool, doc="Show inner axes of the plot widget.")
    def inner_axes(self) -> bool:
        return self.plot_item.getAxis("bottom").isVisible()

    @inner_axes.setter
    def inner_axes(self, value: bool):
        self.plot_item.showAxis("bottom", value)
        self.plot_item.showAxis("left", value)
        self.property_changed.emit("inner_axes", value)

    @SafeProperty(bool, doc="Lock aspect ratio of the plot widget.")
    def lock_aspect_ratio(self) -> bool:
        return bool(self.plot_item.vb.getState()["aspectLocked"])

    @lock_aspect_ratio.setter
    def lock_aspect_ratio(self, value: bool):
        self.plot_item.setAspectLocked(value)

    @SafeProperty(bool, doc="Set auto range for the x-axis.")
    def auto_range_x(self) -> bool:
        return bool(self.plot_item.vb.getState()["autoRange"][0])

    @auto_range_x.setter
    def auto_range_x(self, value: bool):
        self.plot_item.enableAutoRange(x=value)

    @SafeProperty(bool, doc="Set auto range for the y-axis.")
    def auto_range_y(self) -> bool:
        return bool(self.plot_item.vb.getState()["autoRange"][1])

    @auto_range_y.setter
    def auto_range_y(self, value: bool):
        self.plot_item.enableAutoRange(y=value)

    @SafeProperty(int, doc="The font size of the legend font.")
    def legend_label_size(self) -> int:
        if not self.plot_item.legend:
            return
        scale = self.plot_item.legend.scale() * 9
        return scale

    @legend_label_size.setter
    def legend_label_size(self, value: int):
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
        self.cleanup_pyqtgraph()

    def cleanup_pyqtgraph(self):
        """Cleanup pyqtgraph items."""
        item = self.plot_item
        item.vb.menu.close()
        item.vb.menu.deleteLater()
        item.ctrlMenu.close()
        item.ctrlMenu.deleteLater()


if __name__ == "__main__":  # pragma: no cover:
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    set_theme("dark")
    widget = PlotBase()
    widget.show()
    # Just some example data and parameters to test
    widget.y_grid = True
    widget.plot_item.plot([1, 2, 3, 4, 5], [1, 2, 3, 4, 5])

    sys.exit(app.exec_())
