from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QMimeData, Qt, Signal
from qtpy.QtGui import QDrag
from qtpy.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.colors import get_theme_palette
from bec_widgets.utils.error_popups import SafeProperty


class CollapsibleSection(QWidget):
    """A widget that combines a header button with any content widget for collapsible sections

    This widget contains a header button with a title and a content widget.
    The content widget can be any QWidget. The header button can be expanded or collapsed.
    The header also contains an "Add" button that is only visible when hovering over the section.

    Signals:
        section_reorder_requested(str, str): Emitted when the section is dragged and dropped
                                             onto another section for reordering.
                                             Arguments are (source_title, target_title).
    """

    section_reorder_requested = Signal(str, str)  # (source_title, target_title)

    def __init__(self, parent=None, title="", indentation=10, show_add_button=False):
        super().__init__(parent=parent)
        self.title = title
        self.content_widget = None
        self.setAcceptDrops(True)
        self._expanded = True

        # Setup layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(indentation, 0, 0, 0)
        self.main_layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 4, 0)
        header_layout.setSpacing(0)

        # Create header button
        self.header_button = QPushButton()
        self.header_button.clicked.connect(self.toggle_expanded)

        # Enable drag and drop for reordering
        self.header_button.setAcceptDrops(True)
        self.header_button.mousePressEvent = self._header_mouse_press_event
        self.header_button.mouseMoveEvent = self._header_mouse_move_event
        self.header_button.dragEnterEvent = self._header_drag_enter_event
        self.header_button.dropEvent = self._header_drop_event

        self.drag_start_position = None

        # Add header to layout
        header_layout.addWidget(self.header_button)
        header_layout.addStretch()

        self.header_add_button = QPushButton()
        self.header_add_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.header_add_button.setFixedSize(20, 20)
        self.header_add_button.setToolTip("Add item")
        self.header_add_button.setVisible(show_add_button)

        self.header_add_button.setIcon(material_icon("add", size=(20, 20)))
        header_layout.addWidget(self.header_add_button)

        self.main_layout.addLayout(header_layout)

        self._update_expanded_state()

    def set_widget(self, widget):
        """Set the content widget for this collapsible section"""
        # Remove existing content widget if any
        if self.content_widget and self.content_widget.parent() == self:
            self.main_layout.removeWidget(self.content_widget)
            self.content_widget.close()
            self.content_widget.deleteLater()

        self.content_widget = widget
        if self.content_widget:
            self.main_layout.addWidget(self.content_widget)

        self._update_expanded_state()

    def _update_appearance(self):
        """Update the header button appearance based on expanded state"""
        # Use material icons with consistent sizing to match tree items
        icon_name = "keyboard_arrow_down" if self.expanded else "keyboard_arrow_right"
        icon = material_icon(icon_name=icon_name, size=(20, 20), convert_to_pixmap=False)

        self.header_button.setIcon(icon)
        self.header_button.setText(self.title)

        # Get theme colors
        palette = get_theme_palette()
        text_color = palette.text().color().name()

        self.header_button.setStyleSheet(
            f"""
            QPushButton {{
                font-weight: bold;
                text-align: left;
                margin: 0;
                padding: 0px;
                border: none;
                background: transparent;
                color: {text_color};
                icon-size: 20px 20px;
            }}
        """
        )

    def toggle_expanded(self):
        """Toggle the expanded state and update size policy"""
        self.expanded = not self.expanded
        self._update_expanded_state()

    def _update_expanded_state(self):
        """Update the expanded state based on current state"""
        self._update_appearance()
        if self.expanded:
            if self.content_widget:
                self.content_widget.show()
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        else:
            if self.content_widget:
                self.content_widget.hide()
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @SafeProperty(bool)
    def expanded(self) -> bool:
        """Get the expanded state"""
        return self._expanded

    @expanded.setter
    def expanded(self, value: bool):
        """Set the expanded state programmatically"""
        if not isinstance(value, bool):
            raise ValueError("Expanded state must be a boolean")
        if self._expanded == value:
            return
        self._expanded = value
        self._update_appearance()

    def connect_add_button(self, slot):
        """Connect a slot to the add button's clicked signal.

        Args:
            slot: The function to call when the add button is clicked.
        """
        self.header_add_button.clicked.connect(slot)

    def _header_mouse_press_event(self, event):
        """Handle mouse press on header for drag start"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
        QPushButton.mousePressEvent(self.header_button, event)

    def _header_mouse_move_event(self, event):
        """Handle mouse move to start drag operation"""
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_start_position is not None:

            # Check if we've moved far enough to start a drag
            if (event.pos() - self.drag_start_position).manhattanLength() >= 10:

                self._start_drag()
        QPushButton.mouseMoveEvent(self.header_button, event)

    def _start_drag(self):
        """Start the drag operation with a properly aligned widget pixmap"""
        drag = QDrag(self.header_button)
        mime_data = QMimeData()
        mime_data.setText(f"section:{self.title}")
        drag.setMimeData(mime_data)

        # Grab a pixmap of the widget
        widget_pixmap = self.header_button.grab()

        drag.setPixmap(widget_pixmap)

        # Set the hotspot to where the mouse was pressed on the widget
        drag.setHotSpot(self.drag_start_position)

        drag.exec_(Qt.MoveAction)

    def _header_drag_enter_event(self, event):
        """Handle drag enter on header"""
        if event.mimeData().hasText() and event.mimeData().text().startswith("section:"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def _header_drop_event(self, event):
        """Handle drop on header"""
        if event.mimeData().hasText() and event.mimeData().text().startswith("section:"):
            source_title = event.mimeData().text().replace("section:", "")
            if source_title != self.title:
                # Emit signal to parent to handle reordering
                self.section_reorder_requested.emit(source_title, self.title)
            event.acceptProposedAction()
        else:
            event.ignore()
