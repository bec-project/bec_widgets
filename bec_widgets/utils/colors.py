import itertools
import re
from typing import Literal

import bec_qthemes
import numpy as np
import pyqtgraph as pg
from bec_qthemes._os_appearance.listener import OSThemeSwitchListener
from pydantic_core import PydanticCustomError
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication, QPushButton, QToolButton


def get_theme_palette():
    if QApplication.instance() is None or not hasattr(QApplication.instance(), "theme"):
        theme = "dark"
    else:
        theme = QApplication.instance().theme["theme"]
    return bec_qthemes.load_palette(theme)


def set_theme(theme: Literal["dark", "light", "auto"]):
    """
    Set the theme for the application.

    Args:
        theme (Literal["dark", "light", "auto"]): The theme to set. "auto" will automatically switch between dark and light themes based on the system theme.
    """
    app = QApplication.instance()
    bec_qthemes.setup_theme(theme)
    pg.setConfigOption("background", "w" if app.theme["theme"] == "light" else "k")
    apply_theme(theme)

    # pylint: disable=protected-access
    if theme != "auto":
        return

    def callback():
        app.theme["theme"] = listener._theme.lower()
        apply_theme(listener._theme.lower())

    listener = OSThemeSwitchListener(callback)

    app.installEventFilter(listener)


def apply_theme(theme: Literal["dark", "light"]):
    """
    Apply the theme to all pyqtgraph widgets. Do not use this function directly. Use set_theme instead.
    """
    app = QApplication.instance()
    # go through all pyqtgraph widgets and set background
    children = itertools.chain.from_iterable(
        top.findChildren(pg.GraphicsLayoutWidget) for top in app.topLevelWidgets()
    )
    for pg_widget in children:
        pg_widget.setBackground("k" if theme == "dark" else "w")

    dark_mode_buttons = [
        button
        for button in app.topLevelWidgets()
        if hasattr(button, "dark_mode_enabled")
        and hasattr(button, "mode_button")
        and isinstance(button.mode_button, (QPushButton, QToolButton))
    ]

    for button in dark_mode_buttons:
        button.dark_mode_enabled = theme == "dark"
        button.update_mode_button()
    # now define stylesheet according to theme and apply it
    style = bec_qthemes.load_stylesheet(theme)
    app.setStyleSheet(style)


