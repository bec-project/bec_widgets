import os

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

from bec_widgets.utils import UILoader
from bec_widgets.utils.widget_io import WidgetIO


class MotorMapSettings(QWidget):
    def __init__(self, parent=None, target_widget: QWidget = None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        current_path = os.path.dirname(__file__)

        self.ui = UILoader(self).loader(os.path.join(current_path, "motor_map_settings.ui"))
        self.target_widget = target_widget

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)

    @Slot(dict)
    def display_current_settings(self, config: dict):
        WidgetIO.set_value(self.ui.max_points, config["max_points"])
        WidgetIO.set_value(self.ui.trace_dim, config["num_dim_points"])
        WidgetIO.set_value(self.ui.precision, config["precision"])
        WidgetIO.set_value(self.ui.scatter_size, config["scatter_size"])
        background_intensity = int((config["background_value"] / 255) * 100)
        WidgetIO.set_value(self.ui.background_value, background_intensity)
        color = config["color"]
        self.ui.color.setColor(color)

    @Slot()
    def accept_changes(self):
        max_points = WidgetIO.get_value(self.ui.max_points)
        num_dim_points = WidgetIO.get_value(self.ui.trace_dim)
        precision = WidgetIO.get_value(self.ui.precision)
        scatter_size = WidgetIO.get_value(self.ui.scatter_size)
        background_intensity = int(WidgetIO.get_value(self.ui.background_value) * 0.01 * 255)
        color = self.ui.color.color().toTuple()

        if self.target_widget is not None:
            self.target_widget.set_max_points(max_points)
            self.target_widget.set_num_dim_points(num_dim_points)
            self.target_widget.set_precision(precision)
            self.target_widget.set_scatter_size(scatter_size)
            self.target_widget.set_background_value(background_intensity)
            self.target_widget.set_color(color)


class MotorMapDialog(QDialog):
    def __init__(self, parent=None, target_widget: QWidget = None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.setModal(False)

        self.setWindowTitle("Motor Map Settings")

        self.target_widget = target_widget
        self.widget = MotorMapSettings(target_widget=self.target_widget)
        self.widget.display_current_settings(self.target_widget._config_dict)
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
