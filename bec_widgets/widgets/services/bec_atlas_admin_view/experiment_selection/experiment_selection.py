"""Experiment Selection View for BEC Atlas Admin Widget"""

from datetime import datetime
from typing import Any

from bec_lib.logger import bec_logger
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QSizePolicy,
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
        main_layout.setContentsMargins(0, 0, 0, 0)
        # main_layout.setSpacing(12)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

        self._tabs = QTabWidget(self)
        main_layout.addWidget(self._tabs, stretch=1)

        self._card_tab = ExperimentMatCard(
            parent=self, show_activate_button=True, button_text="Activate Next Experiment"
        )
        self._card_tab.experiment_selected.connect(self._emit_selected_experiment)
        if self._next_experiment:
            self._card_tab.set_experiment_info(self._next_experiment)
        self._table_tab = QWidget(self)
        self._tabs.addTab(self._card_tab, "Next Experiment")
        self._tabs.addTab(self._table_tab, "Manual Selection")

        self._build_table_tab()
        self._tabs.currentChanged.connect(self._on_tab_changed)
        # main_layout.addStretch()

        button_layout = QHBoxLayout()
        main_layout.addLayout(button_layout)
        self._apply_table_filters()
        self.restore_default_view()

    def restore_default_view(self):
        """Reset the view to the default state, showing the next experiment card."""
        self._tabs.setCurrentWidget(self._card_tab)

    def set_experiment_infos(self, experiment_infos: list[dict]):
        self._experiment_infos = experiment_infos
        self._next_experiment = self._select_next_experiment(self._experiment_infos)
        if self._next_experiment:
            self._card_tab.set_experiment_info(self._next_experiment)
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
        self._side_card = ExperimentMatCard(
            parent=self, show_activate_button=True, button_text="Activate Next Experiment"
        )
        self._side_card.experiment_selected.connect(self._emit_selected_experiment)
        hor_layout.addWidget(self._side_card, stretch=2)  # Ratio 5:2 between table and card
        layout.addLayout(hor_layout)

    @SafeSlot()
    @SafeSlot(int)
    @SafeSlot(bool)  # Overload for buttons
    def _apply_table_filters(self, *args, **kwargs):
        if self._tabs.currentWidget() is not self._table_tab:
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
        # Clear table before populating, this keeps headers intact
        self._table.setRowCount(0)
        # Refill table
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
        if self._tabs.currentWidget() is not self._table_tab:
            return
        index = self._table.selectionModel().selectedRows()
        if len(index) > 0:
            index = index[0]
            self._side_card.set_experiment_info(self._table_infos[index.row()])

    def _emit_selected_experiment(self):
        if self._tabs.currentWidget() is self._card_tab and self._next_experiment:
            self.experiment_selected.emit(self._next_experiment)
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
            if self._next_experiment:
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
            "_id": "p22622",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_xda_bs", "p22622"],
            "realm_id": "TestBeamline",
            "proposal": "12345967",
            "title": "Test Experiment for Mat Card Widget",
            "firstname": "John",
            "lastname": "Doe",
            "email": "john.doe@psi.ch",
            "account": "doe_j",
            "pi_firstname": "Jane",
            "pi_lastname": "Smith",
            "pi_email": "jane.smith@psi.ch",
            "pi_account": "smith_j",
            "eaccount": "e22622",
            "pgroup": "p22622",
            "abstract": "This is a test abstract for the experiment mat card widget. It should be long enough to test text wrapping and display in the card. The abstract provides a brief overview of the experiment, its goals, and its significance. This text is meant to simulate a real abstract that might be associated with an experiment in the BEC Atlas system. The card should be able to handle abstracts of varying lengths without any issues, ensuring that the user can read the full abstract even if it is quite long.",
            "schedule": [{"start": "01/01/2025 08:00:00", "end": "03/01/2025 18:00:00"}],
            "proposal_submitted": "15/12/2024",
            "proposal_expire": "31/12/2025",
            "proposal_status": "Scheduled",
            "delta_last_schedule": 30,
            "mainproposal": "",
        },
        {
            "_id": "p22623",
            "owner_groups": ["admin"],
            "access_groups": ["unx-sls_xda_bs", "p22623"],
            "realm_id": "TestBeamline",
            "proposal": "",
            "title": "Experiment without Proposal",
            "firstname": "Alice",
            "lastname": "Johnson",
            "email": "alice.johnson@psi.ch",
            "account": "johnson_a",
            "pi_firstname": "Bob",
            "pi_lastname": "Brown",
            "pi_email": "bob.brown@psi.ch",
            "pi_account": "brown_b",
            "eaccount": "e22623",
            "pgroup": "p22623",
            "abstract": "",
            "schedule": [],
            "proposal_submitted": "",
            "proposal_expire": "",
            "proposal_status": "",
            "delta_last_schedule": None,
            "mainproposal": "",
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
