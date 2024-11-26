import pyqtgraph as pg
from qtpy.QtCore import Property
from qtpy.QtWidgets import QApplication, QFrame, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton


class RoundedFrame(BECWidget, QFrame):
    """
    A custom QFrame with rounded corners and optional theme updates.
    The frame can contain any QWidget, however it is mainly designed to wrap PlotWidgets to provide a consistent look and feel with other BEC Widgets.
    """

    def __init__(
        self,
        parent=None,
        content_widget: QWidget = None,
        background_color: str = None,
        theme_update: bool = True,
        radius: int = 10,
        **kwargs,
    ):
        super().__init__(**kwargs)
        QFrame.__init__(self, parent)

        self.background_color = background_color
        self.theme_update = theme_update if background_color is None else False
        self._radius = radius

        # Apply rounded frame styling
        self.setObjectName("roundedFrame")
        self.update_style()

        # Create a layout for the frame
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)  # Set 5px margin

        # Add the content widget to the layout
        if content_widget:
            layout.addWidget(content_widget)

        # Store reference to the content widget
        self.content_widget = content_widget

        # Automatically apply initial styles to the PlotWidget if applicable
        if isinstance(content_widget, pg.PlotWidget):
            self.apply_plot_widget_style()

        self._connect_to_theme_change()

    def apply_theme(self, theme: str):
        """
        Apply the theme to the frame and its content if theme updates are enabled.
        """
        if not self.theme_update:
            return

        # Update background color based on the theme
        if theme == "light":
            self.background_color = "#e9ecef"  # Subtle contrast for light mode
        else:
            self.background_color = "#141414"  # Dark mode

        self.update_style()

        # Update PlotWidget's background color and axis styles if applicable
        if isinstance(self.content_widget, pg.PlotWidget):
            self.apply_plot_widget_style()

    @Property(int)
    def radius(self):
        """Radius of the rounded corners."""
        return self._radius

    @radius.setter
    def radius(self, value: int):
        self._radius = value
        self.update_style()

    def update_style(self):
        """
        Update the style of the frame based on the background color.
        """
        if self.background_color:
            self.setStyleSheet(
                f"""
                QFrame#roundedFrame {{
                    background-color: {self.background_color}; 
                    border-radius: {self._radius}; /* Rounded corners */
                }}
            """
            )

    def apply_plot_widget_style(self, border: str = "none"):
        """
        Automatically apply background, border, and axis styles to the PlotWidget.

        Args:
            border (str): Border style (e.g., 'none', '1px solid red').
        """
        if isinstance(self.content_widget, pg.PlotWidget):
            # Sync PlotWidget's background color with the RoundedFrame's background color
            self.content_widget.setBackground(self.background_color)

            # Calculate contrast-optimized axis and label colors
            if self.background_color == "#e9ecef":  # Light mode
                label_color = "#000000"
                axis_color = "#666666"
            else:  # Dark mode
                label_color = "#FFFFFF"
                axis_color = "#CCCCCC"

            # Apply axis label and tick colors
            plot_item = self.content_widget.getPlotItem()
            plot_item.getAxis("left").setPen(pg.mkPen(color=axis_color))
            plot_item.getAxis("bottom").setPen(pg.mkPen(color=axis_color))
            plot_item.getAxis("left").setTextPen(pg.mkPen(color=label_color))
            plot_item.getAxis("bottom").setTextPen(pg.mkPen(color=label_color))

            # Apply border style via stylesheet
            self.content_widget.setStyleSheet(
                f"""
                PlotWidget {{
                    border: {border}; /* Explicitly set the border */
                }}
            """
            )


class ExampleApp(QWidget):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rounded Plots Example")

        # Main layout
        layout = QVBoxLayout(self)

        dark_button = DarkModeButton()

        # Create PlotWidgets
        plot1 = pg.PlotWidget()
        plot1.plot([1, 3, 2, 4, 6, 5], pen="r")

        plot2 = pg.PlotWidget()
        plot2.plot([1, 2, 4, 8, 16, 32], pen="r")

        # Wrap PlotWidgets in RoundedFrame
        rounded_plot1 = RoundedFrame(content_widget=plot1, theme_update=True)
        rounded_plot2 = RoundedFrame(content_widget=plot2, theme_update=True)
        round = RoundedFrame()

        # Add to layout
        layout.addWidget(dark_button)
        layout.addWidget(rounded_plot1)
        layout.addWidget(rounded_plot2)
        layout.addWidget(round)

        self.setLayout(layout)

        # Simulate theme change after 2 seconds
        from qtpy.QtCore import QTimer

        def change_theme():
            rounded_plot1.apply_theme("light")
            rounded_plot2.apply_theme("dark")

        QTimer.singleShot(100, change_theme)


if __name__ == "__main__":  # pragma: no cover
    app = QApplication([])

    window = ExampleApp()
    window.show()

    app.exec()
