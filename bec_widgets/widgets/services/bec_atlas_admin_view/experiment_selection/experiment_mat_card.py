"""Mat-card like widget to display experiment details. Optionally, a button on the bottom which the user can click to trigger the selection of the experiment."""

from bec_lib.messages import ExperimentInfoMessage
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_theme_palette
from bec_widgets.utils.round_frame import RoundedFrame
from bec_widgets.widgets.services.bec_atlas_admin_view.experiment_selection.utils import (
    format_name,
    format_schedule,
)
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton


class BorderLessLabel(QLabel):
    """A QLabel that does not show any border, even when stylesheets try to apply one."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet("border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)


class ExperimentMatCard(BECWidget, QWidget):

    RPC = False

    experiment_selected = Signal(dict)

    def __init__(
        self,
        parent=None,
        show_activate_button: bool = True,
        button_text: str = "Activate",
        title: str = "Next Experiment",
        **kwargs,
    ):
        super().__init__(parent=parent, theme_update=True, **kwargs)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.experiment_info = {}
        self._abstract_text = ""

        # Add card frame with shadow and custom styling
        self._card_frame = QFrame(parent=self)
        layout = QVBoxLayout(self._card_frame)
        self._card_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        palette = get_theme_palette()
        self._card_frame.setStyleSheet(
            f"""
                QFrame {{
                    border: 1px solid {palette.mid().color().name()};
                    background: {palette.base().color().name()};
                }}
            """
        )
        shadow = QGraphicsDropShadowEffect(self._card_frame)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(palette.shadow().color())
        self._card_frame.setGraphicsEffect(shadow)

        self._group_box = QGroupBox(self._card_frame)
        self._group_box.setStyleSheet(
            "QGroupBox { border: none; }; QLabel { border: none; padding: 0px; }"
        )
        self._fill_group_box(
            title=title, show_activate_button=show_activate_button, button_text=button_text
        )
        self.apply_theme("light")

    def apply_theme(self, theme: str):
        palette = get_theme_palette()
        self._card_frame.setStyleSheet(
            f"""
                QFrame {{
                    border: 1px solid {palette.mid().color().name()};
                    background: {palette.base().color().name()};
                }}
            """
        )
        shadow = self._card_frame.graphicsEffect()
        if isinstance(shadow, QGraphicsDropShadowEffect):
            shadow.setColor(palette.shadow().color())

    def _fill_group_box(
        self, title: str, show_activate_button: bool, button_text: str = "Activate"
    ):
        group_layout = QVBoxLayout(self._group_box)
        group_layout.setContentsMargins(16, 16, 16, 16)
        group_layout.setSpacing(12)

        title_row = QHBoxLayout()
        self._card_title = BorderLessLabel(title, self._group_box)
        self._card_title.setStyleSheet(
            """
            border: none;
            font-size: 14px;
            font-weight: 600;
            """
        )

        # Add title row and info button to QH layout, then add it to QV layout
        title_row.addWidget(self._card_title)
        title_row.addStretch(1)
        group_layout.addLayout(title_row)

        self._card_grid = QGridLayout()
        self._card_grid.setHorizontalSpacing(12)
        self._card_grid.setVerticalSpacing(8)
        self._card_grid.setColumnStretch(1, 1)

        self._card_pgroup = BorderLessLabel("-", self._group_box)
        self._card_title_value = BorderLessLabel("-", self._group_box)
        self._card_title_value.setWordWrap(True)
        self._card_title_value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._card_name = BorderLessLabel("-", self._group_box)
        self._card_start = BorderLessLabel("-", self._group_box)
        self._card_end = BorderLessLabel("-", self._group_box)

        self._card_row_labels = []

        def _row_label(text):
            label = BorderLessLabel(text, self._group_box)
            self._card_row_labels.append(label)
            return label

        self._card_grid.addWidget(_row_label("Name"), 0, 0)
        self._card_grid.addWidget(self._card_name, 0, 1)
        self._card_grid.addWidget(_row_label("Title"), 1, 0)
        self._card_grid.addWidget(self._card_title_value, 1, 1)
        self._card_grid.addWidget(_row_label("P-group"), 2, 0)
        self._card_grid.addWidget(self._card_pgroup, 2, 1)
        self._card_grid.addWidget(_row_label("Schedule (start)"), 3, 0)
        self._card_grid.addWidget(self._card_start, 3, 1)
        self._card_grid.addWidget(_row_label("Schedule (end)"), 4, 0)
        self._card_grid.addWidget(self._card_end, 4, 1)

        # Add to groupbox
        group_layout.addLayout(self._card_grid)

        # Add abstract field at the bottom of the card.
        self._abstract_label = BorderLessLabel("", self._group_box)
        self._abstract_label.setWordWrap(True)
        self._abstract_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        group_layout.addWidget(self._abstract_label)

        # Add activate button at the bottom
        self._activate_button = QPushButton(button_text, self._group_box)
        self._activate_button.clicked.connect(self._emit_next_experiment)
        self._activate_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        group_layout.addWidget(self._activate_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._activate_button.setVisible(show_activate_button)
        self._activate_button.setEnabled(False)

        self._card_frame.layout().setContentsMargins(12, 12, 12, 12)
        self._card_frame.layout().addWidget(self._group_box)

        card_row = QHBoxLayout()
        card_row.addStretch(0)
        card_row.addWidget(self._card_frame)
        card_row.addStretch(0)

        layout = self.layout()
        layout.addStretch(0)
        layout.addLayout(card_row)
        layout.addStretch(0)

    def _emit_next_experiment(self):
        self.experiment_selected.emit(self.experiment_info)

    def clear_experiment_info(self):
        """
        Clear the experiment information displayed on the card and disable the activate button.
        """
        self._card_pgroup.setText("-")
        self._card_title_value.setText("-")
        self._card_name.setText("-")
        self._card_start.setText("-")
        self._card_end.setText("-")
        self._abstract_text = ""
        self._abstract_label.setText("")
        self.experiment_info = {}
        self._activate_button.setEnabled(False)

    def set_experiment_info(self, info: ExperimentInfoMessage | dict):
        """
        Set the experiment information to display on the card.

        Args:
            info (ExperimentInfoMessage | dict): The experiment information to display. Can be either a
                dictionary or an ExperimentInfoMessage instance.
        """
        if isinstance(info, dict):
            info = ExperimentInfoMessage(**info)

        start, end = format_schedule(info.schedule)
        self._card_pgroup.setText(info.pgroup or "-")
        self._card_title_value.setText(info.title or "-")
        self._card_name.setText(format_name(info))
        self._card_start.setText(start or "-")
        self._card_end.setText(end or "-")
        self._abstract_text = (info.abstract or "").strip()
        self._abstract_label.setText(self._abstract_text if self._abstract_text else "")
        self.experiment_info = info.model_dump()
        self._activate_button.setEnabled(True)

    def set_title(self, title: str):
        """
        Set the title displayed at the top of the card.

        Args:
            title (str): The title text to display.
        """
        self._card_title.setText(title)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    exp_info = {
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
    }

    app = QApplication(sys.argv)

    apply_theme("dark")
    w = QWidget()
    l = QVBoxLayout(w)
    button = DarkModeButton()
    widget = ExperimentMatCard()
    widget.set_experiment_info(exp_info)
    widget.set_title("Scheduled Experiment")
    l.addWidget(button)
    l.addWidget(widget)
    w.resize(w.sizeHint())
    w.show()
    sys.exit(app.exec())
