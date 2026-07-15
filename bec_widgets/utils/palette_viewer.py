from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors, get_theme_palette
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton


class PaletteViewer(BECWidget, QWidget):
    """
    This class is a widget that displays current palette colors.
    """

    ICON_NAME = "palette"
    RPC = False

    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setFixedSize(400, 600)
        layout = QVBoxLayout(self)
        dark_mode_button = DarkModeButton(self)
        layout.addWidget(dark_mode_button)

        # Create a scroll area to hold the color boxes
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Create a frame to hold the color boxes
        self.frame = QFrame(self)
        self.frame_layout = QGridLayout(self.frame)
        self.frame_layout.setSpacing(0)
        self.frame_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area.setWidget(self.frame)
        layout.addWidget(scroll_area)

        self.setLayout(layout)

        self.update_palette()

    def apply_theme(self, theme) -> None:
        """
        Apply the theme to the widget.

        Args:
            theme (str): The theme to apply.
        """
        self.update_palette()

    def clear_palette(self) -> None:
        """
        Clear the palette colors from the frame.
        Recursively removes all widgets and layouts in the frame layout.
        """
        # Iterate over all items in the layout in reverse to safely remove them
        for i in reversed(range(self.frame_layout.count())):
            item = self.frame_layout.itemAt(i)

            # If the item is a layout, clear its contents
            if isinstance(item, QHBoxLayout):
                # Recursively remove all widgets from the layout
                for j in reversed(range(item.count())):
                    widget = item.itemAt(j).widget()
                    if widget:
                        item.removeWidget(widget)
                        widget.deleteLater()
                self.frame_layout.removeItem(item)

            # If the item is a widget, remove and delete it
            elif item.widget():
                widget = item.widget()
                self.frame_layout.removeWidget(widget)
                widget.deleteLater()

    def update_palette(self) -> None:
        """
        Update the palette colors in the frame.
        """
        self.clear_palette()
        palette_label = QLabel("Palette Colors (e.g. palette.windowText().color())")
        palette_label.setStyleSheet("font-weight: bold;")
        self.frame_layout.addWidget(palette_label, 0, 0)

        palette = get_theme_palette()
        # Add the palette colors (roles) to the frame
        palette_roles = [
            palette.windowText,
            palette.toolTipText,
            palette.placeholderText,
            palette.text,
            palette.buttonText,
            palette.highlight,
            palette.link,
            palette.light,
            palette.midlight,
            palette.mid,
            palette.shadow,
            palette.button,
            palette.brightText,
            palette.toolTipBase,
            palette.alternateBase,
            palette.dark,
            palette.base,
            palette.window,
            palette.highlightedText,
            palette.linkVisited,
        ]

        offset = 1
        for i, pal in enumerate(palette_roles):
            i += offset
            color = pal().color()
            label_layout = QHBoxLayout()
            color_label = QLabel(f"{pal().color().name()} ({pal.__name__})")
            background_label = self.background_label_with_clipboard(color)
            label_layout.addWidget(color_label)
            label_layout.addWidget(background_label)
            self.frame_layout.addLayout(label_layout, i, 0)

        # add a horizontal spacer
        spacer = QLabel()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.frame_layout.addWidget(spacer, i + 1, 0)

        accent_colors_label = QLabel("Accent Colors (e.g. accent_colors.default)")
        accent_colors_label.setStyleSheet("font-weight: bold;")
        self.frame_layout.addWidget(accent_colors_label, i + 2, 0)

        accent_colors = get_accent_colors()
        items = [
            (accent_colors.default, "default"),
            (accent_colors.success, "success"),
            (accent_colors.warning, "warning"),
            (accent_colors.emergency, "emergency"),
            (accent_colors.highlight, "highlight"),
        ]

        offset = len(palette_roles) + 2
        for i, (color, name) in enumerate(items):
            i += offset
            label_layout = QHBoxLayout()
            color_label = QLabel(f"{color.name()} ({name})")
            background_label = self.background_label_with_clipboard(color)
            label_layout.addWidget(color_label)
            label_layout.addWidget(background_label)
            self.frame_layout.addLayout(label_layout, i + 2, 0)

    def background_label_with_clipboard(self, color) -> QLabel:
        """
        Create a label with a background color that copies the color to the clipboard when clicked.

        Args:
            color (QColor): The color to display in the background.

        Returns:
            QLabel: The label with the background color.
        """
        button = QLabel()
        button.setStyleSheet(f"QLabel {{ background-color: {color.name()}; }}")
        button.setToolTip("Click to copy color to clipboard")
        button.setCursor(Qt.PointingHandCursor)
        button.mousePressEvent = lambda event: QApplication.clipboard().setText(color.name())
        return button


if __name__ == "__main__":  # pragma: no cover
    import sys

    app = QApplication(sys.argv)
    viewer = PaletteViewer()
    viewer.show()
    sys.exit(app.exec_())
