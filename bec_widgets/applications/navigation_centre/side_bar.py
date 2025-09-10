from __future__ import annotations

from bec_qthemes import material_icon
from qtpy import QtWidgets
from qtpy.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt, Signal
from qtpy.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import SafeProperty, SafeSlot
from bec_widgets.applications.navigation_centre.reveal_animator import ANIMATION_DURATION
from bec_widgets.applications.navigation_centre.side_bar_components import (
    DarkModeNavItem,
    NavigationItem,
    SectionHeader,
    SideBarSeparator,
)


class SideBar(QScrollArea):
    view_selected = Signal(str)
    toggled = Signal(bool)

    def __init__(
        self,
        parent=None,
        title: str = "Control Panel",
        collapsed_width: int = 56,
        expanded_width: int = 250,
        anim_duration: int = ANIMATION_DURATION,
    ):
        super().__init__(parent=parent)
        self.setObjectName("SideBar")

        # private attributes
        self._is_expanded = False
        self._collapsed_width = collapsed_width
        self._expanded_width = expanded_width
        self._anim_duration = anim_duration

        # containers
        self.components = {}
        self._item_opts: dict[str, dict] = {}

        # Scroll area properties
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setFixedWidth(self._collapsed_width)

        # Content widget holding buttons for switching views
        self.content = QWidget(self)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(4)
        self.setWidget(self.content)

        # Track active navigation item
        self._active_id = None

        # Top row with title and toggle button
        self.toggle_row = QWidget(self)
        self.toggle_row_layout = QHBoxLayout(self.toggle_row)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("TopTitle")
        self.title_label.setStyleSheet("font-weight: 600;")
        self.title_fx = QGraphicsOpacityEffect(self.title_label)
        self.title_label.setGraphicsEffect(self.title_fx)
        self.title_fx.setOpacity(0.0)
        self.title_label.setVisible(False)  # TODO dirty trick to avoid layout shift

        self.toggle = QToolButton(self)
        self.toggle.setCheckable(False)
        self.toggle.setIcon(material_icon("keyboard_arrow_right", convert_to_pixmap=False))
        self.toggle.clicked.connect(self.on_expand)

        self.toggle_row_layout.addWidget(self.title_label, 1, Qt.AlignLeft | Qt.AlignVCenter)
        self.toggle_row_layout.addWidget(self.toggle, 1, Qt.AlignHCenter | Qt.AlignVCenter)

        # To push the content up always
        self._bottom_spacer = QtWidgets.QSpacerItem(
            0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )

        # Add core widgets to layout
        self.content_layout.addWidget(self.toggle_row)
        self.content_layout.addItem(self._bottom_spacer)

        # Animations
        self.width_anim = QPropertyAnimation(self, b"bar_width")
        self.width_anim.setDuration(self._anim_duration)
        self.width_anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.title_anim = QPropertyAnimation(self.title_fx, b"opacity")
        self.title_anim.setDuration(self._anim_duration)
        self.title_anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.group = QParallelAnimationGroup(self)
        self.group.addAnimation(self.width_anim)
        self.group.addAnimation(self.title_anim)
        self.group.finished.connect(self._on_anim_finished)

        app = QtWidgets.QApplication.instance()
        if app is not None and hasattr(app, "theme") and hasattr(app.theme, "theme_changed"):
            app.theme.theme_changed.connect(self._on_theme_changed)

    @SafeProperty(int)
    def bar_width(self) -> int:
        """
        Get the current width of the side bar.

        Returns:
            int: The current width of the side bar.
        """
        return self.width()

    @bar_width.setter
    def bar_width(self, width: int):
        """
        Set the width of the side bar.

        Args:
            width(int): The new width of the side bar.
        """
        self.setFixedWidth(width)

    @SafeProperty(bool)
    def is_expanded(self) -> bool:
        """
        Check if the side bar is expanded.

        Returns:
            bool: True if the side bar is expanded, False otherwise.
        """
        return self._is_expanded

    @SafeSlot()
    @SafeSlot(bool)
    def on_expand(self):
        """
        Toggle the expansion state of the side bar.
        """
        self._is_expanded = not self._is_expanded
        self.toggle.setIcon(
            material_icon(
                "keyboard_arrow_left" if self._is_expanded else "keyboard_arrow_right",
                convert_to_pixmap=False,
            )
        )

        if self._is_expanded:
            self.toggle_row_layout.setAlignment(self.toggle, Qt.AlignRight | Qt.AlignVCenter)

        self.group.stop()
        # Setting limits for animations of the side bar
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(
            self._expanded_width if self._is_expanded else self._collapsed_width
        )
        self.title_anim.setStartValue(self.title_fx.opacity())
        self.title_anim.setEndValue(1.0 if self._is_expanded else 0.0)

        # Setting limits for animations of the components
        for comp in self.components.values():
            if hasattr(comp, "setup_animations"):
                comp.setup_animations(self._is_expanded)

        self.group.start()
        if self._is_expanded:
            # TODO do not like this trick, but it is what it is for now
            self.title_label.setVisible(self._is_expanded)
            for comp in self.components.values():
                if hasattr(comp, "set_visible"):
                    comp.set_visible(self._is_expanded)
        self.toggled.emit(self._is_expanded)

    @SafeSlot()
    def _on_anim_finished(self):
        if not self._is_expanded:
            self.toggle_row_layout.setAlignment(self.toggle, Qt.AlignHCenter | Qt.AlignVCenter)
            # TODO do not like this trick, but it is what it is for now
            self.title_label.setVisible(self._is_expanded)
            for comp in self.components.values():
                if hasattr(comp, "set_visible"):
                    comp.set_visible(self._is_expanded)

    @SafeSlot(str)
    def _on_theme_changed(self, theme_name: str):
        # Refresh toggle arrow icon so it picks up the new theme
        self.toggle.setIcon(
            material_icon(
                "keyboard_arrow_left" if self._is_expanded else "keyboard_arrow_right",
                convert_to_pixmap=False,
            )
        )
        # Refresh each component that supports it
        for comp in self.components.values():
            if hasattr(comp, "refresh_theme"):
                comp.refresh_theme()
            else:
                comp.style().unpolish(comp)
                comp.style().polish(comp)
                comp.update()
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def add_section(self, title: str, id: str, position: int | None = None) -> SectionHeader:
        """
        Add a section header to the side bar.

        Args:
            title(str): The title of the section.
            id(str): Unique ID for the section.
            position(int, optional): Position to insert the section header.

        Returns:
            SectionHeader: The created section header.

        """
        header = SectionHeader(self, title, anim_duration=self._anim_duration)
        position = position if position is not None else self.content_layout.count() - 1
        self.content_layout.insertWidget(position, header)
        for anim in header.animations:
            self.group.addAnimation(anim)
        self.components[id] = header
        return header

    def add_separator(
        self, *, from_top: bool = True, position: int | None = None
    ) -> SideBarSeparator:
        """
        Add a separator line to the side bar. Separators are treated like regular
        items; you can place multiple separators anywhere using `from_top` and `position`.
        """
        line = SideBarSeparator(self)
        line.setStyleSheet("margin:12px;")
        self._insert_nav_item(line, from_top=from_top, position=position)
        return line

    def add_item(
        self,
        icon: str,
        title: str,
        id: str,
        mini_text: str | None = None,
        position: int | None = None,
        *,
        from_top: bool = True,
        toggleable: bool = True,
        exclusive: bool = True,
    ) -> NavigationItem:
        """
        Add a navigation item to the side bar.

        Args:
            icon(str): Icon name for the nav item.
            title(str): Title for the nav item.
            id(str): Unique ID for the nav item.
            mini_text(str, optional): Short text for the nav item when sidebar is collapsed.
            position(int, optional): Position to insert the nav item.
            from_top(bool, optional): Whether to count position from the top or bottom.
            toggleable(bool, optional): Whether the nav item is toggleable.
            exclusive(bool, optional): Whether the nav item is exclusive.

        Returns:
            NavigationItem: The created navigation item.
        """
        item = NavigationItem(
            parent=self,
            title=title,
            icon_name=icon,
            mini_text=mini_text,
            toggleable=toggleable,
            exclusive=exclusive,
            anim_duration=self._anim_duration,
        )
        self._insert_nav_item(item, from_top=from_top, position=position)
        for anim in item.build_animations():
            self.group.addAnimation(anim)
        self.components[id] = item
        # Connect activation to activation logic, passing id unchanged
        item.activated.connect(lambda id=id: self.activate_item(id))
        return item

    def activate_item(self, target_id: str, *, emit_signal: bool = True):
        target = self.components.get(target_id)
        if target is None:
            return
        # Non-toggleable acts like an action: do not change any toggled states
        if hasattr(target, "toggleable") and not target.toggleable:
            self._active_id = target_id
            if emit_signal:
                self.view_selected.emit(target_id)
            return

        is_exclusive = getattr(target, "exclusive", True)
        if is_exclusive:
            # Radio-like behavior among exclusive items only
            for comp_id, comp in self.components.items():
                if not isinstance(comp, NavigationItem):
                    continue
                if comp is target:
                    comp.set_active(True)
                else:
                    # Only untoggle other items that are also exclusive
                    if getattr(comp, "exclusive", True):
                        comp.set_active(False)
                    # Leave non-exclusive items as they are
        else:
            # Non-exclusive toggles independently
            target.set_active(not target.is_active())

        self._active_id = target_id
        if emit_signal:
            self.view_selected.emit(target_id)

    def add_dark_mode_item(
        self, id: str = "dark_mode", position: int | None = None
    ) -> DarkModeNavItem:
        """
        Add a dark mode toggle item to the side bar.

        Args:
            id(str): Unique ID for the dark mode item.
            position(int, optional): Position to insert the dark mode item.

        Returns:
            DarkModeNavItem: The created dark mode navigation item.
        """
        item = DarkModeNavItem(parent=self, id=id, anim_duration=self._anim_duration)
        # compute bottom insertion point (same semantics as from_top=False)
        self._insert_nav_item(item, from_top=False, position=position)
        for anim in item.build_animations():
            self.group.addAnimation(anim)
        self.components[id] = item
        item.activated.connect(lambda id=id: self.activate_item(id))
        return item

    def _insert_nav_item(
        self, item: QWidget, *, from_top: bool = True, position: int | None = None
    ):
        if from_top:
            base_index = self.content_layout.indexOf(self._bottom_spacer)
            pos = base_index if position is None else min(base_index, position)
        else:
            base = self.content_layout.indexOf(self._bottom_spacer) + 1
            pos = base if position is None else base + max(0, position)
        self.content_layout.insertWidget(pos, item)
