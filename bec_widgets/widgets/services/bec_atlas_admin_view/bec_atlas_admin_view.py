from __future__ import annotations

import json
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QHBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.services.bec_atlas_admin_view.bec_atlas_http_service import (
    BECAtlasHTTPService,
    HTTPResponse,
)
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.experiment_selection import (
    CurrentExperimentInfoFrame,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib.messages import ExperimentInfoMessage


class BECAtlasAdminView(BECWidget, QWidget):

    def __init__(
        self,
        parent=None,
        atlas_url: str = "https://bec-atlas-qa.psi.ch/api/v1",
        headers: dict | None = None,
    ):
        super().__init__(parent=parent)
        if headers is None:
            headers = {"accept": "application/json"}
        # Main layout
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(24, 18, 24, 18)
        self.main_layout.setSpacing(24)

        # Atlas HTTP service
        self.atlas_http_service = BECAtlasHTTPService(
            parent=self, base_url=atlas_url, headers=headers
        )

        # Current Experinment Info Frame
        self.current_experiment_frame = CurrentExperimentInfoFrame(parent=self)
        self.dummy_msg_frame = CurrentExperimentInfoFrame(parent=self)
        self.dummy_acl_frame = CurrentExperimentInfoFrame(parent=self)
        self.main_layout.addWidget(self.current_experiment_frame)
        self.main_layout.addWidget(self.dummy_msg_frame)
        self.main_layout.addWidget(self.dummy_acl_frame)

        # Connect signals
        self.atlas_http_service.http_response_received.connect(self._display_response)
        self.current_experiment_frame.request_change_experiment.connect(
            self._on_request_change_experiment
        )

    def set_experiment_info(self, experiment_info: ExperimentInfoMessage) -> None:
        """Set the current experiment information to display."""
        self.current_experiment_frame.set_experiment_info(experiment_info)

    def _on_request_change_experiment(self):
        """Handle the request to change the current experiment."""

        # For demonstration, we will just call the method to get realms.
        # In a real application, this could open a dialog to select a new experiment.
        self.atlas_http_service.login()  # Ensure we are authenticated before fetching realms

    def _display_response(self, response: dict):
        """Display the HTTP response in the text edit widget."""
        response = HTTPResponse(**response)
        text = f"Endpoint: {response.request_url}\nStatus Code: {response.status}\n\n"
        if response.data:
            data_str = ""
            if isinstance(response.data, str):
                data_str = response.data
            elif isinstance(response.data, dict):
                data_str = json.dumps(response.data, indent=4)
            elif isinstance(response.data, list):
                for item in response.data:
                    data_str += json.dumps(item, indent=4) + "\n"
            text += f"Response Data:\n{data_str}"
        print(text)
        # self.response_text.setPlainText(text)

    def cleanup(self):
        self.atlas_http_service.cleanup()
        return super().cleanup()


if __name__ == "__main__":
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)

    apply_theme("light")
    window = BECAtlasAdminView()

    exp_info_dict = {
        "realm_id": "ADDAMS",
        "proposal": "20190723",
        "title": "In situ heat treatment of Transformation Induced Plasticity High Entropy Alloys: engineering the microstructure for optimum mechanical properties.",
        "firstname": "Efthymios",
        "lastname": "Polatidis",
        "email": "polatidis@upatras.gr",
        "account": "",
        "pi_firstname": "Efthymios",
        "pi_lastname": "Polatidis",
        "pi_email": "polatidis@upatras.gr",
        "pi_account": "",
        "eaccount": "e17932",
        "pgroup": "p17932",
        "abstract": "High Entropy Alloys (HEAs) are becoming increasingly important structural materials for numerous engineering applications due to their excellent strength/ductility combination. The proposed material is a novel Al-containing HEA, processed by friction stirring and subsequent annealing, which exhibits the transformation induced plasticity (TRIP) effect. Upon annealing, the parent fcc phase transforms into hcp martensitically which strongly affects the mechanical properties. The main goal of this experiment is to investigate the evolution of phases in this TRIP-HEA, upon isothermal annealing at different temperatures. Obtaining insight into the mechanisms of phase formation during annealing, would aid designing processing methods and tailoring the microstructure with a view to optimizing the mechanical behavior.",
        "schedule": [{"start": "08/07/2019 07:00:00", "end": "09/07/2019 07:00:00"}],
        "proposal_submitted": "15/03/2019",
        "proposal_expire": "31/12/2019",
        "proposal_status": "Finished",
        "delta_last_schedule": 2258,
        "mainproposal": "",
    }
    from bec_lib.messages import ExperimentInfoMessage

    proposal_info = ExperimentInfoMessage(**exp_info_dict)
    window.set_experiment_info(proposal_info)
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
