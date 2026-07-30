from collections import defaultdict
from types import NoneType, SimpleNamespace
from typing import Optional

from bec_lib.endpoints import MessageEndpoints
from bec_qthemes import material_icon
from pydantic import BaseModel, Field
from qtpy.QtCore import QSignalBlocker, Qt, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme, get_accent_colors
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.control.buttons.stop_button.stop_button import StopButton
from bec_widgets.widgets.control.scan_control.scan_docstring import render_scan_tooltip_html
from bec_widgets.widgets.control.scan_control.scan_group_box import ScanGroupBox
from bec_widgets.widgets.control.scan_control.scan_info_adapter import ScanInfoAdapter
from bec_widgets.widgets.control.scan_control.scan_info_dialog import ScanInfoDialog
from bec_widgets.widgets.control.scan_control.scan_selection_dialog import ScanSelectionDialog
from bec_widgets.widgets.editors.scan_metadata.scan_metadata import ScanMetadata


class ScanParameterConfig(BaseModel):
    name: str
    args: Optional[list] = Field(None)
    kwargs: Optional[dict] = Field(None)


class ScanControlConfig(ConnectionConfig):
    default_scan: Optional[str] = Field(None)
    allowed_scans: Optional[list] = Field(None)
    scans: Optional[dict[str, ScanParameterConfig]] = defaultdict(dict)


