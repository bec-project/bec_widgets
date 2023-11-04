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
    QLayout,
)
from PyQt5.QtCore import Qt
import msgpack

from bec_widgets.bec_dispatcher import bec_dispatcher
from bec_lib.core import MessageEndpoints


class ScanArgType:
    DEVICE = "device"
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"


class BundleGroup(QWidget):
    WIDGET_HANDLER = {
        ScanArgType.DEVICE: QLineEdit,
        ScanArgType.FLOAT: QDoubleSpinBox,
        ScanArgType.INT: QSpinBox,
        ScanArgType.BOOL: QCheckBox,
    }

    def __init__(self, arg_input, parent=None):
        super().__init__(parent)
        self.arg_input = arg_input
        self.init_ui()

    def init_ui(self):
        self.layout = QHBoxLayout(self)
        for param, param_type in self.arg_input.items():
            widget_class = self.WIDGET_HANDLER.get(param_type)
            if widget_class:
                widget = widget_class(self)
                if isinstance(widget, QDoubleSpinBox):
                    widget.setAlignment(Qt.AlignLeft)  # Align to left
                self.layout.addWidget(widget)
            else:
                print(f"Unsupported annotation '{param_type}' for parameter '{param}'")


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

    def _init_UI(self):
        self.verticalLayout = QVBoxLayout(self)

        self.scan_selection_group = QGroupBox("Scan Selection", self)
        self.scan_selection_layout = QVBoxLayout(self.scan_selection_group)

        self.comboBox_scan_selection = QComboBox(self.scan_selection_group)
        self.scan_selection_layout.addWidget(self.comboBox_scan_selection)
        # self.scan_selection_layout.addWidget(QPushButton("Connect", self.scan_selection_group)) #TODO button probably not needed

        self.verticalLayout.addWidget(self.scan_selection_group)

        self.scan_control_group = QGroupBox("Scan Control", self)
        self.scan_control_layout = QVBoxLayout(self.scan_control_group)
        self.verticalLayout.addWidget(self.scan_control_group)

        # Kwargs layout
        self.kwargs_layout = QVBoxLayout()
        self.scan_control_layout.addLayout(self.kwargs_layout)

        # 1st Separator
        self.add_horizontal_separator(self.scan_control_layout)

        # Buttons
        self.button_layout = QHBoxLayout()
        self.add_bundle_button = QPushButton("Add Bundle", self.scan_control_group)
        self.add_bundle_button.clicked.connect(self.add_bundle)
        self.remove_bundle_button = QPushButton("Remove Bundle", self.scan_control_group)
        self.remove_bundle_button.clicked.connect(self.remove_bundle)
        self.button_layout.addWidget(self.add_bundle_button)
        self.button_layout.addWidget(self.remove_bundle_button)
        self.scan_control_layout.addLayout(self.button_layout)

        # 2nd Separator
        self.add_horizontal_separator(self.scan_control_layout)

        # Args layout
        self.args_layout = QVBoxLayout()
        self.scan_control_layout.addLayout(self.args_layout)

        self.populate_scans()
        self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selected)

    def add_horizontal_separator(self, layout) -> None:
        """
        Adds a horizontal separator to the given layout
        Args:
            layout: Layout to add the separator to

        """
        separator = QFrame(self.scan_control_group)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

    def populate_scans(self):
        msg = self.client.producer.get(MessageEndpoints.available_scans())
        self.available_scans = msgpack.loads(msg)
        self.comboBox_scan_selection.addItems(self.available_scans.keys())

    def on_scan_selected(self):
        selected_scan_name = self.comboBox_scan_selection.currentText()
        selected_scan_info = self.available_scans.get(selected_scan_name, {})

        # Clear the previous input fields
        self.clear_layout(self.args_layout)
        self.clear_layout(self.kwargs_layout)

        # Generate kwargs input
        self.generate_kwargs_input_fields(selected_scan_info)

        # TODO until HERE!
        # Args section
        self.arg_input = selected_scan_info.get("arg_input", {})  # Get arg_input from selected scan
        self.add_labels(self.arg_input.keys(), self.args_layout)  # Add labels
        self.add_widgets_row_to_layout(
            self.args_layout, self.arg_input.items()
        )  # Add first row of widgets

        # self.generate_input_fields(selected_scan_info) #TODO probably not needed

        print(10 * "#" + f"{selected_scan_name}" + 10 * "#")
        print(10 * "#" + "selected_scan_info" + 10 * "#")
        print(selected_scan_info)

    def add_labels(self, labels: list, layout) -> None:
        """
        Adds labels to the given layout in QHBox layout
        Args:
            labels(list): List of labels to add
            layout: Layout to add the labels to

        """
        label_layout = QHBoxLayout()
        for col_idx, param in enumerate(labels):
            label = QLabel(param.capitalize(), self.scan_control_group)
            label_layout.addWidget(label)

        layout.addLayout(label_layout)

    def generate_kwargs_input_fields(self, scan_info: dict) -> None:
        """
        Generates input fields for kwargs
        Args:
            scan_info(dict): Dictionary containing scan information
        """
        # Clear the previous input fields
        self.clear_layout(self.kwargs_layout)

        # Get kwargs and signature
        required_kwargs = scan_info.get("required_kwargs", [])
        signature = scan_info.get("signature", [])

        # Add labels
        self.add_labels(required_kwargs, self.kwargs_layout)

        # Add widgets
        self.add_widgets_row_to_layout(self.kwargs_layout, required_kwargs, signature)

    def add_widgets_row_to_layout(
        self, layout: QLayout, items: list, signature: dict = None
    ) -> None:
        """
        Adds widgets to the given layout as a row in QHBox layout
        Args:
            layout(QLayout): Layout to add the widgets to
            items(list): List of items to add
            signature(dict): Dictionary containing signature information for kwargs

        Returns:

        """
        item_type, item_name = None, None
        widget_row_layout = QHBoxLayout()
        for row_idx, item in enumerate(items):
            if signature:
                kwarg_info = next((info for info in signature if info["name"] == item), None)
                if kwarg_info:
                    item_type = kwarg_info.get("annotation", "_empty")
                    item_name = item
            else:
                item_name, item_type = item

            widget_class = self.WIDGET_HANDLER.get(
                item_type, None
            )  # TODO fix crash when unsupported annotation
            if widget_class is None:
                print(f"Unsupported annotation '{item_type}' for parameter '{item_name}'")
                continue
            # Generated widget by HANDLER
            widget = widget_class(self.scan_control_group)
            widget_row_layout.addWidget(widget)
            print(
                f"Added widget {widget} to layout {layout}"
            )  # TODO remove when app will be working correctly

        layout.addLayout(widget_row_layout)

    def clear_layout(self, layout: QLayout) -> None:  # TODO like this probably
        """
        Clears completely the given layout, even if there are  sub-layouts
        Args:
            layout: Layout to clear
        """
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout:
                    self.clear_layout(sub_layout)
                    sub_layout.setParent(None)  # disown layout
                    sub_layout.deleteLater()  # schedule layout for deletion

    def add_bundle(self) -> None:
        """Adds a bundle to the scan control layout"""
        self.add_widgets_row_to_layout(
            self.args_layout, self.arg_input.items()
        )  # Add first row of widgets

    # def remove_bundle(self):
    #     # print layout children
    #     print("layout children:")
    #     for i in range(self.args_layout.count()):
    #         print(self.args_layout.itemAt(i).widget())

    #
    def remove_bundle(self) -> None:
        """Removes the last bundle from the scan control layout"""
        last_bundle_index = self.args_layout.count() - 1  # Index of the last bundle
        if last_bundle_index > 1:  # Ensure that there is at least one bundle left
            last_bundle_layout_item = self.args_layout.takeAt(last_bundle_index)
            last_bundle_layout = last_bundle_layout_item.layout()
            if last_bundle_layout:
                self.clear_layout(last_bundle_layout)  # Clear the last bundle layout
            last_bundle_layout_item.setParent(None)  # Disown layout item
            last_bundle_layout_item.deleteLater()  # Schedule layout item for deletion

        self.window().resize(self.window().sizeHint())  # Resize window to fit contents

    # remove last row of widgets
    # self.args_layout.itemAt(self.args_layout.count() - 1).widget().deleteLater()


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
