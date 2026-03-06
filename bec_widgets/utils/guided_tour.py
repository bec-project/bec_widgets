"""Module providing a guided help system for creating interactive GUI tours."""

from __future__ import annotations

import sys
import weakref
from typing import Callable, Dict, List, Literal, TypedDict
from uuid import uuid4

import louie
from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from louie import saferef
from qtpy.QtCore import QEvent, QObject, QRect, Qt, Signal
from qtpy.QtGui import QAction, QColor, QKeySequence, QPainter, QPen, QShortcut
from qtpy.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QPushButton,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import ExpandableMenuAction, MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar

logger = bec_logger.logger


class TourStep(TypedDict):
    """Type definition for a tour step."""

    widget_ref: (
        louie.saferef.BoundMethodWeakref
        | weakref.ReferenceType[
            QWidget | QAction | QRect | Callable[[], tuple[QWidget | QAction | QRect, str | None]]
        ]
        | Callable[[], tuple[QWidget | QAction | QRect, str | None]]
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
        box.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color.name()};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
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
        self.back_btn.setToolTip("Press Backspace to go back")

        # Next button with material icon
        self.next_btn = QPushButton("Next")
        self.next_btn.setIcon(material_icon("arrow_forward"))
        self.next_btn.setToolTip("Press Enter to continue")

        btn_layout.addStretch()
        btn_layout.addWidget(self.back_btn)
        btn_layout.addWidget(self.next_btn)

        layout.addLayout(top_layout)
        layout.addWidget(self.label)
        layout.addLayout(btn_layout)

        # Escape closes the tour
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self.close_btn.click)
        # Enter and Return activates the next button
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, activated=self.next_btn.click)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, activated=self.next_btn.click)
        # Map Backspace to the back button
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, activated=self.back_btn.click)

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

        Args:
            rect(QRect): rectangle to highlight
            title(str): Title text for the step
            text(str): Main content text for the step
            current_step(int):  Current step number
            total_steps(int): Total number of steps in the tour
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

        # Update the focus policy of the buttons
        self.back_btn.setEnabled(current_step > 1)

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

    def __init__(self, main_window: QWidget, *, enforce_visibility: bool = True):
        super().__init__()
        self._visible_check: bool = enforce_visibility
        self.main_window_ref = saferef.safe_ref(main_window)
        self.overlay = None
        self._registered_widgets: Dict[str, TourStep] = {}
        self._tour_steps: List[TourStep] = []
        self._current_index = 0
        self._active = False

    @property
    def main_window(self) -> QWidget | None:
        """Get the main window from weak reference."""
        if self.main_window_ref and callable(self.main_window_ref):
            widget = self.main_window_ref()
            if isinstance(widget, QWidget):
                return widget
        return None

    def register_widget(
        self,
        *,
        widget: (
            QWidget | QAction | QRect | Callable[[], tuple[QWidget | QAction | QRect, str | None]]
        ),
        text: str = "",
        title: str = "",
    ) -> str:
        """
        Register a widget with help text for tours.

        Args:
            widget (QWidget | QAction | QRect | Callable[[], tuple[QWidget | QAction | QRect, str | None]]): The target widget or a callable that returns the widget and its help text.
            text (str): The help text for the widget. This will be shown during the tour.
            title (str, optional): A title for the widget (defaults to its class name or action text).

        Returns:
            str: The unique ID for the registered widget.
        """
        step_id = str(uuid4())
        # If it's a plain callable
        if callable(widget) and not hasattr(widget, "__self__"):
            widget_ref = widget
            default_title = "Widget"
        elif isinstance(widget, QAction):
            widget_ref = weakref.ref(widget)
            default_title = widget.text() or "Action"
        elif hasattr(widget, "get_toolbar_button") and callable(widget.get_toolbar_button):

            def _resolve_toolbar_button(toolbar_action=widget):
                button = toolbar_action.get_toolbar_button()
                return (button, None)

            widget_ref = _resolve_toolbar_button
            default_title = getattr(widget, "tooltip", "Toolbar Menu")
        elif isinstance(widget, QRect):
            widget_ref = widget
            default_title = "Area"
        else:
            widget_ref = saferef.safe_ref(widget)
            default_title = widget.__class__.__name__ if hasattr(widget, "__class__") else "Widget"

        self._registered_widgets[step_id] = {
            "widget_ref": widget_ref,
            "text": text,
            "title": title or default_title,
        }
        logger.debug(f"Registered widget {title or default_title} with ID {step_id}")
        return step_id

    def _action_highlight_rect(self, action: QAction) -> QRect | None:
        """
        Try to find the QRect in main_window coordinates that should be highlighted for the given QAction.
        Returns None if not found (e.g. not visible).
        """
        mw = self.main_window
        if mw is None:
            return None
        # Try toolbars first
        for tb in mw.findChildren(QToolBar):
            btn = tb.widgetForAction(action)
            if btn and btn.isVisible():
                rect = btn.rect()
                top_left = btn.mapTo(mw, rect.topLeft())
                return QRect(top_left, rect.size())
        # Try menu bars
        menubars = []
        if hasattr(mw, "menuBar") and callable(getattr(mw, "menuBar", None)):
            mb = mw.menuBar()
            if mb and mb not in menubars:
                menubars.append(mb)
        menubars += [mb for mb in mw.findChildren(QMenuBar) if mb not in menubars]
        menubars += [mb for mb in mw.findChildren(QMenu) if mb not in menubars]

        for mb in menubars:
            if action in mb.actions():
                ar = mb.actionGeometry(action)
                top_left = mb.mapTo(mw, ar.topLeft())
                return QRect(top_left, ar.size())

        return None

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

        Returns:
            bool: True if the tour was created successfully, False if any step IDs were not found
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
            self._show_current_step(direction="prev")

    def _show_current_step(self, direction: Literal["next"] | Literal["prev"] = "next"):
        """Display the current step."""
        if not self._active or not self.overlay:
            return

        step = self._tour_steps[self._current_index]
        step_title = step["title"]

        target, step_text = self._resolve_step_target(step)
        if target is None:
            self._advance_past_invalid_step(
                step_title, reason="Step target no longer exists.", direction=direction
            )
            return

        main_window = self.main_window
        if main_window is None:
            logger.error("Main window no longer exists (weak reference is dead)")
            self.stop_tour()
            return

        highlight_rect = self._get_highlight_rect(
            main_window, target, step_title, direction=direction
        )
        if highlight_rect is None:
            return

        # Calculate step numbers
        current_step = self._current_index + 1
        total_steps = len(self._tour_steps)

        self.overlay.show_step(highlight_rect, step_title, step_text, current_step, total_steps)

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

    def _resolve_step_target(self, step: TourStep) -> tuple[QWidget | QAction | QRect | None, str]:
        """
        Resolve the target widget/action for the given step.

        Args:
            step(TourStep): The tour step to resolve.

        Returns:
            tuple[QWidget | QAction | QRect | None, str]: The resolved target, optional QRect, and the step text.
        """
        widget_ref = step.get("widget_ref")
        step_text = step.get("text", "")

        if isinstance(widget_ref, (louie.saferef.BoundMethodWeakref, weakref.ReferenceType)):
            target = widget_ref()
        else:
            target = widget_ref

        if target is None:
            return None, step_text

        if callable(target) and not isinstance(target, (QWidget, QAction, QRect)):
            result = target()
            if isinstance(result, tuple):
                target, alt_text = result
                if alt_text:
                    step_text = alt_text
            else:
                target = result

        return target, step_text

    def _get_highlight_rect(
        self,
        main_window: QWidget,
        target: QWidget | QAction | QRect,
        step_title: str,
        direction: Literal["next"] | Literal["prev"] = "next",
    ) -> QRect | None:
        """
        Get the QRect in main_window coordinates to highlight for the given target.

        Args:
            main_window(QWidget): The main window containing the target.
            target(QWidget | QAction): The target widget or action to highlight.
            step_title(str): The title of the current step (for logging purposes).

        Returns:
            QRect | None: The rectangle to highlight, or None if not found/visible.
        """
        if isinstance(target, QRect):
            return target
        if isinstance(target, QAction):
            rect = self._action_highlight_rect(target)
            if rect is None:
                self._advance_past_invalid_step(
                    step_title,
                    reason=f"Could not find visible widget or menu for QAction {target.text()!r}.",
                    direction=direction,
                )
                return None
            return rect

        if isinstance(target, QWidget):
            if self._visible_check:
                if not target.isVisible():
                    self._advance_past_invalid_step(
                        step_title, reason=f"Widget {target!r} is not visible.", direction=direction
                    )
                    return None
            rect = target.rect()
            top_left = target.mapTo(main_window, rect.topLeft())
            return QRect(top_left, rect.size())

        if isinstance(target, QTableWidgetItem):
            # NOTE: On header items (which are also QTableWidgetItems), this does not work,
            # Header items are just used as data containers by Qt, thus, we have to directly
            # pass the QRect through the method (+ make sure the appropriate header section
            # is visible). This can be handled in the callable method.)
            table = target.tableWidget()

            if self._visible_check:
                if not table.isVisible():
                    self._advance_past_invalid_step(
                        step_title,
                        reason=f"Table widget {table!r} is not visible.",
                        direction=direction,
                    )
                    return None

            # Table item
            if table.item(target.row(), target.column()) == target:
                table.scrollToItem(target, QAbstractItemView.ScrollHint.PositionAtCenter)
                rect = table.visualItemRect(target)
                top_left = table.viewport().mapTo(main_window, rect.topLeft())
                return QRect(top_left, rect.size())

        self._advance_past_invalid_step(
            step_title, reason=f"Unsupported step target type: {type(target)}", direction=direction
        )
        return None

    def _advance_past_invalid_step(
        self, step_title: str, *, reason: str, direction: Literal["next"] | Literal["prev"] = "next"
    ):
        """
        Skip the current step (or stop the tour) when the target cannot be visualised.
        """
        logger.warning(f"{reason} Skipping step {step_title!r}.")
        if direction == "next":
            if self._current_index < len(self._tour_steps) - 1:
                self._current_index += 1
                self._show_current_step()
            else:
                self.stop_tour()
        elif direction == "prev":
            if self._current_index > 0:
                self._current_index -= 1
                self._show_current_step(direction="prev")
            else:
                self.stop_tour()

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

    def set_visibility_enforcement(self, enabled: bool):
        """Enable or disable visibility checks when highlighting widgets."""
        self._visible_check = enabled

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
        self.setWindowTitle("Guided Tour Demo")
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Welcome to the guided tour demo with toolbar support."))
        self.btn1 = QPushButton("Primary Button")
        self.btn2 = QPushButton("Secondary Button")
        self.status_label = QLabel("Use the controls below or the toolbar to interact.")
        self.start_tour_btn = QPushButton("Start Guided Tour")

        layout.addWidget(self.btn1)
        layout.addWidget(self.btn2)
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.start_tour_btn)
        self.setCentralWidget(central)

        # Guided tour system
        self.guided_help = GuidedTour(self)

        # Menus for demonstrating QAction support in menu bars
        self._init_menu_bar()

        # Modular toolbar showcasing QAction targets
        self._init_toolbar()

        # Register widgets and actions with help text
        primary_step = self.guided_help.register_widget(
            widget=self.btn1,
            text="The primary button updates the status text when clicked.",
            title="Primary Button",
        )
        secondary_step = self.guided_help.register_widget(
            widget=self.btn2,
            text="The secondary button complements the demo layout.",
            title="Secondary Button",
        )
        toolbar_action_step = self.guided_help.register_widget(
            widget=self.toolbar_tour_action.action,
            text="Toolbar actions are supported in the guided tour. This one also starts the tour.",
            title="Toolbar Tour Action",
        )
        tools_menu_step = self.guided_help.register_widget(
            widget=self.toolbar.components.get_action("menu_tools"),
            text="Expandable toolbar menus group related actions. This button opens the tools menu.",
            title="Tools Menu",
        )

        sub_menu_action = self.tools_menu_actions["notes"].action

        def get_sub_menu_action():
            # open the tools menu
            menu_button = self.tools_menu_action._button_ref()
            if menu_button:
                menu_button.showMenu()

            return (
                self.tools_menu_action.actions["notes"].action,
                "This action allows you to add notes.",
            )

        sub_menu = self.guided_help.register_widget(
            widget=get_sub_menu_action,
            text="This is a sub-action within the tools menu.",
            title="Add Note Action",
        )

        # Create tour from registered widgets
        self.tour_step_ids = [
            sub_menu,
            primary_step,
            secondary_step,
            toolbar_action_step,
            tools_menu_step,
        ]
        widget_ids = self.tour_step_ids
        self.guided_help.create_tour(widget_ids)

        # Connect start button
        self.start_tour_btn.clicked.connect(self.guided_help.start_tour)

    def _init_menu_bar(self):
        menu_bar = self.menuBar()
        info_menu = menu_bar.addMenu("Info")
        info_menu.setObjectName("info-menu")
        self.info_menu = info_menu
        self.info_menu_action = info_menu.menuAction()
        self.about_action = info_menu.addAction("About This Demo")

    def _init_toolbar(self):
        self.toolbar = ModularToolBar(parent=self)
        self.addToolBar(self.toolbar)

        self.toolbar_tour_action = MaterialIconAction(
            "play_circle", tooltip="Start the guided tour", parent=self
        )
        self.toolbar.components.add_safe("tour-start", self.toolbar_tour_action)

        self.toolbar_highlight_action = MaterialIconAction(
            "visibility", tooltip="Highlight the primary button", parent=self
        )
        self.toolbar.components.add_safe("inspect-primary", self.toolbar_highlight_action)

        demo_bundle = self.toolbar.new_bundle("demo")
        demo_bundle.add_action("tour-start")
        demo_bundle.add_action("inspect-primary")

        self._setup_tools_menu()
        self.toolbar.show_bundles(["demo", "menu_tools"])
        self.toolbar.refresh()

        self.toolbar_tour_action.action.triggered.connect(self.guided_help.start_tour)

    def _setup_tools_menu(self):
        self.tools_menu_actions: dict[str, MaterialIconAction] = {
            "notes": MaterialIconAction(
                icon_name="note_add", tooltip="Add a note", filled=True, parent=self
            ),
            "bookmark": MaterialIconAction(
                icon_name="bookmark_add", tooltip="Bookmark current view", filled=True, parent=self
            ),
            "settings": MaterialIconAction(
                icon_name="tune", tooltip="Adjust settings", filled=True, parent=self
            ),
        }
        self.tools_menu_action = ExpandableMenuAction(
            label="Tools ", actions=self.tools_menu_actions
        )
        self.toolbar.components.add_safe("menu_tools", self.tools_menu_action)
        bundle = ToolbarBundle("menu_tools", self.toolbar.components)
        bundle.add_action("menu_tools")
        self.toolbar.add_bundle(bundle)


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    from bec_qthemes import apply_theme

    apply_theme("dark")
    w = MainWindow()
    w.resize(400, 300)
    w.show()
    sys.exit(app.exec())
