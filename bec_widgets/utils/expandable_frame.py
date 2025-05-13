from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeProperty, SafeSlot


class ExpandableGroupFrame(QFrame):

    EXPANDED_ICON_NAME: str = "collapse_all"
    COLLAPSED_ICON_NAME: str = "expand_all"

    def __init__(
        self, title: str, parent: QWidget | None = None, expanded: bool = True, icon: str = ""
    ) -> None:
        super().__init__(parent=parent)
        self._expanded = expanded

        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Plain)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self._layout)

        self._title_layout = QHBoxLayout()
        self._layout.addLayout(self._title_layout)

        self._title = QLabel(f"<b>{title}</b>")
        self._title_icon = QLabel()
        self._title_layout.addWidget(self._title_icon)
        self._title_layout.addWidget(self._title)
        self.icon_name = icon

        self._title_layout.addStretch(1)

        self._expansion_button = QToolButton()
        self._update_expansion_icon()
        self._title_layout.addWidget(self._expansion_button, stretch=1)

        self._contents = QWidget(self)
        self._layout.addWidget(self._contents)

        self._expansion_button.clicked.connect(self.switch_expanded_state)
        self.expanded = self._expanded  # type: ignore

    def set_layout(self, layout: QLayout) -> None:
        self._contents.setLayout(layout)
        self._contents.layout().setContentsMargins(0, 0, 0, 0)  # type: ignore

    @SafeSlot()
    def switch_expanded_state(self):
        self.expanded = not self.expanded  # type: ignore
        self._update_expansion_icon()

    @SafeProperty(bool)
    def expanded(self):  # type: ignore
        return self._expanded

    @expanded.setter
    def expanded(self, expanded: bool):
        self._expanded = expanded
        self._contents.setVisible(expanded)
        self.updateGeometry()

    def _update_expansion_icon(self):
        self._expansion_button.setIcon(
            material_icon(icon_name=self.EXPANDED_ICON_NAME, size=(10, 10), convert_to_pixmap=False)
            if self.expanded
            else material_icon(
                icon_name=self.COLLAPSED_ICON_NAME, size=(10, 10), convert_to_pixmap=False
            )
        )

    @SafeProperty(str)
    def icon_name(self):  # type: ignore
        return self._title_icon_name

    @icon_name.setter
    def icon_name(self, icon_name: str):
        self._title_icon_name = icon_name
        self._set_title_icon(self._title_icon_name)

    def _set_title_icon(self, icon_name: str):
        if icon_name:
            self._title_icon.setVisible(True)
            self._title_icon.setPixmap(
                material_icon(icon_name=icon_name, size=(20, 20), convert_to_pixmap=True)
            )
        else:
            self._title_icon.setVisible(False)
