import os

from qtpy.QtWidgets import QVBoxLayout

from bec_widgets.qt_utils.error_popups import SafeSlot as Slot
from bec_widgets.qt_utils.settings_dialog import SettingWidget
from bec_widgets.utils import UILoader
from bec_widgets.utils.widget_io import WidgetIO


class MotorMapSettings(SettingWidget):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        current_path = os.path.dirname(__file__)

        self.ui = UILoader(self).loader(os.path.join(current_path, "motor_map_settings.ui"))

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
        color = self.ui.color.get_color("RGBA")

        if self.target_widget is not None:
            self.target_widget.set_max_points(max_points)
            self.target_widget.set_num_dim_points(num_dim_points)
            self.target_widget.set_precision(precision)
            self.target_widget.set_scatter_size(scatter_size)
            self.target_widget.set_background_value(background_intensity)
            self.target_widget.set_color(color)
