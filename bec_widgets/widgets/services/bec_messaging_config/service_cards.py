"""Module for service scope cards used by the messaging configuration widget."""

from __future__ import annotations

import uuid
from enum import IntEnum
from typing import TYPE_CHECKING, Literal, Type

from bec_qthemes import material_icon
from qtpy.QtCore import QRegularExpression, Qt, QTimer, Signal  # type: ignore[attr-defined]
from qtpy.QtGui import QRegularExpressionValidator
from qtpy.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QStackedLayout,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_lib import messages

CardType = Literal["scilog", "signal", "teams"]


class ScopeListWidget(QScrollArea):
    """A scrollable list that stacks scope cards neatly at the top."""

    cards_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(4, 8, 4, 8)
        self._layout.setSpacing(16)

        self._spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self._layout.addSpacerItem(self._spacer)

        self.setWidget(self._container)

    def add_card(self, card: BaseScopeCard) -> None:
        """Insert a card above the trailing spacer.

        Args:
            card (BaseScopeCard): The card widget to add to the list.
        """
        idx = self._layout.count() - 1
        self._layout.insertWidget(idx, card)
        card.delete_requested.connect(lambda: self._remove_card(card))
        card.delete_requested.connect(self.cards_changed)
        card.data_changed.connect(self.cards_changed)
        self.cards_changed.emit()

    def clear_cards(self) -> None:
        """Remove all cards without touching the trailing spacer."""
        for index in range(self._layout.count() - 2, -1, -1):
            item = self._layout.itemAt(index)
            if item is None:
                continue
            card = item.widget()
            if isinstance(card, BaseScopeCard):
                self._layout.removeWidget(card)
                card.deleteLater()
        self.cards_changed.emit()

    def cards(self) -> list[BaseScopeCard]:
        """Return the cards currently stored in the list."""
        results: list[BaseScopeCard] = []
        for index in range(self._layout.count()):
            item = self._layout.itemAt(index)
            if item is None:
                continue
            card = item.widget()
            if isinstance(card, BaseScopeCard):
                results.append(card)
        return results

    def _remove_card(self, card: BaseScopeCard) -> None:
        self._layout.removeWidget(card)
        card.deleteLater()
        self.cards_changed.emit()


