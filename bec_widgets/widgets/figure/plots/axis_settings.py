import os

import qdarktheme
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils import UILoader
from bec_widgets.utils.widget_io import WidgetIO


class AxisSettings(QWidget):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        current_path = os.path.dirname(__file__)
        self.ui = UILoader().load_ui(os.path.join(current_path, "axis_settings.ui"), self)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)

        # Hardcoded values for best appearance
        self.setMinimumHeight(280)
        self.setMaximumHeight(280)
        self.resize(380, 280)

    @Slot(dict)
    def display_current_settings(self, axis_config: dict):
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


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    qdarktheme.setup_theme("dark")
    window = AxisSettings()
    window.show()
    sys.exit(app.exec_())
