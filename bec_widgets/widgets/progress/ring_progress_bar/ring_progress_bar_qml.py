"""Ring progress bar rendered with Qt Quick (QML).

:class:`RingProgressBarQML` has the same public API as :class:`RingProgressBar`; only the ring
container is replaced by a QQuickWidget that draws the rings with ``QtQuick.Shapes`` and adds a
legend, animated values and an empty state.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, Signal, Slot

from bec_widgets.utils.quick import DictListModel, create_quick_widget, release_quick_widget
from bec_widgets.utils.ux_kit import PortedPropertiesMixin
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import RingProgressBar
from bec_widgets.widgets.progress.ring_progress_bar.ring_ux_common import RingStateContainer

QML_FILE = Path(__file__).parent / "qml" / "RingProgressView.qml"

RING_ROLES = [
    "index",
    "label",
    "mode",
    "color",
    "trackColor",
    "fraction",
    "lineWidth",
    "gap",
    "startAngle",
    "direction",
    "valueText",
    "percentText",
    "done",
    "highlighted",
]


class RingViewBackend(QObject):
    """Bridge between :class:`QuickRingContainer` and ``RingProgressView.qml``."""

    changed = Signal()

    def __init__(self, container: "QuickRingContainer"):
        super().__init__(container)
        self._container = container
        self._model = DictListModel(RING_ROLES, self)
        self._center_text = ""
        self._center_caption = ""
        self._max_line_width = 10
        self._inner_offset = 0
        self._highlighted = -1
        self._show_legend = True

    def update_from(self, container: RingStateContainer) -> None:
        """Copy the container state into the model and properties."""
        self._model.set_items(container.snapshots())
        self._center_text, self._center_caption = container.center_texts()
        self._max_line_width = container.get_max_ring_size()
        self._inner_offset = max(
            (ring["gap"] + ring["lineWidth"] for ring in self._model.items), default=0
        )
        self._highlighted = container.highlighted
        self.changed.emit()

    @Slot(int)
    def setHighlighted(self, index: int) -> None:  # pylint: disable=invalid-name
        """Highlight a ring from QML hover."""
        self._container.set_highlighted(index)

    @Slot()
    def openSettings(self) -> None:  # pylint: disable=invalid-name
        """Open the ring settings dialog."""
        self._container.request_settings()

    def _set_show_legend(self, show: bool) -> None:
        self._show_legend = bool(show)
        self.changed.emit()

    rings = Property(QObject, lambda self: self._model, constant=True)
    centerText = Property(str, lambda self: self._center_text, notify=changed)
    centerCaption = Property(str, lambda self: self._center_caption, notify=changed)
    maxLineWidth = Property(int, lambda self: self._max_line_width, notify=changed)
    innerOffset = Property(int, lambda self: self._inner_offset, notify=changed)
    highlighted = Property(int, lambda self: self._highlighted, notify=changed)
    showLegend = Property(bool, lambda self: self._show_legend, notify=changed)


class QuickRingContainer(RingStateContainer):
    """Ring container that renders through a QML view."""

    def _init_view(self) -> None:
        self.backend = RingViewBackend(self)
        self.view = create_quick_widget(self, QML_FILE, {"backend": self.backend})
        self.layout().addWidget(self.view)

    def _sync_view(self) -> None:
        self.backend.update_from(self)

    def apply_theme(self, _theme: str | None = None) -> None:
        """Match the view clear colour to the window background."""
        self.view.setClearColor(self.palette().window().color())

    def closeEvent(self, event):  # pylint: disable=invalid-name
        release_quick_widget(self.view)
        super().closeEvent(event)


class RingProgressBarQML(PortedPropertiesMixin, RingProgressBar):
    """Ring progress bar rendered with QML; same API as :class:`RingProgressBar`."""

    PLUGIN = False
    RPC = False
    rpc_widget_class = "RingProgressBar"
    PORTED_FROM = RingProgressBar

    def _create_ring_container(self) -> QuickRingContainer:
        return QuickRingContainer(self)

    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        self.ring_progress_bar.apply_theme(theme)

    @property
    def show_legend(self) -> bool:
        """Whether the legend next to the rings is shown."""
        return self.ring_progress_bar.backend.showLegend

    @show_legend.setter
    def show_legend(self, show: bool):
        self.ring_progress_bar.backend._set_show_legend(show)  # pylint: disable=protected-access


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = RingProgressBarQML()
    for value in (72, 35, 90):
        widget.add_ring().set_value(value)
    widget.show()
    sys.exit(app.exec())
