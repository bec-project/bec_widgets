import numpy as np
import pyqtgraph as pg
from pyqtgraph import mkColor


class Colors:
    @staticmethod
    def golden_ratio(num: int) -> list:
        """Calculate the golden ratio for a given number of angles.

        Args:
            num (int): Number of angles
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
    def golden_angle_color(colormap: str, num: int) -> list:
        """
        Extract num colors for from the specified colormap following golden angle distribution.

        Args:
            colormap (str): Name of the colormap
            num (int): Number of requested colors

        Returns:
            list: List of colors with length <num>

        Raises:
            ValueError: If the number of requested colors is greater than the number of colors in the colormap.
        """

        cmap = pg.colormap.get(colormap)
        cmap_colors = cmap.color
        if num > len(cmap_colors):
            raise ValueError(
                f"Number of colors requested ({num}) is greater than the number of colors in the colormap ({len(cmap_colors)})"
            )
        angles = Colors.golden_ratio(len(cmap_colors))
        color_selection = np.round(np.interp(angles, (-np.pi, np.pi), (0, len(cmap_colors))))
        colors = [
            mkColor(tuple((cmap_colors[int(ii)] * 255).astype(int))) for ii in color_selection[:num]
        ]
        return colors
