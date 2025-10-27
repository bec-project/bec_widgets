"""Module providing a guided help system for creating interactive GUI tours."""

from __future__ import annotations

import sys
import weakref
from typing import Callable, Dict, List, Optional, TypedDict
from uuid import uuid4

import louie
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from louie import saferef
from qtpy.QtCore import QEvent, QObject, QRect, Qt, Signal
from qtpy.QtGui import QColor, QPainter, QPen
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger


class TourStep(TypedDict):
    """Type definition for a tour step."""

    widget_ref: (
        louie.saferef.BoundMethodWeakref
        | weakref.ReferenceType[QWidget | Callable[[], tuple[QWidget, str | None]]]
        | Callable[[], tuple[QWidget, str | None]]
        | None
    )
    text: str
    title: str


class TutorialOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Keep mouse events enabled for the overlay but we'll handle them manually
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.current_rect = QRect()
        self.message_box = self._create_message_box()
        self.message_box.hide()

    def _create_message_box(self):
        box = QFrame(self)
        app = QApplication.instance()
        bg_color = app.palette().window().color()
        box.setStyleSheet(
            f"""
            QFrame {{
                background-color: {bg_color.name()};
                border-radius: 8px;
                padding: 8px;
            }}
        """
        )
        layout = QVBoxLayout(box)

        # Top layout with close button (left) and step indicator (right)
        top_layout = QHBoxLayout()

        # Close button on the left with material icon
        self.close_btn = QPushButton()
        self.close_btn.setIcon(material_icon("close"))
        self.close_btn.setToolTip("Close")
        self.close_btn.setMaximumSize(32, 32)

        # Step indicator on the right
        self.step_label = QLabel()
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.step_label.setStyleSheet("color: #666; font-size: 12px; font-weight: bold;")

        top_layout.addWidget(self.close_btn)
        top_layout.addStretch()
        top_layout.addWidget(self.step_label)

        # Main content label
        self.label = QLabel()
        self.label.setWordWrap(True)

        # Bottom navigation buttons
        btn_layout = QHBoxLayout()

        # Back button with material icon
        self.back_btn = QPushButton("Back")
        self.back_btn.setIcon(material_icon("arrow_back"))

        # Next button with material icon
        self.next_btn = QPushButton("Next")
        self.next_btn.setIcon(material_icon("arrow_forward"))

        btn_layout.addStretch()
        btn_layout.addWidget(self.back_btn)
        btn_layout.addWidget(self.next_btn)

        layout.addLayout(top_layout)
        layout.addWidget(self.label)
        layout.addLayout(btn_layout)
        return box

    def paintEvent(self, event):  # pylint: disable=unused-argument
        if not self.current_rect.isValid():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Create semi-transparent overlay color
        overlay_color = QColor(0, 0, 0, 160)
        # Use exclusive coordinates to avoid 1px gaps caused by QRect.bottom()/right() being inclusive.
        r = self.current_rect
        rect_x, rect_y, rect_w, rect_h = r.x(), r.y(), r.width(), r.height()

        # Paint overlay in 4 regions around the highlighted widget using exclusive bounds
        # Top region (everything above the highlight)
        if rect_y > 0:
            top_rect = QRect(0, 0, self.width(), rect_y)
            painter.fillRect(top_rect, overlay_color)

        # Bottom region (everything below the highlight)
        bottom_y = rect_y + rect_h
        if bottom_y < self.height():
            bottom_rect = QRect(0, bottom_y, self.width(), self.height() - bottom_y)
            painter.fillRect(bottom_rect, overlay_color)

        # Left region (to the left of the highlight)
        if rect_x > 0:
            left_rect = QRect(0, rect_y, rect_x, rect_h)
            painter.fillRect(left_rect, overlay_color)

        # Right region (to the right of the highlight)
        right_x = rect_x + rect_w
        if right_x < self.width():
            right_rect = QRect(right_x, rect_y, self.width() - right_x, rect_h)
            painter.fillRect(right_rect, overlay_color)

        # Draw highlight border around the clear area. Expand slightly so border doesn't leave a hairline gap.
        border_rect = QRect(rect_x - 2, rect_y - 2, rect_w + 4, rect_h + 4)
        painter.setPen(QPen(QColor(76, 175, 80), 3))  # Green border
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(border_rect, 8, 8)
        painter.end()

    def show_step(
        self, rect: QRect, title: str, text: str, current_step: int = 1, total_steps: int = 1
    ):
        """
        rect must already be in the overlay's coordinate space (i.e. mapped).
        This method positions the message box so it does not overlap the rect.
        """
        self.current_rect = rect

        # Update step indicator in top right
        self.step_label.setText(f"Step {current_step} of {total_steps}")

        # Update main content text (without step number since it's now in top right)
        content_text = f"<b>{title}</b><br>{text}" if title else text
        self.label.setText(content_text)
        self.message_box.adjustSize()  # ensure layout applied
        message_size = self.message_box.size()  # actual widget size (width, height)

        spacing = 15

        # Preferred placement: to the right, vertically centered
        pos_x = rect.right() + spacing
        pos_y = rect.center().y() - (message_size.height() // 2)

        # If it would go off the right edge, try left of the widget
        if pos_x + message_size.width() > self.width():
            pos_x = rect.left() - message_size.width() - spacing
            # vertical center is still good, but if that overlaps top/bottom we'll clamp below

        # If it goes off the left edge (no space either side), place below, centered horizontally
        if pos_x < spacing:
            pos_x = rect.center().x() - (message_size.width() // 2)
            pos_y = rect.bottom() + spacing

        # If it goes off the bottom, try moving it above the widget
        if pos_y + message_size.height() > self.height() - spacing:
            # if there's room above the rect, put it there
            candidate_y = rect.top() - message_size.height() - spacing
            if candidate_y >= spacing:
                pos_y = candidate_y
            else:
                # otherwise clamp to bottom with spacing
                pos_y = max(spacing, self.height() - message_size.height() - spacing)

        # If it goes off the top, clamp down
        pos_y = max(spacing, pos_y)

        # Make sure we don't poke the left edge
        pos_x = max(spacing, min(pos_x, self.width() - message_size.width() - spacing))

        # Apply geometry and show
        self.message_box.setGeometry(
            int(pos_x), int(pos_y), message_size.width(), message_size.height()
        )
        self.message_box.show()
        self.update()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Resize:
            self.setGeometry(obj.rect())
        return False


class GuidedTour(QObject):
    """
    A guided help system for creating interactive GUI tours.

    Allows developers to register widgets with help text and create guided tours.
    """

    tour_started = Signal()
    tour_finished = Signal()
    step_changed = Signal(int, int)  # current_step, total_steps

    def __init__(self, main_window: QWidget):
        super().__init__()
        self.main_window_ref = saferef.safe_ref(main_window)
        self.overlay = None
        self._registered_widgets: Dict[str, TourStep] = {}
        self._tour_steps: List[TourStep] = []
        self._current_index = 0
        self._active = False

    @property
    def main_window(self) -> Optional[QWidget]:
        """Get the main window from weak reference."""
        if self.main_window_ref and callable(self.main_window_ref):
            widget = self.main_window_ref()
            if isinstance(widget, QWidget):
                return widget
        return None

    def register_widget(
        self,
        *,
        widget: QWidget | Callable[[], tuple[QWidget, str | None]],
        text: str = "",
        title: str = "",
    ) -> str:
        """
        Register a widget with help text for tours.

        Args:
            widget (QWidget | Callable[[], tuple[QWidget, str | None]]): The target widget or a callable that returns the widget and its help text.
            text (str): The help text for the widget. This will be shown during the tour.
            title (str, optional): A title for the widget (defaults to its class name).

        Returns:
            str: The unique ID for the registered widget.
        """
        step_id = str(uuid4())

        # Check if it is a bound method
        if callable(widget) and not hasattr(widget, "__self__"):
            # We are dealing with a plain callable
            widget_ref = widget
        else:
            # Create weak reference for QWidget instances
            widget_ref = saferef.safe_ref(widget)

        self._registered_widgets[step_id] = {
            "widget_ref": widget_ref,
            "text": text,
            "title": title
            or (widget.__class__.__name__ if hasattr(widget, "__class__") else "Widget"),
        }
        logger.debug(f"Registered widget {title} with ID {step_id}")
        return step_id

    def unregister_widget(self, step_id: str) -> bool:
        """
        Unregister a previously registered widget.

        Args:
            step_id (str): The unique ID of the registered widget.

        Returns:
            bool: True if the widget was unregistered, False if not found.
        """
        if self._active:
            raise RuntimeError("Cannot unregister widget while tour is active")
        if step_id in self._registered_widgets:
            if self._registered_widgets[step_id] in self._tour_steps:
                self._tour_steps.remove(self._registered_widgets[step_id])
            del self._registered_widgets[step_id]
            return True
        return False

    def create_tour(self, step_ids: List[str] | None = None) -> bool:
        """
        Create a tour from registered widget IDs.

        Args:
            step_ids (List[str], optional): List of registered widget IDs to include in the tour. If None, all registered widgets will be included.
        """
        if step_ids is None:
            step_ids = list(self._registered_widgets.keys())

        tour_steps = []
        for step_id in step_ids:
            if step_id not in self._registered_widgets:
                logger.error(f"Step ID {step_id} not found")
                return False
            tour_steps.append(self._registered_widgets[step_id])

        self._tour_steps = tour_steps
        logger.info(f"Created tour with {len(tour_steps)} steps")
        return True

    @SafeSlot()
    def start_tour(self):
        """Start the guided tour."""
        if not self._tour_steps:
            self.create_tour()

        if self._active:
            logger.warning("Tour already active")
            return

        main_window = self.main_window
        if main_window is None:
            logger.error("Main window no longer exists (weak reference is dead)")
            return

        self._active = True
        self._current_index = 0

        # Create overlay
        self.overlay = TutorialOverlay(main_window)
        self.overlay.setGeometry(main_window.rect())
        self.overlay.show()
        main_window.installEventFilter(self.overlay)

        # Connect signals
        self.overlay.next_btn.clicked.connect(self.next_step)
        self.overlay.back_btn.clicked.connect(self.prev_step)
        self.overlay.close_btn.clicked.connect(self.stop_tour)

        main_window.installEventFilter(self)
        self._show_current_step()
        self.tour_started.emit()
        logger.info("Started guided tour")

    @SafeSlot()
    def stop_tour(self):
        """Stop the current tour."""
        if not self._active:
            return

        self._active = False

        main_window = self.main_window
        if self.overlay and main_window:
            main_window.removeEventFilter(self.overlay)
            self.overlay.hide()
            self.overlay.deleteLater()
            self.overlay = None

        if main_window:
            main_window.removeEventFilter(self)
        self.tour_finished.emit()
        logger.info("Stopped guided tour")

    @SafeSlot()
    def next_step(self):
        """Move to next step or finish tour if on last step."""
        if not self._active:
            return

        if self._current_index < len(self._tour_steps) - 1:
            self._current_index += 1
            self._show_current_step()
        else:
            # On last step, finish the tour
            self.stop_tour()

    @SafeSlot()
    def prev_step(self):
        """Move to previous step."""
        if not self._active:
            return

        if self._current_index > 0:
            self._current_index -= 1
            self._show_current_step()

    def _show_current_step(self):
        """Display the current step."""
        if not self._active or not self.overlay:
            return

        step = self._tour_steps[self._current_index]
        widget_ref = step.get("widget_ref")

        step_title = step["title"]
        widget = None
        step_text = step["text"]

        # Resolve weak reference
        if isinstance(widget_ref, (louie.saferef.BoundMethodWeakref, weakref.ReferenceType)):
            widget = widget_ref()
        else:
            widget = widget_ref

        # If the widget does not exist, log warning and skip to next step or stop tour
        if not widget:
            logger.warning(
                f"Widget for step {step['title']} no longer exists (weak reference is dead)"
            )
            # Skip to next step or stop tour if this was the last step
            if self._current_index < len(self._tour_steps) - 1:
                self._current_index += 1
                self._show_current_step()
            else:
                self.stop_tour()
            return

        # If the user provided a callable, resolve it to get the widget and optional alt text
        if callable(widget):
            widget, alt_text = widget()
            if alt_text:
                step_text = alt_text

        if not widget.isVisible():
            logger.warning(f"Widget for step {step['title']} is not visible")
            return

        # Map widget coordinates to overlay coordinates
        main_window = self.main_window
        if main_window is None:
            logger.error("Main window no longer exists (weak reference is dead)")
            self.stop_tour()
            return

        rect = widget.rect()
        top_left = widget.mapTo(main_window, rect.topLeft())
        global_rect = QRect(top_left, rect.size())

        # Calculate step numbers
        current_step = self._current_index + 1
        total_steps = len(self._tour_steps)

        self.overlay.show_step(global_rect, step_title, step_text, current_step, total_steps)

        # Update button states
        self.overlay.back_btn.setEnabled(self._current_index > 0)

        # Update next button text and state
        is_last_step = self._current_index >= len(self._tour_steps) - 1
        if is_last_step:
            self.overlay.next_btn.setText("Finish")
            self.overlay.next_btn.setIcon(material_icon("check"))
            self.overlay.next_btn.setEnabled(True)
        else:
            self.overlay.next_btn.setText("Next")
            self.overlay.next_btn.setIcon(material_icon("arrow_forward"))
            self.overlay.next_btn.setEnabled(True)

        self.step_changed.emit(self._current_index + 1, len(self._tour_steps))

    def get_registered_widgets(self) -> Dict[str, TourStep]:
        """Get all registered widgets."""
        return self._registered_widgets.copy()

    def clear_registrations(self):
        """Clear all registered widgets."""
        if self._active:
            self.stop_tour()
        self._registered_widgets.clear()
        self._tour_steps.clear()
        logger.info("Cleared all registrations")

    def eventFilter(self, obj, event):
        """Handle window resize/move events to update step positioning."""
        if event.type() in (QEvent.Type.Move, QEvent.Type.Resize):
            if self._active:
                self._show_current_step()
        return super().eventFilter(obj, event)


################################################################################
############ # Example usage of GuidedTour system ##############################
################################################################################


class MainWindow(QMainWindow):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Guided Help Demo")
        central = QWidget()
        layout = QVBoxLayout(central)

        # Create demo widgets
        self.btn1 = QPushButton("Button 1")
        self.btn2 = QPushButton("Button 2")
        self.start_tour_btn = QPushButton("Start Guided Tour")

        layout.addWidget(QLabel("Welcome to the Guided Help Demo!"))
        layout.addWidget(self.btn1)
        layout.addWidget(self.btn2)
        layout.addWidget(self.start_tour_btn)
        layout.addStretch()
        self.setCentralWidget(central)

        # Create guided help system
        self.guided_help = GuidedTour(self)

        # Register widgets with help text
        self.guided_help.register_widget(
            widget=self.btn1,
            text="This is the first button. It demonstrates how to highlight a widget and show help text next to it.",
            title="First Button",
        )

        def widget_with_alt_text():
            import numpy as np

            if np.random.randint(0, 10) % 2 == 0:
                return (self.btn2, None)
            return (self.btn2, "This is an alternative help text for Button 2.")

        self.guided_help.register_widget(
            widget=widget_with_alt_text,
            text="This is the second button. Notice how the help tooltip is positioned smartly to stay visible.",
            title="Second Button",
        )

        # Create tour from registered widgets
        widget_ids = list(self.guided_help.get_registered_widgets().keys())
        self.guided_help.create_tour(widget_ids)

        # Connect start button
        self.start_tour_btn.clicked.connect(self.guided_help.start_tour)


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    from bec_qthemes import apply_theme

    apply_theme("dark")
    w = MainWindow()
    w.resize(400, 300)
    w.show()
    sys.exit(app.exec())
