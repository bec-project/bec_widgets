import os

from PySide6.QtWidgets import QDialog, QDialogButtonBox
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils import UILoader
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.widget_io import WidgetIO


class AxisSettings(QWidget):
    def __init__(self, parent=None, target_widget: QWidget = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        current_path = os.path.dirname(__file__)
        self.ui = UILoader().load_ui(os.path.join(current_path, "axis_settings.ui"), self)
        self.target_widget = target_widget

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)

        # Hardcoded values for best appearance
        self.setMinimumHeight(280)
        self.setMaximumHeight(280)
        self.resize(380, 280)

        self.display_current_settings(self.target_widget._config_dict.get("axis", {}))

    @Slot(dict)
    def display_current_settings(self, axis_config: dict):

        if dict == {}:
            return

        # Top Box
        WidgetIO.set_value(self.ui.plot_title, axis_config["title"])

        # X Axis Box
        WidgetIO.set_value(self.ui.x_label, axis_config["x_label"])
        WidgetIO.set_value(self.ui.x_scale, axis_config["x_scale"])
        WidgetIO.set_value(self.ui.x_grid, axis_config["x_grid"])
        if axis_config["x_lim"] is not None:
            WidgetIO.check_and_adjust_limits(self.ui.x_min, axis_config["x_lim"][0])
            WidgetIO.check_and_adjust_limits(self.ui.x_max, axis_config["x_lim"][1])
            WidgetIO.set_value(self.ui.x_min, axis_config["x_lim"][0])
            WidgetIO.set_value(self.ui.x_max, axis_config["x_lim"][1])

        # Y Axis Box
        WidgetIO.set_value(self.ui.y_label, axis_config["y_label"])
        WidgetIO.set_value(self.ui.y_scale, axis_config["y_scale"])
        WidgetIO.set_value(self.ui.y_grid, axis_config["y_grid"])
        if axis_config["y_lim"] is not None:
            WidgetIO.check_and_adjust_limits(self.ui.y_min, axis_config["y_lim"][0])
            WidgetIO.check_and_adjust_limits(self.ui.y_max, axis_config["y_lim"][1])
            WidgetIO.set_value(self.ui.y_min, axis_config["y_lim"][0])
            WidgetIO.set_value(self.ui.y_max, axis_config["y_lim"][1])

    @Slot()
    def accept_changes(self):
        title = WidgetIO.get_value(self.ui.plot_title)

        # X Axis
        x_label = WidgetIO.get_value(self.ui.x_label)
        x_scale = self.ui.x_scale.currentText()
        x_grid = WidgetIO.get_value(self.ui.x_grid)
        x_lim = (WidgetIO.get_value(self.ui.x_min), WidgetIO.get_value(self.ui.x_max))

        # Y Axis
        y_label = WidgetIO.get_value(self.ui.y_label)
        y_scale = self.ui.y_scale.currentText()
        y_grid = WidgetIO.get_value(self.ui.y_grid)
        y_lim = (WidgetIO.get_value(self.ui.y_min), WidgetIO.get_value(self.ui.y_max))

        self.target_widget.set(
            title=title,
            x_label=x_label,
            x_scale=x_scale,
            x_lim=x_lim,
            y_label=y_label,
            y_scale=y_scale,
            y_lim=y_lim,
        )
        self.target_widget.set_grid(x_grid, y_grid)


class AxisSettingsDialog(QDialog):
    def __init__(self, parent=None, target_widget: QWidget = None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.setModal(False)

        self.setWindowTitle("Axis Settings")
        self.target_widget = target_widget
        self.widget = AxisSettings(target_widget=self.target_widget)
        # self.widget.display_current_settings(self.target_widget._config_dict)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.widget)
        self.layout.addWidget(self.button_box)

    @Slot()
    def accept(self):
        self.widget.accept_changes()
        super().accept()
