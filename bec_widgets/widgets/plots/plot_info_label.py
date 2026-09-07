from __future__ import annotations

from collections.abc import Iterable

import pyqtgraph as pg
from qtpy.QtCore import QRectF


class TextOnlyLegendSample(pg.graphicsItems.LegendItem.ItemSample):
    """Zero-size legend sample for text-only rows.

    The stock ItemSample expects a plottable item with an ``opts`` dict; since
    PySide 6.10 an exception raised inside its paint() override propagates out
    of the C++ paint loop and crashes the application.
    """

    def __init__(self):
        super().__init__(item=None)
        self.setFixedWidth(0)
        self.setFixedHeight(0)

    def boundingRect(self):
        return QRectF(0, 0, 0, 0)

    def paint(self, p, *args):
        pass

    def mouseClickEvent(self, event):
        event.ignore()


class PlotInfoLabel(pg.LegendItem):
    """Paint-safe text overlay for plot metadata.

    Plot widgets submit (label, value) rows; this class owns the pyqtgraph
    legend mechanics and keeps the display independent from any specific
    metadata source such as scans.
    """

    def __init__(self, offset: tuple[int, int] = (-30, 1), theme: str = "light"):
        super().__init__(offset=offset, horSpacing=0)
        self._rows: list[tuple[str, str | None]] = []
        self._offset = offset
        self.set_theme(theme)
        self.setVisible(False)

    @property
    def rows(self) -> list[tuple[str, str | None]]:
        """Return a copy of the currently displayed rows."""
        return list(self._rows)

    def set_rows(self, rows: Iterable[tuple[str, object | None]]) -> None:
        """
        Replace all displayed rows. Unchanged rows are not re-rendered.

        Args:
            rows(Iterable[tuple[str, object | None]]): An iterable of (label, value) pairs to display. The label is a string and the value can be any object or None.
        """
        rows = [(str(label), None if value is None else str(value)) for label, value in rows]
        if rows == self._rows:
            return
        self._rows = rows
        self.redraw()

    def reset_position(self) -> None:
        """Reset the label to its default anchored position."""
        self.setOffset(self._offset)

    def set_theme(self, theme: str) -> None:
        """Update the label colors for the active application theme."""
        if theme == "dark":
            brush = pg.mkBrush(pg.mkColor(50, 50, 50, 150))
            color = pg.mkColor(255, 255, 255)
        else:
            brush = pg.mkBrush(pg.mkColor(240, 240, 240, 150))
            color = pg.mkColor(0, 0, 0)
        self.setBrush(brush)
        self.setLabelTextColor(color)
        self.redraw()

    def redraw(self) -> None:
        """Rebuild the pyqtgraph legend rows from scratch."""
        self.clear()
        for label, value in self._rows:
            self.addItem(TextOnlyLegendSample(), self._format_row(label, value))

    @staticmethod
    def _format_row(label: str, value: str | None) -> str:
        if value is None:
            return label
        return f"{label}: {value}"
