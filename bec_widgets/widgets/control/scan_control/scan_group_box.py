from typing import Literal, Sequence

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy.QtCore import Property, Qt, Signal, Slot
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.flow_layout import FlowLayoutWidget
from bec_widgets.utils.scan_arg_metadata import (
    apply_numeric_limits,
    apply_numeric_precision,
    apply_unit_metadata,
    device_units,
)
from bec_widgets.utils.widget_io import WidgetIO
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import (
    BECDeviceFilter,
    DeviceComboBox,
)

logger = bec_logger.logger


class ScanArgType:
    DEVICE = "device"
    FLOAT = "float"
    INT = "int"
    BOOL = "bool"
    STR = "str"
    DEVICEBASE = "DeviceBase"
    LITERALS_DICT = "dict"  # Used when the type is provided as a dict with Literal key


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")

        layout = QFormLayout()

        self.precision_spin_box = QSpinBox()
        self.precision_spin_box.setRange(
            -2147483647, 2147483647
        )  # 2147483647 is the largest int which qt allows

        self.step_size_spin_box = QDoubleSpinBox()
        self.step_size_spin_box.setRange(-float("inf"), float("inf"))

        fixed_width = 80
        self.precision_spin_box.setFixedWidth(fixed_width)
        self.step_size_spin_box.setFixedWidth(fixed_width)

        layout.addRow("Decimal Precision:", self.precision_spin_box)
        layout.addRow("Step Size:", self.step_size_spin_box)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def getValues(self):
        return self.precision_spin_box.value(), self.step_size_spin_box.value()


