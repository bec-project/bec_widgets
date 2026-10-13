"""Compact status-bar pill for the BEC status box.

The pill shows the overall BEC state in a few words. Clicking it opens the full status box in a
popup, which has a button to put a status box into the dock area.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QPoint, QSize, Qt, Signal
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.colors import rgba
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.services.bec_status_box.status_box_widgets import theme_colors, tone_color

PILL_TEXT = {"All core services running": "BEC running", "Waiting for BEC services": "BEC: waiting"}


class StatusPopup(QFrame):
    """Popup frame holding the full status box and the dock button."""

    dock_requested = Signal()

    def __init__(self, parent: QWidget, status_box: BECStatusBox):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("StatusPopup")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        header = QHBoxLayout()
        title = QLabel("BEC services", self)
        title.setObjectName("popupTitle")
        self.dock_button = QToolButton(self)
        self.dock_button.setObjectName("dockButton")
        self.dock_button.setText("Open in dock area")
        self.dock_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.dock_button.setIconSize(QSize(16, 16))
        self.dock_button.setAutoRaise(True)
        self.dock_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dock_button.clicked.connect(self._on_dock)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.dock_button)
        layout.addLayout(header)
        self.status_box = status_box
        status_box.setParent(self)
        layout.addWidget(status_box, 1)
        self.resize(400, 540)
        self.apply_theme()

    def _on_dock(self):
        self.hide()
        self.dock_requested.emit()

    def apply_theme(self) -> None:
        """Restyle with the current theme colors."""
        colors = theme_colors()
        self.dock_button.setIcon(
            material_icon(
                "dock_to_right", size=(16, 16), color=colors["FG"], convert_to_pixmap=False
            )
        )
        self.setStyleSheet(
            f"#StatusPopup {{ background: {colors['BG'].name()}; border: 1px solid "
            f"{colors['BORDER'].name()}; border-radius: 8px; }}"
            f"#popupTitle {{ color: {colors['FG'].name()}; font-weight: bold; }}"
        )


class BECStatusPill(QPushButton):
    """A pill for the status bar that summarises BEC and opens the status box on click.

    Args:
        parent (QWidget | None): The parent widget, usually the main window.
        view (str | None): View of the status box in the popup, "qml" or "widgets".
        client: The BEC client, passed to the status box.
    """

    dock_requested = Signal()

    def __init__(self, parent: QWidget | None = None, view: str | None = None, client=None):
        super().__init__(parent)
        self.setObjectName("BECStatusPill")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setIconSize(QSize(10, 10))
        self.status_box = BECStatusBox(view=view, client=client, rpc_exposed=False)
        self.popup = StatusPopup(self, self.status_box)
        self.popup.dock_requested.connect(self.dock_requested)
        self.model = self.status_box.model
        self.model.summaryChanged.connect(self.refresh)
        self.model.restartChanged.connect(self.refresh)
        self.clicked.connect(self.toggle_popup)
        theme = getattr(QApplication.instance(), "theme", None)
        if theme is not None:
            theme.theme_changed.connect(self.apply_theme)
        self.refresh()

    @property
    def tone(self) -> str:
        """The tone of the pill, following a running restart first."""
        state = self.model.restartState
        if state:
            return {"running": "progress", "done": "success"}.get(state, "emergency")
        return self.model.tone

    def text_for_state(self) -> str:
        """The short pill text."""
        if self.model.restartState:
            return self.model.restartText.replace("BEC server", "BEC")
        return PILL_TEXT.get(self.model.headline, self.model.headline)

    def refresh(self) -> None:
        """Update the text, colors and tooltip from the model."""
        self.setText(self.text_for_state())
        self.setToolTip(f"{self.model.headline}\n{self.model.detail}\nClick for details")
        self.apply_theme()

    def apply_theme(self, _theme: str | None = None) -> None:
        """Restyle with the current theme colors."""
        colors = theme_colors()
        accent = tone_color(colors, self.tone)
        self.setIcon(material_icon("circle", size=(10, 10), color=accent, filled=True))
        self.setStyleSheet(
            f"#BECStatusPill {{ color: {colors['FG'].name()}; background: {rgba(accent, 38)};"
            f" border: 1px solid {rgba(accent, 120)}; border-radius: 9px; padding: 1px 10px;"
            f" font-size: 11px; }}"
            f"#BECStatusPill:hover {{ background: {rgba(accent, 70)}; }}"
        )
        self.popup.apply_theme()

    def toggle_popup(self) -> None:
        """Open the status box above the pill, or close it when open."""
        if self.popup.isVisible():
            self.popup.hide()
            return
        size = self.popup.size()
        anchor = self.mapToGlobal(QPoint(self.width(), 0))
        self.popup.move(anchor.x() - size.width(), anchor.y() - size.height() - 6)
        self.popup.show()
        self.popup.raise_()

    def cleanup(self) -> None:
        """Clean up the status box inside the popup."""
        self.status_box.cleanup()
        self.status_box.deleteLater()
        self.popup.deleteLater()
