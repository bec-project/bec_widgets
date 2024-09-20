import os

from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtWidgets import QPushButton, QTreeWidgetItem, QVBoxLayout, QWidget

from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors

logger = bec_logger.logger


class LMFitDialog(BECWidget, QWidget):
    """Dialog for displaying the fit summary and params for LMFit DAP processes"""

    ICON_NAME = "monitoring"
    # Signal to emit the currently selected fit curve_id
    selected_fit = Signal(str)
    # Signal to emit a move action in form of a tuple (param_name, value)
    move_action = Signal(tuple)

    def __init__(
        self,
        parent=None,
        client=None,
        config=None,
        target_widget=None,
        gui_id: str | None = None,
        ui_file="lmfit_dialog_vertical.ui",
    ):
        """
        Initialises the LMFitDialog widget.

        Args:
            parent (QWidget): The parent widget.
            client: BEC client object.
            config: Configuration of the widget.
            target_widget: The widget that the settings will be taken from and applied to.
            gui_id (str): GUI ID.
            ui_file (str): The UI file to be loaded.
        """
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)
        self._ui_file = ui_file
        self.target_widget = target_widget

        current_path = os.path.dirname(__file__)
        self.ui = UILoader(self).loader(os.path.join(current_path, self._ui_file))
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)
        self.summary_data = {}
        self._fit_curve_id = None
        self._deci_precision = 3
        self._always_show_latest = False
        self.ui.curve_list.currentItemChanged.connect(self.display_fit_details)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self._active_actions = []
        self._enable_actions = True
        self._move_buttons = []
        self._accent_colors = get_accent_colors()
        self.action_buttons = {}

    @property
    def enable_actions(self) -> bool:
        """Property to enable the move to buttons."""
        return self._enable_actions

    @enable_actions.setter
    def enable_actions(self, enable: bool):
        self._enable_actions = enable
        for button in self.action_buttons.values():
            button.setEnabled(enable)

    @Property(list)
    def active_action_list(self) -> list[str]:
        """Property to list the names of the fit parameters for which actions should be enabled."""
        return self._active_actions

    @active_action_list.setter
    def active_action_list(self, actions: list[str]):
        self._active_actions = actions

    # This slot needed?
    @Slot(bool)
    def set_actions_enabled(self, enable: bool) -> bool:
        """Slot to enable the move to buttons.

        Args:
            enable (bool): Whether to enable the action buttons.
        """
        self.enable_actions = enable

    @Property(bool)
    def always_show_latest(self):
        """Property to indicate if always the latest DAP update is displayed."""
        return self._always_show_latest

    @always_show_latest.setter
    def always_show_latest(self, show: bool):
        self._always_show_latest = show

    @Property(bool)
    def hide_curve_selection(self):
        """Property for showing the curve selection."""
        return not self.ui.group_curve_selection.isVisible()

    @hide_curve_selection.setter
    def hide_curve_selection(self, show: bool):
        """Setter for showing the curve selection.

        Args:
            show (bool): Whether to show the curve selection.
        """
        self.ui.group_curve_selection.setVisible(not show)

    @Property(bool)
    def hide_summary(self) -> bool:
        """Property for showing the summary."""
        return not self.ui.group_summary.isVisible()

    @hide_summary.setter
    def hide_summary(self, show: bool):
        """Setter for showing the summary.

        Args:
            show (bool): Whether to show the summary.
        """
        self.ui.group_summary.setVisible(not show)

    @Property(bool)
    def hide_parameters(self) -> bool:
        """Property for showing the parameters."""
        return not self.ui.group_parameters.isVisible()

    @hide_parameters.setter
    def hide_parameters(self, show: bool):
        """Setter for showing the parameters.

        Args:
            show (bool): Whether to show the parameters.
        """
        self.ui.group_parameters.setVisible(not show)

    @property
    def fit_curve_id(self) -> str:
        """Property for the currently displayed fit curve_id."""
        return self._fit_curve_id

    @fit_curve_id.setter
    def fit_curve_id(self, curve_id: str):
        """Setter for the currently displayed fit curve_id.

        Args:
            fit_curve_id (str): The curve_id of the fit curve to be displayed.
        """
        self._fit_curve_id = curve_id
        self.selected_fit.emit(curve_id)

    @Slot(str)
    def remove_dap_data(self, curve_id: str):
        """Remove the DAP data for the given curve_id.

        Args:
            curve_id (str): The curve_id of the DAP data to be removed.
        """
        self.summary_data.pop(curve_id, None)
        self.refresh_curve_list()

    @Slot(str)
    def select_curve(self, curve_id: str):
        """Select active curve_id in the curve list.

        Args:
            curve_id (str): curve_id to be selected.
        """
        self.fit_curve_id = curve_id

    @Slot(dict, dict)
    def update_summary_tree(self, data: dict, metadata: dict):
        """Update the summary tree with the given data.

        Args:
            data (dict): Data for the DAP Summary.
            metadata (dict): Metadata of the fit curve.
        """
        curve_id = metadata.get("curve_id", "")
        self.summary_data.update({curve_id: data})
        self.refresh_curve_list()
        if self.fit_curve_id is None or self.always_show_latest is True:
            self.fit_curve_id = curve_id
        if curve_id != self.fit_curve_id:
            return
        if data is None:
            return
        self.ui.summary_tree.clear()
        chi_squared = data.get("chisqr", 0.0)
        if isinstance(chi_squared, float) or isinstance(chi_squared, int):
            chi_squared = f"{chi_squared:.{self._deci_precision}f}"
        else:
            chi_squared = "None"
        reduced_chi_squared = data.get("redchi", 0.0)
        if isinstance(reduced_chi_squared, float) or isinstance(reduced_chi_squared, int):
            reduced_chi_squared = f"{reduced_chi_squared:.{self._deci_precision}f}"
        else:
            reduced_chi_squared = "None"
        r_squared = data.get("rsquared", 0.0)
        if isinstance(r_squared, float) or isinstance(r_squared, int):
            r_squared = f"{r_squared:.{self._deci_precision}f}"
        else:
            r_squared = "None"
        properties = [
            ("Model", data.get("model", "")),
            ("Method", data.get("method", "")),
            ("Chi-Squared", chi_squared),
            ("Reduced Chi-Squared", reduced_chi_squared),
            ("R-Squared", r_squared),
            ("Message", data.get("message", "")),
        ]
        for prop, val in properties:
            QTreeWidgetItem(self.ui.summary_tree, [prop, val])
        self.update_param_tree(data.get("params", []))

    def _update_summary_data(self, curve_id: str, data: dict):
        """Update the summary data with the given data.

        Args:
            curve_id (str): The curve_id of the fit curve.
            data (dict): The data to be updated.
        """
        self.summary_data.update({curve_id: data})
        if self.fit_curve_id is not None:
            return
        self.fit_curve_id = curve_id

    def update_param_tree(self, params):
        """Update the parameter tree with the given parameters.

        Args:
            params (list): List of LMFit parameters for the fit curve.
        """
        self._move_buttons = []
        self.ui.param_tree.clear()
        for param in params:
            param_name = param[0]
            param_value = param[1]
            if isinstance(param_value, float) or isinstance(param_value, int):
                param_value = f"{param_value:.{self._deci_precision}f}"
            else:
                param_value = "None"
            param_std = param[7]
            if isinstance(param_std, float) or isinstance(param_std, int):
                param_std = f"{param_std:.{self._deci_precision}f}"
            else:
                param_std = "None"

            tree_item = QTreeWidgetItem(self.ui.param_tree, [param_name, param_value, param_std])
            if param_name in self.active_action_list:  # pylint: disable=unsupported-membership-test
                # Create a push button to move the motor to a specific position
                widget = QWidget()
                button = QPushButton(f"Move to {param_name}")
                button.clicked.connect(self._create_move_action(param_name, param[1]))
                if self.enable_actions is True:
                    button.setEnabled(True)
                else:
                    button.setEnabled(False)
                button.setStyleSheet(
                    f"""
                    QPushButton:enabled {{ background-color: {self._accent_colors.success.name()};color: white; }} 
                    QPushButton:disabled {{ background-color: grey;color: white; }}
                    """
                )
                self.action_buttons[param_name] = button
                layout = QVBoxLayout()
                layout.addWidget(self.action_buttons[param_name])
                layout.setContentsMargins(0, 0, 0, 0)
                widget.setLayout(layout)
                self.ui.param_tree.setItemWidget(tree_item, 3, widget)

    def _create_move_action(self, param_name: str, param_value: float) -> callable:
        """Create a move action for the given parameter name and value.

        Args:
            param_name (str): The name of the parameter.
            param_value (float): The value of the parameter.
        Returns:
            callable: The move action with the given parameter name and value.
        """

        def move_action():
            self.move_action.emit((param_name, param_value))

        return move_action

    def populate_curve_list(self):
        """Populate the curve list with the available fit curves."""
        for curve_name in self.summary_data:
            self.ui.curve_list.addItem(curve_name)

    def refresh_curve_list(self):
        """Refresh the curve list with the updated data."""
        self.ui.curve_list.clear()
        self.populate_curve_list()

    def display_fit_details(self, current):
        """Callback for displaying the fit details of the selected curve.

        Args:
            current: The current item in the curve list.
        """
        if current:
            curve_name = current.text()
            self.fit_curve_id = curve_name
            data = self.summary_data[curve_name]
            if data is None:
                return
            self.update_summary_tree(data, {"curve_id": curve_name})


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication  # pylint: disable=ungrouped-imports

    app = QApplication(sys.argv)
    dialog = LMFitDialog()
    dialog.show()
    sys.exit(app.exec_())
