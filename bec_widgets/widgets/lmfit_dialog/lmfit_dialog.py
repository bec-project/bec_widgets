import os

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, Signal, Slot
from qtpy.QtWidgets import QTreeWidgetItem, QVBoxLayout, QWidget

from bec_widgets.utils import UILoader
from bec_widgets.utils.bec_widget import BECWidget

logger = bec_logger.logger


class LMFitDialog(BECWidget, QWidget):
    """Dialog for displaying the fit summary and params for LMFit DAP processes"""

    ICON_NAME = "monitoring"
    selected_fit = Signal(str)

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
        self.ui.curve_list.currentItemChanged.connect(self.display_fit_details)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)

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

    @property
    def fit_curve_id(self):
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
        if self.fit_curve_id is None:
            self.fit_curve_id = curve_id
        if curve_id != self.fit_curve_id:
            return
        if data is None:
            return
        self.ui.summary_tree.clear()
        properties = [
            ("Model", data.get("model", "")),
            ("Method", data.get("method", "")),
            ("Chi-Squared", f"{data.get('chisqr', 0.0):.{self._deci_precision}f}"),
            ("Reduced Chi-Squared", f"{data.get('redchi', 0.0):.{self._deci_precision}f}"),
            ("R-Squared", f"{data.get('rsquared', 0.0):.{self._deci_precision}f}"),
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
        self.ui.param_tree.clear()
        for param in params:
            param_name, param_value, param_std = (
                param[0],
                f"{param[1]:.{self._deci_precision}f}",
                f"{param[7]:.{self._deci_precision}f}",
            )
            QTreeWidgetItem(self.ui.param_tree, [param_name, param_value, param_std])

    def populate_curve_list(self):
        """Populate the curve list with the available fit curves."""
        for curve_name in self.summary_data.keys():
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


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    dialog = LMFitDialog()
    dialog.show()
    sys.exit(app.exec_())
