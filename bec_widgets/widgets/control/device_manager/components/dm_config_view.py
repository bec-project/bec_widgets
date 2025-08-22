"""Module with a config view for the device manager."""

from __future__ import annotations

import yaml
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget


class DMConfigView(BECWidget, QtWidgets.QWidget):
    def __init__(self, parent=None, client=None):
        super().__init__(client=client, parent=parent)
        self.stacked_layout = QtWidgets.QStackedLayout()
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_layout.setSpacing(0)
        self.setLayout(self.stacked_layout)

        # Monaco widget
        self.monaco_editor = MonacoWidget()
        self._customize_monaco()
        self.stacked_layout.addWidget(self.monaco_editor)

        self._overlay_widget = QtWidgets.QLabel(text="Select single device to show config")
        self._customize_overlay()
        self.stacked_layout.addWidget(self._overlay_widget)
        self.stacked_layout.setCurrentWidget(self._overlay_widget)

    def _customize_monaco(self):

        self.monaco_editor.set_language("yaml")
        self.monaco_editor.set_vim_mode_enabled(False)
        self.monaco_editor.set_minimap_enabled(False)
        # self.monaco_editor.setFixedHeight(600)
        self.monaco_editor.set_readonly(True)

    def _customize_overlay(self):
        self._overlay_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._overlay_widget.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:0, y2:1,stop:0 #ffffff, stop:1 #e0e0e0);"
        )
        self._overlay_widget.setAutoFillBackground(True)
        self._overlay_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )

    @SafeSlot(dict)
    def on_select_config(self, device: dict):
        """Handle selection of a device from the device table."""
        if not device:
            text = ""
            self.stacked_layout.setCurrentWidget(self._overlay_widget)
        else:
            text = yaml.dump(device, default_flow_style=False)
            self.stacked_layout.setCurrentWidget(self.monaco_editor)
        self.monaco_editor.set_readonly(False)  # Enable editing
        self.monaco_editor.set_text(text)
        self.monaco_editor.set_readonly(True)  # Disable editing again


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    config_view = DMConfigView()
    config_view.show()
    sys.exit(app.exec_())
