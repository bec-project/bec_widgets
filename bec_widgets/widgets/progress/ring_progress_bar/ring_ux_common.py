"""State shared by the QML and QWidget ports of the ring progress bar.

Both ports keep :class:`Ring` objects as the source of truth, so every ring keeps its full API
(``set_value``, ``set_update``, ...), its settings dialog support and its BEC subscriptions. The
rings are not painted themselves; instead every change is forwarded to the container, which
turns the rings into plain snapshots that the QML view or the painted QWidget render.
"""

from __future__ import annotations

from qtpy.QtCore import Signal
from qtpy.QtWidgets import QLabel, QWidget

from bec_widgets.utils.ux_kit import PortedPropertiesMixin
from bec_widgets.widgets.progress.ring_progress_bar.ring import Ring
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_bar import (
    RingProgressContainerWidget,
)


class TrackedRing(PortedPropertiesMixin, Ring):
    """A :class:`Ring` that reports its changes to the container instead of painting itself."""

    PORTED_FROM = Ring
    # Same client-side API as Ring; the ports are not published separately over RPC.
    RPC = False
    rpc_widget_class = "Ring"

    def _request_update(self, *, refresh_tooltip: bool = True):
        container = self.progress_container
        if container is not None and hasattr(container, "ring_changed"):
            container.ring_changed(self)

    def paintEvent(self, event):  # pylint: disable=invalid-name
        """Rings are rendered by the container."""


class CenterText(QLabel):
    """Hidden label holding the center text; reports changes so the view can follow."""

    text_changed = Signal(str)

    def setText(self, text: str):  # pylint: disable=invalid-name
        """Set the text and notify the view."""
        changed = text != self.text()
        super().setText(text)
        if changed:
            self.text_changed.emit(text)


def format_number(value: float, precision: int) -> str:
    """Format with the ring precision, without trailing zeros (``12.500`` -> ``12.5``)."""
    text = f"{value:.{max(0, int(precision))}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def ring_label(ring: Ring, index: int) -> str:
    """Human readable name of what a ring shows."""
    config = ring.config
    if config.mode == "scan":
        return "Scan progress"
    if config.mode == "device" and config.device:
        return f"{config.device}:{config.signal}" if config.signal else config.device
    return f"Ring {index + 1}"


class RingStateContainer(RingProgressContainerWidget):
    """Container keeping the ring list and exposing it as snapshots for a renderer.

    Subclasses build their renderer in :meth:`_init_view` and refresh it in :meth:`_sync_view`.
    """

    def __init__(self, parent: QWidget | None = None, **kwargs):
        self._owner = parent
        self._highlighted = -1
        self._syncing_enabled = False
        super().__init__(parent=parent, **kwargs)
        self.setMouseTracking(False)
        self._syncing_enabled = True
        self._sync_view()

    # ---- RingProgressContainerWidget overrides ------------------------------------------

    def initialize_center_label(self):
        """Keep the center text in a hidden label and build the renderer instead."""
        layout = self.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.center_label = CenterText("", parent=self)
        self.center_label.hide()
        self.center_label.text_changed.connect(lambda _text: self._refresh())
        self._init_view()

    def add_ring(self, config: dict | None = None) -> Ring:
        """Add a ring; see :meth:`RingProgressContainerWidget.add_ring`."""
        ring = TrackedRing(parent=self)
        ring.hide()
        ring.gap = self.gap * len(self.rings)
        ring.set_value(0)
        self.rings.append(ring)
        if config:
            ring.link_colors = config.pop("link_colors", True)
            ring.load_settings(config)
        if self.color_map:
            self.set_colors_from_map(self.color_map)
        self.update()
        return ring

    def remove_ring(self, index: int | None = None):
        """Remove a ring; see :meth:`RingProgressContainerWidget.remove_ring`."""
        self._highlighted = -1
        super().remove_ring(index)

    def clear_all(self):
        """Remove all rings."""
        self._highlighted = -1
        super().clear_all()

    def update(self, *args):
        """Refresh the renderer, then schedule a repaint."""
        self._refresh()
        super().update(*args)

    # Hover tooltips are replaced by the legend, which shows the same details permanently.
    def mouseMoveEvent(self, event):  # pylint: disable=invalid-name
        QWidget.mouseMoveEvent(self, event)

    def leaveEvent(self, event):  # pylint: disable=invalid-name
        QWidget.leaveEvent(self, event)

    def refresh_hover_tooltip(self, ring: Ring, event=None):
        """Not used by the ports: the legend shows the ring details."""

    def is_ring_hovered(self, ring: Ring) -> bool:
        return 0 <= self._highlighted < len(self.rings) and self.rings[self._highlighted] is ring

    # ---- shared state --------------------------------------------------------------------

    def ring_changed(self, _ring: Ring) -> None:
        """Called by every :class:`TrackedRing` after a change."""
        self._refresh()

    def _refresh(self) -> None:
        if self._syncing_enabled:
            self._sync_view()

    @property
    def highlighted(self) -> int:
        """Index of the ring highlighted by hover, -1 for none."""
        return self._highlighted

    def set_highlighted(self, index: int) -> None:
        """Highlight one ring (and its legend row); -1 clears the highlight."""
        index = index if 0 <= index < len(self.rings) else -1
        if index == self._highlighted:
            return
        self._highlighted = index
        self._refresh()

    def ring_gap(self, index: int) -> int:
        """Distance of ring ``index`` from the outermost ring, in pixels."""
        return self.gap * index

    def snapshots(self) -> list[dict]:
        """Plain description of every ring, in drawing order (outermost first)."""
        snapshots = []
        for index, ring in enumerate(self.rings):
            config = ring.config
            span = config.max_value - config.min_value
            fraction = (config.value - config.min_value) / span if span else 0.0
            fraction = max(0.0, min(1.0, fraction))
            precision = int(config.precision)
            snapshots.append(
                {
                    "index": index,
                    "label": ring_label(ring, index),
                    "mode": config.mode,
                    "color": ring.color.name(),
                    "trackColor": ring.background_color.name(),
                    "fraction": fraction,
                    "lineWidth": int(config.line_width),
                    "gap": self.ring_gap(index),
                    "startAngle": int(config.start_position),
                    "direction": int(config.direction),
                    "valueText": (
                        f"{format_number(config.value, precision)}"
                        f" / {format_number(config.max_value, precision)}"
                    ),
                    "percentText": f"{fraction * 100:.0f}%",
                    "done": fraction >= 1.0,
                    "highlighted": index == self._highlighted,
                }
            )
        return snapshots

    def center_texts(self) -> tuple[str, str]:
        """Big and small center text.

        The center label set through the API wins; without one, the first ring's percentage is
        shown so the widget is informative without configuration.
        """
        text = self.center_label.text()
        if text:
            return text, ""
        if not self.rings:
            return "", ""
        first = self.snapshots()[0]
        return first["percentText"], first["label"]

    def request_settings(self) -> None:
        """Open the settings dialog of the owning RingProgressBar (used by the empty state)."""
        opener = getattr(self._owner, "_open_settings_dialog", None)
        if callable(opener):
            opener()

    # ---- renderer hooks ------------------------------------------------------------------

    def _init_view(self) -> None:
        """Create the renderer and add it to ``self.layout()``."""
        raise NotImplementedError

    def _sync_view(self) -> None:
        """Push the current snapshots to the renderer."""
        raise NotImplementedError
