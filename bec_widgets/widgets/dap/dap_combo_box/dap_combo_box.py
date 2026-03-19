"""Module for DapComboBox widget class to select a DAP model from a combobox."""

from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtWidgets import QComboBox

from bec_widgets.utils.bec_widget import BECWidget

logger = bec_logger.logger


class DapComboBox(BECWidget, QComboBox):
    """
    Editable combobox listing the available DAP models.

    The widget behaves as a plain QComboBox and keeps ``fit_model_combobox`` as an alias to itself
    for backwards compatibility with older call sites.
    """

    ICON_NAME = "data_exploration"
    PLUGIN = True
    USER_ACCESS = ["select_y_axis", "select_x_axis", "select_fit_model"]

    ### Signals ###
    # Signal to emit a new dap_config: (x_axis, y_axis, fit_model). Can be used to add a new DAP process
    # in the BECWaveformWidget using its add_dap method. The signal is emitted when the user selects a new
    # fit model, but only if x_axis and y_axis are set.
    new_dap_config = Signal(str, str, str)
    # Signal to emit the name of the updated x_axis
    x_axis_updated = Signal(str)
    # Signal to emit the name of the updated y_axis
    y_axis_updated = Signal(str)
    # Signal to emit the name of the updated fit model
    fit_model_updated = Signal(str)

    def __init__(
        self,
        parent=None,
        client=None,
        gui_id: str | None = None,
        default_fit: str | None = None,
        **kwargs,
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, **kwargs)
        self.fit_model_combobox = self  # Just for backwards compatibility with older call sites, the widget itself is the combobox
        self._available_models: list[str] = []
        self._x_axis = None
        self._y_axis = None
        self._is_valid_input = False

        self.setEditable(True)

        self.populate_fit_model_combobox()
        self.currentTextChanged.connect(self._on_text_changed)
        self.select_default_fit(default_fit)
        self.check_validity(self.currentText())

    def select_default_fit(self, default_fit: str | None = "GaussianModel"):
        """Set the default fit model.

        Args:
            default_fit(str): Default fit model.
        """
        if self._validate_dap_model(default_fit):
            self.select_fit_model(default_fit)
        elif self.available_models:
            self.select_fit_model(self.available_models[0])

    @property
    def available_models(self):
        """Available models property."""
        return self._available_models

    @available_models.setter
    def available_models(self, available_models: list[str]):
        """Set the available models.

        Args:
            available_models(list[str]): Available models.
        """
        self._available_models = available_models

    @Property(str)
    def x_axis(self):
        """X axis property."""
        return self._x_axis

    @x_axis.setter
    def x_axis(self, x_axis: str):
        """Set the x axis.

        Args:
            x_axis(str): X axis.
        """
        # TODO add validator for x axis -> Positioner? or also device (must be monitored)!!
        self._x_axis = x_axis
        self.x_axis_updated.emit(x_axis)

    @Property(str)
    def y_axis(self):
        """Y axis property."""
        # TODO add validator for y axis -> Positioner & Device? Must be a monitored device!!
        return self._y_axis

    @y_axis.setter
    def y_axis(self, y_axis: str):
        """Set the y axis.

        Args:
            y_axis(str): Y axis.
        """
        self._y_axis = y_axis
        self.y_axis_updated.emit(y_axis)

    @Slot(str)
    def _on_text_changed(self, fit_name: str):
        """
        Validate and emit updates for the current text.

        Args:
            fit_name(str): The current text in the combobox, representing the selected fit model.
        """
        self.check_validity(fit_name)
        if not self._is_valid_input:
            return

        self.fit_model_updated.emit(fit_name)
        if self.x_axis is not None and self.y_axis is not None:
            self.new_dap_config.emit(self._x_axis, self._y_axis, fit_name)

    @Slot(str)
    def check_validity(self, fit_name: str):
        """
        Highlight invalid manual entries similarly to DeviceComboBox.

        Args:
            fit_name(str): The current text in the combobox, representing the selected fit model.
        """
        if self._validate_dap_model(fit_name):
            self._is_valid_input = True
            self.setStyleSheet("border: 1px solid transparent;")
        else:
            self._is_valid_input = False
            if self.isEnabled():
                self.setStyleSheet("border: 1px solid red;")
            else:
                self.setStyleSheet("border: 1px solid transparent;")

    @Slot(str)
    def select_x_axis(self, x_axis: str):
        """Slot to update the x axis.

        Args:
            x_axis(str): X axis.
        """
        self.x_axis = x_axis
        self._on_text_changed(self.currentText())

    @Slot(str)
    def select_y_axis(self, y_axis: str):
        """Slot to update the y axis.

        Args:
            y_axis(str): Y axis.
        """
        self.y_axis = y_axis
        self._on_text_changed(self.currentText())

    @Slot(str)
    def select_fit_model(self, fit_name: str | None):
        """Slot to update the fit model.

        Args:
            fit_name(str): Fit model name.
        """
        if not self._validate_dap_model(fit_name):
            raise ValueError(f"Fit {fit_name} is not valid.")
        self.setCurrentText(fit_name)

    def populate_fit_model_combobox(self):
        """Populate the fit_model_combobox with the devices."""
        # pylint: disable=protected-access
        available_plugins = getattr(getattr(self.client, "dap", None), "_available_dap_plugins", {})
        self.available_models = [model for model in available_plugins.keys()]
        self.clear()
        self.addItems(self.available_models)

    def _validate_dap_model(self, model: str | None) -> bool:
        """Validate the DAP model.

        Args:
            model(str): Model name.
        """
        if model is None:
            return False
        return model in self.available_models

    @property
    def is_valid_input(self) -> bool:
        """Whether the current text matches an available DAP model."""
        return self._is_valid_input


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    dialog = DapComboBox()
    dialog.show()
    sys.exit(app.exec_())
