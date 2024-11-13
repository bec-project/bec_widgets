from __future__ import annotations

import os
from typing import Literal

from bec_qthemes import material_icon
from pydantic import BaseModel
from qtpy.QtCore import QObject, Slot
from qtpy.QtWidgets import QComboBox, QLineEdit, QPushButton, QSpinBox, QTableWidget, QVBoxLayout

import bec_widgets
from bec_widgets.qt_utils.error_popups import WarningPopupUtility
from bec_widgets.qt_utils.settings_dialog import SettingWidget
from bec_widgets.utils import Colors, UILoader
from bec_widgets.widgets.control.device_input.device_line_edit.device_line_edit import (
    DeviceLineEdit,
)
from bec_widgets.widgets.dap.dap_combo_box.dap_combo_box import DapComboBox
from bec_widgets.widgets.utility.visual.color_button.color_button import ColorButton

MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class CurveSettings(SettingWidget):
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        current_path = os.path.dirname(__file__)

        self.ui = UILoader(self).loader(os.path.join(current_path, "curve_dialog.ui"))
        self._setup_icons()

        self.warning_util = WarningPopupUtility(self)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)

        self.ui.add_curve.clicked.connect(self.add_curve)
        self.ui.add_dap.clicked.connect(self.add_dap)
        self.ui.x_mode.currentIndexChanged.connect(self.set_x_mode)
        self.ui.normalize_colors_scan.clicked.connect(lambda: self.change_colormap("scan"))
        self.ui.normalize_colors_dap.clicked.connect(lambda: self.change_colormap("dap"))

    def _setup_icons(self):
        add_icon = material_icon(icon_name="add", size=(20, 20), convert_to_pixmap=False)
        self.ui.add_dap.setIcon(add_icon)
        self.ui.add_dap.setToolTip("Add DAP Curve")
        self.ui.add_curve.setIcon(add_icon)
        self.ui.add_curve.setToolTip("Add Scan Curve")

    @Slot(dict)
    def display_current_settings(self, config: dict | BaseModel):

        # What elements should be enabled
        x_name = self.target_widget.waveform._x_axis_mode["name"]
        x_entry = self.target_widget.waveform._x_axis_mode["entry"]
        self._enable_ui_elements(x_name, x_entry)
        cm = self.target_widget.config.color_palette
        self.ui.color_map_selector_scan.colormap = cm

        # Scan Curve Table
        for source in ["scan_segment", "async"]:
            for label, curve in config[source].items():
                row_count = self.ui.scan_table.rowCount()
                self.ui.scan_table.insertRow(row_count)
                DialogRow(
                    parent=self,
                    table_widget=self.ui.scan_table,
                    client=self.target_widget.client,
                    row=row_count,
                    config=curve.config,
                ).add_scan_row()

        # Add DAP Curves
        for label, curve in config["DAP"].items():
            row_count = self.ui.dap_table.rowCount()
            self.ui.dap_table.insertRow(row_count)
            DialogRow(
                parent=self,
                table_widget=self.ui.dap_table,
                client=self.target_widget.client,
                row=row_count,
                config=curve.config,
            ).add_dap_row()

    def _enable_ui_elements(self, name, entry):
        if name is None:
            name = "best_effort"
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
            self.ui.dap_table.setEnabled(False)
            self.ui.add_dap.setEnabled(False)
            if self.ui.dap_table.rowCount() > 0:
                self.warning_util.show_warning(
                    title="DAP Warning",
                    message="DAP is not supported without specific x-axis device. All current DAP curves will be removed.",
                    detailed_text=f"Affected curves: {[self.ui.dap_table.cellWidget(row, 0).text() for row in range(self.ui.dap_table.rowCount())]}",
                )
        else:
            self.ui.x_name.setEnabled(True)
            self.ui.x_entry.setEnabled(True)
            self.ui.dap_table.setEnabled(True)
            self.ui.add_dap.setEnabled(True)

    @Slot()
    def change_colormap(self, target: Literal["scan", "dap"]):
        if target == "scan":
            cm = self.ui.color_map_selector_scan.colormap
            table = self.ui.scan_table
        if target == "dap":
            cm = self.ui.color_map_selector_dap.colormap
            table = self.ui.dap_table
        rows = table.rowCount()
        colors = Colors.golden_angle_color(colormap=cm, num=max(10, rows + 1), format="HEX")
        color_button_col = 2 if target == "scan" else 3
        for row in range(rows):
            table.cellWidget(row, color_button_col).set_color(colors[row])

    @Slot()
    def accept_changes(self):
        self.accept_curve_changes()

    def accept_curve_changes(self):
        sources = ["scan_segment", "async", "DAP"]
        old_curves = []

        for source in sources:
            old_curves += list(self.target_widget.waveform._curves_data[source].values())
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

        if x_mode not in ["index", "timestamp", "best_effort"]:

            for row in range(self.ui.dap_table.rowCount()):
                y_name = self.ui.dap_table.cellWidget(row, 0).text()
                y_entry = self.ui.dap_table.cellWidget(row, 1).text()
                dap = self.ui.dap_table.cellWidget(row, 2).currentText()
                color = self.ui.dap_table.cellWidget(row, 3).get_color()
                style = self.ui.dap_table.cellWidget(row, 4).currentText()
                width = self.ui.dap_table.cellWidget(row, 5).value()
                symbol_size = self.ui.dap_table.cellWidget(row, 6).value()

                self.target_widget.add_dap(
                    x_name=x_name,
                    x_entry=x_entry,
                    y_name=y_name,
                    y_entry=y_entry,
                    dap=dap,
                    color=color,
                    pen_style=style,
                    pen_width=width,
                    symbol_size=symbol_size,
                )
        self.target_widget.scan_history(-1)

    def add_curve(self):
        row_count = self.ui.scan_table.rowCount()
        self.ui.scan_table.insertRow(row_count)
        DialogRow(
            parent=self,
            table_widget=self.ui.scan_table,
            client=self.target_widget.client,
            row=row_count,
            config=None,
        ).add_scan_row()

    def add_dap(self):
        row_count = self.ui.dap_table.rowCount()
        self.ui.dap_table.insertRow(row_count)
        DialogRow(
            parent=self,
            table_widget=self.ui.dap_table,
            client=self.target_widget.client,
            row=row_count,
            config=None,
        ).add_dap_row()