class ScanSpinBox(QSpinBox):
    def __init__(
        self, parent=None, arg_name: str = None, default: int | None = None, *args, **kwargs
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.arg_name = arg_name
        self.setRange(-2147483647, 2147483647)  # 2147483647 is the largest int which qt allows
        if default is not None:
            self.setValue(default)


class ScanLiteralsComboBox(QComboBox):
    def __init__(
        self, parent=None, arg_name: str | None = None, default: str | None = None, *args, **kwargs
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.arg_name = arg_name
        self.default = default
        if default is not None:
            self.setCurrentText(default)

    def set_literals(self, literals: Sequence[str | int | float | None]) -> None:
        """
        Set the list of literals for the combo box.

        Args:
            literals: List of literal values (can be strings, integers, floats or None)
        """
        self.clear()
        literals = set(literals)  # Remove duplicates
        if None in literals:
            literals.remove(None)
            self.addItem("")

        self.addItems([str(value) for value in literals])

        # find index of the default value
        index = max(self.findText(str(self.default)), 0)
        self.setCurrentIndex(index)

    def get_value(self) -> str | None:
        return self.currentText() if self.currentText() else None


class ScanDoubleSpinBox(QDoubleSpinBox):
    def __init__(
        self, parent=None, arg_name: str = None, default: float | None = None, *args, **kwargs
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.arg_name = arg_name
        self.setRange(-float("inf"), float("inf"))
        if default is not None:
            self.setValue(default)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showSettingsDialog)

        self.setToolTip("Right click to open settings dialog for decimal precision and step size.")

    def showSettingsDialog(self):
        dialog = SettingsDialog(self)
        dialog.precision_spin_box.setValue(self.decimals())
        dialog.step_size_spin_box.setValue(self.singleStep())

        if dialog.exec_() == QDialog.Accepted:
            precision, step_size = dialog.getValues()
            self.setDecimals(precision)
            self.setSingleStep(step_size)


class ScanLineEdit(QLineEdit):
    def __init__(
        self, parent=None, arg_name: str = None, default: str | None = None, *args, **kwargs
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.arg_name = arg_name
        if default is not None:
            self.setText(default)


class ScanCheckBox(QCheckBox):
    def __init__(
        self, parent=None, arg_name: str = None, default: bool | None = None, *args, **kwargs
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.arg_name = arg_name
        if default is not None:
            self.setChecked(default)


class ScanGroupBox(QGroupBox):
    WIDGET_HANDLER = {
        ScanArgType.DEVICE: DeviceComboBox,
        ScanArgType.DEVICEBASE: DeviceComboBox,
        ScanArgType.FLOAT: ScanDoubleSpinBox,
        ScanArgType.INT: ScanSpinBox,
        ScanArgType.BOOL: ScanCheckBox,
        ScanArgType.STR: ScanLineEdit,
        ScanArgType.LITERALS_DICT: ScanLiteralsComboBox,
    }

    device_selected = Signal(str)
    reference_units_changed = Signal(object, str, object)

    def __init__(
        self,
        parent=None,
        box_type=Literal["args", "kwargs"],
        config: dict | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(parent=parent, *args, **kwargs)
        self.config = config
        self.box_type = box_type
        self._hide_add_remove_buttons = False

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(6, 6, 6, 6)
        hbox_layout = QHBoxLayout()
        self._root_layout.addLayout(hbox_layout)
        self._bundles_layout = QVBoxLayout()
        self._bundles_layout.setContentsMargins(0, 0, 0, 0)
        self._bundles_layout.setSpacing(8)
        self._root_layout.addLayout(self._bundles_layout)

        # Add bundle button
        self.button_add_bundle = QPushButton(self)
        self.button_add_bundle.setIcon(
            material_icon(icon_name="add", size=(15, 15), convert_to_pixmap=False)
        )
        # Remove bundle button
        self.button_remove_bundle = QPushButton(self)
        self.button_remove_bundle.setIcon(
            material_icon(icon_name="remove", size=(15, 15), convert_to_pixmap=False)
        )
        hbox_layout.addWidget(self.button_add_bundle)
        hbox_layout.addWidget(self.button_remove_bundle)

        self.labels = []
        self.widgets = []
        self._widget_configs = {}
        self._widget_labels = {}
        self._widget_bundle_indexes = {}
        self._bundle_widgets = []
        self._bundle_containers = []
        self.selected_devices = {}

        self.init_box(self.config)

        self.button_add_bundle.clicked.connect(self.add_widget_bundle)
        self.button_remove_bundle.clicked.connect(self.remove_widget_bundle)

    # NOTE: no sizing overrides are needed. Qt propagates height-for-width natively
    # (FlowLayout -> FlowLayoutWidget -> QVBoxLayout -> QGroupBox): QWidgetItem consults
    # layout()->totalHeightForWidth(), which already includes the title-aware group box
    # margins. Host layouts should top-align or stretch below the box; ScanControl uses
    # layout.setAlignment(Qt.AlignTop).

    def init_box(self, config: dict):
        box_name = config.get("name", "ScanGroupBox")
        self.inputs = config.get("inputs", {})
        self.setTitle(box_name)

        if self.box_type == "args":
            min_bundle = self.config.get("min", 1)
            for _ in range(1, min_bundle + 1):
                self.add_input_widgets(self.inputs)
        else:
            self.add_input_widgets(self.inputs)
            self.button_add_bundle.setVisible(False)
            self.button_remove_bundle.setVisible(False)

    def add_input_widgets(self, group_inputs: dict) -> None:
        """
        Adds the given arg_group from arg_bundle to the scan control layout.

        Args:
            group_inputs(dict): Dictionary containing the arg_group information.
        """
        bundle_index = len(self._bundle_widgets)
        bundle_container = FlowLayoutWidget(
            self,
            horizontal_spacing=8,
            vertical_spacing=8,
            minimum_item_width=130,
            normalize_item_sizes=True,
        )
        bundle_layout = bundle_container.flow_layout
        bundle_widgets = []
        self._bundles_layout.addWidget(bundle_container)
        self._bundle_containers.append(bundle_container)
        self._bundle_widgets.append(bundle_widgets)

        for item in group_inputs:
            arg_name = item.get("name", None)
            default = item.get("default", None)
            item_type = item.get("type", None)
            if isinstance(item_type, dict) and "Literal" in item_type:
                widget_class = self.WIDGET_HANDLER.get(ScanArgType.LITERALS_DICT, None)
            else:
                widget_class = self.WIDGET_HANDLER.get(item["type"], None)
            if widget_class is None:
                logger.error(
                    f"Unsupported annotation '{item['type']}' for parameter '{item['name']}'"
                )
                continue
            if default == "_empty":
                default = None
            if widget_class is DeviceComboBox:
                widget = widget_class(
                    parent=self.parent(),
                    arg_name=arg_name,
                    default=default,
                    device_filter=BECDeviceFilter.DEVICE,
                    include_signals_with_write_access=True,
                    autocomplete=True,
                )
            else:
                widget = widget_class(parent=self.parent(), arg_name=arg_name, default=default)
            apply_numeric_precision(widget, item)
            apply_numeric_limits(widget, item)
            if isinstance(widget, DeviceComboBox):
                self.selected_devices[widget] = ""
                widget.device_selected.connect(self.emit_device_selected)
                widget.currentTextChanged.connect(
                    lambda text, device_widget=widget: self._handle_device_text_changed(
                        device_widget, text
                    )
                )
            if isinstance(widget, ScanLiteralsComboBox):
                widget.set_literals(item["type"].get("Literal", []))
            self._widget_configs[widget] = item
            apply_unit_metadata(widget, item)

            label = QLabel(text=item.get("display_name", item.get("name", None)), parent=self)
            label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            tile = QWidget(bundle_container)
            tile.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(0, 0, 0, 0)
            tile_layout.setSpacing(2)
            tile_layout.addWidget(label)
            tile_layout.addWidget(widget)
            bundle_layout.addWidget(tile)

            self.labels.append(label)
            self.widgets.append(widget)
            bundle_widgets.append(widget)
            self._widget_labels[widget] = label
            self._widget_bundle_indexes[widget] = bundle_index

    @Slot(str)
    def emit_device_selected(self, device_name):
        sender = self.sender()
        self.selected_devices[sender] = device_name.strip()
        if isinstance(sender, DeviceComboBox):
            units = device_units(sender.get_current_device())
            self._update_reference_units(sender, units)
            self._emit_reference_units_changed(sender, units)
        selected_devices_str = " ".join(self.selected_devices.values())
        self.device_selected.emit(selected_devices_str)

    def add_widget_bundle(self):
        """
        Adds a new row of widgets to the scan control layout. Only usable for arg_groups.
        """
        arg_max = self.config.get("max", None)
        if arg_max is not None and self.count_arg_rows() >= arg_max:
            return

        self.add_input_widgets(self.inputs)

    def remove_widget_bundle(self):
        """
        Removes the last row of widgets from the scan control layout. Only usable for arg_groups.
        """
        arg_min = self.config.get("min", None)
        row = self.count_arg_rows()
        if row <= 0:
            return
        if arg_min is not None and row <= arg_min:
            return

        self._remove_bundle(row - 1)

        selected_devices_str = " ".join(self.selected_devices.values())
        self.device_selected.emit(selected_devices_str.strip())

    def remove_all_widget_bundles(self):
        """Remove every widget bundle from the scan control layout."""
        while self._bundle_widgets:
            self._remove_bundle(len(self._bundle_widgets) - 1)
        self.device_selected.emit("")

    def _remove_bundle(self, bundle_index: int) -> None:
        bundle_widgets = self._bundle_widgets.pop(bundle_index)
        bundle_container = self._bundle_containers.pop(bundle_index)

        for widget in bundle_widgets:
            if isinstance(widget, DeviceComboBox):
                self.selected_devices.pop(widget, None)
            self._widget_configs.pop(widget, None)
            label = self._widget_labels.pop(widget, None)
            if label in self.labels:
                self.labels.remove(label)
            self._widget_bundle_indexes.pop(widget, None)
            if widget in self.widgets:
                self.widgets.remove(widget)
            widget.close()
            widget.deleteLater()

        self._bundles_layout.removeWidget(bundle_container)
        bundle_container.close()
        bundle_container.deleteLater()

        for widget, index in list(self._widget_bundle_indexes.items()):
            if index > bundle_index:
                self._widget_bundle_indexes[widget] = index - 1

    @Property(bool)
    def hide_add_remove_buttons(self):
        return self._hide_add_remove_buttons

    @hide_add_remove_buttons.setter
    def hide_add_remove_buttons(self, hide: bool):
        self._hide_add_remove_buttons = hide
        if not hide and self.box_type == "args":
            self.button_add_bundle.show()
            self.button_remove_bundle.show()
            return
        self.button_add_bundle.hide()
        self.button_remove_bundle.hide()

    def get_parameters(self, device_object: bool = True):
        """
        Returns the parameters from the widgets in the scan control layout formatted to run scan from BEC.
        """
        if self.box_type == "args":
            return self._get_arg_parameters(device_object=device_object)
        elif self.box_type == "kwargs":
            return self._get_kwarg_parameters(device_object=device_object)

    def _get_arg_parameters(self, device_object: bool = True):
        args = []
        for bundle_widgets in self._bundle_widgets:
            for widget in bundle_widgets:
                if isinstance(widget, DeviceComboBox) and device_object:
                    value = widget.get_current_device()
                elif isinstance(widget, DeviceComboBox):
                    value = widget.currentText()
                else:
                    value = WidgetIO.get_value(widget)
                args.append(value)
        return args

    def _get_kwarg_parameters(self, device_object: bool = True):
        kwargs = {}
        for widget in self.widgets:
            if isinstance(widget, DeviceComboBox) and device_object:
                value = widget.get_current_device().name
            elif isinstance(widget, DeviceComboBox):
                value = widget.currentText()
            elif isinstance(widget, ScanLiteralsComboBox):
                value = widget.get_value()
            else:
                value = WidgetIO.get_value(widget)
            kwargs[widget.arg_name] = value
        return kwargs

    def count_arg_rows(self):
        return len(self._bundle_widgets)

    def label_for_widget(self, widget) -> QLabel | None:
        """Return the label paired with a scan input widget."""
        return self._widget_labels.get(widget)

    def label_texts(self) -> list[str]:
        """Return labels in the same order as ``widgets``."""
        return [
            self._widget_labels[widget].text()
            for widget in self.widgets
            if widget in self._widget_labels
        ]

    def get_bundle_widgets(self, index: int) -> list[QWidget]:
        """Return input widgets for a positional-argument bundle."""
        return list(self._bundle_widgets[index])

    def set_parameters(self, parameters: list | dict):
        if self.box_type == "args":
            self._set_arg_parameters(parameters)
        elif self.box_type == "kwargs":
            self._set_kwarg_parameters(parameters)

    def _set_arg_parameters(self, parameters: list):
        self.remove_all_widget_bundles()
        if not parameters:
            return

        inputs_per_bundle = len(self.inputs)
        if inputs_per_bundle == 0:
            return

        bundles_needed = -(-len(parameters) // inputs_per_bundle)

        for _ in range(bundles_needed):
            self.add_input_widgets(self.inputs)

        for i, value in enumerate(parameters):
            WidgetIO.set_value(self.widgets[i], value)

    def _set_kwarg_parameters(self, parameters: dict):
        for widget in self.widgets:
            for key, value in parameters.items():
                if widget.arg_name == key:
                    WidgetIO.set_value(widget, value)
                    break

    def _refresh_widget_label(self, widget, item: dict) -> None:
        label = self._widget_labels.get(widget)
        if label is None:
            return
        label.setText(item.get("display_name", item.get("name", None)))

    def _update_reference_units(self, device_widget: DeviceComboBox, units: str | None) -> None:
        source_bundle = self._widget_bundle_indexes.get(device_widget)
        if source_bundle is None:
            return
        source_name = device_widget.arg_name

        for widget in self.widgets:
            item = self._widget_configs.get(widget, {})
            if item.get("reference_units") != source_name:
                continue
            if self.box_type == "args" and self._widget_bundle_indexes.get(widget) != source_bundle:
                continue
            apply_unit_metadata(widget, item, units)
            self._refresh_widget_label(widget, item)

    def apply_reference_units(self, reference_name: str, units: str | None) -> None:
        """
        Apply units to widgets that reference an argument owned by another group box.

        Cross-box references only have one widget row, so row scoping is intentionally handled by
        the source group before this method is called.
        """
        for widget in self.widgets:
            item = self._widget_configs.get(widget, {})
            if item.get("reference_units") != reference_name:
                continue
            apply_unit_metadata(widget, item, units)
            self._refresh_widget_label(widget, item)

    def _emit_reference_units_changed(
        self, device_widget: DeviceComboBox, units: str | None
    ) -> None:
        reference_name = getattr(device_widget, "arg_name", None)
        if not reference_name:
            return
        self.reference_units_changed.emit(self, reference_name, units)

    def _handle_device_text_changed(self, device_widget: DeviceComboBox, device_name: str) -> None:
        if not device_widget.validate_device(device_name):
            self.selected_devices[device_widget] = ""
            self._update_reference_units(device_widget, None)
            self._emit_reference_units_changed(device_widget, None)
