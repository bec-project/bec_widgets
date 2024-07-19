import os

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QDialog, QTreeWidgetItem, QVBoxLayout

from bec_widgets.utils import UILoader


class FitSummaryWidget(QDialog):
    def __init__(self, parent=None, target_widget=None):
        super().__init__(parent=parent)

        self.target_widget = target_widget
        self.summary_data = self.target_widget.get_dap_summary()

        self.setModal(True)

        current_path = os.path.dirname(__file__)
        self.ui = UILoader(self).loader(os.path.join(current_path, "dap_summary.ui"))
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)

        self.ui.curve_list.currentItemChanged.connect(self.display_fit_details)
        self.ui.refresh_button.clicked.connect(self.refresh_dap)

        self.populate_curve_list()

    def populate_curve_list(self):
        for curve_name in self.summary_data.keys():
            self.ui.curve_list.addItem(curve_name)

    def display_fit_details(self, current):
        if current:
            curve_name = current.text()
            data = self.summary_data[curve_name]
            if data is None:
                return
            self.refresh_trees(data)

    @Slot()
    def refresh_dap(self):
        self.ui.curve_list.clear()
        self.summary_data = self.target_widget.get_dap_summary()
        self.populate_curve_list()

    def refresh_trees(self, data):
        self.update_summary_tree(data)
        self.update_param_tree(data["params"])

    def update_summary_tree(self, data):
        self.ui.summary_tree.clear()
        properties = [
            ("Model", data.get("model", "")),
            ("Method", data.get("method", "")),
            ("Chi-Squared", str(data.get("chisqr", ""))),
            ("Reduced Chi-Squared", str(data.get("redchi", ""))),
            ("AIC", str(data.get("aic", ""))),
            ("BIC", str(data.get("bic", ""))),
            ("R-Squared", str(data.get("rsquared", ""))),
            ("Message", data.get("message", "")),
        ]
        for prop, val in properties:
            QTreeWidgetItem(self.ui.summary_tree, [prop, val])

    def update_param_tree(self, params):
        self.ui.param_tree.clear()
        for param in params:
            param_name, param_value, param_std = param[0], str(param[1]), str(param[7])
            QTreeWidgetItem(self.ui.param_tree, [param_name, param_value, param_std])
