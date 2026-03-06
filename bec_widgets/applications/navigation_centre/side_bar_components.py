from __future__ import annotations

from bec_qthemes import material_icon
from qtpy import QtCore
from qtpy.QtCore import QEasingCurve, QPropertyAnimation, Qt
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import SafeProperty
from bec_widgets.applications.navigation_centre.reveal_animator import (
    ANIMATION_DURATION,
    RevealAnimator,
)


def get_on_primary():
    app = QApplication.instance()
    if app is not None and hasattr(app, "theme"):
        return app.theme.color("ON_PRIMARY")
    return "#FFFFFF"


def get_fg():
    app = QApplication.instance()
    if app is not None and hasattr(app, "theme"):
        return app.theme.color("FG")
    return "#FFFFFF"


class SideBarSeparator(QFrame):
    """A horizontal line separator for use in SideBar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SideBarSeparator")
        self.setFrameShape(QFrame.NoFrame)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(2)
        self.setProperty("variant", "separator")


class SectionHeader(QWidget):
    """A section header with a label and a horizontal line below."""

    def __init__(self, parent=None, text: str = None, anim_duration: int = ANIMATION_DURATION):
        super().__init__(parent)
        self.setObjectName("SectionHeader")

        self.lbl = QLabel(text, self)
        self.lbl.setObjectName("SectionHeaderLabel")
        self.lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._reveal = RevealAnimator(self.lbl, duration=anim_duration, initially_revealed=False)

        self.line = SideBarSeparator(self)

        lay = QVBoxLayout(self)
        # keep your margins/spacing preferences here if needed
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(6)
        lay.addWidget(self.lbl)
        lay.addWidget(self.line)

        self.animations = self.build_animations()

    def build_animations(self) -> list[QPropertyAnimation]:
        """
        Build and return animations for expanding/collapsing the sidebar.

        Returns:
            list[QPropertyAnimation]: List of animations.
        """
        return self._reveal.animations()

    def setup_animations(self, expanded: bool):
        """
        Setup animations for expanding/collapsing the sidebar.

        Args:
            expanded(bool): True if the sidebar is expanded, False if collapsed.
        """
        self._reveal.setup(expanded)


class NavigationItem(QWidget):
    """A nav tile with an icon + labels and an optional expandable body.
    Provides animations for collapsed/expanded sidebar states via
    build_animations()/setup_animations(), similar to SectionHeader.
    """

    activated = QtCore.Signal()

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        icon_name: str,
        mini_text: str | None = None,
        toggleable: bool = True,
        exclusive: bool = True,
        anim_duration: int = ANIMATION_DURATION,
    ):
        super().__init__(parent=parent)
        self.setObjectName("NavigationItem")

        # Private attributes
        self._title = title
        self._icon_name = icon_name
        self._mini_text = mini_text or title
        self._toggleable = toggleable
        self._toggled = False
        self._exclusive = exclusive

        # Main Icon
        self.icon_btn = QToolButton(self)
        self.icon_btn.setIcon(material_icon(self._icon_name, filled=False, convert_to_pixmap=False))
        self.icon_btn.setAutoRaise(True)
        self._icon_size_collapsed = QtCore.QSize(20, 20)
        self._icon_size_expanded = QtCore.QSize(26, 26)
        self.icon_btn.setIconSize(self._icon_size_collapsed)
        # Remove QToolButton hover/pressed background/outline
        self.icon_btn.setStyleSheet("""
            QToolButton:hover { background: transparent; border: none; }
            QToolButton:pressed { background: transparent; border: none; }
            """)

        # Mini label below icon
        self.mini_lbl = QLabel(self._mini_text, self)
        self.mini_lbl.setObjectName("NavMiniLabel")
        self.mini_lbl.setAlignment(Qt.AlignCenter)
        self.mini_lbl.setStyleSheet("font-size: 10px;")
        self.reveal_mini_lbl = RevealAnimator(
            widget=self.mini_lbl,
            initially_revealed=True,
            animate_width=False,
            duration=anim_duration,
        )

        # Container for icon + mini label
        self.mini_icon = QWidget(self)
        mini_lay = QVBoxLayout(self.mini_icon)
        mini_lay.setContentsMargins(0, 2, 0, 2)
        mini_lay.setSpacing(2)
        mini_lay.addWidget(self.icon_btn, 0, Qt.AlignCenter)
        mini_lay.addWidget(self.mini_lbl, 0, Qt.AlignCenter)

        # Title label
        self.title_lbl = QLabel(self._title, self)
        self.title_lbl.setObjectName("NavTitleLabel")
        self.title_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_lbl.setStyleSheet("font-size: 13px;")
        self.reveal_title_lbl = RevealAnimator(
            widget=self.title_lbl,
            initially_revealed=False,
            animate_height=False,
            duration=anim_duration,
        )
        self.title_lbl.setVisible(False)  # TODO dirty trick to avoid layout shift

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 2, 12, 2)
        lay.setSpacing(6)
        lay.addWidget(self.mini_icon, 0, Qt.AlignHCenter | Qt.AlignTop)
        lay.addWidget(self.title_lbl, 1, Qt.AlignLeft | Qt.AlignVCenter)

        self.icon_size_anim = QPropertyAnimation(self.icon_btn, b"iconSize")
        self.icon_size_anim.setDuration(anim_duration)
        self.icon_size_anim.setEasingCurve(QEasingCurve.InOutCubic)

        # Connect icon button to emit activation
        self.icon_btn.clicked.connect(self._emit_activated)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_StyledBackground, True)

    def is_active(self) -> bool:
        """Return whether the item is currently active/selected."""
        return self.property("toggled") is True

    def build_animations(self) -> list[QPropertyAnimation]:
        """
        Build and return animations for expanding/collapsing the sidebar.

        Returns:
            list[QPropertyAnimation]: List of animations.
        """
        return (
            self.reveal_title_lbl.animations()
            + self.reveal_mini_lbl.animations()
            + [self.icon_size_anim]
        )

    def setup_animations(self, expanded: bool):
        """
        Setup animations for expanding/collapsing the sidebar.

        Args:
            expanded(bool): True if the sidebar is expanded, False if collapsed.
        """
        self.reveal_mini_lbl.setup(not expanded)
        self.reveal_title_lbl.setup(expanded)
        self.icon_size_anim.setStartValue(self.icon_btn.iconSize())
        self.icon_size_anim.setEndValue(
            self._icon_size_expanded if expanded else self._icon_size_collapsed
        )

    def set_visible(self, visible: bool):
        """Set visibility of the title label."""
        self.title_lbl.setVisible(visible)

    def _emit_activated(self):
        self.activated.emit()

    def set_active(self, active: bool):
        """
        Set the active/selected state of the item.

        Args:
            active(bool): True to set active, False to deactivate.
        """
        self.setProperty("toggled", active)
        self.toggled = active
        # ensure style refresh
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        self.activated.emit()
        super().mousePressEvent(event)

    @SafeProperty(bool)
    def toggleable(self) -> bool:
        """
        Whether the item is toggleable (like a button) or not (like an action).

        Returns:
            bool: True if toggleable, False otherwise.
        """
        return self._toggleable

    @toggleable.setter
    def toggleable(self, value: bool):
        """
        Set whether the item is toggleable (like a button) or not (like an action).
        Args:
            value(bool): True to make toggleable, False otherwise.
        """
        self._toggleable = bool(value)

    @SafeProperty(bool)
    def toggled(self) -> bool:
        """
        Whether the item is currently toggled/selected.

        Returns:
            bool: True if toggled, False otherwise.
        """
        return self._toggled

    @toggled.setter
    def toggled(self, value: bool):
        """
        Set whether the item is currently toggled/selected.

        Args:
            value(bool): True to set toggled, False to untoggle.
        """
        self._toggled = value
        if value:
            new_icon = material_icon(
                self._icon_name, filled=True, color=get_on_primary(), convert_to_pixmap=False
            )
        else:
            new_icon = material_icon(
                self._icon_name, filled=False, color=get_fg(), convert_to_pixmap=False
            )
        self.icon_btn.setIcon(new_icon)
        # Re-polish so QSS applies correct colors to icon/labels
        for w in (self, self.icon_btn, self.title_lbl, self.mini_lbl):
            w.style().unpolish(w)
            w.style().polish(w)
            w.update()

    @SafeProperty(bool)
    def exclusive(self) -> bool:
        """
        Whether the item is exclusive in its toggle group.

        Returns:
            bool: True if exclusive, False otherwise.
        """
        return self._exclusive

    @exclusive.setter
    def exclusive(self, value: bool):
        """
        Set whether the item is exclusive in its toggle group.

        Args:
            value(bool): True to make exclusive, False otherwise.
        """
        self._exclusive = bool(value)

    def refresh_theme(self):
        # Recompute icon/label colors according to current theme and state
        # Trigger the toggled setter to rebuild the icon with the correct color
        self.toggled = self._toggled
        # Ensure QSS-driven text/icon colors refresh
        for w in (self, self.icon_btn, self.title_lbl, self.mini_lbl):
            w.style().unpolish(w)
            w.style().polish(w)
            w.update()


class DarkModeNavItem(NavigationItem):
    """Bottom action item that toggles app theme and updates its icon/text."""

    def __init__(
        self, parent=None, *, id: str = "dark_mode", anim_duration: int = ANIMATION_DURATION
    ):
        super().__init__(
            parent=parent,
            title="Dark mode",
            icon_name="dark_mode",
            mini_text="Dark",
            toggleable=False,  # action-like, no selection highlight changes
            exclusive=False,
            anim_duration=anim_duration,
        )
        self._id = id
        self._sync_from_qapp_theme()
        self.activated.connect(self.toggle_theme)

    def _qapp_dark_enabled(self) -> bool:
        qapp = QApplication.instance()
        return bool(getattr(getattr(qapp, "theme", None), "theme", None) == "dark")

    def _sync_from_qapp_theme(self):
        is_dark = self._qapp_dark_enabled()
        # Update labels
        self.title_lbl.setText("Light mode" if is_dark else "Dark mode")
        self.mini_lbl.setText("Light" if is_dark else "Dark")
        # Update icon
        self.icon_btn.setIcon(
            material_icon("light_mode" if is_dark else "dark_mode", convert_to_pixmap=False)
        )

    def refresh_theme(self):
        self._sync_from_qapp_theme()
        for w in (self, self.icon_btn, self.title_lbl, self.mini_lbl):
            w.style().unpolish(w)
            w.style().polish(w)
            w.update()

    def toggle_theme(self):
        """Toggle application theme and update icon/text."""
        from bec_widgets.utils.colors import apply_theme

        is_dark = self._qapp_dark_enabled()

        apply_theme("light" if is_dark else "dark")
        self._sync_from_qapp_theme()
