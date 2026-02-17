"""Experiment Selection View for BEC Atlas Admin Widget"""

from datetime import datetime
from typing import Any

from bec_lib.logger import bec_logger
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from thefuzz import fuzz

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.experiment_mat_card import (
    ExperimentMatCard,
)

# from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.material_push_button import (
#     MaterialPushButton,
# )
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.utils import (
    format_name,
    format_schedule,
)

logger = bec_logger.logger

FUZZY_SEARCH_THRESHOLD = 80


def is_match(text: str, data: dict[str, Any], relevant_keys: list[str], enable_fuzzy: bool) -> bool:
    """
    Check if the text matches any of the relevant keys in the row data.

    Args:
        text (str): The text to search for.
        data (dict[str, Any]): The data to search in.
        relevant_keys (list[str]): The keys to consider for searching.
        enable_fuzzy (bool): Whether to use fuzzy matching.
    Returns:
        bool: True if a match is found, False otherwise.
    """
    for key in relevant_keys:
        data_value = str(data.get(key, "") or "")
        if enable_fuzzy:
            match_ratio = fuzz.partial_ratio(text.lower(), data_value.lower())
            if match_ratio >= FUZZY_SEARCH_THRESHOLD:
                return True
        else:
            if text.lower() in data_value.lower():
                return True
    return False


