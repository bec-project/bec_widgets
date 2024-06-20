import qdarktheme
from bec_lib.endpoints import MessageEndpoints
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils import BECConnector
from bec_widgets.widgets.buttons.stop_button.stop_button import StopButton
from bec_widgets.widgets.scan_control.scan_group_box import ScanGroupBox


class ScanControl(BECConnector, QWidget):

    def __init__(
        self, parent=None, client=None, gui_id: str | None = None, allowed_scans: list | None = None
    ):
        super().__init__(client=client, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)

        # Client from BEC + shortcuts to device manager and scans
        self.get_bec_shortcuts()

        # Main layout
        self.layout = QVBoxLayout(self)
        self.arg_box = None
        self.kwarg_boxes = []
        self.expert_mode = False  # TODO implement in the future versions

        # Scan list - allowed scans for the GUI
        self.allowed_scans = allowed_scans

        # Create and set main layout
        self._init_UI()

    def _init_UI(self):
        """
        Initializes the UI of the scan control widget. Create the top box for scan selection and populate scans to main combobox.
        """

        # Scan selection group box
        self.scan_selection_group = self.create_scan_selection_group()
        self.scan_selection_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.layout.addWidget(self.scan_selection_group)

        # Connect signals
        self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selected)
        self.button_run_scan.clicked.connect(self.run_scan)
        self.button_add_bundle.clicked.connect(self.add_arg_bundle)
        self.button_remove_bundle.clicked.connect(self.remove_arg_bundle)

        # Initialize scan selection
        self.populate_scans()

    def create_scan_selection_group(self) -> QGroupBox:
        """
        Creates the scan selection group box with combobox to select the scan and start/stop button.

        Returns:
            QGroupBox: Group box containing the scan selection widgets.
        """

        scan_selection_group = QGroupBox("Scan Selection", self)
        self.scan_selection_layout = QGridLayout(scan_selection_group)
        self.comboBox_scan_selection = QComboBox(scan_selection_group)
        # Run button
        self.button_run_scan = QPushButton("Start", scan_selection_group)
        self.button_run_scan.setStyleSheet("background-color:  #559900; color: white")
        # Stop button
        self.button_stop_scan = StopButton(parent=scan_selection_group)
        # Add bundle button
        self.button_add_bundle = QPushButton("Add Bundle", scan_selection_group)
        # Remove bundle button
        self.button_remove_bundle = QPushButton("Remove Bundle", scan_selection_group)

        self.scan_selection_layout.addWidget(self.comboBox_scan_selection, 0, 0, 1, 2)
        self.scan_selection_layout.addWidget(self.button_run_scan, 1, 0)
        self.scan_selection_layout.addWidget(self.button_stop_scan, 1, 1)
        self.scan_selection_layout.addWidget(self.button_add_bundle, 2, 0)
        self.scan_selection_layout.addWidget(self.button_remove_bundle, 2, 1)

        return scan_selection_group

    def populate_scans(self):
        """Populates the scan selection combo box with available scans from BEC session."""
        self.available_scans = self.client.connector.get(
            MessageEndpoints.available_scans()
        ).resource
        if self.allowed_scans is None:
            supported_scans = ["ScanBase", "SyncFlyScanBase", "AsyncFlyScanBase"]
            allowed_scans = [
                scan_name
                for scan_name, scan_info in self.available_scans.items()
                if scan_info["base_class"] in supported_scans and len(scan_info["gui_config"]) > 0
            ]

        else:
            allowed_scans = self.allowed_scans
        self.comboBox_scan_selection.addItems(allowed_scans)

    def on_scan_selected(self):
        """Callback for scan selection combo box"""
        self.reset_layout()
        selected_scan_name = self.comboBox_scan_selection.currentText()
        selected_scan_info = self.available_scans.get(selected_scan_name, {})

        gui_config = selected_scan_info.get("gui_config", {})
        self.arg_group = gui_config.get("arg_group", None)
        self.kwarg_groups = gui_config.get("kwarg_groups", None)

        if self.arg_box is None:
            self.button_add_bundle.setEnabled(False)
            self.button_remove_bundle.setEnabled(False)

        if len(self.arg_group["arg_inputs"]) > 0:
            self.button_add_bundle.setEnabled(True)
            self.button_remove_bundle.setEnabled(True)
            self.add_arg_group(self.arg_group)  # TODO here class method for arg box
        if len(self.kwarg_groups) > 0:
            self.add_kwargs_boxes(self.kwarg_groups)

        self.update()
        self.adjustSize()

    def add_kwargs_boxes(self, groups: list):
        """
        Adds the given gui_groups to the scan control layout.

        Args:
            groups(list): List of dictionaries containing the gui_group information.
        """
        for group in groups:
            box = ScanGroupBox(box_type="kwargs", config=group)
            box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            self.layout.addWidget(box)
            self.kwarg_boxes.append(box)

    def add_arg_group(self, group: dict):
        """
        Adds the given gui_groups to the scan control layout.

        Args:
        """
        self.arg_box = ScanGroupBox(box_type="args", config=group)
        self.arg_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.layout.addWidget(self.arg_box)

    def add_arg_bundle(self):
        self.arg_box.add_widget_bundle()

    def remove_arg_bundle(self):
        self.arg_box.remove_widget_bundle()

    def reset_layout(self):
        """Clears the scan control layout from GuiGroups and ArgGroups boxes."""
        if self.arg_box is not None:
            self.layout.removeWidget(self.arg_box)
            self.arg_box.deleteLater()
            self.arg_box = None
        if self.kwarg_boxes != []:
            self.remove_kwarg_boxes()

    def remove_kwarg_boxes(self):
        for box in self.kwarg_boxes:
            self.layout.removeWidget(box)
            box.deleteLater()
        self.kwarg_boxes = []

    def run_scan(self):
        args = []
        kwargs = {}
        if self.arg_box is not None:
            args = self.arg_box.get_parameters()
        for box in self.kwarg_boxes:
            box_kwargs = box.get_parameters()
            kwargs.update(box_kwargs)
        scan_function = getattr(self.scans, self.comboBox_scan_selection.currentText())
        if callable(scan_function):
            scan_function(*args, **kwargs)

    def close(self):
        super().close()


# Application example
if __name__ == "__main__":  # pragma: no cover
    app = QApplication([])
    scan_control = ScanControl()

    qdarktheme.setup_theme("auto")
    window = scan_control
    window.show()
    app.exec()
