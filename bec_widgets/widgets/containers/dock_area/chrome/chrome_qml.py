"""QML version of the dock area chrome: the Add widget gallery and the empty state.

Both views share :class:`~.gallery_common.GalleryController` with the QWidget version, so search,
highlight, placement and starter layouts behave the same.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import QPoint, Qt, Signal
from qtpy.QtWidgets import QFrame, QVBoxLayout, QWidget

from bec_widgets.utils.quick.host import ThemeTokens, create_quick_widget, release_quick_widget
from bec_widgets.widgets.containers.dock_area.chrome.gallery_common import GalleryController

QML_DIR = Path(__file__).parent / "qml"


class WidgetGalleryQmlPopup(QFrame):
    """The Add widget gallery as a popup rendered with Qt Quick.

    Args:
        controller(GalleryController): Shared gallery state.
        parent(QWidget | None): Parent widget.
    """

    def __init__(self, controller: GalleryController, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("widgetGalleryQml")
        self.controller = controller
        self.resize(460, 540)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(
            self, QML_DIR / "WidgetGallery.qml", {"backend": controller}
        )
        self.view.setClearColor(ThemeTokens().card)
        layout.addWidget(self.view)
        root = self.view.rootObject()
        if root is not None:
            root.closeRequested.connect(self.close)
        controller.widget_requested.connect(lambda *_: self.close())

    def open_at(self, anchor: QWidget | None) -> None:
        """Show the gallery below ``anchor`` (or centred on the parent)."""
        self.controller.reset()
        if anchor is not None:
            pos = anchor.mapToGlobal(QPoint(0, anchor.height() + 4))
        else:
            parent = self.parentWidget()
            center = parent.mapToGlobal(parent.rect().center()) if parent else QPoint(200, 200)
            pos = center - QPoint(self.width() // 2, self.height() // 2)
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen is not None:
            pos.setX(max(screen.left(), min(pos.x(), screen.right() - self.width())))
            pos.setY(max(screen.top(), min(pos.y(), screen.bottom() - self.height())))
        self.move(pos)
        self.show()
        self.view.setFocus(Qt.FocusReason.PopupFocusReason)
        root = self.view.rootObject()
        if root is not None:
            root.focusSearch()

    def refresh_theme(self) -> None:
        """The QML scene follows ``theme`` by itself; only the clear colour is updated."""
        self.view.setClearColor(ThemeTokens().card)

    def cleanup(self) -> None:
        """Unload the scene before the controller goes away."""
        release_quick_widget(self.view)


class EmptyStateQml(QWidget):
    """The empty-workspace view rendered with Qt Quick.

    Args:
        controller(GalleryController): Shared gallery state (starter layouts).
        parent(QWidget | None): Parent widget.
    """

    add_requested = Signal()

    def __init__(self, controller: GalleryController, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("dockEmptyStateQml")
        self.controller = controller
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(self, QML_DIR / "EmptyState.qml", {"backend": controller})
        self.view.setClearColor(ThemeTokens().bg)
        layout.addWidget(self.view)
        root = self.view.rootObject()
        if root is not None:
            root.addRequested.connect(self.add_requested)

    def refresh_theme(self) -> None:
        """The QML scene follows ``theme`` by itself; only the clear colour is updated."""
        self.view.setClearColor(ThemeTokens().bg)

    def cleanup(self) -> None:
        """Unload the scene before the controller goes away."""
        release_quick_widget(self.view)


class ProfileSwitcherQmlPopup(QFrame):
    """The profile switcher as a popup rendered with Qt Quick.

    Args:
        controller(ProfileSwitcherController): Shared switcher state.
        parent(QWidget | None): Parent widget.
    """

    def __init__(self, controller, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("profileSwitcherQml")
        self.controller = controller
        self.resize(420, 460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(
            self, QML_DIR / "ProfileSwitcher.qml", {"backend": controller}
        )
        self.view.setClearColor(ThemeTokens().card)
        layout.addWidget(self.view)
        root = self.view.rootObject()
        if root is not None:
            root.closeRequested.connect(self.close)
        controller.profile_chosen.connect(lambda *_: self.close())

    def open_at(self, anchor: QWidget | None) -> None:
        """Show the switcher below ``anchor``, right-aligned with it."""
        self.controller.reset()
        if anchor is not None:
            pos = anchor.mapToGlobal(QPoint(anchor.width() - self.width(), anchor.height() + 4))
        else:
            parent = self.parentWidget()
            center = parent.mapToGlobal(parent.rect().center()) if parent else QPoint(200, 200)
            pos = center - QPoint(self.width() // 2, self.height() // 2)
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen is not None:
            pos.setX(max(screen.left(), min(pos.x(), screen.right() - self.width())))
            pos.setY(max(screen.top(), min(pos.y(), screen.bottom() - self.height())))
        self.move(pos)
        self.show()
        self.view.setFocus(Qt.FocusReason.PopupFocusReason)
        root = self.view.rootObject()
        if root is not None:
            root.focusSearch()

    def refresh_theme(self) -> None:
        """The QML scene follows ``theme`` by itself; only the clear colour is updated."""
        self.view.setClearColor(ThemeTokens().card)

    def cleanup(self) -> None:
        """Unload the scene before the controller goes away."""
        release_quick_widget(self.view)
