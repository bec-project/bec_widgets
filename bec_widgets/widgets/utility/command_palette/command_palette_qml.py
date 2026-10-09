"""Qt Quick rendering of the command palette card.

Twin of :mod:`command_palette_qwidget`. The QML scene in ``qml/CommandPaletteView.qml`` binds to
the shared :class:`CommandPaletteController` and its list model; it draws its own shadow inside
:attr:`PaletteCardQuick.shadow_margin`.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import QMetaObject, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils.quick.host import ThemeTokens, create_quick_widget, release_quick_widget
from bec_widgets.widgets.utility.command_palette.palette_core import CommandPaletteController

QML_FILE = Path(__file__).parent / "qml" / "CommandPaletteView.qml"


class PaletteCardQuick(QWidget):
    """Hosts the QML palette card in a transparent :class:`QQuickWidget`.

    Args:
        controller(CommandPaletteController): Shared search state.
        parent(QWidget | None): The hosting overlay.
    """

    shadow_margin = 24

    def __init__(self, controller: CommandPaletteController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(
            self,
            QML_FILE,
            {"backend": controller, "paletteModel": controller.model, "margin": self.shadow_margin},
        )
        # let the dimmed window show through the rounded corners and the shadow
        self.view.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.view.setClearColor(QColor(Qt.GlobalColor.transparent))
        layout.addWidget(self.view)

    def focus_input(self) -> None:
        """Give the keyboard focus to the QML search field."""
        self.view.setFocus(Qt.FocusReason.PopupFocusReason)
        root = self.view.rootObject()
        if root is not None:
            QMetaObject.invokeMethod(root, "opened")

    def refresh_theme(self, _tokens: ThemeTokens) -> None:
        """The QML ``theme`` object follows the application theme on its own."""

    def release(self) -> None:
        """Unload the scene before the controller goes away."""
        release_quick_widget(self.view)
