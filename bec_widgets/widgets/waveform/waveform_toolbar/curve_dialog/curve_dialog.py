from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel
from qtpy.QtCore import QObject, QSize, Slot
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QComboBox, QLineEdit, QPushButton, QSpinBox, QTableWidget, QVBoxLayout

import bec_widgets
from bec_widgets.qt_utils.error_popups import WarningPopupUtility
from bec_widgets.qt_utils.settings_dialog import SettingWidget
from bec_widgets.utils import Colors, UILoader
from bec_widgets.widgets.color_button.color_button import ColorButton
from bec_widgets.widgets.device_line_edit.device_line_edit import DeviceLineEdit

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
        add_icon = QIcon()
        add_icon.addFile(
            os.path.join(MODULE_PATH, "assets", "toolbar_icons", "add.svg"), size=QSize(20, 20)
        )
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
        self.ui.color_map_selector_scan.combo.setCurrentText(cm)

        # Scan Curve Table
        for label, curve in config["scan_segment"].items():
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
            cm = self.ui.color_map_selector_scan.combo.currentText()
            table = self.ui.scan_table
        if target == "dap":
            cm = self.ui.color_map_selector_dap.combo.currentText()
            table = self.ui.dap_table
        rows = table.rowCount()
        colors = Colors.golden_angle_color(colormap=cm, num=rows + 1, format="HEX")
        color_button_col = 2 if target == "scan" else 3
        for row, color in zip(range(rows), colors):
            table.cellWidget(row, color_button_col).setColor(color)

    @Slot()
    def accept_changes(self):
        self.accept_curve_changes()

    def accept_curve_changes(self):
        old_curves_scans = list(self.target_widget.waveform._curves_data["scan_segment"].values())
        old_curves_dap = list(self.target_widget.waveform._curves_data["DAP"].values())
        for curve in old_curves_scans:
            curve.remove()
        for curve in old_curves_dap:
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

        self.dap_combo = QComboBox()
        self.populate_dap_combobox()

        # Styling
        self.color_button = ColorButton()
        self.style_combo = StyleComboBox()
        self.width = QSpinBox()
        self.width.setMinimum(1)
        self.width.setMaximum(20)
        self.width.setValue(2)

        self.symbol_size = QSpinBox()
        self.symbol_size.setMinimum(1)
        self.symbol_size.setMaximum(20)
        self.symbol_size.setValue(5)

        self.remove_button.clicked.connect(
            lambda: self.remove_row()
        )  # From some reason do not work without lambda

    def populate_dap_combobox(self):
        available_models = [
            attr
            for attr in dir(self.client.dap)
            if not attr.startswith("__")
            and not callable(getattr(self.client.dap, attr))
            and not attr.startswith("_")
        ]
        self.dap_combo.addItems(available_models)

    def add_scan_row(self):
        if self.config is not None:
            self.device_line_edit.setText(self.config.signals.y.name)
            self.entry_line_edit.setText(self.config.signals.y.entry)
            self.color_button.setColor(self.config.color)
            self.style_combo.setCurrentText(self.config.pen_style)
            self.width.setValue(self.config.pen_width)
            self.symbol_size.setValue(self.config.symbol_size)
        else:
            default_color = Colors.golden_angle_color(
                colormap="magma", num=self.row + 1, format="HEX"
            )[-1]
            self.color_button.setColor(default_color)

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
            self.dap_combo.setCurrentText(self.config.signals.dap)
            self.color_button.setColor(self.config.color)
            self.style_combo.setCurrentText(self.config.pen_style)
            self.width.setValue(self.config.pen_width)
            self.symbol_size.setValue(self.config.symbol_size)
        else:
            default_color = Colors.golden_angle_color(
                colormap="magma", num=self.row + 1, format="HEX"
            )[-1]
            self.color_button.setColor(default_color)

        self.table_widget.setCellWidget(self.row, 0, self.device_line_edit)
        self.table_widget.setCellWidget(self.row, 1, self.entry_line_edit)
        self.table_widget.setCellWidget(self.row, 2, self.dap_combo)
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
        icon_path = os.path.join(MODULE_PATH, "assets", "toolbar_icons", "remove.svg")
        self.setIcon(QIcon(icon_path))
