from __future__ import annotations

import slugify
from bec_lib import bl_states
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.forms_from_types.pydantic_widget_form import PydanticWidgetForm
from bec_widgets.utils.name_utils import pascal_to_snake
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox

BEAMLINE_STATE_STATUS_LABELS = {
    "valid": "VALID",
    "invalid": "INVALID",
    "warning": "WARNING",
    "unknown": "UNKNOWN",
}

SUPPORTED_BEAMLINE_STATES: tuple[type[bl_states.BeamlineState], ...] = (
    bl_states.DeviceWithinLimitsState,
    bl_states.ShutterState,
)


class AddBeamlineStateDialog(QDialog):
    """Dialog for creating supported beamline state configurations."""

    def __init__(self, parent: QWidget | None = None, client=None) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("Add Beamline State")
        self._cleaned_up = False
        self._client = client
        self._config: bl_states.BeamlineStateConfig | None = None
        self._auto_generated_name: str | None = None

        self._type_combo = QComboBox(self)
        for state_class in SUPPORTED_BEAMLINE_STATES:
            self._type_combo.addItem(state_class.__name__, state_class)
        self._type_combo.currentIndexChanged.connect(self._update_config_form)

        self._form = QFormLayout()
        self._form.addRow("State type", self._type_combo)
        self._config_form_host = QVBoxLayout()
        self._config_form: PydanticWidgetForm | None = None

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)
        layout.addLayout(self._config_form_host)
        layout.addWidget(self._buttons)
        self.setLayout(layout)
        self._update_config_form()
        self._fit_to_contents()

    def config(self) -> bl_states.BeamlineStateConfig:
        state_class = self._selected_state_class()
        config_class = state_class.CONFIG_CLASS
        name = self._state_name()
        data = self._config_form.get_data()
        data["name"] = name
        return config_class.model_validate(data)

    def accept(self) -> None:
        try:
            self._config = self.config()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid Beamline State", str(exc))
            return
        super().accept()

    @property
    def config_result(self) -> bl_states.BeamlineStateConfig:
        if self._config is None:
            raise RuntimeError("Beamline state dialog was not accepted with a valid config.")
        return self._config

    def cleanup(self) -> None:
        if self._cleaned_up:
            return
        self._cleaned_up = True
        if self._config_form is not None:
            self._config_form.cleanup()
            self._config_form.close()
            self._config_form.deleteLater()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.cleanup()
        super().closeEvent(event)

    @SafeSlot(str)
    def _on_valid_device_selected(self, device: str) -> None:
        if self._cleaned_up:
            return
        name_widget = self._config_form.input_widget("name")
        current_name = name_widget.text().strip()
        if current_name and current_name != self._auto_generated_name:
            return
        suffix = slugify.slugify(
            pascal_to_snake(self._selected_state_class().__name__), separator="_"
        )
        generated_name = f"{slugify.slugify(device, separator='_')}_{suffix}"
        self._auto_generated_name = generated_name
        name_widget.setText(generated_name)

    @SafeSlot(int)
    def _update_config_form(self, _index: int = 0) -> None:
        previous_data = self._config_form.raw_data() if self._config_form is not None else {}
        if self._config_form is not None:
            self._config_form_host.removeWidget(self._config_form)
            self._config_form.cleanup()
            self._config_form.setParent(None)
            self._config_form.deleteLater()
        config_class = self._selected_state_class().CONFIG_CLASS
        data = {
            key: value
            for key, value in previous_data.items()
            if key in config_class.model_fields and value is not None
        }
        self._config_form = PydanticWidgetForm(config_class, parent=self, client=self._client)
        self._config_form.set_partial_data(data)
        self._config_form_host.addWidget(self._config_form)
        for device_widget in self._config_form.input_widgets_by_type(DeviceComboBox):
            device_widget.device_selected.connect(self._on_valid_device_selected)
        self._fit_to_contents()

    def _fit_to_contents(self) -> None:
        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.layout().activate()
        self.setFixedSize(self.sizeHint().expandedTo(self.minimumSizeHint()))

    def _selected_state_class(self) -> type[bl_states.BeamlineState]:
        state_class = self._type_combo.currentData()
        if state_class is None:
            raise RuntimeError("No beamline state class selected.")
        return state_class

    def _state_name(self) -> str:
        name_widget = self._config_form.input_widget("name")
        raw_name = name_widget.text().strip()
        if not raw_name:
            raise ValueError("Name is required.")
        name = slugify.slugify(raw_name, separator="_")
        name_widget.setText(name)
        return name


class StatusFilterDialog(QDialog):
    """Dialog for selecting visible beamline state statuses."""

    def __init__(self, selected_statuses: set[str] | None, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("Filter Beamline State Status")
        self._checkboxes: dict[str, QCheckBox] = {}

        controls = QHBoxLayout()
        select_all = QPushButton("Select all", self)
        clear = QPushButton("Clear", self)
        select_all.clicked.connect(lambda: self._set_all(True))
        clear.clicked.connect(lambda: self._set_all(False))
        controls.addWidget(select_all)
        controls.addWidget(clear)
        controls.addStretch(1)

        list_layout = QVBoxLayout()
        for status, label in BEAMLINE_STATE_STATUS_LABELS.items():
            checkbox = QCheckBox(label, self)
            checkbox.setChecked(selected_statuses is None or status in selected_statuses)
            self._checkboxes[status] = checkbox
            list_layout.addWidget(checkbox)
        list_layout.addStretch(1)

        box = QGroupBox("Displayed status", self)
        box.setLayout(list_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(box)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def selected_statuses(self) -> set[str] | None:
        selected = {status for status, checkbox in self._checkboxes.items() if checkbox.isChecked()}
        if selected == set(self._checkboxes):
            return None
        return selected

    def _set_all(self, checked: bool) -> None:
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(checked)


class DeviceFilterDialog(QDialog):
    """Dialog for filtering beamline states by configured device."""

    def __init__(
        self,
        devices: list[str],
        selected_devices: set[str] | None,
        device_filter_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle("Filter Beamline State Devices")
        self._checkboxes: dict[str, QCheckBox] = {}

        self._device_text = QLineEdit(self)
        self._device_text.setPlaceholderText("Device name or comma-separated names")
        self._device_text.setText(device_filter_text)

        list_layout = QVBoxLayout()
        for device in devices:
            checkbox = QCheckBox(device, self)
            checkbox.setChecked(selected_devices is not None and device in selected_devices)
            self._checkboxes[device] = checkbox
            list_layout.addWidget(checkbox)
        list_layout.addStretch(1)

        box = QGroupBox("Known devices", self)
        box.setLayout(list_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._device_text)
        layout.addWidget(box)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def selected_devices(self) -> set[str] | None:
        selected = {device for device, checkbox in self._checkboxes.items() if checkbox.isChecked()}
        return selected or None

    def filter_text(self) -> str:
        return self._device_text.text().strip()