class Colors:

    @staticmethod
    def golden_ratio(num: int) -> list:
        """Calculate the golden ratio for a given number of angles.

        Args:
            num (int): Number of angles

        Returns:
            list: List of angles calculated using the golden ratio.
        """
        phi = 2 * np.pi * ((1 + np.sqrt(5)) / 2)
        angles = []
        for ii in range(num):
            x = np.cos(ii * phi)
            y = np.sin(ii * phi)
            angle = np.arctan2(y, x)
            angles.append(angle)
        return angles

    @staticmethod
    def golden_angle_color(
        colormap: str, num: int, format: Literal["QColor", "HEX", "RGB"] = "QColor"
    ) -> list:
        """
        Extract num colors from the specified colormap following golden angle distribution and return them in the specified format.

        Args:
            colormap (str): Name of the colormap.
            num (int): Number of requested colors.
            format (Literal["QColor","HEX","RGB"]): The format of the returned colors ('RGB', 'HEX', 'QColor').

        Returns:
            list: List of colors in the specified format.

        Raises:
            ValueError: If the number of requested colors is greater than the number of colors in the colormap.
        """
        cmap = pg.colormap.get(colormap)
        cmap_colors = cmap.getColors(mode="float")
        if num > len(cmap_colors):
            raise ValueError(
                f"Number of colors requested ({num}) is greater than the number of colors in the colormap ({len(cmap_colors)})"
            )
        angles = Colors.golden_ratio(len(cmap_colors))
        color_selection = np.round(np.interp(angles, (-np.pi, np.pi), (0, len(cmap_colors))))
        colors = []
        ii = 0
        while len(colors) < num:
            color_index = int(color_selection[ii])
            color = cmap_colors[color_index]
            app = QApplication.instance()
            if hasattr(app, "theme") and app.theme["theme"] == "light":
                background = 255
            else:
                background = 0
            if np.abs(np.mean(color[:3] * 255) - background) < 50:
                ii += 1
                continue

            if format.upper() == "HEX":
                colors.append(QColor.fromRgbF(*color).name())
            elif format.upper() == "RGB":
                colors.append(tuple((np.array(color) * 255).astype(int)))
            elif format.upper() == "QCOLOR":
                colors.append(QColor.fromRgbF(*color))
            else:
                raise ValueError("Unsupported format. Please choose 'RGB', 'HEX', or 'QColor'.")
            ii += 1
        return colors

    @staticmethod
    def hex_to_rgba(hex_color: str, alpha=255) -> tuple:
        """
        Convert HEX color to RGBA.

        Args:
            hex_color(str): HEX color string.
            alpha(int): Alpha value (0-255). Default is 255 (opaque).

        Returns:
            tuple: RGBA color tuple (r, g, b, a).
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 6:
            r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
        elif len(hex_color) == 8:
            r, g, b, a = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4, 6))
            return (r, g, b, a)
        else:
            raise ValueError("HEX color must be 6 or 8 characters long.")
        return (r, g, b, alpha)

    @staticmethod
    def rgba_to_hex(r: int, g: int, b: int, a: int = 255) -> str:
        """
        Convert RGBA color to HEX.

        Args:
            r(int): Red value (0-255).
            g(int): Green value (0-255).
            b(int): Blue value (0-255).
            a(int): Alpha value (0-255). Default is 255 (opaque).

        Returns:
            hec_color(str): HEX color string.
        """
        return "#{:02X}{:02X}{:02X}{:02X}".format(r, g, b, a)

    @staticmethod
    def validate_color(color: tuple | str) -> tuple | str:
        """
        Validate the color input if it is HEX or RGBA compatible. Can be used in any pydantic model as a field validator.

        Args:
            color(tuple|str): The color to be validated. Can be a tuple of RGBA values or a HEX string.

        Returns:
            tuple|str: The validated color.
        """
        CSS_COLOR_NAMES = {
            "aliceblue",
            "antiquewhite",
            "aqua",
            "aquamarine",
            "azure",
            "beige",
            "bisque",
            "black",
            "blanchedalmond",
            "blue",
            "blueviolet",
            "brown",
            "burlywood",
            "cadetblue",
            "chartreuse",
            "chocolate",
            "coral",
            "cornflowerblue",
            "cornsilk",
            "crimson",
            "cyan",
            "darkblue",
            "darkcyan",
            "darkgoldenrod",
            "darkgray",
            "darkgreen",
            "darkgrey",
            "darkkhaki",
            "darkmagenta",
            "darkolivegreen",
            "darkorange",
            "darkorchid",
            "darkred",
            "darksalmon",
            "darkseagreen",
            "darkslateblue",
            "darkslategray",
            "darkslategrey",
            "darkturquoise",
            "darkviolet",
            "deeppink",
            "deepskyblue",
            "dimgray",
            "dimgrey",
            "dodgerblue",
            "firebrick",
            "floralwhite",
            "forestgreen",
            "fuchsia",
            "gainsboro",
            "ghostwhite",
            "gold",
            "goldenrod",
            "gray",
            "green",
            "greenyellow",
            "grey",
            "honeydew",
            "hotpink",
            "indianred",
            "indigo",
            "ivory",
            "khaki",
            "lavender",
            "lavenderblush",
            "lawngreen",
            "lemonchiffon",
            "lightblue",
            "lightcoral",
            "lightcyan",
            "lightgoldenrodyellow",
            "lightgray",
            "lightgreen",
            "lightgrey",
            "lightpink",
            "lightsalmon",
            "lightseagreen",
            "lightskyblue",
            "lightslategray",
            "lightslategrey",
            "lightsteelblue",
            "lightyellow",
            "lime",
            "limegreen",
            "linen",
            "magenta",
            "maroon",
            "mediumaquamarine",
            "mediumblue",
            "mediumorchid",
            "mediumpurple",
            "mediumseagreen",
            "mediumslateblue",
            "mediumspringgreen",
            "mediumturquoise",
            "mediumvioletred",
            "midnightblue",
            "mintcream",
            "mistyrose",
            "moccasin",
            "navajowhite",
            "navy",
            "oldlace",
            "olive",
            "olivedrab",
            "orange",
            "orangered",
            "orchid",
            "palegoldenrod",
            "palegreen",
            "paleturquoise",
            "palevioletred",
            "papayawhip",
            "peachpuff",
            "peru",
            "pink",
            "plum",
            "powderblue",
            "purple",
            "red",
            "rosybrown",
            "royalblue",
            "saddlebrown",
            "salmon",
            "sandybrown",
            "seagreen",
            "seashell",
            "sienna",
            "silver",
            "skyblue",
            "slateblue",
            "slategray",
            "slategrey",
            "snow",
            "springgreen",
            "steelblue",
            "tan",
            "teal",
            "thistle",
            "tomato",
            "turquoise",
            "violet",
            "wheat",
            "white",
            "whitesmoke",
            "yellow",
            "yellowgreen",
        }
        if isinstance(color, str):
            hex_pattern = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")
            if hex_pattern.match(color):
                return color
            elif color.lower() in CSS_COLOR_NAMES:
                return color
            else:
                raise PydanticCustomError(
                    "unsupported color",
                    "The color must be a valid HEX string or CSS Color.",
                    {"wrong_value": color},
                )
        elif isinstance(color, tuple):
            if len(color) != 4:
                raise PydanticCustomError(
                    "unsupported color",
                    "The color must be a tuple of 4 elements (R, G, B, A).",
                    {"wrong_value": color},
                )
            for value in color:
                if not 0 <= value <= 255:
                    raise PydanticCustomError(
                        "unsupported color",
                        f"The color values must be between 0 and 255 in RGBA format (R,G,B,A)",
                        {"wrong_value": color},
                    )
            return color

    @staticmethod
    def validate_color_map(color_map: str) -> str:
        """
        Validate the colormap input if it is supported by pyqtgraph. Can be used in any pydantic model as a field validator. If validation fails it prints all available colormaps from pyqtgraph instance.

        Args:
            color_map(str): The colormap to be validated.

        Returns:
            str: The validated colormap.
        """
        available_colormaps = pg.colormap.listMaps()
        if color_map not in available_colormaps:
            raise PydanticCustomError(
                "unsupported colormap",
                f"Colormap '{color_map}' not found in the current installation of pyqtgraph. Choose on the following: {available_colormaps}.",
                {"wrong_value": color_map},
            )
        return color_map
