from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.scan_control.scan_group_box import ScanGroupBox
from bec_widgets.widgets.stop_button.stop_button import StopButton


class ScanControl(BECWidget, QWidget):

    scan_started = Signal()
    scan_selected = Signal(str)

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
        self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selection_changed)
        self.button_run_scan.clicked.connect(self.run_scan)

        # Add bundle button
        self.button_add_bundle = QPushButton("Add Bundle")
        self.button_add_bundle.setVisible(False)
        # Remove bundle button
        self.button_remove_bundle = QPushButton("Remove Bundle")
        self.button_remove_bundle.setVisible(False)

        bundle_layout = QHBoxLayout()
        bundle_layout.addWidget(self.button_add_bundle)
        bundle_layout.addWidget(self.button_remove_bundle)
        self.layout.addLayout(bundle_layout)

        self.button_add_bundle.clicked.connect(self.add_arg_bundle)
        self.button_remove_bundle.clicked.connect(self.remove_arg_bundle)

        self.scan_selected.connect(self.scan_select)

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

        self.scan_selection_layout.addWidget(self.comboBox_scan_selection, 0, 0, 1, 2)
        self.scan_selection_layout.addWidget(self.button_run_scan, 1, 0)
        self.scan_selection_layout.addWidget(self.button_stop_scan, 1, 1)

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

    def on_scan_selection_changed(self, index: int):
        """Callback for scan selection combo box"""
        selected_scan_name = self.comboBox_scan_selection.currentText()
        self.scan_selected.emit(selected_scan_name)

    @Property(bool)
    def hide_scan_control_buttons(self):
        return not self.button_run_scan.isVisible()

    @hide_scan_control_buttons.setter
    def hide_scan_control_buttons(self, hide: bool):
        self.show_scan_control_buttons(not hide)

    @Slot(bool)
    def show_scan_control_buttons(self, show: bool):
        """Shows or hides the scan control buttons."""
        self.button_run_scan.setVisible(show)
        self.button_stop_scan.setVisible(show)

        show_group = show or self.button_run_scan.isVisible()
        self.scan_selection_group.setVisible(show_group)

    @Property(bool)
    def hide_scan_selection_combobox(self):
        return not self.comboBox_scan_selection.isVisible()

    @hide_scan_selection_combobox.setter
    def hide_scan_selection_combobox(self, hide: bool):
        self.show_scan_selection_combobox(not hide)

    @Slot(bool)
    def show_scan_selection_combobox(self, show: bool):
        """Shows or hides the scan selection combobox."""
        self.comboBox_scan_selection.setVisible(show)

        show_group = show or self.button_run_scan.isVisible()
        self.scan_selection_group.setVisible(show_group)

    @Slot(str)
    def scan_select(self, scan_name: str):
        """
        Slot for scan selection. Updates the scan control layout based on the selected scan.

        Args:
            scan_name(str): Name of the selected scan.
        """
        self.reset_layout()
        selected_scan_info = self.available_scans.get(scan_name, {})

        gui_config = selected_scan_info.get("gui_config", {})
        self.arg_group = gui_config.get("arg_group", None)
        self.kwarg_groups = gui_config.get("kwarg_groups", None)

        show_bundle_buttons = bool(self.arg_group["arg_inputs"])

        self.button_add_bundle.setVisible(show_bundle_buttons)
        self.button_remove_bundle.setVisible(show_bundle_buttons)

        if show_bundle_buttons:
            self.add_arg_group(self.arg_group)
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

    @Slot()
    def add_arg_bundle(self):
        self.arg_box.add_widget_bundle()

    @Slot()
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

    @Slot()
    def run_scan(self):
        self.scan_started.emit()
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

    def cleanup(self):
        self.button_stop_scan.cleanup()
        if self.arg_box:
            for widget in self.arg_box.widgets:
                if hasattr(widget, "cleanup"):
                    widget.cleanup()
        for kwarg_box in self.kwarg_boxes:
            for widget in kwarg_box.widgets:
                if hasattr(widget, "cleanup"):
                    widget.cleanup()
        super().cleanup()


# Application example
if __name__ == "__main__":  # pragma: no cover
    from bec_widgets.utils.colors import set_theme

    app = QApplication([])
    scan_control = ScanControl()

    set_theme("auto")
    window = scan_control
    window.show()
    app.exec()
