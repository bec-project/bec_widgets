import os

from bec_qthemes import material_icon
from pyqtgraph import ColorMapWidget
from PySide6.QtWidgets import QComboBox, QPushButton, QVBoxLayout, QWidget

from bec_widgets.utils import UILoader
from bec_widgets.widgets.containers.expantion_panel.expansion_panel import ExpansionPanel
from bec_widgets.widgets.control.device_input.device_line_edit.device_line_edit import (
    DeviceLineEdit,
)
from bec_widgets.widgets.control.device_input.signal_line_edit.signal_line_edit import (
    SignalLineEdit,
)


class CurveSettingWidget(QWidget):
    """
        Widget that lets a user set up curves for the Waveform widget.
    It allows:
      - Selecting color palette for the entire widget
      - Choosing x-axis mode
      - Selecting device and signal
      - Adding a new curve
      - Viewing existing curves in a QTreeWidget
    """

    def __init__(self, parent=None, target_widget=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.setObjectName("CurveSettings")
        self.current_path = os.path.dirname(__file__)
        self.main_setting_ui = UILoader().load_ui(
            os.path.join(self.current_path, "main_settings.ui"), self
        )

        self.target_widget = target_widget

        self.layout = QVBoxLayout(self)
        # self.layout.addWidget(self.ui)

        self.main_setting = ExpansionPanel(title="Main Settings", expanded=True)
        self.curve_setting_1 = ExpansionPanel(title="Curve 1", expanded=False)
        self.curve_setting_2 = ExpansionPanel(title="Curve 2", expanded=False)
        self.curve_setting_3 = ExpansionPanel(title="Curve 3", expanded=False)

        self.layout.addWidget(self.main_setting)
        for cs in [self.curve_setting_1, self.curve_setting_2, self.curve_setting_3]:
            self.layout.addWidget(cs)
            self._init_curve(cs)
        self._init_main_settings()
        # add spacer
        self.layout.addStretch()

    def _init_main_settings(self):
        self.main_setting.content_layout.addWidget(self.main_setting_ui)

    def _init_curve(self, curve_setting):
        icon = material_icon("delete", color=(255, 0, 0, 255))
        delete_button = QPushButton()
        delete_button.setIcon(icon)
        curve_ui = UILoader().load_ui(os.path.join(self.current_path, "curve_3.ui"), self)
        curve_setting.header_layout.addWidget(delete_button)
        curve_setting.content_layout.addWidget(curve_ui)


if __name__ == "__main__":
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = CurveSettingWidget()
    widget.show()
    sys.exit(app.exec_())