class DialogRow(QObject):
    def __init__(
        self,
        parent=None,
        table_widget: QTableWidget = None,
        row: int = None,
        config: dict = None,
        client=None,
    ):

        super().__init__(parent=parent)
        self.client = client

        self.table_widget = table_widget
        self.row = row
        self.config = config
        self.init_default_widgets()

    def init_default_widgets(self):

        # Remove Button
        self.remove_button = RemoveButton()

        # Name and Entry
        self.device_line_edit = DeviceLineEdit()
        self.entry_line_edit = QLineEdit()

        self.dap_combo = DapComboBox()
        self.dap_combo.populate_fit_model_combobox()
        self.dap_combo.select_fit_model("GaussianModel")

        # Styling
        self.color_button = ColorButton()
        self.style_combo = StyleComboBox()
        self.width = QSpinBox()
        self.width.setMinimum(1)
        self.width.setMaximum(20)
        self.width.setValue(4)

        self.symbol_size = QSpinBox()
        self.symbol_size.setMinimum(1)
        self.symbol_size.setMaximum(20)
        self.symbol_size.setValue(7)

        self.remove_button.clicked.connect(
            lambda: self.remove_row()
        )  # From some reason do not work without lambda

    def add_scan_row(self):
        if self.config is not None:
            self.device_line_edit.setText(self.config.signals.y.name)
            self.entry_line_edit.setText(self.config.signals.y.entry)
            self.color_button.set_color(self.config.color)
            self.style_combo.setCurrentText(self.config.pen_style)
            self.width.setValue(self.config.pen_width)
            self.symbol_size.setValue(self.config.symbol_size)
        else:
            default_colors = Colors.golden_angle_color(
                colormap="magma", num=max(10, self.row + 1), format="HEX"
            )
            default_color = default_colors[self.row]
            self.color_button.set_color(default_color)

        self.table_widget.setCellWidget(self.row, 0, self.device_line_edit)
        self.table_widget.setCellWidget(self.row, 1, self.entry_line_edit)
        self.table_widget.setCellWidget(self.row, 2, self.color_button)
        self.table_widget.setCellWidget(self.row, 3, self.style_combo)
        self.table_widget.setCellWidget(self.row, 4, self.width)
        self.table_widget.setCellWidget(self.row, 5, self.symbol_size)
        self.table_widget.setCellWidget(self.row, 6, self.remove_button)

    def add_dap_row(self):
        if self.config is not None:
            self.device_line_edit.setText(self.config.signals.y.name)
            self.entry_line_edit.setText(self.config.signals.y.entry)
            self.dap_combo.fit_model_combobox.setCurrentText(self.config.signals.dap)
            self.color_button.set_color(self.config.color)
            self.style_combo.setCurrentText(self.config.pen_style)
            self.width.setValue(self.config.pen_width)
            self.symbol_size.setValue(self.config.symbol_size)
        else:
            default_colors = Colors.golden_angle_color(
                colormap="magma", num=max(10, self.row + 1), format="HEX"
            )
            default_color = default_colors[self.row]
            self.color_button.set_color(default_color)

        self.table_widget.setCellWidget(self.row, 0, self.device_line_edit)
        self.table_widget.setCellWidget(self.row, 1, self.entry_line_edit)
        self.table_widget.setCellWidget(self.row, 2, self.dap_combo.fit_model_combobox)
        self.table_widget.setCellWidget(self.row, 3, self.color_button)
        self.table_widget.setCellWidget(self.row, 4, self.style_combo)
        self.table_widget.setCellWidget(self.row, 5, self.width)
        self.table_widget.setCellWidget(self.row, 6, self.symbol_size)
        self.table_widget.setCellWidget(self.row, 7, self.remove_button)

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


class RemoveButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        icon = material_icon("disabled_by_default", size=(20, 20), convert_to_pixmap=False)
        self.setIcon(icon)
