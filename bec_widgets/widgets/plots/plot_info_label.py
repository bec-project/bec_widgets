from __future__ import annotations

from collections.abc import Iterable, Mapping

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

    Plot widgets submit arbitrary rows; this class owns the pyqtgraph legend
    mechanics and keeps the display independent from any specific metadata
    source such as scans.
    """

    def __init__(self, offset: tuple[int, int] = (-30, 1), theme: str = "light"):
        super().__init__(offset=offset, horSpacing=0)
        self._rows: list[tuple[str, object | None]] = []
        self._offset = offset
        self._has_drawn_rows = False
        self.set_theme(theme)
        self.setVisible(False)

    @property
    def rows(self) -> list[tuple[str, object | None]]:
        """Return a copy of the currently submitted rows."""
        return list(self._rows)

    def set_rows(
        self, rows: Mapping[str, object | None] | Iterable[tuple[str, object | None]]
    ) -> None:
        """Replace all displayed rows."""
        if isinstance(rows, Mapping):
            rows = rows.items()
        self._rows = [(str(label), value) for label, value in rows]
        self.redraw()

    def add_row(self, label: str, value: object | None = None) -> None:
        """Append one displayed row."""
        self._rows.append((str(label), value))
        self.redraw()

    def clear_rows(self) -> None:
        """Remove all displayed rows and hide the label."""
        self._rows = []
        self._has_drawn_rows = False
        self.clear()
        self.setVisible(False)

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
        """Refresh the pyqtgraph legend rows."""
        previous_pos = self.pos()
        preserve_pos = self._has_drawn_rows and self.isVisible()
        row_texts = [self._format_row(label, value) for label, value in self._rows]
        if len(row_texts) == len(self.items):
            for row_text, (_, label_item) in zip(row_texts, self.items, strict=True):
                label_item.setText(row_text)
            self.updateSize()
        else:
            self.clear()
            for row_text in row_texts:
                self.addItem(TextOnlyLegendSample(), row_text)
            if preserve_pos:
                self.setPos(previous_pos)
        self._has_drawn_rows = bool(self._rows)

    @staticmethod
    def _format_row(label: str, value: object | None) -> str:
        if value is None:
            return label
        return f"{label}: {value}"
