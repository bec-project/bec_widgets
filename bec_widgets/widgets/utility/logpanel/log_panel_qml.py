"""Reworked BEC log panel rendered with Qt Quick (QML).

Same UX as :mod:`log_panel_qwidget`; all state and actions live in
:class:`~.log_ux_common.LogPanelBackend` and the rows come from its ``LogFeedModel``. Only the
drawing is QML (``qml/LogPanelView.qml``).
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QFontDatabase, QKeySequence, QShortcut
from qtpy.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.quick import create_quick_widget, release_quick_widget
from bec_widgets.widgets.utility.logpanel.log_ux_common import LogPanelBackend

QML_FILE = Path(__file__).parent / "qml" / "LogPanelView.qml"


class LogPanelQml(BECWidget, QWidget):
    """Live BEC log viewer with level chips, search with highlight, follow-tail and folding.

    Args:
        parent: Parent widget.
        backend(LogPanelBackend | None): Use an existing backend (tests, demos). By default the
            panel creates one fed by the live BEC log stream.
    """

    PLUGIN = False
    RPC = False
    ICON_NAME = "browse_activity"

    def __init__(
        self, parent: QWidget | None = None, backend: LogPanelBackend | None = None, **kwargs
    ):
        super().__init__(parent=parent, **kwargs)
        self.backend = backend or LogPanelBackend(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
        self.view = create_quick_widget(
            self, QML_FILE, {"backend": self.backend, "monoFamily": mono}
        )
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.view)
        for keys, slot in (
            (QKeySequence.StandardKey.Find, self.backend.focus_search),
            (QKeySequence.StandardKey.FindNext, self.backend.nextMatch),
            (QKeySequence.StandardKey.FindPrevious, self.backend.prevMatch),
            (QKeySequence.StandardKey.Copy, self._copy_current),
            (QKeySequence(Qt.Key.Key_End), self.backend.jumpToLatest),
        ):
            shortcut = QShortcut(keys, self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)
        self.backend.scroll_to_end.emit()

    @SafeSlot()
    def _copy_current(self) -> None:
        row = self.backend.model.current_row()
        if row >= 0:
            self.backend.copyRow(row)

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """Re-read the theme colours used by the rows (the QML theme bridge follows itself)."""
        self.backend.refresh_theme()
        self.view.setClearColor(self.palette().window().color())

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        return QSize(900, 420)

    def cleanup(self):
        """Unload the scene and detach from the BEC log stream."""
        release_quick_widget(self.view)
        self.backend.cleanup()
        super().cleanup()
