from __future__ import annotations

from qtpy.QtCore import QPoint, QRect, QSize, Qt
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLayout,
    QLayoutItem,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyle,
    QWidget,
)


class FlowLayout(QLayout):
    """
    A horizontal wrapping layout for Qt widgets.

    Adapted from the Qt "Flow Layout" example
    (https://doc.qt.io/qt-6/qtwidgets-layouts-flowlayout-example.html), extended with an
    optional minimum item width and uniform (normalized) item sizing.

    The layout places items left-to-right until the next item no longer fits, then starts a
    new row. Item dimensions are based on each item's minimum size and size hint, optionally
    expanded by ``minimum_item_width``.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        margin: int = 0,
        horizontal_spacing: int = -1,
        vertical_spacing: int = -1,
        minimum_item_width: int | None = None,
        normalize_item_sizes: bool = False,
    ):
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self._horizontal_spacing = horizontal_spacing
        self._vertical_spacing = vertical_spacing
        self._minimum_item_width = minimum_item_width
        self._normalize_item_sizes = normalize_item_sizes
        self._cached_normalized_size: QSize | None = None
        self._normalized_cache_valid = False
        self.setContentsMargins(margin, margin, margin, margin)

    def __del__(self):
        # Drain the layout items, mirroring the destructor of Qt's C++ FlowLayout example
        # and its official PySide6 port. This is needed because:
        #
        # - QLayout.addWidget() creates a C++ QWidgetItem (~80 bytes) per widget and hands
        #   it to our addItem(); by Qt's ownership contract the layout owns it.
        # - Built-in layouts free their items in their own C++ destructors, but a custom
        #   layout stores items where the C++ base class cannot see them (self._items),
        #   and ~QLayout cannot call our overridden takeAt()/count() during destruction
        #   (virtual dispatch is already unwound). Without this drain the C++ structs leak.
        # - takeAt() transfers item ownership to the Python wrapper, which frees the C++
        #   side on garbage collection.
        #
        # Measured: churning 300 layouts x 100 items leaks ~2.4 MB without the drain and
        # ~0 with it. Omitting it changes no behavior (items do not own the widgets, and
        # widget cleanup runs via closeEvent independently) - it only causes a slow,
        # hard-to-attribute memory creep in long-running sessions with layout churn.
        try:
            item = self.takeAt(0)
            while item:
                item = self.takeAt(0)
        except RuntimeError:
            # The underlying C++ layout is already destroyed; nothing left to drain.
            pass

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)
        self.invalidate()

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            item = self._items.pop(index)
            self.invalidate()
            return item
        return None

    def invalidate(self) -> None:
        self._normalized_cache_valid = False
        self._cached_normalized_size = None
        super().invalidate()

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations()

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        # Mirror Qt's FlowLayout: a wrapping layout advertises its minimum size as the
        # preferred size so the widget is content to be narrow and wrap, instead of
        # demanding a single-row width that would defeat the wrapping.
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        normalized_size = self._normalized_item_size()
        for item in self._items:
            if item.isEmpty():
                continue
            size = size.expandedTo(self._item_size(item, normalized_size))

        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective_rect = rect.adjusted(left, top, -right, -bottom)
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        normalized_size = self._normalized_item_size()
        space_x = self._smart_spacing(QStyle.PixelMetric.PM_LayoutHorizontalSpacing)
        space_y = self._smart_spacing(QStyle.PixelMetric.PM_LayoutVerticalSpacing)

        for item in self._items:
            if item.isEmpty():
                continue

            item_size = self._item_size(item, normalized_size)
            next_x = x + item_size.width() + space_x

            # Wrap when the item would overflow the row. Unlike the Qt example
            # (`next_x - space_x > right()`), the `+ 1` keeps an exactly-fitting item on
            # the current row; the `line_height > 0` guard matches Qt and never wraps
            # before anything was placed on the row.
            if line_height > 0 and next_x - space_x > effective_rect.right() + 1:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item_size.width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y() + bottom

    def _item_size(self, item: QLayoutItem, normalized_size: QSize | None = None) -> QSize:
        if normalized_size is not None:
            return QSize(normalized_size)

        size = item.sizeHint().expandedTo(item.minimumSize())
        if self._minimum_item_width is not None:
            size.setWidth(max(size.width(), self._minimum_item_width))
        return size

    def _normalized_item_size(self) -> QSize | None:
        if not self._normalize_item_sizes:
            return None
        if self._normalized_cache_valid:
            return self._cached_normalized_size

        normalized_size = QSize()
        for item in self._items:
            if item.isEmpty():
                continue
            normalized_size = normalized_size.expandedTo(self._item_size(item))
        self._cached_normalized_size = normalized_size if normalized_size.isValid() else None
        self._normalized_cache_valid = True
        return self._cached_normalized_size

    def _smart_spacing(self, pixel_metric: QStyle.PixelMetric) -> int:
        spacing = (
            self._horizontal_spacing
            if pixel_metric == QStyle.PixelMetric.PM_LayoutHorizontalSpacing
            else self._vertical_spacing
        )
        if spacing >= 0:
            return spacing

        parent = self.parent()
        if parent is not None and not parent.isWidgetType():
            # Parent is another layout; use its spacing, but never feed a -1 sentinel
            # into positioning (that would overlap items by 1px per gap).
            return max(0, parent.spacing())

        widget = parent if parent is not None else None
        style = widget.style() if widget is not None else QApplication.style()
        spacing = style.pixelMetric(pixel_metric, None, widget)
        if spacing < 0:
            # Some styles (e.g. native macOS) return -1 from pixelMetric by design and
            # expose the real value via layoutSpacing(), like the Qt example does.
            orientation = (
                Qt.Orientation.Horizontal
                if pixel_metric == QStyle.PixelMetric.PM_LayoutHorizontalSpacing
                else Qt.Orientation.Vertical
            )
            spacing = style.layoutSpacing(
                QSizePolicy.ControlType.PushButton,
                QSizePolicy.ControlType.PushButton,
                orientation,
                None,
                widget,
            )
        return max(0, spacing)


class FlowLayoutWidget(QWidget):
    """
    Thin convenience container with a :class:`FlowLayout` installed.

    QWidget natively defers ``hasHeightForWidth``/``heightForWidth``/``minimumSizeHint``
    to the installed layout, so no forwarding overrides are needed. Only ``sizeHint`` is
    overridden: it deliberately advertises the layout's minimum size so parent layouts let
    the widget stay narrow and wrap, instead of the tall height-for-width-corrected
    default hint.
    """

    def __init__(self, parent: QWidget | None = None, **layout_kwargs):
        super().__init__(parent)
        self.flow_layout = FlowLayout(self, **layout_kwargs)

    def sizeHint(self) -> QSize:
        return self.flow_layout.sizeHint()


if __name__ == "__main__":  # pragma: no cover
    app = QApplication([])

    window = FlowLayoutWidget(
        margin=12,
        horizontal_spacing=8,
        vertical_spacing=8,
        minimum_item_width=140,
        normalize_item_sizes=True,
    )
    window.setWindowTitle("FlowLayout demo")

    widgets = [
        QPushButton("Run"),
        QPushButton("Pause"),
        QDoubleSpinBox(),
        QComboBox(),
        QCheckBox("Relative"),
        QSlider(Qt.Orientation.Horizontal),
        QPushButton("Restore last parameters"),
        QPushButton("Abort"),
    ]
    widgets[3].addItems(["line_scan", "grid_scan", "round_scan"])
    widgets[5].setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    for widget in widgets:
        window.flow_layout.addWidget(widget)

    window.resize(520, 180)
    window.show()
    app.exec()
