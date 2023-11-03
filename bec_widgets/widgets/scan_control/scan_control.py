import sys
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QComboBox,
    QPushButton,
    QVBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QGridLayout,
)

import msgpack

from bec_widgets.bec_dispatcher import bec_dispatcher
from bec_lib.core import MessageEndpoints


class ScanArgType:
    DEVICE = "device"
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"


class ScanControl(QWidget):
    WIDGET_HANDLER = {
        ScanArgType.DEVICE: QLineEdit,
        ScanArgType.FLOAT: QDoubleSpinBox,
        ScanArgType.INT: QSpinBox,
        ScanArgType.BOOL: QCheckBox,
    }

    def __init__(self, parent=None, client=None):
        super().__init__(parent)

        # Client from BEC + shortcuts to device manager and scans
        self.client = bec_dispatcher.client if client is None else client
        self.dev = self.client.device_manager.devices
        self.scans = self.client.scans

        # Create and set main layout
        self._init_UI()

        # Populate scans to ComboBox for scan selection
        self.populate_scans()

        # Connect signals #TODO so far not useful
        # self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selected)

    def _init_UI(self):
        self.verticalLayout = QVBoxLayout(self)

        self.scan_selection_group = QGroupBox("Scan Selection", self)
        self.scan_selection_layout = QVBoxLayout(self.scan_selection_group)

        self.comboBox_scan_selection = QComboBox(self.scan_selection_group)
        self.scan_selection_layout.addWidget(self.comboBox_scan_selection)
        self.scan_selection_layout.addWidget(QPushButton("Connect", self.scan_selection_group))

        self.verticalLayout.addWidget(self.scan_selection_group)

        self.scan_control_group = QGroupBox("Scan Control", self)
        self.scan_control_layout = QVBoxLayout(self.scan_control_group)
        self.verticalLayout.addWidget(self.scan_control_group)

        self.bundle_spinBox = QSpinBox(self.scan_control_group)
        self.bundle_spinBox.setValue(1)  # default value
        self.bundle_spinBox.setMinimum(1)
        self.bundle_layout = QHBoxLayout()
        self.bundle_layout.addWidget(QLabel("Bundle Size:", self.scan_control_group))
        self.bundle_layout.addWidget(self.bundle_spinBox)
        self.scan_control_layout.addLayout(self.bundle_layout)

        self.kwargs_layout = QGridLayout()
        self.scan_control_layout.addLayout(self.kwargs_layout)

        self.separator = QFrame(self.scan_control_group)
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setFrameShadow(QFrame.Sunken)
        self.scan_control_layout.addWidget(self.separator)

        self.args_layout = QGridLayout()
        self.scan_control_layout.addLayout(self.args_layout)

        self.populate_scans()
        self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selected)

    def populate_scans(self):
        msg = self.client.producer.get(MessageEndpoints.available_scans())
        self.available_scans = msgpack.loads(msg)
        self.comboBox_scan_selection.addItems(self.available_scans.keys())

    def on_scan_selected(self):
        selected_scan_name = self.comboBox_scan_selection.currentText()
        selected_scan_info = self.available_scans.get(selected_scan_name, {})
        self.generate_input_fields(selected_scan_info)

        print(10 * "#" + f"{selected_scan_name}" + 10 * "#")
        print(10 * "#" + "selected_scan_info" + 10 * "#")
        print(selected_scan_info)

    def clear_previous_fields(self, layout):
        for i in reversed(range(layout.count())):
            layout.itemAt(i).widget().deleteLater()

    def add_widgets_to_layout(self, layout, items, signature=None):
        for row_idx, item in enumerate(items):
            if signature:  # handling kwargs
                kwarg_info = next((info for info in signature if info["name"] == item), None)
                if kwarg_info:
                    item_type = kwarg_info.get("annotation", "_empty")
                    item_name = item
            else:  # handling arg_input
                item_name, item_type = item

            widget_class = self.WIDGET_HANDLER.get(item_type, None)
            if widget_class is None:
                print(f"Unsupported annotation '{item_type}' for parameter '{item_name}'")
                continue  # Skip unsupported annotations

            label = QLabel(item_name.capitalize(), self.scan_control_group)
            widget = widget_class(self.scan_control_group)
            layout.addWidget(label, row_idx, 0)
            layout.addWidget(widget, row_idx, 1)

    def generate_input_fields(self, scan_info):
        # Clear the previous input fields
        self.clear_previous_fields(self.kwargs_layout)
        self.clear_previous_fields(self.args_layout)

        arg_input = scan_info.get("arg_input", {})
        required_kwargs = scan_info.get("required_kwargs", [])

        self.add_widgets_to_layout(
            self.kwargs_layout, required_kwargs, scan_info.get("signature", [])
        )
        self.add_widgets_to_layout(self.args_layout, arg_input.items())


if __name__ == "__main__":
    from bec_widgets.bec_dispatcher import bec_dispatcher

    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    app = QApplication([])
    scan_control = ScanControl(client=client)

    window = scan_control
    window.show()
    app.exec_()
