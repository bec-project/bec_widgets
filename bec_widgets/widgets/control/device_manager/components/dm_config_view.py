"""Module with a config view for the device manager."""

from __future__ import annotations

import traceback

import yaml
from bec_lib.logger import bec_logger
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget

logger = bec_logger.logger


class DMConfigView(QtWidgets.QWidget):
    """Widget to show the config of a selected device in YAML format."""

    RPC = False

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.stacked_layout = QtWidgets.QStackedLayout()
        self.stacked_layout.setContentsMargins(0, 0, 0, 0)
        self.stacked_layout.setSpacing(0)
        self.setLayout(self.stacked_layout)

        # Monaco widget
        self.monaco_editor = MonacoWidget(parent=self)
        self._customize_monaco()
        self.stacked_layout.addWidget(self.monaco_editor)

        # Overlay widget
        self._overlay_text = "Select a single device to view its config."
        self._overlay_widget = QtWidgets.QLabel(text=self._overlay_text)
        self._customize_overlay()
        self.stacked_layout.addWidget(self._overlay_widget)
        self.stacked_layout.setCurrentWidget(self._overlay_widget)

    def _customize_monaco(self):
        """Customize the Monaco editor for YAML display."""
        self.monaco_editor.set_language("yaml")
        self.monaco_editor.set_vim_mode_enabled(False)
        self.monaco_editor.set_minimap_enabled(False)
        self.monaco_editor.set_readonly(True)
        self.monaco_editor.editor.set_scroll_beyond_last_line_enabled(False)
        self.monaco_editor.editor.set_line_numbers_mode("off")

    def _customize_overlay(self):
        """Customize the overlay widget."""
        self._overlay_widget.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._overlay_widget.setAutoFillBackground(True)
        self._overlay_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )

    @SafeSlot(dict)
    def on_select_config(self, device: list[dict]):
        """
        Handle selection of a device from the device table. If more than one device is selected,
        show an overlay message. Otherwise, display the device config in YAML format.

        Args:
            device (list[dict]): The selected device configuration.
        """
        if len(device) != 1:
            text = ""
            self.stacked_layout.setCurrentWidget(self._overlay_widget)
        else:
            try:
                # Cast set to list to ensure proper YAML dumping
                cfg = device[0]
                for k, v in cfg.items():
                    if isinstance(v, set):
                        cfg[k] = list(v)
                text = yaml.dump(cfg, default_flow_style=False)
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


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    widget.setLayout(layout)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    config_view = DMConfigView()
    layout.addWidget(config_view)
    combo_box = QtWidgets.QComboBox()
    config = config_view.client.device_manager._get_redis_device_config()
    combo_box.addItems([""] + [f"{v} : {item.get('name', '')}" for v, item in enumerate(config)])

    def on_select(text):
        if text == "":
            config_view.on_select_config([])
        else:
            index = int(text.split(" : ")[0])
            config_view.on_select_config([config[index]])

    combo_box.currentTextChanged.connect(on_select)
    layout.addWidget(combo_box)
    widget.show()
    sys.exit(app.exec_())
