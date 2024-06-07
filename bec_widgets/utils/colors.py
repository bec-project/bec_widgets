import re
from typing import Literal

import numpy as np
import pyqtgraph as pg
from pydantic_core import PydanticCustomError
from qtpy.QtGui import QColor


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
        for ii in color_selection[:num]:
            color = cmap_colors[int(ii)]
            if format.upper() == "HEX":
                colors.append(QColor.fromRgbF(*color).name())
            elif format.upper() == "RGB":
                colors.append(tuple((np.array(color) * 255).astype(int)))
            elif format.upper() == "QCOLOR":
                colors.append(QColor.fromRgbF(*color))
            else:
                raise ValueError("Unsupported format. Please choose 'RGB', 'HEX', or 'QColor'.")
        return colors

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
