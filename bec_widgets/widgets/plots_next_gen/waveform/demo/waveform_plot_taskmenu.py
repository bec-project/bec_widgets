"""
waveform_plot_taskmenu.py

Implements the dialog to edit WaveformPlot's 'curvesJson' property,
and the QPyDesignerTaskMenuExtension to integrate into Qt Designer.
"""

import json

from qtpy.QtDesigner import QExtensionFactory, QPyDesignerTaskMenuExtension
from qtpy.QtGui import QAction
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QPushButton,
    QLineEdit,
    QColorDialog,
)
from qtpy.QtCore import Qt, Slot

from bec_widgets.widgets.plots_next_gen.waveform.demo.waveform_demo import WaveformPlot


# We'll import the widget class name for type-checking


class WaveformCurvesDialog(QDialog):
    """
    A dialog allowing the user to edit the JSON for curves.
    We store an internal list of dicts with "label", "color", etc.
    """

    def __init__(self, curves_json: str, parent=None):
        super().__init__(parent, Qt.WindowTitleHint | Qt.WindowSystemMenuHint)
        self.setWindowTitle("Edit Curves")
        self.resize(400, 300)

        self._data = []
        # Try to parse incoming JSON
        try:
            arr = json.loads(curves_json)
            if isinstance(arr, list):
                self._data = arr
        except:
            pass

        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        # Layout for the "list" of curve rows
        self.curves_layout = QVBoxLayout()
        main_layout.addLayout(self.curves_layout)

        # "Add curve" button
        add_btn = QPushButton("Add Curve")
        add_btn.clicked.connect(self._on_add_curve)
        main_layout.addWidget(add_btn)

        # OK/Cancel
        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        main_layout.addWidget(box)

        # Build row widgets
        self._refresh_rows()

    def _refresh_rows(self):
        # Clear existing row widgets
        while True:
            item = self.curves_layout.takeAt(0)
            if not item:
                break
            w = item.widget()
            if w:
                w.deleteLater()

        # Rebuild a row for each entry
        for idx, cinfo in enumerate(self._data):
            row_widget = self._create_curve_row(idx, cinfo)
            self.curves_layout.addWidget(row_widget)

    def _create_curve_row(self, idx: int, info: dict):
        container = QWidget(self)
        hl = QHBoxLayout(container)

        # label text
        label_edit = QLineEdit(info.get("label", ""), container)
        label_edit.setPlaceholderText("Label")
        label_edit.textChanged.connect(lambda txt, i=idx: self._on_label_changed(i, txt))
        hl.addWidget(label_edit)

        # color button
        color_btn = QPushButton(info.get("color", "Pick Color"), container)
        color_btn.clicked.connect(lambda _=None, i=idx: self._pick_color(i))
        hl.addWidget(color_btn)

        # remove button
        rm_btn = QPushButton("X", container)
        rm_btn.clicked.connect(lambda _=None, i=idx: self._on_remove_curve(i))
        hl.addWidget(rm_btn)

        return container

    def _on_add_curve(self):
        self._data.append({"label": "NewCurve", "color": "blue"})
        self._refresh_rows()

    def _on_remove_curve(self, idx: int):
        if 0 <= idx < len(self._data):
            self._data.pop(idx)
            self._refresh_rows()

    def _on_label_changed(self, idx: int, text: str):
        if 0 <= idx < len(self._data):
            self._data[idx]["label"] = text

    def _pick_color(self, idx: int):
        if 0 <= idx < len(self._data):
            old_col = self._data[idx].get("color", "#ff0000")
            dlg = QColorDialog(self)
            dlg.setCurrentColor(dlg.currentColor())  # Or parse old_col if you wish
            if dlg.exec_() == QDialog.Accepted:
                c = dlg.selectedColor().name()
                self._data[idx]["color"] = c
            self._refresh_rows()

    def curves_json(self) -> str:
        """Return the final JSON after user edits."""
        return json.dumps(self._data, indent=2)


class WaveformPlotTaskMenu(QPyDesignerTaskMenuExtension):
    """
    Implements a "Task Menu" action for WaveformPlot in Qt Designer:
    'Edit Curves...' which opens WaveformCurvesDialog.
    """

    def __init__(self, widget: WaveformPlot, parent=None):
        super().__init__(parent)
        self._widget = widget
        self._edit_action = QAction("Edit Curves...", self)
        self._edit_action.triggered.connect(self._edit_curves)

    def taskActions(self):
        return [self._edit_action]

    def preferredEditAction(self):
        return self._edit_action

    @Slot()
    def _edit_curves(self):
        # read current property
        old_json = self._widget.curvesJson

        # pop up the dialog
        dlg = WaveformCurvesDialog(old_json, parent=self._widget)
        if dlg.exec_() == QDialog.Accepted:
            # get new JSON
            new_json = dlg.curves_json()
            # set property so Designer picks it up
            self._widget.setProperty("curvesJson", new_json)


class WaveformPlotTaskMenuFactory(QExtensionFactory):
    """
    The factory that creates a WaveformPlotTaskMenu if the widget is a WaveformPlot.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

    @staticmethod
    def task_menu_iid():
        return "org.qt-project.Qt.Designer.TaskMenu"

    def createExtension(self, obj, iid, parent):
        # Check we are asked for a TaskMenu extension and the widget is our WaveformPlot
        if iid == self.task_menu_iid() and isinstance(obj, WaveformPlot):
            return WaveformPlotTaskMenu(obj, parent)
        return None
