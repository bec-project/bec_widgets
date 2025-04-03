from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.settings_dialog import SettingWidget
from bec_widgets.widgets.control.device_input.device_line_edit.device_line_edit import (
    DeviceLineEdit,
)
from bec_widgets.widgets.plots.waveform.settings.curve_settings.curve_tree import CurveTree

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.plots.waveform.waveform import Waveform


class CurveSetting(SettingWidget):
    def __init__(self, parent=None, target_widget: Waveform = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)
        self.setProperty("skip_settings", True)
        self.setObjectName("CurveSetting")
        self.target_widget = target_widget

        self.layout = QVBoxLayout(self)

        self._init_x_box()
        self._init_y_box()

        self.setFixedWidth(580)  # TODO height is still debate

    def _init_x_box(self):
        self.x_axis_box = QGroupBox("X Axis")
        self.x_axis_box.layout = QHBoxLayout(self.x_axis_box)
        self.x_axis_box.layout.setContentsMargins(10, 10, 10, 10)
        self.x_axis_box.layout.setSpacing(10)

        self.mode_combo_label = QLabel("Mode")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["auto", "index", "timestamp", "device"])

        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.device_x_label = QLabel("Device")
        self.device_x = DeviceLineEdit()

        self.signal_x_label = QLabel("Signal")
        self.signal_x = QLineEdit()

        self._get_x_mode_from_waveform()
        self.switch_x_device_selection()

        self.mode_combo.currentTextChanged.connect(self.switch_x_device_selection)

        self.x_axis_box.layout.addWidget(self.mode_combo_label)
        self.x_axis_box.layout.addWidget(self.mode_combo)
        self.x_axis_box.layout.addWidget(self.spacer)
        self.x_axis_box.layout.addWidget(self.device_x_label)
        self.x_axis_box.layout.addWidget(self.device_x)
        self.x_axis_box.layout.addWidget(self.signal_x_label)
        self.x_axis_box.layout.addWidget(self.signal_x)

        self.x_axis_box.setFixedHeight(80)
        self.layout.addWidget(self.x_axis_box)

    def _get_x_mode_from_waveform(self):
        if self.target_widget.x_mode in ["auto", "index", "timestamp"]:
            self.mode_combo.setCurrentText(self.target_widget.x_mode)
        else:
            self.mode_combo.setCurrentText("device")

    def switch_x_device_selection(self):
        if self.mode_combo.currentText() == "device":
            self.device_x.setEnabled(True)
            self.device_x.setText(self.target_widget.x_axis_mode["name"])
            self.signal_x.setText(self.target_widget.x_axis_mode["entry"])
        else:
            self.device_x.setEnabled(False)

    def _init_y_box(self):
        self.y_axis_box = QGroupBox("Y Axis")
        self.y_axis_box.layout = QVBoxLayout(self.y_axis_box)
        self.y_axis_box.layout.setContentsMargins(0, 0, 0, 0)
        self.y_axis_box.layout.setSpacing(0)

        self.curve_manager = CurveTree(self, waveform=self.target_widget)
        self.y_axis_box.layout.addWidget(self.curve_manager)

        self.layout.addWidget(self.y_axis_box)

    @SafeSlot()
    def accept_changes(self):
        """
        Accepts the changes made in the settings widget and applies them to the target widget.
        """
        if self.mode_combo.currentText() == "device":
            self.target_widget.x_mode = self.device_x.text()
            signal_x = self.signal_x.text()
            if signal_x != "":
                self.target_widget.x_entry = signal_x
        else:
            self.target_widget.x_mode = self.mode_combo.currentText()
        self.curve_manager.send_curve_json()

    @SafeSlot()
    def refresh(self):
        """Refresh the curve tree and the x axis combo box in the case Waveform is modified from rpc."""
        self.curve_manager.refresh_from_waveform()
        self._get_x_mode_from_waveform()
