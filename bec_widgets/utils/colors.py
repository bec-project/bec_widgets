from typing import Literal

import numpy as np
import pyqtgraph as pg
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
