import pyqtgraph as pg
from qtpy.QtCore import Property
from qtpy.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton


class RoundedFrame(QFrame):
    """
    A custom QFrame with rounded corners and optional theme updates.
    The frame can contain any QWidget, however it is mainly designed to wrap PlotWidgets to provide a consistent look and feel with other BEC Widgets.
    """

    def __init__(
        self,
        parent=None,
        content_widget: QWidget = None,
        background_color: str = None,
        orientation: str = "horizontal",
        radius: int = 10,
    ):
        QFrame.__init__(self, parent)

        self.background_color = background_color
        self._radius = radius

        # Apply rounded frame styling
        self.setProperty("skip_settings", True)
        self.setObjectName("roundedFrame")

        # Create a layout for the frame
        if orientation == "vertical":
            self.layout = QVBoxLayout(self)
            self.layout.setContentsMargins(5, 5, 5, 5)
        else:
            self.layout = QHBoxLayout(self)
            self.layout.setContentsMargins(5, 5, 5, 5)  # Set 5px margin

        # Add the content widget to the layout
        if content_widget:
            self.layout.addWidget(content_widget)

        # Store reference to the content widget
        self.content_widget = content_widget

        # Automatically apply initial styles to the GraphicalLayoutWidget if applicable
        self.apply_plot_widget_style()

    def apply_theme(self, theme: str):
        """
        Apply the theme to the frame and its content if theme updates are enabled.
        """
        if self.content_widget is not None and isinstance(
            self.content_widget, pg.GraphicsLayoutWidget
        ):
            self.content_widget.setBackground(self.background_color)

        # Update background color based on the theme
        if theme == "light":
            self.background_color = "#e9ecef"  # Subtle contrast for light mode
        else:
            self.background_color = "#141414"  # Dark mode

        self.update_style()

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
        self.apply_plot_widget_style()

    def apply_plot_widget_style(self, border: str = "none"):
        """
        Automatically apply background, border, and axis styles to the PlotWidget.

        Args:
            border (str): Border style (e.g., 'none', '1px solid red').
        """
        if isinstance(self.content_widget, pg.GraphicsLayoutWidget):
            # Apply border style via stylesheet
            self.content_widget.setStyleSheet(
                f"""
                GraphicsLayoutWidget {{
                    border: {border}; /* Explicitly set the border */
                }}
            """
            )
            self.content_widget.setBackground(self.background_color)


class ExampleApp(QWidget):  # pragma: no cover
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rounded Plots Example")

        # Main layout
        layout = QVBoxLayout(self)

        dark_button = DarkModeButton()

        # Create PlotWidgets
        plot1 = pg.GraphicsLayoutWidget()
        plot_item_1 = pg.PlotItem()
        plot_item_1.plot([1, 3, 2, 4, 6, 5], pen="r")
        plot1.plot_item = plot_item_1

        plot2 = pg.GraphicsLayoutWidget()
        plot_item_2 = pg.PlotItem()
        plot_item_2.plot([1, 2, 4, 8, 16, 32], pen="r")
        plot2.plot_item = plot_item_2

        # Wrap PlotWidgets in RoundedFrame
        rounded_plot1 = RoundedFrame(parent=self, content_widget=plot1)
        rounded_plot2 = RoundedFrame(parent=self, content_widget=plot2)

        # Add to layout
        layout.addWidget(dark_button)
        layout.addWidget(rounded_plot1)
        layout.addWidget(rounded_plot2)

        self.setLayout(layout)

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
