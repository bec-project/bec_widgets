import pyqtgraph as pg
from qtpy.QtCore import Property, Qt
from qtpy.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QWidget

from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton


class RoundedFrame(QFrame):
    # TODO this should be removed completely in favor of QSS styling, no time now
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

        # Ensure QSS can paint background/border on this widget
        self.setAttribute(Qt.WA_StyledBackground, True)

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
        self.update_style()

    def apply_theme(self, theme: str):
        """Deprecated: RoundedFrame no longer handles theme; styling is QSS-driven."""
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
        self.setStyleSheet(f"""
                QFrame#roundedFrame {{
                    border-radius: {self._radius}px;
                }}
            """)
        self.apply_plot_widget_style()

    def apply_plot_widget_style(self, border: str = "none"):
        """
        Let QSS/pyqtgraph handle plot styling; avoid overriding here.
        """
        if isinstance(self.content_widget, pg.GraphicsLayoutWidget):
            self.content_widget.setStyleSheet("")


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

        # Add to layout (no RoundedFrame wrapper; QSS styles plots)
        layout.addWidget(dark_button)
        layout.addWidget(plot1)
        layout.addWidget(plot2)

        self.setLayout(layout)

        # Theme flip demo removed; global theming applies automatically


if __name__ == "__main__":  # pragma: no cover
    app = QApplication([])

    window = ExampleApp()
    window.show()

    app.exec()