class ExperimentSelection(QWidget):
    experiment_selected = Signal(dict)

    def __init__(self, experiment_infos=None, parent=None):
        super().__init__(parent=parent)
        self._experiment_infos = experiment_infos or []
        self._next_experiment = self._select_next_experiment(self._experiment_infos)
        self._enable_fuzzy_search: bool = True
        self._hidden_rows: set[int] = set()
        self._headers: dict[str, str] = {
            "pgroup": "P-group",
            "title": "Title",
            "name": "Name",
            "schedule_start": "Schedule (start)",
            "schedule_end": "Schedule (end)",
        }
        self._table_infos: list[dict[str, Any]] = []

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        self._tabs = QTabWidget(self)
        main_layout.addWidget(self._tabs, stretch=1)

        self._card_tab = ExperimentMatCard(parent=self, show_activate_button=False)
        if self._next_experiment:
            self._card_tab.set_experiment_info(self._next_experiment)
        self._table_tab = QWidget(self)
        self._tabs.addTab(self._card_tab, "Next Experiment")
        self._tabs.addTab(self._table_tab, "Manual Selection")

        self._build_table_tab()
        self._tabs.currentChanged.connect(self._on_tab_changed)
        # main_layout.addStretch()

        button_layout = QHBoxLayout()
        self._select_button = QPushButton("Activate", self)
        self._select_button.setEnabled(False)
        self._select_button.clicked.connect(self._emit_selected_experiment)
        self._cancel_button = QPushButton("Cancel", self)
        self._cancel_button.clicked.connect(self.close)
        button_layout.addWidget(self._select_button)
        button_layout.addWidget(self._cancel_button)
        main_layout.addLayout(button_layout)
        self._apply_table_filters()

    def _setup_search(self, layout: QVBoxLayout):
        """
        Create components related to the search functionality

        Args:
            layout (QVBoxLayout): The layout to which the search components will be added.
        """

        # Create search bar
        search_layout = QHBoxLayout()
        self.search_label = QLabel("Search:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter experiments...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._apply_row_filter)
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input)

        # Add exact match toggle
        fuzzy_layout = QHBoxLayout()
        self.fuzzy_label = QLabel("Exact Match:")
        self.fuzzy_is_disabled = QCheckBox()

        self.fuzzy_is_disabled.stateChanged.connect(self._state_change_fuzzy_search)
        self.fuzzy_is_disabled.setToolTip(
            "Enable approximate matching (OFF) and exact matching (ON)"
        )
        self.fuzzy_label.setToolTip("Enable approximate matching (OFF) and exact matching (ON)")
        fuzzy_layout.addWidget(self.fuzzy_label)
        fuzzy_layout.addWidget(self.fuzzy_is_disabled)
        fuzzy_layout.addStretch()

        # Add both search components to the layout
        self.search_controls = QHBoxLayout()
        self.search_controls.addLayout(search_layout)
        self.search_controls.addSpacing(20)  # Add some space between the search box and toggle
        self.search_controls.addLayout(fuzzy_layout)

        # Add filter section for proposals

        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(12, 0, 12, 0)
        filter_layout.setSpacing(12)
        self._with_proposals = QCheckBox("Show experiments with proposals", self)
        self._without_proposals = QCheckBox("Show experiments without proposals", self)
        self._with_proposals.setChecked(True)
        self._without_proposals.setChecked(True)
        self._with_proposals.toggled.connect(self._apply_table_filters)
        self._without_proposals.toggled.connect(self._apply_table_filters)
        filter_layout.addWidget(self._with_proposals)
        filter_layout.addWidget(self._without_proposals)
        filter_layout.addStretch(1)
        self.search_controls.addLayout(filter_layout)

        # Insert the search controls layout at the top of the table
        layout.addLayout(self.search_controls)

    def _build_table_tab(self):
        layout = QVBoxLayout(self._table_tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self._setup_search(layout)

        # # Add filter section
        # filter_layout = QHBoxLayout()
        # self._with_proposals = QCheckBox("Show experiments with proposals", self)
        # self._without_proposals = QCheckBox("Show experiments without proposals", self)
        # self._with_proposals.setChecked(True)
        # self._without_proposals.setChecked(True)
        # self._with_proposals.toggled.connect(self._apply_table_filters)
        # self._without_proposals.toggled.connect(self._apply_table_filters)
        # filter_layout.addWidget(self._with_proposals)
        # filter_layout.addWidget(self._without_proposals)
        # filter_layout.addStretch(1)
        # layout.addLayout(filter_layout)

        # Add table
        hor_layout = QHBoxLayout()
        self._table = QTableWidget(self._table_tab)
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(list(self._headers.values()))
        vh = self._table.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(vh.minimumSectionSize())
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setWordWrap(True)
        self._table.setStyleSheet("QTableWidget::item { padding: 4px; }")

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self._table.itemSelectionChanged.connect(self._update_selection_state)
        hor_layout.addWidget(self._table, stretch=5)
        hor_layout.addSpacing(12)  # Add space between table and side card

        # Add side card for experiment details
        self._side_card = ExperimentMatCard(parent=self, show_activate_button=False)
        hor_layout.addWidget(self._side_card, stretch=2)  # Ratio 5:2 between table and card
        layout.addLayout(hor_layout)

    @SafeSlot()
    def _apply_table_filters(self):
        if self._tabs.currentWidget() is not self._table_tab:
            self._select_button.setEnabled(True)
            return

        show_with = self._with_proposals.isChecked()
        show_without = self._without_proposals.isChecked()

        self._table_infos = []
        for info in self._experiment_infos:
            has_proposal = bool(info.get("proposal"))
            if has_proposal and not show_with:
                continue
            if not has_proposal and not show_without:
                continue
            self._table_infos.append(info)

        self._populate_table()
        self._update_selection_state()

    def _populate_table(self):
        self._table.setRowCount(len(self._table_infos))
        for row, info in enumerate(self._table_infos):
            pgroup = info.get("pgroup", "")
            title = info.get("title", "")
            name = format_name(info)
            start, end = format_schedule(info.get("schedule"))

            self._table.setItem(row, 0, QTableWidgetItem(pgroup))
            self._table.setItem(row, 1, QTableWidgetItem(title))
            self._table.setItem(row, 2, QTableWidgetItem(name))
            self._table.setItem(row, 3, QTableWidgetItem(start))
            self._table.setItem(row, 4, QTableWidgetItem(end))

        width = self._table.viewport().width()
        self._table.resizeRowsToContents()
        self._table.resize(width, self._table.height())
        # self._table.resizeRowsToContents()

    @SafeSlot()
    def _update_selection_state(self):
        has_selection = False
        if self._tabs.currentWidget() is not self._table_tab:
            self._select_button.setEnabled(True)
            return
        index = self._table.selectionModel().selectedRows()
        if not index:
            has_selection = False
        if len(index) > 0:
            index = index[0]
            self._side_card.set_experiment_info(self._table_infos[index.row()])
            has_selection = True
        self._select_button.setEnabled(has_selection)

    def _emit_selected_experiment(self):
        if self._tabs.currentWidget() is self._card_tab:
            self.experiment_selected.emit(self._next_experiment)
            logger.info(f"Emitting next experiment signal with info: {self._next_experiment}")
            return
        selected = self._table.selectionModel().selectedRows()
        if not selected:
            return
        row = selected[0].row()
        if 0 <= row < len(self._table_infos):
            self.experiment_selected.emit(self._table_infos[row])
            logger.info(f"Emitting next experiment signal with info: {self._table_infos[row]}")

    def _select_next_experiment(self, experiment_infos: list[dict]) -> dict | None:
        candidates = []
        for info in experiment_infos:
            start, _ = format_schedule(info.get("schedule"), as_datetime=True)
            if start is None:
                continue
            candidates.append((start, info))

        if not candidates:
            return experiment_infos[0] if experiment_infos else None

        now = datetime.now()
        future = [entry for entry in candidates if entry[0] >= now]
        pool = future or candidates
        return min(pool, key=lambda entry: abs(entry[0] - now))[1]

    def _on_tab_changed(self, index):
        if self._tabs.widget(index) is self._table_tab:
            self._table.resizeRowsToContents()
            self._side_card.set_experiment_info(self._next_experiment)
        self._apply_table_filters()

    def _get_column_data(self, row) -> dict[str, str]:
        output = {}
        for ii, header in enumerate(self._headers.values()):
            item = self._table.item(row, ii)
            if item is None:
                output[header] = ""
                continue
            output[header] = item.text()
        return output

    @SafeSlot(str)
    def _apply_row_filter(self, text_input: str):
        """Apply a filter to the table rows based on the filter text."""
        if not text_input:
            for row in self._hidden_rows:
                self._table.setRowHidden(row, False)
            self._hidden_rows.clear()
            return
        for row in range(self._table.rowCount()):
            experiment_data = self._get_column_data(row)
            if is_match(
                text_input, experiment_data, list(self._headers.values()), self._enable_fuzzy_search
            ):
                self._table.setRowHidden(row, False)
                self._hidden_rows.discard(row)
            else:
                self._table.setRowHidden(row, True)
                self._hidden_rows.add(row)

    @SafeSlot(int)
    def _state_change_fuzzy_search(self, enabled: int):
        """Handle state changes for the fuzzy search toggle."""
        self._enable_fuzzy_search = not bool(enabled)
        # Re-apply filter with updated fuzzy search setting
        current_text = self.search_input.text()
        self._apply_row_filter(current_text)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    experiment_infos = [
        {
            "_id": "p22619",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22619"],
            "realm_id": "Debye",
            "proposal": "20250267",
            "title": "Iridium-Tantalum Mixed Metal Oxides for the Acidic Oxygen Evolution Reaction",
            "firstname": "Andreas",
            "lastname": "Göpfert",
            "email": "a.goepfert@fz-juelich.de",
            "account": "",
            "pi_firstname": "Andreas",
            "pi_lastname": "Göpfert",
            "pi_email": "a.goepfert@fz-juelich.de",
            "pi_account": "",
            "eaccount": "e22619",
            "pgroup": "p22619",
            "abstract": "The coordination environment, the electronic structure, and the interatomic distance of the different Ta- and Ir-based nanocrystalline electrocatalysts need to be examined to prove the structure of the catalysts. XANES and EXAFS spectra of the Ir and Ta L3-edge need to be recorded.",
            "schedule": [
                {"start": "23/07/2025 23:00:00", "end": "24/07/2025 07:00:00"},
                {"start": "24/07/2025 23:00:00", "end": "27/07/2025 15:00:00"},
            ],
            "proposal_submitted": "07/05/2025",
            "proposal_expire": "",
            "proposal_status": "Finished",
            "delta_last_schedule": 160,
            "mainproposal": "",
        },
        {
            "_id": "p22622",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22622"],
            "realm_id": "Debye",
            "proposal": "20250656",
            "title": "In-situ XAS Investigation of Cu Single-Atom Catalysts under Pulsed Electrochemical CO2 reduction reaction",
            "firstname": "Adam",
            "lastname": "Clark",
            "email": "adam.clark@psi.ch",
            "account": "clark_a",
            "pi_firstname": "Adam",
            "pi_lastname": "Clark",
            "pi_email": "adam.clark@psi.ch",
            "pi_account": "clark_a",
            "eaccount": "e22622",
            "pgroup": "p22622",
            "abstract": "",
            "schedule": [{"start": "27/06/2025 15:00:00", "end": "30/06/2025 07:00:00"}],
            "proposal_submitted": "13/06/2025",
            "proposal_expire": "31/12/2025",
            "proposal_status": "Finished",
            "delta_last_schedule": 187,
            "mainproposal": "",
        },
        {
            "_id": "p22621",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22621"],
            "realm_id": "Debye",
            "proposal": "20250681",
            "title": "Tracking Fe dynamics and coordination in N2O-mediated red-ox reactions",
            "firstname": "Adam",
            "lastname": "Clark",
            "email": "adam.clark@psi.ch",
            "account": "clark_a",
            "pi_firstname": "Adam",
            "pi_lastname": "Clark",
            "pi_email": "adam.clark@psi.ch",
            "pi_account": "clark_a",
            "eaccount": "e22621",
            "pgroup": "p22621",
            "abstract": "",
            "schedule": [{"start": "09/07/2025 15:00:00", "end": "12/07/2025 15:00:00"}],
            "proposal_submitted": "25/06/2025",
            "proposal_expire": "31/12/2025",
            "proposal_status": "Finished",
            "delta_last_schedule": 175,
            "mainproposal": "",
        },
        {
            "_id": "p22481",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22481"],
            "realm_id": "Debye",
            "proposal": "",
            "title": "p22481",
            "firstname": "Adam",
            "lastname": "Clark",
            "email": "adam.clark@psi.ch",
            "account": "clark_a",
            "pi_firstname": "",
            "pi_lastname": "",
            "pi_email": "",
            "pi_account": "",
            "eaccount": "e22481",
            "pgroup": "p22481",
            "abstract": "Debye beamline commissioning pgroup",
            "schedule": [{}],
            "proposal_submitted": None,
            "proposal_expire": None,
            "proposal_status": None,
            "delta_last_schedule": None,
            "mainproposal": None,
        },
        {
            "_id": "p22540",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22540"],
            "realm_id": "Debye",
            "proposal": "",
            "title": "p22540",
            "firstname": "Markus",
            "lastname": "Knecht",
            "email": "markus.knecht@psi.ch",
            "account": "knecht_m",
            "pi_firstname": "",
            "pi_lastname": "",
            "pi_email": "",
            "pi_account": "",
            "eaccount": "e22540",
            "pgroup": "p22540",
            "abstract": "Yet another testaccount",
            "schedule": [{}],
            "proposal_submitted": None,
            "proposal_expire": None,
            "proposal_status": None,
            "delta_last_schedule": None,
            "mainproposal": None,
        },
        {
            "_id": "p22890",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22890"],
            "realm_id": "Debye",
            "proposal": "",
            "title": "p22890",
            "firstname": "Adam",
            "lastname": "Clark",
            "email": "adam.clark@psi.ch",
            "account": "clark_a",
            "pi_firstname": "",
            "pi_lastname": "",
            "pi_email": "",
            "pi_account": "",
            "eaccount": "e22890",
            "pgroup": "p22890",
            "abstract": "Debye Beamline E-account",
            "schedule": [{}],
            "proposal_submitted": None,
            "proposal_expire": None,
            "proposal_status": None,
            "delta_last_schedule": None,
            "mainproposal": None,
        },
        {
            "_id": "p22900",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22900"],
            "realm_id": "Debye",
            "proposal": "",
            "title": "p22900",
            "firstname": "Adam",
            "lastname": "Clark",
            "email": "adam.clark@psi.ch",
            "account": "clark_a",
            "pi_firstname": "",
            "pi_lastname": "",
            "pi_email": "",
            "pi_account": "",
            "eaccount": "e22900",
            "pgroup": "p22900",
            "abstract": "",
            "schedule": [{}],
            "proposal_submitted": None,
            "proposal_expire": None,
            "proposal_status": None,
            "delta_last_schedule": None,
            "mainproposal": None,
        },
        {
            "_id": "p22901",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22901"],
            "realm_id": "Debye",
            "proposal": "",
            "title": "p22901",
            "firstname": "Adam",
            "lastname": "Clark",
            "email": "adam.clark@psi.ch",
            "account": "clark_a",
            "pi_firstname": "",
            "pi_lastname": "",
            "pi_email": "",
            "pi_account": "",
            "eaccount": "e22901",
            "pgroup": "p22901",
            "abstract": "",
            "schedule": [{}],
            "proposal_submitted": None,
            "proposal_expire": None,
            "proposal_status": None,
            "delta_last_schedule": None,
            "mainproposal": None,
        },
        {
            "_id": "p19492",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p19492"],
            "realm_id": "Debye",
            "proposal": "",
            "title": "p19492",
            "firstname": "Klaus",
            "lastname": "Wakonig",
            "email": "klaus.wakonig@psi.ch",
            "account": "wakonig_k",
            "pi_firstname": "",
            "pi_lastname": "",
            "pi_email": "",
            "pi_account": "",
            "eaccount": "e19492",
            "pgroup": "p19492",
            "abstract": "BEC tests",
            "schedule": [{}],
            "proposal_submitted": None,
            "proposal_expire": None,
            "proposal_status": None,
            "delta_last_schedule": None,
            "mainproposal": None,
        },
        {
            "_id": "p22914",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22914"],
            "realm_id": "Debye",
            "proposal": "20250676",
            "title": "ReMade: Monitoring tin speciation in zeolites for renewable sugar catalysis",
            "firstname": "Gleb",
            "lastname": "Ivanushkin",
            "email": "gleb.ivanushkin@kuleuven.be",
            "account": "",
            "pi_firstname": "Gleb",
            "pi_lastname": "Ivanushkin",
            "pi_email": "gleb.ivanushkin@kuleuven.be",
            "pi_account": "",
            "eaccount": "e22914",
            "pgroup": "p22914",
            "abstract": "Efficient conversion of renewable feedstocks, such as biomass, into fuels and chemicals is crucial for a sustainable chemical industry. While there is a vast amount of literature available on the catalytic properties of Sn-Beta, the Lewis acid site chemistry has never been assessed in situ under relevant industrial conditions. We propose (1) an in situ XAS investigation of sugar conversion on tin-containing zeolites of different loading and synthesis origin. Since we also speculate that the pore opening size could vary in the materials, depending on the method of preparation, the investigation will be focused on the conversion of larger substrates rather than dihydroxy acetone.",
            "schedule": [{"start": "13/11/2025 07:00:00", "end": "16/11/2025 07:00:00"}],
            "proposal_submitted": "23/06/2025",
            "proposal_expire": "",
            "proposal_status": "Finished",
            "delta_last_schedule": 49,
            "mainproposal": "",
        },
        {
            "_id": "p22979",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22979"],
            "realm_id": "Debye",
            "proposal": "20250865",
            "title": "Studying the dynamic Fe speciation in Fe-ZSM5 for low-temperature liquid phase methane partial oxidation",
            "firstname": "John Mark Christian",
            "lastname": "Dela Cruz",
            "email": "john.dela-cruz@psi.ch",
            "account": "delacr_j",
            "pi_firstname": "Maarten",
            "pi_lastname": "Nachtegaal",
            "pi_email": "maarten.nachtegaal@psi.ch",
            "pi_account": "nachtegaal",
            "eaccount": "e22979",
            "pgroup": "p22979",
            "abstract": "This operando XAS study aims to investigate the evolution of Fe speciation in ZSM-5 under low-temperature (<90 °C) liquid-phase conditions during the partial oxidation of methane to methanol. These reaction conditions remain largely unexplored, and the exact reaction mechanism at the active site is still unresolved. Most previous in situ experiments have not been representative of actual catalytic testing environments. To address this gap, we employ a capillary flow reactor that enables both operando XAS measurements and catalytic testing under relevant conditions.",
            "schedule": [{"start": "04/12/2025 07:00:00", "end": "05/12/2025 07:00:00"}],
            "proposal_submitted": "20/08/2025",
            "proposal_expire": "31/12/2025",
            "proposal_status": "Finished",
            "delta_last_schedule": 28,
            "mainproposal": "",
        },
        {
            "_id": "p22978",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22978"],
            "realm_id": "Debye",
            "proposal": "20250867",
            "title": "Synthesis-Dependent Redox Dynamics of Fe-Zeolites in NO-Assisted N2O Decomposition",
            "firstname": "Gabriela-Teodora",
            "lastname": "Dutca",
            "email": "gabriela-teodora.dutca@psi.ch",
            "account": "dutca_g",
            "pi_firstname": "Gabriela-Teodora",
            "pi_lastname": "Dutca",
            "pi_email": "gabriela-teodora.dutca@psi.ch",
            "pi_account": "dutca_g",
            "eaccount": "e22978",
            "pgroup": "p22978",
            "abstract": "This study focuses on the investigation of the redox and coordination dynamics of Fe ions in Fe-zeolites during their interaction with N2O in N2O decomposition as well as with NO and N2O simultaneously in NO-assisted N2O decomposition. To this end, time-resolved quick-XAS will be employed at the Fe K-edge in transient experiments. These will allow us to capture transient redox changes on a (sub)second timescale, enabling direct correlation between the extent of redox dynamics of Fe ions and the synthesis method of the Fe zeolites. The results will provide insights into the influence of synthesis methods on active site evolution under reaction conditions, guiding the rational design of improved Fe zeolite catalysts.",
            "schedule": [{"start": "05/12/2025 07:00:00", "end": "08/12/2025 07:00:00"}],
            "proposal_submitted": "20/08/2025",
            "proposal_expire": "31/12/2025",
            "proposal_status": "Finished",
            "delta_last_schedule": 27,
            "mainproposal": "",
        },
        {
            "_id": "p22977",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22977"],
            "realm_id": "Debye",
            "proposal": "20250871",
            "title": "Towards Atomic-Level Insight into Rhenium Surface Dispersion on TiO2 for Low-Temperature and High Pressure Methanol Synthesis from CO2 Hydrogenation",
            "firstname": "Iván",
            "lastname": "López Luque",
            "email": "i.ivanlopezluque@tudelft.nl",
            "account": "ext-lopezl_i",
            "pi_firstname": "Iván",
            "pi_lastname": "López Luque",
            "pi_email": "i.ivanlopezluque@tudelft.nl",
            "pi_account": "ext-lopezl_i",
            "eaccount": "e22977",
            "pgroup": "p22977",
            "abstract": "We propose operando XAS/XRD experiments at the PSI Debye beamline to resolve the atomic-scale evolution of Re/TiO2 catalysts during CO2 hydrogenation. Debye’s high flux and stability are essential for tracking subtle changes at the Re L3-edge under in situ calcination, reduction, and reaction conditions. Real-time XANES will monitor redox dynamics, while room-temperature EXAFS and simultaneous XRD will reveal coordination and structural evolution. The beamline’s unique energy range and operando cell compatibility make it ideally suited to establish correlations between Re dispersion, support interactions, and catalytic performance under realistic conditions.",
            "schedule": [{"start": "12/12/2025 07:00:00", "end": "15/12/2025 07:00:00"}],
            "proposal_submitted": "19/08/2025",
            "proposal_expire": "31/12/2025",
            "proposal_status": "Finished",
            "delta_last_schedule": 20,
            "mainproposal": "",
        },
        {
            "_id": "p22976",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p22976"],
            "realm_id": "Debye",
            "proposal": "20250876",
            "title": "Operando Pd K-edge XAS analysis of an active phase in a multicomponent catalyst enabling enhanced MTH performance",
            "firstname": "Matteo",
            "lastname": "Vanni",
            "email": "matteo.vanni@psi.ch",
            "account": "",
            "pi_firstname": "Vladimir",
            "pi_lastname": "Paunovic",
            "pi_email": "vladimir.paunovic@psi.ch",
            "pi_account": "paunovic_v",
            "eaccount": "e22976",
            "pgroup": "p22976",
            "abstract": "The conversion of methanol into hydrocarbons (MTH) over one-dimensional zeolites offers a promising route to sustainable olefins and fuels, but suffers from rapid catalyst deactivation. Incorporation of Pd into the catalyst formulation, combined with H2 cofeeds, significantly extends catalyst lifetime after an initial induction period. Using operando XAS, we aim to identify the Pd phase responsible for the enhanced olefin selectivity and prolonged catalyst stability, and to elucidate the dynamics of Pd restructuring at the onset of the reaction.",
            "schedule": [{"start": "20/11/2025 07:00:00", "end": "22/11/2025 07:00:00"}],
            "proposal_submitted": "20/08/2025",
            "proposal_expire": "31/12/2025",
            "proposal_status": "Finished",
            "delta_last_schedule": 42,
            "mainproposal": "",
        },
        {
            "_id": "p23034",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p23034"],
            "realm_id": "Debye",
            "proposal": "",
            "title": "p23034",
            "firstname": "Daniele",
            "lastname": "Bonavia",
            "email": "daniele.bonavia@psi.ch",
            "account": "",
            "pi_firstname": "",
            "pi_lastname": "",
            "pi_email": "",
            "pi_account": "",
            "eaccount": "e23034",
            "pgroup": "p23034",
            "abstract": "creation of eaccount to make a pgroup for daniele",
            "schedule": [{}],
            "proposal_submitted": None,
            "proposal_expire": None,
            "proposal_status": None,
            "delta_last_schedule": None,
            "mainproposal": None,
        },
        {
            "_id": "p23039",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_x01da_bs", "p23039"],
            "realm_id": "Debye",
            "proposal": "",
            "title": "p23039",
            "firstname": "Adam",
            "lastname": "Clark",
            "email": "adam.clark@psi.ch",
            "account": "clark_a",
            "pi_firstname": "",
            "pi_lastname": "",
            "pi_email": "",
            "pi_account": "",
            "eaccount": "e23039",
            "pgroup": "p23039",
            "abstract": "shell",
            "schedule": [{}],
            "proposal_submitted": None,
            "proposal_expire": None,
            "proposal_status": None,
            "delta_last_schedule": None,
            "mainproposal": None,
        },
    ]

    app = QApplication([])
    from bec_qthemes import apply_theme

    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    apply_theme("light")
    w = QWidget()
    l = QVBoxLayout(w)
    dark_button = DarkModeButton()
    l.addWidget(dark_button)
    widget = ExperimentSelection(experiment_infos)
    l.addWidget(widget)
    w.resize(1280, 920)
    w.show()
    app.exec()
