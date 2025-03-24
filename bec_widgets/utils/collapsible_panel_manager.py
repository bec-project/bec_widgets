from __future__ import annotations

import sys
from typing import Literal

import pyqtgraph as pg
from qtpy.QtCore import Property, QEasingCurve, QObject, QPropertyAnimation
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from typeguard import typechecked

from bec_widgets.widgets.containers.layout_manager.layout_manager import LayoutManagerWidget


class DimensionAnimator(QObject):
    """
    Helper class to animate the size of a panel widget.
    """

    def __init__(self, panel_widget: QWidget, direction: str):
        super().__init__()
        self.panel_widget = panel_widget
        self.direction = direction
        self._size = 0

    @Property(int)
    def panel_width(self):
        """
        Returns the current width of the panel widget.
        """
        return self._size

    @panel_width.setter
    def panel_width(self, val: int):
        """
        Set the width of the panel widget.

        Args:
            val(int): The width to set.
        """
        self._size = val
        self.panel_widget.setFixedWidth(val)

    @Property(int)
    def panel_height(self):
        """
        Returns the current height of the panel widget.
        """
        return self._size

    @panel_height.setter
    def panel_height(self, val: int):
        """
        Set the height of the panel widget.

        Args:
            val(int): The height to set.
        """
        self._size = val
        self.panel_widget.setFixedHeight(val)


class CollapsiblePanelManager(QObject):
    """
    Manager class to handle collapsible panels from a main widget using LayoutManagerWidget.
    """

    def __init__(self, layout_manager: LayoutManagerWidget, reference_widget: QWidget, parent=None):
        super().__init__(parent)
        self.layout_manager = layout_manager
        self.reference_widget = reference_widget
        self.animations = {}
        self.panels = {}
        self.direction_settings = {
            "left": {"property": b"maximumWidth", "default_size": 200},
            "right": {"property": b"maximumWidth", "default_size": 200},
            "top": {"property": b"maximumHeight", "default_size": 150},
            "bottom": {"property": b"maximumHeight", "default_size": 150},
        }

    def add_panel(
        self,
        direction: Literal["left", "right", "top", "bottom"],
        panel_widget: QWidget,
        target_size: int | None = None,
        duration: int = 300,
    ):
        """
        Add a panel widget to the layout manager.

        Args:
            direction(Literal["left", "right", "top", "bottom"]): Direction of the panel.
            panel_widget(QWidget): The panel widget to add.
            target_size(int, optional): The target size of the panel. Defaults to None.
            duration(int): The duration of the animation in milliseconds. Defaults to 300.
        """
        if direction not in self.direction_settings:
            raise ValueError("Direction must be one of 'left', 'right', 'top', 'bottom'.")

        if target_size is None:
            target_size = self.direction_settings[direction]["default_size"]

        self.layout_manager.add_widget_relative(
            widget=panel_widget, reference_widget=self.reference_widget, position=direction
        )
        panel_widget.setVisible(False)

        # Set initial constraints as flexible
        if direction in ["left", "right"]:
            panel_widget.setMaximumWidth(0)
            panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            panel_widget.setMaximumHeight(0)
            panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.panels[direction] = {
            "widget": panel_widget,
            "direction": direction,
            "target_size": target_size,
            "duration": duration,
            "animator": None,
        }

    def toggle_panel(
        self,
        direction: Literal["left", "right", "top", "bottom"],
        target_size: int | None = None,
        duration: int | None = None,
        easing_curve: QEasingCurve = QEasingCurve.InOutQuad,
        ensure_max: bool = False,
        scale: float | None = None,
        animation: bool = True,
    ):
        """
        Toggle the specified panel.

        Parameters:
            direction (Literal["left", "right", "top", "bottom"]): Direction of the panel to toggle.
            target_size (int, optional): Override target size for this toggle.
            duration (int, optional): Override the animation duration.
            easing_curve (QEasingCurve): Animation easing curve.
            ensure_max (bool): If True, animate as a fixed-size panel.
            scale (float, optional): If provided, calculate target_size from main widget size.
            animation (bool): If False, no animation is performed; panel instantly toggles.
        """
        if direction not in self.panels:
            raise ValueError(f"No panel found in direction '{direction}'.")

        panel_info = self.panels[direction]
        panel_widget = panel_info["widget"]
        dir_settings = self.direction_settings[direction]

        # Determine final target size
        if scale is not None:
            main_rect = self.reference_widget.geometry()
            if direction in ["left", "right"]:
                computed_target = int(main_rect.width() * scale)
            else:
                computed_target = int(main_rect.height() * scale)
            final_target_size = computed_target
        else:
            if target_size is None:
                final_target_size = panel_info["target_size"]
            else:
                final_target_size = target_size

        if duration is None:
            duration = panel_info["duration"]

        expanding_property = dir_settings["property"]
        currently_visible = panel_widget.isVisible()

        if ensure_max:
            if panel_info["animator"] is None:
                panel_info["animator"] = DimensionAnimator(panel_widget, direction)
            animator = panel_info["animator"]

            if direction in ["left", "right"]:
                prop_name = b"panel_width"
            else:
                prop_name = b"panel_height"
        else:
            animator = None
            prop_name = expanding_property

        if currently_visible:
            # Hide the panel
            if ensure_max:
                start_value = final_target_size
                end_value = 0
                finish_callback = lambda w=panel_widget, d=direction: self._after_hide_reset(w, d)
            else:
                start_value = (
                    panel_widget.width()
                    if direction in ["left", "right"]
                    else panel_widget.height()
                )
                end_value = 0
                finish_callback = lambda w=panel_widget: w.setVisible(False)
        else:
            # Show the panel
            start_value = 0
            end_value = final_target_size
            finish_callback = None
            if ensure_max:
                # Fix panel exactly
                if direction in ["left", "right"]:
                    panel_widget.setMinimumWidth(0)
                    panel_widget.setMaximumWidth(final_target_size)
                    panel_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
                else:
                    panel_widget.setMinimumHeight(0)
                    panel_widget.setMaximumHeight(final_target_size)
                    panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            else:
                # Flexible mode
                if direction in ["left", "right"]:
                    panel_widget.setMinimumWidth(0)
                    panel_widget.setMaximumWidth(final_target_size)
                    panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                else:
                    panel_widget.setMinimumHeight(0)
                    panel_widget.setMaximumHeight(final_target_size)
                    panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            panel_widget.setVisible(True)

        if not animation:
            # No animation: instantly set final state
            if end_value == 0:
                # Hiding
                if ensure_max:
                    # Reset after hide
                    self._after_hide_reset(panel_widget, direction)
                else:
                    panel_widget.setVisible(False)
            else:
                # Showing
                if ensure_max:
                    # Already set fixed size
                    if direction in ["left", "right"]:
                        panel_widget.setFixedWidth(end_value)
                    else:
                        panel_widget.setFixedHeight(end_value)
                else:
                    # Just set maximum dimension
                    if direction in ["left", "right"]:
                        panel_widget.setMaximumWidth(end_value)
                    else:
                        panel_widget.setMaximumHeight(end_value)
            return

        # With animation
        animation = QPropertyAnimation(animator if ensure_max else panel_widget, prop_name)
        animation.setDuration(duration)
        animation.setStartValue(start_value)
        animation.setEndValue(end_value)
        animation.setEasingCurve(easing_curve)

        if end_value == 0 and finish_callback:
            animation.finished.connect(finish_callback)
        elif end_value == 0 and not finish_callback:
            animation.finished.connect(lambda w=panel_widget: w.setVisible(False))

        animation.start()
        self.animations[panel_widget] = animation

    @typechecked
    def _after_hide_reset(
        self, panel_widget: QWidget, direction: Literal["left", "right", "top", "bottom"]
    ):
        """
        Reset the panel widget after hiding it in ensure_max mode.

        Args:
            panel_widget(QWidget): The panel widget to reset.
            direction(Literal["left", "right", "top", "bottom"]): The direction of the panel.
        """
        # Called after hiding a panel in ensure_max mode
        panel_widget.setVisible(False)
        if direction in ["left", "right"]:
            panel_widget.setMinimumWidth(0)
            panel_widget.setMaximumWidth(0)
            panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            panel_widget.setMinimumHeight(0)
            panel_widget.setMaximumHeight(16777215)
            panel_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


