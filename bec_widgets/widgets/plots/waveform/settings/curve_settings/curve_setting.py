from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.settings_dialog import SettingWidget
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox
from bec_widgets.widgets.plots.waveform.settings.curve_settings.curve_tree import CurveTree

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.plots.waveform.waveform import Waveform


class CurveSetting(SettingWidget):
    def __init__(self, parent=None, target_widget: Waveform = None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)
        self.setProperty("skip_settings", True)
        self.target_widget = target_widget
        self._x_settings_connected = False

        self.layout = QVBoxLayout(self)

        self._init_x_box()
        self._init_y_box()

    def sizeHint(self) -> QSize:
        """
        Returns the size hint for the settings widget.
        """
        return QSize(800, 500)

    def _init_x_box(self):
        self.x_axis_box = QGroupBox("X Axis")
        self.x_axis_box.layout = QHBoxLayout(self.x_axis_box)
        self.x_axis_box.layout.setContentsMargins(10, 10, 10, 10)
        self.x_axis_box.layout.setSpacing(10)

        self.mode_combo_label = QLabel("Mode")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["auto", "index", "timestamp", "device"])
        self.mode_combo.setMinimumWidth(120)

        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.device_x_label = QLabel("Device")
        self.device_x = DeviceComboBox(parent=self)
        self.device_x.insertItem(0, "")
        self.device_x.setEditable(True)
        self.device_x.setMinimumWidth(180)

        self.signal_x_label = QLabel("Signal")
        self.signal_x = SignalComboBox(parent=self)
        self.signal_x.include_config_signals = False
        self.signal_x.insertItem(0, "")
        self.signal_x.setEditable(True)
        self.signal_x.setMinimumWidth(180)

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
            self._x_settings_connected = True
            self.device_x.currentTextChanged.connect(self.signal_x.set_device)
            self.device_x.device_reset.connect(self.signal_x.reset_selection)

            self.device_x.setEnabled(True)
            self.signal_x.setEnabled(True)
            item = self.device_x.findText(self.target_widget.x_axis_mode["name"])
            self.device_x.setCurrentIndex(item if item != -1 else 0)
            signal_x = self.target_widget.x_axis_mode.get("entry", "")
            if signal_x:
                self.signal_x.set_to_obj_name(signal_x)
            else:
                # If no match is found, set to the first enabled item
                if not self.signal_x.set_to_first_enabled():
                    # If no enabled item is found, set to the first item
                    self.signal_x.setCurrentIndex(0)
        else:
            self.device_x.setEnabled(False)
            self.signal_x.setEnabled(False)
            self.device_x.setCurrentIndex(0)
            self.signal_x.setCurrentIndex(0)

            if self._x_settings_connected:
                self._x_settings_connected = False
                self.device_x.currentTextChanged.disconnect(self.signal_x.set_device)
                self.device_x.device_reset.disconnect(self.signal_x.reset_selection)

    def _init_y_box(self):
        self.y_axis_box = QGroupBox("Y Axis")
        self.y_axis_box.layout = QVBoxLayout(self.y_axis_box)
        self.y_axis_box.layout.setContentsMargins(0, 0, 0, 0)
        self.y_axis_box.layout.setSpacing(0)

        self.curve_manager = CurveTree(self, waveform=self.target_widget)
        self.y_axis_box.layout.addWidget(self.curve_manager)

        self.layout.addWidget(self.y_axis_box)

    @SafeSlot(popup_error=True)
    def accept_changes(self):
        """
        Accepts the changes made in the settings widget and applies them to the target widget.
        """
        if self.mode_combo.currentText() == "device":
            self.target_widget.x_mode = self.device_x.currentText()
            signal_x = self.signal_x.currentText()
            signal_data = self.signal_x.itemData(self.signal_x.currentIndex())
            if signal_x != "":
                self.target_widget.x_entry = signal_data.get("obj_name", signal_x)
        else:
            self.target_widget.x_mode = self.mode_combo.currentText()
        self.curve_manager.send_curve_json()

    @SafeSlot()
    def refresh(self):
        """Refresh the curve tree and the x axis combo box in the case Waveform is modified from rpc."""
        self.curve_manager.refresh_from_waveform()
        self._get_x_mode_from_waveform()

    def cleanup(self):
        """Cleanup the widget."""
        self.device_x.close()
        self.device_x.deleteLater()
        self.signal_x.close()
        self.signal_x.deleteLater()
        self.curve_manager.close()
        self.curve_manager.deleteLater()
