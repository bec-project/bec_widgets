"""Device and signal pickers whose popup is rendered with Qt Quick (QML).

Same behaviour as the QWidget pickers in :mod:`picker_qwidget`; both popups are views over
:class:`~bec_widgets.widgets.control.device_input.picker.picker_common.PickerController`.
The field itself stays a :class:`QComboBox` so the pickers remain drop-in replacements for
:class:`DeviceComboBox` and :class:`SignalComboBox`; only the popup is QML.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, Qt, Signal, Slot
from qtpy.QtWidgets import QVBoxLayout

from bec_widgets.utils.quick import create_quick_widget, release_quick_widget
from bec_widgets.widgets.control.device_input.picker.picker_common import (
    DevicePickerBase,
    PickerPopupBase,
    SignalPickerBase,
)
from bec_widgets.widgets.control.device_input.picker.picker_model import PickerController

QML_FILE = Path(__file__).parent / "qml" / "PickerPopupView.qml"


class PickerBackend(QObject):
    """Bridge between :class:`PickerController` and ``PickerPopupView.qml``."""

    rowsChanged = Signal()  # pylint: disable=invalid-name
    highlightChanged = Signal()  # pylint: disable=invalid-name
    detailChanged = Signal()  # pylint: disable=invalid-name
    queryChanged = Signal()  # pylint: disable=invalid-name
    focusRequested = Signal()  # pylint: disable=invalid-name

    def __init__(self, controller: PickerController, parent: QObject | None = None):
        super().__init__(parent)
        self._controller = controller
        controller.rows_changed.connect(self.rowsChanged)
        controller.highlight_changed.connect(self.highlightChanged)
        controller.detail_changed.connect(self.detailChanged)
        controller.query_changed.connect(self.queryChanged)

    # pylint: disable=invalid-name
    @Slot(str)
    def setQuery(self, text: str) -> None:
        """Filter the rows."""
        self._controller.set_query(text)

    @Slot(int)
    def move(self, step: int) -> None:
        """Move the highlight."""
        self._controller.move_highlight(step)

    @Slot(int)
    def page(self, step: int) -> None:
        """Move the highlight by a page."""
        self._controller.page_highlight(step)

    @Slot(int)
    def hover(self, row: int) -> None:
        """Highlight the row under the mouse."""
        self._controller.set_highlight(row)

    @Slot(int)
    def accept(self, row: int) -> None:
        """Pick a row (-1 for the highlighted one)."""
        self._controller.accept(row)

    @Slot()
    def dismiss(self) -> None:
        """Close without picking."""
        self._controller.dismiss()

    @property
    def controller(self) -> PickerController:
        """Controller this backend forwards."""
        return self._controller

    rows = Property(QObject, lambda self: self.controller.model, constant=True)
    highlight = Property(int, lambda self: self.controller.highlight, notify=highlightChanged)
    query = Property(str, lambda self: self.controller.query, notify=queryChanged)
    placeholder = Property(str, lambda self: self.controller.placeholder, notify=queryChanged)
    summary = Property(str, lambda self: self.controller.summary, notify=rowsChanged)
    detail = Property("QVariantMap", lambda self: self.controller.detail, notify=detailChanged)


class PickerPopupQml(PickerPopupBase):
    """Popup window that hosts ``PickerPopupView.qml``."""

    def __init__(self, picker):
        super().__init__(picker)
        self.backend = PickerBackend(self.controller, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(self, QML_FILE, {"backend": self.backend})
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.view)
        self.refresh_theme()

    def focus_search(self) -> None:
        self.view.setFocus()
        self.backend.focusRequested.emit()

    def refresh_theme(self) -> None:
        self.view.setClearColor(self.palette().window().color())

    def release(self) -> None:
        release_quick_widget(self.view)


class DevicePickerQML(DevicePickerBase):
    """Device combobox with a searchable, grouped popup rendered in QML.

    Drop-in replacement for :class:`DeviceComboBox`; see :class:`DevicePickerBase`.
    """

    ICON_NAME = "manage_search"

    def _create_popup(self):
        return PickerPopupQml(self)


class SignalPickerQML(SignalPickerBase):
    """Signal combobox with a searchable, grouped popup rendered in QML.

    Drop-in replacement for :class:`SignalComboBox`; see :class:`SignalPickerBase`.
    """

    ICON_NAME = "manage_search"

    def _create_popup(self):
        return PickerPopupQml(self)
