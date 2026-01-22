from __future__ import annotations

import re
from typing import Literal

import numpy as np
import pyqtgraph as pg
from bec_lib import bec_logger
from bec_qthemes import apply_theme as apply_theme_global
from bec_qthemes._theme import AccentColors
from pydantic_core import PydanticCustomError
from qtpy.QtCore import QEvent, QEventLoop
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QApplication

logger = bec_logger.logger


def get_theme_name():
    if QApplication.instance() is None or not hasattr(QApplication.instance(), "theme"):
        return "dark"
    else:
        return QApplication.instance().theme.theme


def get_theme_palette():
    # FIXME this is legacy code, should be removed in the future
    app = QApplication.instance()
    palette = app.palette()
    return palette


def get_accent_colors() -> AccentColors:
    """
    Get the accent colors for the current theme. These colors are extensions of the color palette
    and are used to highlight specific elements in the UI.
    """
    if QApplication.instance() is None or not hasattr(QApplication.instance(), "theme"):
        accent_colors = AccentColors()
        return accent_colors
    return QApplication.instance().theme.accent_colors


def process_all_deferred_deletes(qapp):
    qapp.sendPostedEvents(None, QEvent.DeferredDelete)
    qapp.processEvents(QEventLoop.AllEvents)


def apply_theme(theme: Literal["dark", "light"]):
    """
    Apply the theme via the global theming API. This updates QSS, QPalette, and pyqtgraph globally.
    """
    logger.info(f"Applying theme: {theme}")
    process_all_deferred_deletes(QApplication.instance())
    apply_theme_global(theme)
    process_all_deferred_deletes(QApplication.instance())


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
    def set_theme_offset(theme: Literal["light", "dark"] | None = None, offset=0.2) -> tuple:
        """
        Set the theme offset to avoid colors too close to white or black with light or dark theme respectively for pyqtgraph plot background.

        Args:
            theme(str): The theme to be applied.
            offset(float): Offset to avoid colors too close to white or black with light or dark theme respectively for pyqtgraph plot background.

        Returns:
            tuple: Tuple of min_pos and max_pos.

        Raises:
            ValueError: If theme_offset is not between 0 and 1.
        """

        if offset < 0 or offset > 1:
            raise ValueError("theme_offset must be between 0 and 1")

        if theme is None:
            app = QApplication.instance()
            if hasattr(app, "theme"):
                theme = app.theme.theme

        if theme == "light":
            min_pos = 0.0
            max_pos = 1 - offset
        else:
            min_pos = 0.0 + offset
            max_pos = 1.0

        return min_pos, max_pos

    @staticmethod
    def evenly_spaced_colors(
        colormap: str,
        num: int,
        format: Literal["QColor", "HEX", "RGB"] = "QColor",
        theme_offset=0.2,
        theme: Literal["light", "dark"] | None = None,
    ) -> list:
        """
        Extract `num` colors from the specified colormap, evenly spaced along its range,
        and return them in the specified format.

        Args:
            colormap (str): Name of the colormap.
            num (int): Number of requested colors.
            format (Literal["QColor","HEX","RGB"]): The format of the returned colors ('RGB', 'HEX', 'QColor').
            theme_offset (float): Has to be between 0-1. Offset to avoid colors too close to white or black with light or dark theme respectively for pyqtgraph plot background.
            theme (Literal['light', 'dark'] | None): The theme to be applied. Overrides the QApplication theme if specified.

        Returns:
            list: List of colors in the specified format.

        Raises:
            ValueError: If theme_offset is not between 0 and 1.
        """
        if theme_offset < 0 or theme_offset > 1:
            raise ValueError("theme_offset must be between 0 and 1")

        cmap = pg.colormap.get(colormap)
        min_pos, max_pos = Colors.set_theme_offset(theme, theme_offset)

        # Generate positions that are evenly spaced within the acceptable range
        if num == 1:
            positions = np.array([(min_pos + max_pos) / 2])
        else:
            positions = np.linspace(min_pos, max_pos, num)

        # Sample colors from the colormap at the calculated positions
        colors = cmap.map(positions, mode="float")
        color_list = []

        for color in colors:
            if format.upper() == "HEX":
                color_list.append(QColor.fromRgbF(*color).name())
            elif format.upper() == "RGB":
                color_list.append(tuple((np.array(color) * 255).astype(int)))
            elif format.upper() == "QCOLOR":
                color_list.append(QColor.fromRgbF(*color))
            else:
                raise ValueError("Unsupported format. Please choose 'RGB', 'HEX', or 'QColor'.")
        return color_list

    @staticmethod
    def golden_angle_color(
        colormap: str,
        num: int,
        format: Literal["QColor", "HEX", "RGB"] = "QColor",
        theme_offset=0.2,
        theme: Literal["dark", "light"] | None = None,
    ) -> list:
        """
        Extract num colors from the specified colormap following golden angle distribution and return them in the specified format.

        Args:
            colormap (str): Name of the colormap.
            num (int): Number of requested colors.
            format (Literal["QColor","HEX","RGB"]): The format of the returned colors ('RGB', 'HEX', 'QColor').
            theme_offset (float): Has to be between 0-1. Offset to avoid colors too close to white or black with light or dark theme respectively for pyqtgraph plot background.

        Returns:
            list: List of colors in the specified format.

        Raises:
            ValueError: If theme_offset is not between 0 and 1.
        """

        cmap = pg.colormap.get(colormap)
        phi = (1 + np.sqrt(5)) / 2  # Golden ratio
        golden_angle_conjugate = 1 - (1 / phi)  # Approximately 0.38196601125

        min_pos, max_pos = Colors.set_theme_offset(theme, theme_offset)

        # Generate positions within the acceptable range
        positions = np.mod(np.arange(num) * golden_angle_conjugate, 1)
        positions = min_pos + positions * (max_pos - min_pos)

        # Sample colors from the colormap at the calculated positions
        colors = cmap.map(positions, mode="float")
        color_list = []

        for color in colors:
            if format.upper() == "HEX":
                color_list.append(QColor.fromRgbF(*color).name())
            elif format.upper() == "RGB":
                color_list.append(tuple((np.array(color) * 255).astype(int)))
            elif format.upper() == "QCOLOR":
                color_list.append(QColor.fromRgbF(*color))
            else:
                raise ValueError("Unsupported format. Please choose 'RGB', 'HEX', or 'QColor'.")
        return color_list

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
    def validate_color_map(color_map: str, return_error: bool = True) -> str | bool:
        """
        Validate the colormap input if it is supported by pyqtgraph. Can be used in any pydantic model as a field validator. If validation fails it prints all available colormaps from pyqtgraph instance.

        Args:
            color_map(str): The colormap to be validated.

        Returns:
            str: The validated colormap, if colormap is valid.
            bool: False, if colormap is invalid.

        Raises:
            PydanticCustomError: If colormap is invalid.
        """
        available_pg_maps = pg.colormap.listMaps()
        available_mpl_maps = pg.colormap.listMaps("matplotlib")
        available_mpl_colorcet = pg.colormap.listMaps("colorcet")

        available_colormaps = available_pg_maps + available_mpl_maps + available_mpl_colorcet
        if color_map not in available_colormaps:
            if return_error:
                raise PydanticCustomError(
                    "unsupported colormap",
                    f"Colormap '{color_map}' not found in the current installation of pyqtgraph. Choose on the following: {available_colormaps}.",
                    {"wrong_value": color_map},
                )
            else:
                return False
        return color_map

    @staticmethod
    def relative_luminance(color: QColor) -> float:
        """
        Calculate the relative luminance of a QColor according to WCAG 2.0 standards.
        See https://www.w3.org/TR/WCAG21/#dfn-relative-luminance.

        Args:
            color(QColor): The color to calculate the relative luminance for.

        Returns:
            float: The relative luminance of the color.
        """
        r = color.red() / 255.0
        g = color.green() / 255.0
        b = color.blue() / 255.0

        def adjust(c):
            if c <= 0.03928:
                return c / 12.92
            return ((c + 0.055) / 1.055) ** 2.4

        r = adjust(r)
        g = adjust(g)
        b = adjust(b)

        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    @staticmethod
    def _tint_strength(
        accent: QColor, background: QColor, min_tint: float = 0.06, max_tint: float = 0.18
    ) -> float:
        """
        Calculate the tint strength based on the contrast between the accent and background colors.
        min_tint and max_tint define the range of tint strength and are empirically chosen.

        Args:
            accent(QColor): The accent color.
            background(QColor): The background color.
            min_tint(float): The minimum tint strength.
            max_tint(float): The maximum tint strength.

        Returns:
            float: The tint strength between 0 and 1.
        """
        l_accent = Colors.relative_luminance(accent)
        l_bg = Colors.relative_luminance(background)

        contrast = abs(l_accent - l_bg)

        # normalize contrast to a value between 0 and 1
        t = min(contrast / 0.9, 1.0)
        return min_tint + t * (max_tint - min_tint)

    @staticmethod
    def _blend(background: QColor, accent: QColor, t: float) -> QColor:
        """
        Blend two colors based on a tint strength t.
        """
        return QColor(
            round(background.red() + (accent.red() - background.red()) * t),
            round(background.green() + (accent.green() - background.green()) * t),
            round(background.blue() + (accent.blue() - background.blue()) * t),
            round(background.alpha() + (accent.alpha() - background.alpha()) * t),
        )

    @staticmethod
    def subtle_background_color(accent: QColor, background: QColor) -> QColor:
        """
        Generate a subtle, contrast-safe background color derived from an accent color.

        Args:
            accent(QColor): The accent color.
            background(QColor): The background color.
        Returns:
            QColor: The generated subtle background color.
        """
        if not accent.isValid() or not background.isValid():
            return background

        tint = Colors._tint_strength(accent, background)
        return Colors._blend(background, accent, tint)
