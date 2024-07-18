from __future__ import annotations

import os

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QLineEdit, QPushButton, QSpinBox, QTableWidget
from pydantic import BaseModel
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QVBoxLayout

from bec_widgets.qt_utils.settings_dialog import SettingWidget
from bec_widgets.utils import UILoader, Colors
from bec_widgets.widgets.color_button.color_button import ColorButton
from bec_widgets.widgets.device_line_edit.device_line_edit import DeviceLineEdit
from bec_widgets.widgets.figure.plots.plot_base import AxisConfig

from bec_widgets.widgets.figure.plots.waveform.waveform_curve import CurveConfig


class CurveSettings(SettingWidget):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        current_path = os.path.dirname(__file__)

        self.ui = UILoader(self).loader(os.path.join(current_path, "curve_dialog.ui"))

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)

        self.ui.add_curve.clicked.connect(self.add_curve)
        self.ui.x_mode.currentIndexChanged.connect(self.set_x_mode)
        self.ui.normalize_colors.clicked.connect(self.change_colormap)

    @Slot(dict)
    def display_current_settings(self, config: dict | BaseModel):
        curves = config["scan_segment"]

        # set mode of x axis box
        x_name = self.target_widget.waveform._x_axis_mode["name"]
        x_entry = self.target_widget.waveform._x_axis_mode["entry"]
        self._setup_x_box(x_name, x_entry)
        cm = self.target_widget.config.color_palette
        self.ui.color_map_selector.combo.setCurrentText(cm)

        for label, curve in curves.items():
            row_count = self.ui.scan_table.rowCount()
            self.ui.scan_table.insertRow(row_count)
            ScanRow(table_widget=self.ui.scan_table, row=row_count, config=curve.config)

    def _setup_x_box(self, name, entry):
        if name in ["index", "timestamp", "best_effort"]:
            self.ui.x_mode.setCurrentText(name)
            self.set_x_mode()
        else:
            self.ui.x_mode.setCurrentText("device")
            self.set_x_mode()
            self.ui.x_name.setText(name)
            self.ui.x_entry.setText(entry)

    @Slot()
    def set_x_mode(self):
        x_mode = self.ui.x_mode.currentText()
        if x_mode in ["index", "timestamp", "best_effort"]:
            self.ui.x_name.setEnabled(False)
            self.ui.x_entry.setEnabled(False)
        else:
            self.ui.x_name.setEnabled(True)
            self.ui.x_entry.setEnabled(True)

    @Slot()
    def change_colormap(self):
        cm = self.ui.color_map_selector.combo.currentText()
        rows = self.ui.scan_table.rowCount()
        colors = Colors.golden_angle_color(colormap=cm, num=rows + 1, format="HEX")
        for row, color in zip(range(rows), colors):
            self.ui.scan_table.cellWidget(row, 2).setColor(color)
        self.target_widget.set_colormap(cm)

    @Slot()
    def accept_changes(self):
        self.accept_scan_curve_changes()

    def accept_scan_curve_changes(self):
        old_curves = list(self.target_widget.waveform._curves_data["scan_segment"].values())
        for curve in old_curves:
            curve.remove()
        self.get_curve_params()

    def get_curve_params(self):
        x_mode = self.ui.x_mode.currentText()

        if x_mode in ["index", "timestamp", "best_effort"]:
            x_name = x_mode
            x_entry = x_mode
        else:
            x_name = self.ui.x_name.text()
            x_entry = self.ui.x_entry.text()

        self.target_widget.set_x(x_name=x_name, x_entry=x_entry)

        for row in range(self.ui.scan_table.rowCount()):
            y_name = self.ui.scan_table.cellWidget(row, 0).text()
            y_entry = self.ui.scan_table.cellWidget(row, 1).text()
            color = self.ui.scan_table.cellWidget(row, 2).get_color()
            style = self.ui.scan_table.cellWidget(row, 3).currentText()
            width = self.ui.scan_table.cellWidget(row, 4).value()
            symbol_size = self.ui.scan_table.cellWidget(row, 5).value()
            self.target_widget.plot(
                y_name=y_name,
                y_entry=y_entry,
                color=color,
                pen_style=style,
                pen_width=width,
                symbol_size=symbol_size,
            )
        self.target_widget.scan_history(-1)

    def add_curve(self):
        row_count = self.ui.scan_table.rowCount()
        self.ui.scan_table.insertRow(row_count)
        ScanRow(table_widget=self.ui.scan_table, row=row_count, config=None)


class ScanRow(QObject):
    def __init__(
        self,
        parent=None,
        table_widget: QTableWidget = None,
        row=None,
        config: dict | CurveConfig = None,
    ):
        super().__init__(parent=parent)

        current_path = os.path.dirname(__file__)
        # Remove Button
        icon_path = os.path.join(current_path, "remove.svg")
        self.remove_button = QPushButton()
        self.remove_button.setIcon(QIcon(icon_path))

        # Name and Entry
        self.device_line_edit = DeviceLineEdit()
        self.entry_line_edit = QLineEdit()

        # Styling
        default_color = Colors.golden_angle_color(colormap="magma", num=row + 1, format="HEX")[-1]
        self.color_button = ColorButton()
        self.color_button.setColor(default_color)
        self.style_combo = StyleComboBox()
        self.width = QSpinBox()
        self.width.setMinimum(1)
        self.width.setMaximum(20)
        self.width.setValue(2)

        self.symbol_size = QSpinBox()
        self.symbol_size.setMinimum(1)
        self.symbol_size.setMaximum(20)
        self.symbol_size.setValue(5)

        self.table_widget = table_widget
        self.row = row

        self.remove_button.clicked.connect(
            lambda: self.remove_row()
        )  # From some reason do not work without lambda

        if config is not None:
            self.fill_row_from_config(config)

        self.add_row_to_table()

    def fill_row_from_config(self, config):
        self.device_line_edit.setText(config.signals.y.name)
        self.entry_line_edit.setText(config.signals.y.entry)
        self.color_button.setColor(config.color)
        self.style_combo.setCurrentText(config.pen_style)
        self.width.setValue(config.pen_width)
        self.symbol_size.setValue(config.symbol_size)

    def add_row_to_table(self):
        self.table_widget.setCellWidget(self.row, 0, self.device_line_edit)
        self.table_widget.setCellWidget(self.row, 1, self.entry_line_edit)
        self.table_widget.setCellWidget(self.row, 2, self.color_button)
        self.table_widget.setCellWidget(self.row, 3, self.style_combo)
        self.table_widget.setCellWidget(self.row, 4, self.width)
        self.table_widget.setCellWidget(self.row, 5, self.symbol_size)
        self.table_widget.setCellWidget(self.row, 6, self.remove_button)

    @Slot()
    def remove_row(self):
        row = self.table_widget.indexAt(self.remove_button.pos()).row()
        self.cleanup()
        self.table_widget.removeRow(row)

    def cleanup(self):
        self.device_line_edit.cleanup()


class StyleComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems(["solid", "dash", "dot", "dashdot"])
