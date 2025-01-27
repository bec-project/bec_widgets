import sys
from typing import Literal, Optional

from qtpy.QtCore import Property, QEasingCurve, QPropertyAnimation
from qtpy.QtGui import QAction
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.qt_utils.toolbar import MaterialIconAction, ModularToolBar
from bec_widgets.widgets.plots.waveform.waveform_widget import BECWaveformWidget


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
        self.setObjectName("SidePanel")

        self._orientation = orientation
        self._panel_max_width = panel_max_width
        self._animation_duration = animation_duration
        self._animations_enabled = animations_enabled
        self._orientation = orientation

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

            if self._orientation == "left":
                self.main_layout.addWidget(self.toolbar)
                self.main_layout.addWidget(self.container)
            else:
                self.main_layout.addWidget(self.container)
                self.main_layout.addWidget(self.toolbar)

            self.container.layout.addWidget(self.stack_widget)
            self.stack_widget.setMaximumWidth(self._panel_max_width)

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

            if self._orientation == "top":
                self.main_layout.addWidget(self.toolbar)
                self.main_layout.addWidget(self.container)
            else:
                self.main_layout.addWidget(self.container)
                self.main_layout.addWidget(self.toolbar)

            self.container.layout.addWidget(self.stack_widget)
            self.stack_widget.setMaximumHeight(self._panel_max_width)

        if self._orientation in ("left", "right"):
            self.menu_anim = QPropertyAnimation(self, b"panel_width")
        else:
            self.menu_anim = QPropertyAnimation(self, b"panel_height")

        self.menu_anim.setDuration(self._animation_duration)
        self.menu_anim.setEasingCurve(QEasingCurve.InOutQuad)

        if self._orientation in ("left", "right"):
            self.panel_width = 0
        else:
            self.panel_height = 0

    @Property(int)
    def panel_width(self):
        """
        Get the panel width.
        """
        return self._panel_width

    @panel_width.setter
    def panel_width(self, width: int):
        """
        Set the panel width.

        Args:
            width(int): The width of the panel.
        """
        self._panel_width = width
        if self._orientation in ("left", "right"):
            self.stack_widget.setFixedWidth(width)

    @Property(int)
    def panel_height(self):
        """
        Get the panel height.
        """
        return self._panel_height

    @panel_height.setter
    def panel_height(self, height: int):
        """
        Set the panel height.

        Args:
            height(int): The height of the panel.
        """
        self._panel_height = height
        if self._orientation in ("top", "bottom"):
            self.stack_widget.setFixedHeight(height)

    @Property(int)
    def panel_max_width(self):
        """
        Get the maximum width of the panel.
        """
        return self._panel_max_width

    @panel_max_width.setter
    def panel_max_width(self, size: int):
        """
        Set the maximum width of the panel.

        Args:
            size(int): The maximum width of the panel.
        """
        self._panel_max_width = size
        if self._orientation in ("left", "right"):
            self.stack_widget.setMaximumWidth(self._panel_max_width)
        else:
            self.stack_widget.setMaximumHeight(self._panel_max_width)

    @Property(int)
    def animation_duration(self):
        """
        Get the duration of the animation.
        """
        return self._animation_duration

    @animation_duration.setter
    def animation_duration(self, duration: int):
        """
        Set the duration of the animation.

        Args:
            duration(int): The duration of the animation.
        """
        self._animation_duration = duration
        self.menu_anim.setDuration(duration)

    @Property(bool)
    def animations_enabled(self):
        """
        Get the status of the animations.
        """
        return self._animations_enabled

    @animations_enabled.setter
    def animations_enabled(self, enabled: bool):
        """
        Set the status of the animations.

        Args:
            enabled(bool): The status of the animations.
        """
        self._animations_enabled = enabled

    def show_panel(self, idx: int):
        """
        Show the side panel with animation and switch to idx.

        Args:
            idx(int): The index of the panel to show.
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

        Args:
            idx(int): The index of the panel to switch to.
        """
        if self.current_index != idx:
            self.stack_widget.setCurrentIndex(idx)
            self.current_index = idx

    def add_menu(self, action_id: str, icon_name: str, tooltip: str, widget: QWidget, title: str):
        """
        Add a menu to the side panel.

        Args:
            action_id(str): The ID of the action.
            icon_name(str): The name of the icon.
            tooltip(str): The tooltip for the action.
            widget(QWidget): The widget to add to the panel.
            title(str): The title of the panel.
        """
        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("font-size: 16px;")
        spacer = QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding)
        container_layout.addWidget(title_label)
        container_layout.addWidget(widget)
        container_layout.addItem(spacer)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(5)

        index = self.stack_widget.count()
        self.stack_widget.addWidget(container_widget)

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


class ExampleApp(QMainWindow):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Side Panel Example")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.side_panel = SidePanel(self, orientation="left")

        self.layout = QHBoxLayout(central_widget)

        self.layout.addWidget(self.side_panel)
        self.plot = BECWaveformWidget()
        self.layout.addWidget(self.plot)
        self.add_side_menus()

    def add_side_menus(self):
        widget1 = QWidget()
        widget1_layout = QVBoxLayout(widget1)
        widget1_layout.addWidget(QLabel("This is Widget 1"))
        self.side_panel.add_menu(
            action_id="widget1",
            icon_name="counter_1",
            tooltip="Show Widget 1",
            widget=widget1,
            title="Widget 1 Panel",
        )

        widget2 = QWidget()
        widget2_layout = QVBoxLayout(widget2)
        widget2_layout.addWidget(QLabel("This is Widget 2"))
        self.side_panel.add_menu(
            action_id="widget2",
            icon_name="counter_2",
            tooltip="Show Widget 2",
            widget=widget2,
            title="Widget 2 Panel",
        )

        widget3 = QWidget()
        widget3_layout = QVBoxLayout(widget3)
        widget3_layout.addWidget(QLabel("This is Widget 3"))
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
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec())
