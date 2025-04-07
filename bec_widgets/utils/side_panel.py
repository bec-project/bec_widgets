import sys
from typing import Literal, Optional

from qtpy.QtCore import Property, QEasingCurve, QPropertyAnimation
from qtpy.QtGui import QAction
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.toolbar import MaterialIconAction, ModularToolBar


class SidePanel(QWidget):
    """
    Side panel widget that can be placed on the left, right, top, or bottom of the main widget.
    """

    def __init__(
        self,
        parent=None,
        orientation: Literal["left", "right", "top", "bottom"] = "left",
        panel_max_width: int = 200,
        animation_duration: int = 200,
        animations_enabled: bool = True,
    ):
        super().__init__(parent=parent)

        self.setProperty("skip_settings", True)

        self._orientation = orientation
        self._panel_max_width = panel_max_width
        self._animation_duration = animation_duration
        self._animations_enabled = animations_enabled

        self._panel_width = 0
        self._panel_height = 0
        self.panel_visible = False
        self.current_action: Optional[QAction] = None
        self.current_index: Optional[int] = None
        self.switching_actions = False

        self._init_ui()

    def _init_ui(self):
        """
        Initialize the UI elements.
        """
        if self._orientation in ("left", "right"):
            self.main_layout = QHBoxLayout(self)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)

            self.toolbar = ModularToolBar(target_widget=self, orientation="vertical")

            self.container = QWidget()
            self.container.layout = QVBoxLayout(self.container)
            self.container.layout.setContentsMargins(0, 0, 0, 0)
            self.container.layout.setSpacing(0)

            self.stack_widget = QStackedWidget()
            self.stack_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.stack_widget.setMinimumWidth(5)
            self.stack_widget.setMaximumWidth(self._panel_max_width)

            if self._orientation == "left":
                self.main_layout.addWidget(self.toolbar)
                self.main_layout.addWidget(self.container)
            else:
                self.main_layout.addWidget(self.container)
                self.main_layout.addWidget(self.toolbar)

            self.container.layout.addWidget(self.stack_widget)

            self.menu_anim = QPropertyAnimation(self, b"panel_width")
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            self.panel_width = 0  # start hidden

        else:
            self.main_layout = QVBoxLayout(self)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            self.main_layout.setSpacing(0)

            self.toolbar = ModularToolBar(target_widget=self, orientation="horizontal")

            self.container = QWidget()
            self.container.layout = QVBoxLayout(self.container)
            self.container.layout.setContentsMargins(0, 0, 0, 0)
            self.container.layout.setSpacing(0)

            self.stack_widget = QStackedWidget()
            self.stack_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.stack_widget.setMinimumHeight(5)
            self.stack_widget.setMaximumHeight(self._panel_max_width)

            if self._orientation == "top":
                self.main_layout.addWidget(self.toolbar)
                self.main_layout.addWidget(self.container)
            else:
                self.main_layout.addWidget(self.container)
                self.main_layout.addWidget(self.toolbar)

            self.container.layout.addWidget(self.stack_widget)

            self.menu_anim = QPropertyAnimation(self, b"panel_height")
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.panel_height = 0  # start hidden

        self.menu_anim.setDuration(self._animation_duration)
        self.menu_anim.setEasingCurve(QEasingCurve.InOutQuad)

    @Property(int)
    def panel_width(self):
        """Get the panel width."""
        return self._panel_width

    @panel_width.setter
    def panel_width(self, width: int):
        """Set the panel width."""
        self._panel_width = width
        if self._orientation in ("left", "right"):
            self.stack_widget.setFixedWidth(width)

    @Property(int)
    def panel_height(self):
        """Get the panel height."""
        return self._panel_height

    @panel_height.setter
    def panel_height(self, height: int):
        """Set the panel height."""
        self._panel_height = height
        if self._orientation in ("top", "bottom"):
            self.stack_widget.setFixedHeight(height)

    @Property(int)
    def panel_max_width(self):
        """Get the maximum width of the panel."""
        return self._panel_max_width

    @panel_max_width.setter
    def panel_max_width(self, size: int):
        """Set the maximum width of the panel."""
        self._panel_max_width = size
        if self._orientation in ("left", "right"):
            self.stack_widget.setMaximumWidth(self._panel_max_width)
        else:
            self.stack_widget.setMaximumHeight(self._panel_max_width)

    @Property(int)
    def animation_duration(self):
        """Get the duration of the animation."""
        return self._animation_duration

    @animation_duration.setter
    def animation_duration(self, duration: int):
        """Set the duration of the animation."""
        self._animation_duration = duration
        self.menu_anim.setDuration(duration)

    @Property(bool)
    def animations_enabled(self):
        """Get the status of the animations."""
        return self._animations_enabled

    @animations_enabled.setter
    def animations_enabled(self, enabled: bool):
        """Set the status of the animations."""
        self._animations_enabled = enabled

    def show_panel(self, idx: int):
        """
        Show the side panel with animation and switch to idx.
        """
        self.stack_widget.setCurrentIndex(idx)
        self.panel_visible = True
        self.current_index = idx

        if self._orientation in ("left", "right"):
            start_val, end_val = 0, self._panel_max_width
        else:
            start_val, end_val = 0, self._panel_max_width

        if self._animations_enabled:
            self.menu_anim.stop()
            self.menu_anim.setStartValue(start_val)
            self.menu_anim.setEndValue(end_val)
            self.menu_anim.start()
        else:
            if self._orientation in ("left", "right"):
                self.panel_width = end_val
            else:
                self.panel_height = end_val

    def hide_panel(self):
        """
        Hide the side panel with animation.
        """
        self.panel_visible = False
        self.current_index = None

        if self._orientation in ("left", "right"):
            start_val, end_val = self._panel_max_width, 0
        else:
            start_val, end_val = self._panel_max_width, 0

        if self._animations_enabled:
            self.menu_anim.stop()
            self.menu_anim.setStartValue(start_val)
            self.menu_anim.setEndValue(end_val)
            self.menu_anim.start()
        else:
            if self._orientation in ("left", "right"):
                self.panel_width = end_val
            else:
                self.panel_height = end_val

    def switch_to(self, idx: int):
        """
        Switch to the specified index without animation.
        """
        if self.current_index != idx:
            self.stack_widget.setCurrentIndex(idx)
            self.current_index = idx

    def add_menu(
        self,
        action_id: str,
        icon_name: str,
        tooltip: str,
        widget: QWidget,
        title: str | None = None,
    ):
        """
        Add a menu to the side panel.

        Args:
            action_id(str): The ID of the action.
            icon_name(str): The name of the icon.
            tooltip(str): The tooltip for the action.
            widget(QWidget): The widget to add to the panel.
            title(str): The title of the panel.
        """
        # container_widget: top-level container for the stacked page
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(5)

        if title is not None:
            title_label = QLabel(f"<b>{title}</b>")
            title_label.setStyleSheet("font-size: 16px;")
            container_layout.addWidget(title_label)

        # Create a QScrollArea for the actual widget to ensure scrolling if the widget inside is too large
        scroll_area = QScrollArea()
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidgetResizable(True)
        # Let the scroll area expand in both directions if there's room
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll_area.setWidget(widget)

        # Put the scroll area in the container layout
        container_layout.addWidget(scroll_area)

        # Optionally stretch the scroll area to fill vertical space
        container_layout.setStretchFactor(scroll_area, 1)

        # Add container_widget to the stacked widget
        index = self.stack_widget.count()
        self.stack_widget.addWidget(container_widget)

        # Add an action to the toolbar
        action = MaterialIconAction(icon_name=icon_name, tooltip=tooltip, checkable=True)
        self.toolbar.add_action(action_id, action, target_widget=self)

        def on_action_toggled(checked: bool):
            if self.switching_actions:
                return

            if checked:
                if self.current_action and self.current_action != action.action:
                    self.switching_actions = True
                    self.current_action.setChecked(False)
                    self.switching_actions = False

                self.current_action = action.action

                if not self.panel_visible:
                    self.show_panel(index)
                else:
                    self.switch_to(index)
            else:
                if self.current_action == action.action:
                    self.current_action = None
                    self.hide_panel()

        action.action.toggled.connect(on_action_toggled)


