from bec_lib.atlas_models import Device as DeviceConfigModel
from bec_lib.logger import bec_logger
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.services.device_browser.device_item.device_config_form import (
    DeviceConfigForm,
)

logger = bec_logger.logger


class DeviceConfigDialog(BECWidget, QDialog):
    def __init__(self, parent=None, device: str | None = None):
        super().__init__(parent=parent)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._form = DeviceConfigForm()
        self._layout.addWidget(self._form)
        if device:
            self._device = device
            self._fill_form()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self._layout.addWidget(button_box)

    def _fill_form(self):
        self._form.set_data(self._pull_config())

    def _pull_config(self) -> DeviceConfigModel:
        return DeviceConfigModel.model_validate(
            {
                "name": "test_device",
                "enabled": False,
                "deviceClass": "TestDevice",
                "deviceConfig": {},
                "readoutPriority": "baseline",
            }
        )


def main():  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication, QLineEdit, QPushButton, QWidget

    from bec_widgets.utils.colors import set_theme

    dialog = None

    app = QApplication(sys.argv)
    set_theme("light")
    widget = QWidget()
    widget.setLayout(QVBoxLayout())

    device = QLineEdit()
    widget.layout().addWidget(device)

    def _destroy_dialog(*_):
        nonlocal dialog
        dialog = None

    def accept(*args):
        logger.success(f"submitted device config form {dialog} {args}")
        _destroy_dialog()

    def _show_dialog(*_):
        nonlocal dialog
        if dialog is None:
            dialog = DeviceConfigDialog(device=device.text())
            dialog.accepted.connect(accept)
            dialog.rejected.connect(_destroy_dialog)
            dialog.open()

    button = QPushButton("Show device dialog")
    widget.layout().addWidget(button)
    button.clicked.connect(_show_dialog)
    widget.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
