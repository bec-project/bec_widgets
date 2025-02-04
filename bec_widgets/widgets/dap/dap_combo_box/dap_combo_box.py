""" Module for DapComboBox widget class to select a DAP model from a combobox. """

from PySide6.QtWidgets import QSizePolicy

from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtWidgets import QComboBox

from bec_widgets.utils.bec_widget import BECWidget

logger = bec_logger.logger


class DapComboBox(BECWidget, QComboBox):
    """
    The DAPComboBox widget is an extension to the QComboBox with all avaialble DAP model from BEC.

    Args:
        parent: Parent widget.
        client: BEC client object.
        gui_id: GUI ID.
        default: Default device name.
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
        self, parent=None, client=None, gui_id: str | None = None, default_fit: str | None = None
    ):
        BECWidget.__init__(self, client=client, gui_id=gui_id)
        QComboBox.__init__(self, parent=parent)
        self._available_models = None
        self._x_axis = None
        self._y_axis = None
        self.populate_fit_model_combobox()
        self.currentTextChanged.connect(self._update_current_fit)
        # Set default fit model
        self.select_default_fit(default_fit)

    def select_default_fit(self, default_fit: str | None):
        """Set the default fit model.

        Args:
            default_fit(str): Default fit model.
        """
        if self._validate_dap_model(default_fit):
            self.select_fit_model(default_fit)
        else:
            self.select_fit_model("GaussianModel")

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

    def _update_current_fit(self, fit_name: str):
        """Update the current fit."""
        self.fit_model_updated.emit(fit_name)
        if self.x_axis is not None and self.y_axis is not None:
            self.new_dap_config.emit(self._x_axis, self._y_axis, fit_name)

    @Slot(str)
    def select_x_axis(self, x_axis: str):
        """Slot to update the x axis.

        Args:
            x_axis(str): X axis.
        """
        self.x_axis = x_axis
        self._update_current_fit(self.currentText())

    @Slot(str)
    def select_y_axis(self, y_axis: str):
        """Slot to update the y axis.

        Args:
            y_axis(str): Y axis.
        """
        self.y_axis = y_axis
        self._update_current_fit(self.currentText())

    @Slot(str)
    def select_fit_model(self, fit_name: str | None):
        """Slot to update the fit model.

        Args:
            default_device(str): Default device name.
        """
        if not self._validate_dap_model(fit_name):
            raise ValueError(f"Fit {fit_name} is not valid.")
        self.setCurrentText(fit_name)

    def populate_fit_model_combobox(self):
        """Populate the fit_model_combobox with the devices."""
        # pylint: disable=protected-access
        self.available_models = [model for model in self.client.dap._available_dap_plugins.keys()]
        self.clear()
        self.addItems(self.available_models)

    def _validate_dap_model(self, model: str | None) -> bool:
        """Validate the DAP model.

        Args:
            model(str): Model name.
        """
        if model is None:
            return False
        if model not in self.available_models:
            return False
        return True


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=import-outside-toplevel
    from qtpy.QtWidgets import QApplication, QWidget, QVBoxLayout

    from bec_widgets.utils.colors import set_theme

    app = QApplication([])
    set_theme("dark")
    widget = QWidget()
    # widget.setFixedSize(200, 200)
    layout = QVBoxLayout()
    widget.setLayout(layout)
    layout.addWidget(DapComboBox())
    widget.show()
    app.exec_()
