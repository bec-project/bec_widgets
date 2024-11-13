from qtpy.QtWidgets import QDialog, QVBoxLayout

from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog import LMFitDialog


class FitSummaryWidget(QDialog):

    def __init__(self, parent=None, target_widget=None):
        super().__init__(parent=parent)

        self.setModal(True)
        self.target_widget = target_widget
        self.dap_dialog = LMFitDialog(parent=self, ui_file="lmfit_dialog_compact.ui")
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.dap_dialog)
        self.target_widget.dap_summary_update.connect(self.dap_dialog.update_summary_tree)
        self.setLayout(self.layout)
        self._get_dap_from_target_widget()

    def _get_dap_from_target_widget(self) -> None:
        """Get the DAP data from the target widget and update the DAP dialog manually on creation."""
        dap_summary = self.target_widget.get_dap_summary()
        for curve_id, data in dap_summary.items():
            md = {"curve_id": curve_id}
            self.dap_dialog.update_summary_tree(data=data, metadata=md)
