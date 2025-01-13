"""
waveform_plot_config_dialog.py
A single dialog that configures a WaveformPlot's properties:
  - deviceName
  - someFlag
  - curvesJson (with add/remove curve, color picking, etc.)

You can call this dialog in normal code:
    dlg = WaveformPlotConfigDialog(myWaveformPlot)
    if dlg.exec_() == QDialog.Accepted:
        # properties updated

Or from a QDesignerTaskMenu (see waveform_plot_taskmenu.py).
"""

import json

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QColorDialog,
)


class WaveformPlotConfigDialog(QDialog):
    """
    Edits three properties of a WaveformPlot:
      - deviceName  (string)
      - someFlag    (bool)
      - curvesJson  (JSON array of {label, color})

    In real usage, you might add more fields (pen widths, device signals, etc.).
    """

    def __init__(self, waveform_plot, parent=None):
        super().__init__(parent, Qt.WindowTitleHint | Qt.WindowSystemMenuHint)
        self.setWindowTitle("WaveformPlot Configuration")

        self._wp = waveform_plot  # We'll read and write properties on this widget

        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        # ---------------------------
        # Row 1: deviceName
        # ---------------------------
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Device Name:"))
        self._device_name_edit = QLineEdit(self)
        self._device_name_edit.setText(self._wp.deviceName)
        row1.addWidget(self._device_name_edit)
        main_layout.addLayout(row1)

        # ---------------------------
        # Row 2: someFlag (bool)
        # ---------------------------
        row2 = QHBoxLayout()
        self._flag_checkbox = QCheckBox("someFlag", self)
        self._flag_checkbox.setChecked(self._wp.someFlag)
        row2.addWidget(self._flag_checkbox)
        row2.addStretch()
        main_layout.addLayout(row2)

        # ---------------------------
        # The curves config area
        # We'll store an internal list of curves
        # so we can load them from curvesJson
        # and then re-serialize after changes.
        # ---------------------------
        self._curves_data = []
        try:
            arr = json.loads(self._wp.curvesJson)
            if isinstance(arr, list):
                self._curves_data = arr
        except:
            pass

        self._curves_layout = QVBoxLayout()
        main_layout.addLayout(self._curves_layout)

        add_curve_btn = QPushButton("Add Curve")
        add_curve_btn.clicked.connect(self._on_add_curve)
        main_layout.addWidget(add_curve_btn)

        # OK / Cancel
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        main_layout.addWidget(box)

        self._refresh_curves_rows()

    def _refresh_curves_rows(self):
        # Clear old row widgets
        while True:
            item = self._curves_layout.takeAt(0)
            if not item:
                break
            w = item.widget()
            if w:
                w.deleteLater()

        # Create row per curve
        for idx, cinfo in enumerate(self._curves_data):
            row_widget = self._create_curve_row(idx, cinfo)
            self._curves_layout.addWidget(row_widget)

    def _create_curve_row(self, idx, cinfo):
        container = QWidget(self)
        hl = QHBoxLayout(container)

        label_edit = QLineEdit(cinfo.get("label", ""), container)
        label_edit.setPlaceholderText("Label")
        label_edit.textChanged.connect(lambda txt, i=idx: self._on_label_changed(i, txt))
        hl.addWidget(label_edit)

        color_btn = QPushButton(cinfo.get("color", "Pick Color"), container)
        color_btn.clicked.connect(lambda _=None, i=idx: self._pick_color(i))
        hl.addWidget(color_btn)

        rm_btn = QPushButton("X", container)
        rm_btn.clicked.connect(lambda _=None, i=idx: self._on_remove_curve(i))
        hl.addWidget(rm_btn)

        return container

    def _on_add_curve(self):
        self._curves_data.append({"label": "NewCurve", "color": "blue"})
        self._refresh_curves_rows()

    def _on_remove_curve(self, idx: int):
        if 0 <= idx < len(self._curves_data):
            self._curves_data.pop(idx)
            self._refresh_curves_rows()

    def _on_label_changed(self, idx: int, new_label: str):
        if 0 <= idx < len(self._curves_data):
            self._curves_data[idx]["label"] = new_label

    def _pick_color(self, idx: int):
        if 0 <= idx < len(self._curves_data):
            dlg = QColorDialog(self)
            if dlg.exec_() == QDialog.Accepted:
                c = dlg.selectedColor().name()
                self._curves_data[idx]["color"] = c
            self._refresh_curves_rows()

    def accept(self):
        """
        If user presses OK, update the widget's properties:
          deviceName
          someFlag
          curvesJson
        """
        # 1) deviceName
        self._wp.deviceName = self._device_name_edit.text().strip()

        # 2) someFlag
        self._wp.someFlag = self._flag_checkbox.isChecked()

        # 3) curvesJson
        new_json = json.dumps(self._curves_data, indent=2)
        self._wp.curvesJson = new_json

        super().accept()

    # For standalone usage, you can do:
    #   dlg = WaveformPlotConfigDialog(wp)
    #   if dlg.exec_() == QDialog.Accepted:
    #       # properties were updated