####################################################################################################
# The following code is for the GUI control panel to interact with the CollapsiblePanelManager.
# It is not covered by any tests as it serves only as an example for the CollapsiblePanelManager class.
####################################################################################################


class MainWindow(QMainWindow):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Panels with ensure_max, scale, and animation toggle")
        self.resize(800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Buttons
        buttons_layout = QHBoxLayout()
        self.btn_left = QPushButton("Toggle Left (ensure_max=True)")
        self.btn_top = QPushButton("Toggle Top (scale=0.5, no animation)")
        self.btn_right = QPushButton("Toggle Right (ensure_max=True, scale=0.3)")
        self.btn_bottom = QPushButton("Toggle Bottom (no animation)")

        buttons_layout.addWidget(self.btn_left)
        buttons_layout.addWidget(self.btn_top)
        buttons_layout.addWidget(self.btn_right)
        buttons_layout.addWidget(self.btn_bottom)

        main_layout.addLayout(buttons_layout)

        self.layout_manager = LayoutManagerWidget()
        main_layout.addWidget(self.layout_manager)

        # Main widget
        self.main_plot = pg.PlotWidget()
        self.main_plot.plot([1, 2, 3, 4], [4, 3, 2, 1])
        self.layout_manager.add_widget(self.main_plot, 0, 0)

        self.panel_manager = CollapsiblePanelManager(self.layout_manager, self.main_plot)

        # Panels
        self.left_panel = pg.PlotWidget()
        self.left_panel.plot([1, 2, 3], [3, 2, 1])
        self.panel_manager.add_panel("left", self.left_panel, target_size=200)

        self.right_panel = pg.PlotWidget()
        self.right_panel.plot([10, 20, 30], [1, 10, 1])
        self.panel_manager.add_panel("right", self.right_panel, target_size=200)

        self.top_panel = pg.PlotWidget()
        self.top_panel.plot([1, 2, 3], [1, 2, 3])
        self.panel_manager.add_panel("top", self.top_panel, target_size=150)

        self.bottom_panel = pg.PlotWidget()
        self.bottom_panel.plot([2, 4, 6], [10, 5, 10])
        self.panel_manager.add_panel("bottom", self.bottom_panel, target_size=150)

        # Connect buttons
        # Left with ensure_max
        self.btn_left.clicked.connect(
            lambda: self.panel_manager.toggle_panel("left", ensure_max=True)
        )
        # Top with scale=0.5 and no animation
        self.btn_top.clicked.connect(
            lambda: self.panel_manager.toggle_panel("top", scale=0.5, animation=False)
        )
        # Right with ensure_max, scale=0.3
        self.btn_right.clicked.connect(
            lambda: self.panel_manager.toggle_panel("right", ensure_max=True, scale=0.3)
        )
        # Bottom no animation
        self.btn_bottom.clicked.connect(
            lambda: self.panel_manager.toggle_panel("bottom", target_size=100, animation=False)
        )


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