class ScanControl(BECWidget, QWidget):
    """
    Widget to submit new scans to the queue.
    """

    USER_ACCESS = ["attach", "detach", "screenshot"]
    PLUGIN = True
    ICON_NAME = "tune"
    ARG_BOX_POSITION: int = 2
    SUPPORTED_SCAN_BASE_CLASSES = {"ScanBase", "SyncFlyScanBase", "AsyncFlyScanBase", "ScanBaseV4"}

    scan_started = Signal()
    scan_selected = Signal(str)
    device_selected = Signal(str)
    scan_args = Signal(list)

    def __init__(
        self,
        parent=None,
        client=None,
        config: ScanControlConfig | dict | None = None,
        gui_id: str | None = None,
        allowed_scans: list | None = None,
        default_scan: str | None = None,
        **kwargs,
    ):
        if config is None:
            config = ScanControlConfig(
                widget_class=self.__class__.__name__, allowed_scans=allowed_scans
            )
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)

        self._hide_add_remove_buttons = False

        # Client from BEC + shortcuts to device manager and scans
        self.get_bec_shortcuts()

        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setAlignment(Qt.AlignTop)
        self.arg_box = None
        self.kwarg_boxes = []
        self.expert_mode = False  # TODO implement in the future versions
        self.previous_scan = None

        # Widget Default Parameters
        self.config.default_scan = default_scan
        if allowed_scans is not None:
            self.config.allowed_scans = allowed_scans

        self._scan_metadata: dict | None = None
        self._metadata_form = ScanMetadata(parent=self)
        self._hide_arg_box = False
        self._hide_kwarg_boxes = False
        self._hide_scan_control_buttons = False
        self._hide_metadata = False
        self._hide_scan_selection_combobox = False
        self._hide_scan_selector_settings_button = False
        self._scan_info_adapter = ScanInfoAdapter()
        self._scan_info_dialog: ScanInfoDialog | None = None

        # Create and set main layout
        self._init_UI()

    def _init_UI(self):
        """
        Initializes the UI of the scan control widget. Create the top box for scan selection and populate scans to main combobox.
        """
        palette = get_accent_colors()
        if palette is None:
            palette = SimpleNamespace(
                default=QColor("blue"),
                success=QColor("green"),
                warning=QColor("orange"),
                emergency=QColor("red"),
            )
        # Scan selection box
        self.scan_selection_group = QWidget(self)
        QVBoxLayout(self.scan_selection_group)
        scan_selection_layout = QHBoxLayout()
        self.comboBox_scan_selection_label = QLabel("Scan:", self.scan_selection_group)
        self.comboBox_scan_selection = QComboBox(self.scan_selection_group)
        self.scan_info_button = QToolButton(self.scan_selection_group)
        self.scan_info_button.setIcon(material_icon("info", size=(20, 20), convert_to_pixmap=False))
        self.scan_info_button.setAutoRaise(True)
        self.scan_info_button.setToolTip("Show information about the selected scan")
        self.scan_info_button.setAccessibleName("Scan information")
        self.scan_selector_settings_button = QToolButton(self.scan_selection_group)
        self.scan_selector_settings_button.setAutoRaise(True)
        self.scan_selector_settings_button.setIcon(
            material_icon("filter_list", size=(20, 20), convert_to_pixmap=False)
        )
        self.scan_selector_settings_button.setToolTip("Choose scans shown in the selector")
        scan_selection_layout.addWidget(self.comboBox_scan_selection_label, 0)
        scan_selection_layout.addWidget(self.comboBox_scan_selection, 1)
        scan_selection_layout.addWidget(self.scan_info_button, 0)
        scan_selection_layout.addWidget(self.scan_selector_settings_button, 0)
        self.scan_selection_group.layout().addLayout(scan_selection_layout)

        # Button to reload the last scan parameters on demand.
        self.last_scan_button = QPushButton(
            "Restore last scan parameters", self.scan_selection_group
        )
        self.last_scan_button.clicked.connect(self.request_last_executed_scan_parameters)
        self.scan_selection_group.layout().addWidget(self.last_scan_button)
        self.scan_selection_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.layout.addWidget(self.scan_selection_group)

        # Scan control (Run/Stop) buttons
        self.scan_control_group = QWidget(self)
        self.scan_control_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        self.button_layout = QHBoxLayout(self.scan_control_group)
        self.button_run_scan = QPushButton("Start", self.scan_control_group)
        self.button_run_scan.setProperty("variant", "success")
        self.button_stop_scan = StopButton(parent=self.scan_control_group)
        self.button_layout.addWidget(self.button_run_scan)
        self.button_layout.addWidget(self.button_stop_scan)
        self.layout.addWidget(self.scan_control_group)

        # Default scan from config
        if self.config.default_scan is not None:
            self.comboBox_scan_selection.setCurrentText(self.config.default_scan)

        # Connect signals
        self.comboBox_scan_selection.view().pressed.connect(self.save_current_scan_parameters)
        self.comboBox_scan_selection.currentIndexChanged.connect(self.on_scan_selection_changed)
        self.scan_info_button.clicked.connect(self.show_selected_scan_info)
        self.scan_selector_settings_button.clicked.connect(self.show_scan_selector_settings)
        self.button_run_scan.clicked.connect(self.run_scan)

        self.scan_selected.connect(self.scan_select)

        # Initialize scan selection
        self.populate_scans()

        # Append metadata form
        self._add_metadata_form()

    def _add_metadata_form(self):
        # Wrap metadata form in a group box
        self._metadata_group = QGroupBox("Scan Metadata", self)
        self._metadata_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        metadata_layout = QVBoxLayout(self._metadata_group)
        metadata_layout.addWidget(self._metadata_form)

        self.layout.addWidget(self._metadata_group)
        self._metadata_form.update_with_new_scan(self.comboBox_scan_selection.currentText())
        self.scan_selected.connect(self._metadata_form.update_with_new_scan)
        self._metadata_form.form_data_updated.connect(self.update_scan_metadata)
        self._metadata_form.form_data_cleared.connect(self.update_scan_metadata)
        self._metadata_form.validate_form()

    def _scan_docstring(self, scan_name: str) -> str | None:
        scan_info = self.available_scans.get(scan_name, {})
        docstring = scan_info.get("doc") if isinstance(scan_info, dict) else None
        return docstring if isinstance(docstring, str) else None

    @SafeSlot()
    @SafeSlot(bool)
    def show_selected_scan_info(self, *_args) -> None:
        """Show documentation for the currently selected scan without blocking the GUI."""
        self.show_scan_info(self.comboBox_scan_selection.currentText())

    @SafeSlot(str)
    def show_scan_info(self, scan_name: str) -> None:
        """Show documentation for a specific scan."""
        if self._scan_info_dialog is None:
            self._scan_info_dialog = ScanInfoDialog(self)
        self._scan_info_dialog.show_scan(scan_name, self._scan_docstring(scan_name))

    def populate_scans(self):
        """Populates the scan selection combo box with available scans from BEC session."""
        self.available_scans = self.client.connector.get(
            MessageEndpoints.available_scans()
        ).resource
        self._update_scan_selector()

    def _supported_scan_names(self) -> list[str]:
        """Return available scans that can be rendered by this widget."""
        return [
            scan_name
            for scan_name, scan_info in self.available_scans.items()
            if scan_info.get("base_class") in self.SUPPORTED_SCAN_BASE_CLASSES
            and self._scan_info_adapter.has_scan_ui_config(scan_info)
            and not scan_name.startswith("_")
        ]

    def _update_scan_selector(self) -> None:
        """Apply the configured scan filter while preserving the current selection."""
        current_scan = self.comboBox_scan_selection.currentText()
        if current_scan:
            self.save_current_scan_parameters()
        allowed_scans = self.allowed_scans
        if allowed_scans is None:
            visible_scans = self._supported_scan_names()
        else:
            # An explicit filter overrides the support filter and keeps the caller's order;
            # entries not currently available stay in the filter and reappear once published.
            visible_scans = [scan for scan in allowed_scans if scan in self.available_scans]

        with QSignalBlocker(self.comboBox_scan_selection):
            self.comboBox_scan_selection.clear()
            self.comboBox_scan_selection.addItems(visible_scans)
            for index, scan_name in enumerate(visible_scans):
                self.comboBox_scan_selection.setItemData(
                    index,
                    render_scan_tooltip_html(scan_name, self._scan_docstring(scan_name)),
                    Qt.ItemDataRole.ToolTipRole,
                )
            if current_scan in visible_scans:
                self.comboBox_scan_selection.setCurrentText(current_scan)

        self.scan_info_button.setEnabled(bool(visible_scans))
        self._update_run_button_state()
        self._update_selected_scan_tooltip()
        if self.comboBox_scan_selection.currentText() != current_scan:
            self.on_scan_selection_changed(self.comboBox_scan_selection.currentIndex())

    def _update_run_button_state(self) -> None:
        """Start requires a selected scan and valid metadata."""
        has_scan = bool(self.comboBox_scan_selection.currentText())
        self.button_run_scan.setEnabled(has_scan and self._scan_metadata is not None)

    def _update_selected_scan_tooltip(self) -> None:
        """Mirror the selected item's documentation tooltip on the closed combo box."""
        index = self.comboBox_scan_selection.currentIndex()
        tooltip = self.comboBox_scan_selection.itemData(index, Qt.ItemDataRole.ToolTipRole)
        self.comboBox_scan_selection.setToolTip(tooltip or "")

    @SafeSlot()
    @SafeSlot(bool)
    def show_scan_selector_settings(self, *_):
        """Open the scan filter dialog and apply accepted changes."""
        scan_names = self._supported_scan_names()
        allowed_scans = self.allowed_scans
        if allowed_scans is not None:
            # Keep configured entries visible in the dialog even when currently unsupported.
            scan_names += [scan for scan in allowed_scans if scan not in scan_names]
        dialog = ScanSelectionDialog(
            scan_names=scan_names,
            selected_scans=scan_names if allowed_scans is None else allowed_scans,
            scan_docs={scan_name: self._scan_docstring(scan_name) for scan_name in scan_names},
            parent=self,
        )
        try:
            selected_scans = (
                dialog.selected_scans() if dialog.exec() == QDialog.DialogCode.Accepted else None
            )
        finally:
            dialog.deleteLater()
        if selected_scans is not None:
            # Everything checked means "no filter", so scans added later show up as well.
            self.allowed_scans = None if selected_scans == scan_names else selected_scans

    @SafeProperty(list)
    def allowed_scans(self) -> list[str] | None:
        """Scan filter for the selector; None shows every supported scan, including future ones."""
        allowed_scans = getattr(self.config, "allowed_scans", None)
        return None if allowed_scans is None else list(allowed_scans)

    @allowed_scans.setter
    def allowed_scans(self, scan_names: list[str] | str | None):
        """Set the scans displayed in the selector; None clears the filter."""
        if isinstance(scan_names, str):
            scan_names = [scan_names]
        if scan_names is not None:
            scan_names = list(dict.fromkeys(scan_names))
        self.config.allowed_scans = scan_names
        self._update_scan_selector()

    @SafeProperty(bool)
    def hide_scan_selector_settings_button(self) -> bool:
        """Whether the button for configuring visible scans is hidden."""
        return self._hide_scan_selector_settings_button

    @hide_scan_selector_settings_button.setter
    def hide_scan_selector_settings_button(self, hide: bool):
        self._hide_scan_selector_settings_button = bool(hide)
        self.scan_selector_settings_button.setVisible(not self._hide_scan_selector_settings_button)

    def on_scan_selection_changed(self, index: int):
        """Callback for scan selection combo box"""
        selected_scan_name = self.comboBox_scan_selection.currentText()
        self._update_selected_scan_tooltip()
        self.scan_selected.emit(selected_scan_name)
        self.restore_scan_parameters(selected_scan_name)

    @SafeSlot()
    @SafeSlot(bool)
    def request_last_executed_scan_parameters(self, *_):
        """
        Requests the last executed scan parameters from BEC and restores them to the scan control widget.
        """
        current_scan = self.comboBox_scan_selection.currentText()
        history = (
            self.client.connector.xread(
                MessageEndpoints.scan_history(), from_start=True, user_id=self.object_name
            )
            or []
        )

        for scan in reversed(history):
            scan_data = scan.get("data")
            if not scan_data:
                continue

            if scan_data.scan_name != current_scan:
                continue

            ri = getattr(scan_data, "request_inputs", {}) or {}
            args_list = ri.get("arg_bundle", [])
            if args_list and self.arg_box:
                self.arg_box.set_parameters(args_list)

            inputs = ri.get("inputs", {})
            kwargs = ri.get("kwargs", {})
            merged = {**inputs, **kwargs}
            if merged and self.kwarg_boxes:
                for box in self.kwarg_boxes:
                    box.set_parameters(merged)
            break

    @SafeProperty(str)
    def current_scan(self):
        """Returns the scan name for the currently selected scan."""
        return self.comboBox_scan_selection.currentText()

    @current_scan.setter
    def current_scan(self, scan_name: str):
        """Sets the current scan to the given scan name.

        Args:
            scan_name(str): Name of the scan to set as current.
        """
        if scan_name not in self.available_scans:
            return
        self.comboBox_scan_selection.setCurrentText(scan_name)

    @SafeSlot(str)
    def set_current_scan(self, scan_name: str):
        """Slot for setting the current scan to the given scan name.

        Args:
            scan_name(str): Name of the scan to set as current.
        """
        self.current_scan = scan_name

    @SafeProperty(bool)
    def hide_arg_box(self):
        """Property to hide the argument box."""
        return self._hide_arg_box

    @hide_arg_box.setter
    def hide_arg_box(self, hide: bool):
        """Setter for the hide_arg_box property.

        Args:
            hide(bool): Hide or show the argument box.
        """
        self._hide_arg_box = hide
        if self.arg_box is not None:
            self.arg_box.setVisible(not hide)

    @SafeProperty(bool)
    def hide_kwarg_boxes(self):
        """Property to hide the keyword argument boxes."""
        return self._hide_kwarg_boxes

    @hide_kwarg_boxes.setter
    def hide_kwarg_boxes(self, hide: bool):
        """Setter for the hide_kwarg_boxes property.

        Args:
            hide(bool): Hide or show the keyword argument boxes.
        """
        self._hide_kwarg_boxes = hide
        if len(self.kwarg_boxes) > 0:
            for box in self.kwarg_boxes:
                box.setVisible(not hide)

    @SafeProperty(bool)
    def hide_scan_control_buttons(self):
        """Property to hide the scan control buttons."""
        return self._hide_scan_control_buttons

    @hide_scan_control_buttons.setter
    def hide_scan_control_buttons(self, hide: bool):
        """Setter for the hide_scan_control_buttons property.

        Args:
            hide(bool): Hide or show the scan control buttons.
        """
        self._hide_scan_control_buttons = hide
        self.show_scan_control_buttons(not hide)

    @SafeProperty(bool)
    def hide_metadata(self):
        """Property to hide the metadata form."""
        return self._hide_metadata

    @hide_metadata.setter
    def hide_metadata(self, hide: bool):
        """Setter for the hide_metadata property.

        Args:
            hide(bool): Hide or show the metadata form.
        """
        self._hide_metadata = hide
        self._metadata_form.setVisible(not hide)

    @SafeProperty(bool)
    def hide_optional_metadata(self):
        """Property to hide the optional metadata form."""
        return self._metadata_form.hide_optional_metadata

    @hide_optional_metadata.setter
    def hide_optional_metadata(self, hide: bool):
        """Setter for the hide_optional_metadata property.

        Args:
            hide(bool): Hide or show the optional metadata form.
        """
        self._metadata_form.hide_optional_metadata = hide

    @SafeSlot(bool)
    def show_scan_control_buttons(self, show: bool):
        """Shows or hides the scan control buttons."""
        self._hide_scan_control_buttons = not show
        self.scan_control_group.setVisible(show)

    @SafeProperty(bool)
    def hide_scan_selection_combobox(self):
        """Property to hide the scan selection combobox."""
        return self._hide_scan_selection_combobox

    @hide_scan_selection_combobox.setter
    def hide_scan_selection_combobox(self, hide: bool):
        """Setter for the hide_scan_selection_combobox property.

        Args:
            hide(bool): Hide or show the scan selection combobox.
        """
        self._hide_scan_selection_combobox = hide
        self.show_scan_selection_combobox(not hide)

    @SafeSlot(bool)
    def show_scan_selection_combobox(self, show: bool):
        """Shows or hides the scan selection combobox."""
        self._hide_scan_selection_combobox = not show
        self.scan_selection_group.setVisible(show)

    @SafeSlot(str)
    def scan_select(self, scan_name: str):
        """
        Slot for scan selection. Updates the scan control layout based on the selected scan.

        Args:
            scan_name(str): Name of the selected scan.
        """
        self.reset_layout()
        selected_scan_info = self.available_scans.get(scan_name, {})

        gui_config = self._scan_info_adapter.build_scan_ui_config(selected_scan_info)
        arg_group = gui_config.get("arg_group", None)
        kwarg_groups = gui_config.get("kwarg_groups", [])

        if arg_group and bool(arg_group.get("arg_inputs")):
            self.add_arg_group(arg_group)
        if kwarg_groups:
            self.add_kwargs_boxes(kwarg_groups)

        self.update()
        self.adjustSize()

    @SafeProperty(bool)
    def hide_add_remove_buttons(self):
        """Property to hide the add_remove buttons."""
        return self._hide_add_remove_buttons

    @hide_add_remove_buttons.setter
    def hide_add_remove_buttons(self, hide: bool):
        """Setter for the hide_add_remove_buttons property.

        Args:
            hide(bool): Hide or show the add_remove buttons.
        """
        self._hide_add_remove_buttons = hide
        if self.arg_box is not None:
            self.arg_box.hide_add_remove_buttons = hide

    def add_kwargs_boxes(self, groups: list):
        """
        Adds the given gui_groups to the scan control layout.

        Args:
            groups(list): List of dictionaries containing the gui_group information.
        """
        position = self.ARG_BOX_POSITION + (1 if self.arg_box is not None else 0)
        for group in groups:
            box = ScanGroupBox(box_type="kwargs", config=group)
            box.reference_units_changed.connect(self._apply_reference_units_to_other_boxes)
            self.layout.insertWidget(position + len(self.kwarg_boxes), box)
            self.kwarg_boxes.append(box)
            box.setVisible(not self._hide_kwarg_boxes)

    def add_arg_group(self, group: dict):
        """
        Adds the given gui_groups to the scan control layout.

        Args:
        """
        self.arg_box = ScanGroupBox(box_type="args", config=group)
        self.arg_box.device_selected.connect(self.emit_device_selected)
        self.arg_box.reference_units_changed.connect(self._apply_reference_units_to_other_boxes)
        self.arg_box.hide_add_remove_buttons = self._hide_add_remove_buttons
        self.layout.insertWidget(self.ARG_BOX_POSITION, self.arg_box)
        self.arg_box.setVisible(not self._hide_arg_box)

    def _scan_group_boxes(self) -> list[ScanGroupBox]:
        boxes = []
        if self.arg_box is not None:
            boxes.append(self.arg_box)
        boxes.extend(self.kwarg_boxes)
        return boxes

    def _apply_reference_units_to_other_boxes(
        self, source_box: ScanGroupBox, reference_name: str, units: str | None
    ) -> None:
        """
        Propagate device-derived units to scan fields that reference a device in another group.
        """
        for box in self._scan_group_boxes():
            if box is source_box:
                continue
            box.apply_reference_units(reference_name, units)

    @SafeSlot(str)
    def emit_device_selected(self, dev_names):
        """
        Emit the signal to inform about selected device(s)

        "dev_names" is a string separated by space, in case of multiple devices
        """
        self._selected_devices = dev_names
        self.device_selected.emit(dev_names)

    def reset_layout(self):
        """Clears the scan control layout from GuiGroups and ArgGroups boxes."""
        if self.arg_box is not None:
            self.layout.removeWidget(self.arg_box)
            self.arg_box.close()
            self.arg_box.deleteLater()
            self.arg_box = None
        if self.kwarg_boxes != []:
            self.remove_kwarg_boxes()

    def remove_kwarg_boxes(self):
        for box in self.kwarg_boxes:
            self.layout.removeWidget(box)
            box.close()
            box.deleteLater()
        self.kwarg_boxes = []

    def get_scan_parameters(self, bec_object: bool = True):
        """
        Returns the scan parameters for the selected scan.

        Args:
            bec_object(bool): If True, returns the BEC object for the scan parameters such as device objects.
        """
        args = []
        kwargs = {}
        if self.arg_box is not None:
            args = self.arg_box.get_parameters(bec_object)
        for box in self.kwarg_boxes:
            box_kwargs = box.get_parameters(bec_object)
            kwargs.update(box_kwargs)
        if self._scan_metadata is not None:
            kwargs["metadata"] = self._scan_metadata
        return args, kwargs

    def restore_scan_parameters(self, scan_name: str):
        """
        Restores the scan parameters for the given scan name

        Args:
            scan_name(str): Name of the scan to restore the parameters for.
        """
        scan_params = self.config.scans.get(scan_name, None)
        if scan_params is None and self.previous_scan is None:
            return

        if scan_params is None and self.previous_scan is not None:
            previous_scan_params = self.config.scans.get(self.previous_scan, None)
            self._restore_kwargs(previous_scan_params.kwargs)
            return

        if scan_params.args is not None and self.arg_box is not None:
            self.arg_box.set_parameters(scan_params.args)

        self._restore_kwargs(scan_params.kwargs)

    def _restore_kwargs(self, scan_kwargs: dict):
        """Restores the kwargs for the given scan parameters."""
        if scan_kwargs is not None and self.kwarg_boxes is not None:
            for box in self.kwarg_boxes:
                box.set_parameters(scan_kwargs)

    def save_current_scan_parameters(self):
        """Saves the current scan parameters to the scan control config for further use."""
        scan_name = self.comboBox_scan_selection.currentText()
        self.previous_scan = scan_name
        args, kwargs = self.get_scan_parameters(False)
        scan_params = ScanParameterConfig(name=scan_name, args=args, kwargs=kwargs)
        self.config.scans[scan_name] = scan_params

    @SafeSlot(dict)
    @SafeSlot(NoneType)
    def update_scan_metadata(self, md: dict | None):
        self._scan_metadata = md
        self._update_run_button_state()

    @SafeSlot(popup_error=True)
    def run_scan(self):
        """Starts the selected scan with the given parameters."""
        scan_name = self.comboBox_scan_selection.currentText()
        if not scan_name:
            return
        args, kwargs = self.get_scan_parameters()
        self.scan_args.emit(args)
        scan_function = getattr(self.scans, scan_name)
        if callable(scan_function):
            self.scan_started.emit()
            scan_function(*args, **kwargs)

    def cleanup(self):
        """Cleanup the scan control widget."""
        if self._scan_info_dialog is not None:
            self._scan_info_dialog.close()
            self._scan_info_dialog.deleteLater()
            self._scan_info_dialog = None
        super().cleanup()


# Application example
if __name__ == "__main__":  # pragma: no cover
    app = QApplication([])
    scan_control = ScanControl()

    apply_theme("dark")
    window = scan_control
    window.show()
    app.exec()