############################################
# DEMO APPLICATION
############################################


class ExampleApp(QMainWindow):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Side Panel Example")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QHBoxLayout(central_widget)

        # Create side panel
        self.side_panel = SidePanel(self, orientation="left", panel_max_width=250)
        self.layout.addWidget(self.side_panel)

        from bec_widgets.widgets.plots.waveform.waveform import Waveform

        self.plot = Waveform()
        self.layout.addWidget(self.plot)

        self.add_side_menus()

    def add_side_menus(self):
        widget1 = QWidget()
        layout1 = QVBoxLayout(widget1)
        for i in range(15):
            layout1.addWidget(QLabel(f"Widget 1 label row {i}"))
        self.side_panel.add_menu(
            action_id="widget1",
            icon_name="counter_1",
            tooltip="Show Widget 1",
            widget=widget1,
            title="Widget 1 Panel",
        )

        widget2 = QWidget()
        layout2 = QVBoxLayout(widget2)
        layout2.addWidget(QLabel("Short widget 2 content"))
        self.side_panel.add_menu(
            action_id="widget2",
            icon_name="counter_2",
            tooltip="Show Widget 2",
            widget=widget2,
            title="Widget 2 Panel",
        )

        widget3 = QWidget()
        layout3 = QVBoxLayout(widget3)
        for i in range(10):
            layout3.addWidget(QLabel(f"Line {i} for Widget 3"))
        self.side_panel.add_menu(
            action_id="widget3",
            icon_name="counter_3",
            tooltip="Show Widget 3",
            widget=widget3,
            title="Widget 3 Panel",
        )


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    window = ExampleApp()
    window.resize(1000, 700)
    window.show()
    sys.exit(app.exec())
