"""Module with a config view for the device manager."""

from __future__ import annotations

import traceback

import yaml
from bec_lib.logger import bec_logger
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget

logger = bec_logger.logger


class DMConfigView(BECWidget, QtWidgets.QWidget):
    def __init__(self, parent=None, client=None):
        super().__init__(client=client, parent=parent, theme_update=True)
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
        self.monaco_editor.editor.set_scroll_beyond_last_line_enabled(False)
        self.monaco_editor.editor.set_line_numbers_mode("off")

    def _customize_overlay(self):
        self._overlay_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._overlay_widget.setAutoFillBackground(True)
        self._overlay_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )

    @SafeSlot(dict)
    def on_select_config(self, device: list[dict]):
        """Handle selection of a device from the device table."""
        if len(device) != 1:
            text = ""
            self.stacked_layout.setCurrentWidget(self._overlay_widget)
        else:
            try:
                text = yaml.dump(device[0], default_flow_style=False)
                self.stacked_layout.setCurrentWidget(self.monaco_editor)
            except Exception:
                content = traceback.format_exc()
                logger.error(f"Error converting device to YAML:\n{content}")
                text = ""
                self.stacked_layout.setCurrentWidget(self._overlay_widget)
        self.monaco_editor.set_readonly(False)  # Enable editing
        text = text.rstrip()
        self.monaco_editor.set_text(text)
        self.monaco_editor.set_readonly(True)  # Disable editing again


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    widget.setLayout(layout)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    config_view = DMConfigView()
    layout.addWidget(config_view)
    combo_box = QtWidgets.QComboBox()
    config = config_view.client.device_manager._get_redis_device_config()
    combo_box.addItems([""] + [str(v) for v, item in enumerate(config)])

    def on_select(text):
        if text == "":
            config_view.on_select_config([])
        else:
            config_view.on_select_config([config[int(text)]])

    combo_box.currentTextChanged.connect(on_select)
    layout.addWidget(combo_box)
    widget.show()
    sys.exit(app.exec_())
