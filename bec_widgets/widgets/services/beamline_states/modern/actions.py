"""Dialog-based actions shared by the QML and QWidget beamline-state views."""

from __future__ import annotations

from bec_lib import bl_states
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.forms_from_types.pydantic_widget_form import PydanticWidgetForm
from bec_widgets.widgets.services.beamline_states.dialogs import (
    SUPPORTED_BEAMLINE_STATES,
    AddBeamlineStateDialog,
)
from bec_widgets.widgets.services.beamline_states.modern.states_controller import (
    BeamlineStatesController,
)


def config_class_for(state_type: str) -> type[bl_states.BeamlineStateConfig] | None:
    """Return the config class of a supported state type, or ``None``."""
    for state_class in SUPPORTED_BEAMLINE_STATES:
        if state_type in {state_class.__name__, state_class.CONFIG_CLASS.state_type}:
            return state_class.CONFIG_CLASS
    return None


class EditBeamlineStateDialog(QDialog):
    """Edit the parameters of one beamline state with the generated pydantic form."""

    def __init__(
        self,
        name: str,
        config_class: type[bl_states.BeamlineStateConfig],
        parameters: dict,
        parent: QWidget | None = None,
        client=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit {name}")
        self.setMinimumWidth(420)
        self.result_config: bl_states.BeamlineStateConfig | None = None
        self.form = PydanticWidgetForm(
            config_class, parent=self, client=client, read_only_fields={"name"}
        )
        data = {"name": name}
        data.update({k: v for k, v in parameters.items() if k in config_class.model_fields})
        self.form.set_partial_data(data)
        self.form.mark_clean()

        header = QFormLayout()
        header.addRow("Type", QLabel(config_class.__name__, self))

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        self._save = self._buttons.button(QDialogButtonBox.StandardButton.Save)
        self._save.setEnabled(False)
        self._buttons.accepted.connect(self._accept)
        self._buttons.rejected.connect(self.reject)
        self.form.changed.connect(self._on_changed)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.form)
        layout.addWidget(self._buttons)

    def _on_changed(self, *_args) -> None:
        self._save.setEnabled(bool(self.form.dirty_fields() - {"name"}))

    @SafeSlot()
    def _accept(self) -> None:
        try:
            self.result_config = self.form.model_instance()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Beamline State", str(exc))
            return
        self.accept()

    def cleanup(self) -> None:
        """Release the form's BEC widgets."""
        self.form.cleanup()


def open_add_dialog(parent: QWidget, controller: BeamlineStatesController) -> None:
    """Show the add-state dialog and create the state (and interlock entry) in BEC."""
    dialog = AddBeamlineStateDialog(parent, client=controller.client)
    try:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        config = dialog.config_result
        add_to_interlock = dialog.add_to_interlock()
        accepted = dialog.interlock_statuses()
    finally:
        dialog.cleanup()
        dialog.deleteLater()
    if config is None:
        return
    try:
        controller.client.beamline_states.add(config)
    except Exception as exc:  # pylint: disable=broad-except
        QMessageBox.warning(parent, "Cannot Add State", str(exc))
        return
    controller.set_preferred_accepted(config.name, accepted)
    if add_to_interlock:
        controller.toggleWatched(config.name)


def open_edit_dialog(parent: QWidget, controller: BeamlineStatesController, name: str) -> None:
    """Show the edit dialog for ``name`` and push changed parameters to BEC."""
    config = controller.config(name)
    config_class = config_class_for(config.state_type) if config is not None else None
    if config_class is None:
        QMessageBox.warning(parent, "Cannot Edit State", f"'{name}' has an unsupported type.")
        return
    dialog = EditBeamlineStateDialog(
        name, config_class, dict(config.parameters), parent, client=controller.client
    )
    try:
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_config is None:
            return
        new_config = dialog.result_config
    finally:
        dialog.cleanup()
        dialog.deleteLater()
    state_client = getattr(controller.client.beamline_states, name, None)
    if state_client is None:
        QMessageBox.warning(parent, "Cannot Update State", f"'{name}' is not available.")
        return
    try:
        state_client.update_parameters(**new_config.model_dump(exclude={"name"}))
    except Exception as exc:  # pylint: disable=broad-except
        QMessageBox.warning(parent, "Cannot Update State", str(exc))