class BaseScopeCard(QFrame):
    """Base card with shared identity, scope, and enabled fields."""

    delete_requested = Signal()
    data_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._id: str = str(uuid.uuid4())

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet(
            "BaseScopeCard {"
            "  border: 1px solid palette(mid);"
            "  border-radius: 6px;"
            "  background: palette(base);"
            "}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.enabled_checkbox = QCheckBox("Enabled")
        self.enabled_checkbox.setChecked(True)
        self.enabled_checkbox.toggled.connect(self.data_changed)
        header_row.addWidget(self.enabled_checkbox)
        header_row.addStretch(1)

        self._delete_btn = QToolButton()
        delete_icon = material_icon(
            "delete", size=(25, 25), convert_to_pixmap=False, filled=False, color="#CC181E"
        )
        self._delete_btn.setToolTip("Delete this scope configuration")
        self._delete_btn.setIcon(delete_icon)
        self._delete_btn.clicked.connect(self.delete_requested)
        header_row.addWidget(self._delete_btn)

        root.addLayout(header_row)

        identity_row = QHBoxLayout()
        identity_row.setSpacing(16)

        scope_col = QVBoxLayout()
        scope_col.setSpacing(4)
        scope_col.addWidget(QLabel("Scope"))
        self.scope_edit = QLineEdit()
        self.scope_edit.setPlaceholderText("e.g. user, admin")
        self.scope_edit.textChanged.connect(self.data_changed)
        scope_col.addWidget(self.scope_edit)
        identity_row.addLayout(scope_col, 1)

        name_col = QVBoxLayout()
        name_col.setSpacing(4)
        name_col.addWidget(QLabel("Name (optional)"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("display name")
        self.name_edit.textChanged.connect(self.data_changed)
        name_col.addWidget(self.name_edit)
        identity_row.addLayout(name_col, 1)

        root.addLayout(identity_row)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)
        root.addLayout(self.content_layout)

    def get_data(self) -> dict:
        """Return the common payload for a messaging service card."""
        return {
            "id": self._id,
            "scope": self.scope_edit.text(),
            "enabled": self.enabled_checkbox.isChecked(),
            "name": self.name_edit.text() or None,
        }

    def set_data(self, info: messages.MessagingService) -> None:  # type: ignore[name-defined]
        """Populate the shared card fields from a messaging service.

        Args:
            info (messages.MessagingService): The service object used to populate the card.
        """
        self._id = info.id
        self.scope_edit.setText(info.scope)
        self.enabled_checkbox.setChecked(info.enabled)
        self.name_edit.setText(info.name or "")


class SciLogScopeCard(BaseScopeCard):
    """Card used to configure SciLog service settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(QLabel("Logbook ID"))
        self.logbook_id_edit = QLineEdit()
        self.logbook_id_edit.setPlaceholderText("e.g. lb-12345")
        self.logbook_id_edit.textChanged.connect(self.data_changed)
        col.addWidget(self.logbook_id_edit)
        self.content_layout.addLayout(col)

    def get_data(self) -> dict:
        """Return the SciLog-specific payload for this card."""
        data = super().get_data()
        data["service_type"] = "scilog"
        data["logbook_id"] = self.logbook_id_edit.text()
        return data

    def set_data(self, info: messages.SciLogServiceInfo) -> None:  # type: ignore[override]
        """Populate the card from SciLog service information.

        Args:
            info (messages.SciLogServiceInfo): The SciLog service object used to populate the card.
        """
        super().set_data(info)
        self.logbook_id_edit.setText(info.logbook_id)


class TeamsScopeCard(BaseScopeCard):
    """Card used to configure MS Teams service settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        fields_row = QHBoxLayout()
        fields_row.setSpacing(16)

        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(QLabel("Workflow Webhook URL"))
        self.workflow_webhook_url_edit = edit = QLineEdit(parent=self)
        edit.setPlaceholderText("e.g. https://outlook.office.com/webhook/…")
        edit.textChanged.connect(self.data_changed)
        col.addWidget(edit)
        fields_row.addLayout(col, 1)

        self.content_layout.addLayout(fields_row)

    def get_data(self) -> dict:
        """Return the MS Teams-specific payload for this card."""
        data = super().get_data()
        data["service_type"] = "teams"
        data["workflow_webhook_url"] = self.workflow_webhook_url_edit.text()
        return data

    def set_data(self, info: messages.TeamsServiceInfo) -> None:  # type: ignore[override]
        """Populate the card from MS Teams service information.

        Args:
            info (messages.TeamsServiceInfo): The MS Teams service object used to populate the card.
        """
        super().set_data(info)
        self.workflow_webhook_url_edit.setText(info.workflow_webhook_url)


class _SignalState(IntEnum):
    UNCONFIGURED = 0
    PENDING = 1
    CONFIGURED = 2


class SignalScopeCard(BaseScopeCard):
    """Card used to configure Signal service settings and linking state."""

    _MOCK_GROUP_ID = "grp-8a3f291c"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._state = _SignalState.UNCONFIGURED
        self._mock_group_id: str = ""
        self._mock_group_link: str = ""

        stacked_container = QWidget()
        self._stacked = QStackedLayout(stacked_container)
        self._stacked.setContentsMargins(0, 0, 0, 0)
        self.content_layout.addWidget(stacked_container)

        self._build_unconfigured_page()
        self._build_pending_page()
        self._build_configured_page()

        self._stacked.setCurrentIndex(_SignalState.UNCONFIGURED)

    def _build_unconfigured_page(self) -> None:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        phone_col = QVBoxLayout()
        phone_col.setSpacing(4)
        phone_col.addWidget(QLabel("Phone Number"))
        self._phone_edit = QLineEdit()
        self._phone_edit.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"^\+\S*$"), self._phone_edit)
        )
        self._phone_edit.setPlaceholderText("+41791234567")
        self._phone_edit.textChanged.connect(self.data_changed)
        phone_col.addWidget(self._phone_edit)
        row.addLayout(phone_col, 1)

        start_linking_btn = QPushButton("Start Linking")
        start_linking_btn.setFixedWidth(100)
        start_linking_btn.clicked.connect(self._on_ping_clicked)
        row.addWidget(start_linking_btn, 0, Qt.AlignmentFlag.AlignBottom)

        self._stacked.addWidget(page)

    def _build_pending_page(self) -> None:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        waiting_lbl = QLabel("⏳ Waiting for you to reply on Signal…")
        waiting_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(waiting_lbl)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self._on_cancel_clicked)
        row.addWidget(cancel_btn)

        self._stacked.addWidget(page)

    def _build_configured_page(self) -> None:
        page = QWidget()
        row = QHBoxLayout(page)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._linked_lbl = QLabel("🟢 Linked (Group ID: —)")
        self._linked_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self._linked_lbl)

        unlink_btn = QPushButton("Unlink")
        unlink_btn.clicked.connect(self._on_unlink_clicked)
        row.addWidget(unlink_btn)

        self._stacked.addWidget(page)

    def _on_ping_clicked(self) -> None:
        self._state = _SignalState.PENDING
        self._stacked.setCurrentIndex(_SignalState.PENDING)
        QTimer.singleShot(3000, self._mock_backend_confirmation)

    def _mock_backend_confirmation(self) -> None:
        if self._state != _SignalState.PENDING:
            return
        self._mock_group_id = self._MOCK_GROUP_ID
        self._mock_group_link = f"https://signal.group/#{self._mock_group_id}"
        self._linked_lbl.setText(f"🟢 Linked (Group ID: {self._mock_group_id})")
        self._state = _SignalState.CONFIGURED
        self._stacked.setCurrentIndex(_SignalState.CONFIGURED)
        self.data_changed.emit()

    def _on_cancel_clicked(self) -> None:
        self._state = _SignalState.UNCONFIGURED
        self._stacked.setCurrentIndex(_SignalState.UNCONFIGURED)
        self.data_changed.emit()

    def _on_unlink_clicked(self) -> None:
        self._mock_group_id = ""
        self._mock_group_link = ""
        self._state = _SignalState.UNCONFIGURED
        self._stacked.setCurrentIndex(_SignalState.UNCONFIGURED)
        self.data_changed.emit()

    def get_data(self) -> dict:
        """Return the Signal-specific payload for this card."""
        data = super().get_data()
        data["service_type"] = "signal"
        configured = self._state == _SignalState.CONFIGURED
        data["group_id"] = self._mock_group_id if configured else None
        data["group_link"] = self._mock_group_link if configured else None
        return data

    def set_data(self, info: messages.SignalServiceInfo) -> None:  # type: ignore[override]
        """Populate the card from Signal service information.

        Args:
            info (messages.SignalServiceInfo): The Signal service object used to populate the card.
        """
        super().set_data(info)
        if info.group_id:
            self._mock_group_id = info.group_id
            self._mock_group_link = info.group_link or ""
            self._linked_lbl.setText(f"🟢 Linked (Group ID: {self._mock_group_id})")
            self._state = _SignalState.CONFIGURED
            self._stacked.setCurrentIndex(_SignalState.CONFIGURED)
            return
        self._mock_group_id = ""
        self._mock_group_link = ""
        self._state = _SignalState.UNCONFIGURED
        self._stacked.setCurrentIndex(_SignalState.UNCONFIGURED)


_CARD_CLASSES: dict[CardType, Type[BaseScopeCard]] = {
    "scilog": SciLogScopeCard,
    "signal": SignalScopeCard,
    "teams": TeamsScopeCard,
}


def make_card(card_type: CardType) -> BaseScopeCard:
    """Create a new service card for the requested card type.

    Args:
        card_type (CardType): The service type for the card to create.
    """
    return _CARD_CLASSES[card_type]()


def card_from_service(info: object) -> BaseScopeCard:
    """Create and populate a card from a messaging service object.

    Args:
        info (object): A messaging service object with a ``service_type`` attribute.
    """
    service_type: str = getattr(info, "service_type", "")
    card_class = _CARD_CLASSES.get(service_type)  # type: ignore[arg-type]
    if card_class is None:
        raise ValueError(f"Unknown service_type: {service_type!r}")
    card = card_class()
    card.set_data(info)  # type: ignore[arg-type]
    return card
