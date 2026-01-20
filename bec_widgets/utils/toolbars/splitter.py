"""
Draggable splitter for toolbars to allow resizing of toolbar sections.
"""

from typing import Literal

from bec_qthemes import material_icon
from qtpy.QtCore import QPoint, QSize, Qt, Signal
from qtpy.QtGui import QPainter
from qtpy.QtWidgets import QSizePolicy, QWidget


class ResizableSpacer(QWidget):
    """
    A resizable spacer widget for toolbars that can be dragged to expand/contract.

    When connected to a widget, it controls that widget's size along the spacer's
    orientation (maximum width for horizontal, maximum height for vertical),
    ensuring the widget stays flush against the spacer with no gaps.

    Args:
        parent(QWidget | None): Parent widget.
        orientation(Literal["horizontal", "vertical"]): Orientation of the spacer.
        initial_width(int): Initial size of the spacer in pixels along the orientation
            (width for horizontal, height for vertical).
        min_target_size(int): Minimum size of the target widget when resized along the
            orientation (width for horizontal, height for vertical).
        max_target_size(int): Maximum size of the target widget when resized along the
            orientation (width for horizontal, height for vertical).
        target_widget: QWidget | None. The widget whose size along the orientation
            is controlled by this spacer.
    """

    size_changed = Signal(int)

    def __init__(
        self,
        parent=None,
        orientation: Literal["horizontal", "vertical"] = "horizontal",
        initial_width: int = 10,
        min_target_size: int = 6,
        max_target_size: int = 500,
        target_widget: QWidget = None,
    ):
        from bec_widgets.utils.toolbars.bundles import DEFAULT_SIZE, MAX_SIZE

        super().__init__(parent)
        self._target_start_size = None
        self.orientation = orientation
        self._current_width = initial_width
        self._min_width = min_target_size
        self._max_width = max_target_size
        self._dragging = False
        self._drag_start_pos = QPoint()
        self._target_widget = target_widget

        # Determine bounds from kwargs or target hints
        is_horizontal = orientation == "horizontal"
        target_min = target_widget.minimumWidth() if (target_widget and is_horizontal) else 0
        if target_widget and not is_horizontal:
            target_min = target_widget.minimumHeight()
        target_hint = target_widget.sizeHint().width() if (target_widget and is_horizontal) else 0
        if target_widget and not is_horizontal:
            target_hint = target_widget.sizeHint().height()
        target_max_hint = (
            target_widget.maximumWidth() if (target_widget and is_horizontal) else None
        )
        if target_widget and not is_horizontal:
            target_max_hint = target_widget.maximumHeight()
        self._min_target = min_target_size if min_target_size is not None else (target_min or 6)
        self._max_target = (
            max_target_size
            if max_target_size is not None
            else (
                target_max_hint if target_max_hint and target_max_hint < MAX_SIZE else DEFAULT_SIZE
            )
        )

        # Determine a reasonable base width and clamp to bounds
        if target_widget:
            current_size = target_widget.width() if is_horizontal else target_widget.height()
            if current_size > 0:
                self._base_width = current_size
            elif target_min > 0:
                self._base_width = target_min
            elif target_hint > 0:
                self._base_width = target_hint
            else:
                self._base_width = 240
        else:
            self._base_width = 240
        self._base_width = max(self._min_target, min(self._max_target, self._base_width))

        # Set size constraints - Fixed policy to prevent automatic resizing
        # Match toolbar height for proper alignment
        self._toolbar_height = 32  # Standard toolbar height

        if orientation == "horizontal":
            self.setFixedWidth(initial_width)
            self.setFixedHeight(self._toolbar_height)
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.setFixedHeight(initial_width)
            self.setFixedWidth(self._toolbar_height)
            self.setCursor(Qt.CursorShape.SplitVCursor)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.setStyleSheet(
            """
            ResizableSpacer {
                background-color: transparent;
                margin: 0px;
                padding: 0px;
                border: none;
            }
            ResizableSpacer:hover {
                background-color: rgba(100, 100, 200, 80);
            }
        """
        )

        self.setContentsMargins(0, 0, 0, 0)

        if self._target_widget:
            size_policy = self._target_widget.sizePolicy()
            if is_horizontal:
                vertical_policy = size_policy.verticalPolicy()
                self._target_widget.setSizePolicy(QSizePolicy.Policy.Fixed, vertical_policy)
            else:
                horizontal_policy = size_policy.horizontalPolicy()
                self._target_widget.setSizePolicy(horizontal_policy, QSizePolicy.Policy.Fixed)

        # Load Material icon based on orientation
        icon_name = "more_vert" if orientation == "horizontal" else "more_horiz"
        icon_size = 24
        self._icon = material_icon(icon_name, size=(icon_size, icon_size), convert_to_pixmap=False)
        self._icon_size = icon_size

    def set_target_widget(self, widget):
        """Set the widget whose size is controlled by this spacer."""
        self._target_widget = widget
        if widget:
            is_horizontal = self.orientation == "horizontal"
            target_min = widget.minimumWidth() if is_horizontal else widget.minimumHeight()
            target_hint = widget.sizeHint().width() if is_horizontal else widget.sizeHint().height()
            target_max_hint = widget.maximumWidth() if is_horizontal else widget.maximumHeight()
            self._min_target = self._min_target or (target_min or 6)
            self._max_target = (
                self._max_target
                if self._max_target is not None
                else (target_max_hint if target_max_hint and target_max_hint < 10_000_000 else 400)
            )
            current_size = widget.width() if is_horizontal else widget.height()
            if current_size is not None and current_size > 0:
                base = current_size
            elif target_min is not None and target_min > 0:
                base = target_min
            elif target_hint is not None and target_hint > 0:
                base = target_hint
            else:
                base = self._base_width
            base = max(self._min_target, min(self._max_target, base))
            if is_horizontal:
                widget.setFixedWidth(base)
            else:
                widget.setFixedHeight(base)

    def get_target_widget(self):
        """Get the widget whose size is controlled by this spacer."""
        return self._target_widget

    def sizeHint(self):
        if self.orientation == "horizontal":
            return QSize(self._current_width, self._toolbar_height)
        else:
            return QSize(self._toolbar_height, self._current_width)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the Material icon centered in the widget using stored icon size
        x = (self.width() - self._icon_size) // 2
        y = (self.height() - self._icon_size) // 2

        self._icon.paint(painter, x, y, self._icon_size, self._icon_size)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_pos = event.globalPos()
            # Store target's current width if it exists
            if self._target_widget:
                if self.orientation == "horizontal":
                    self._target_start_size = self._target_widget.width()
                else:
                    self._target_start_size = self._target_widget.height()

                size_policy = self._target_widget.sizePolicy()
                if self.orientation == "horizontal":
                    vertical_policy = size_policy.verticalPolicy()
                    self._target_widget.setSizePolicy(QSizePolicy.Policy.Fixed, vertical_policy)
                    self._target_widget.setFixedWidth(self._target_start_size)
                else:
                    horizontal_policy = size_policy.horizontalPolicy()
                    self._target_widget.setSizePolicy(horizontal_policy, QSizePolicy.Policy.Fixed)
                    self._target_widget.setFixedHeight(self._target_start_size)

            event.accept()

    def mouseMoveEvent(self, event):
        if self._dragging:
            current_pos = event.globalPos()
            delta = current_pos - self._drag_start_pos

            if self.orientation == "horizontal":
                delta_pixels = delta.x()
            else:
                delta_pixels = delta.y()

            if self._target_widget:
                new_target_size = self._target_start_size + delta_pixels
                new_target_size = max(self._min_target, min(self._max_target, new_target_size))

                if self.orientation == "horizontal":
                    if new_target_size != self._target_widget.width():
                        self._target_widget.setFixedWidth(new_target_size)
                        self.size_changed.emit(new_target_size)
                else:
                    if new_target_size != self._target_widget.height():
                        self._target_widget.setFixedHeight(new_target_size)
                        self.size_changed.emit(new_target_size)

            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            event.accept()
