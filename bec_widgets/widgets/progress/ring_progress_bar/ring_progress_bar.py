import json
from typing import Literal

import pyqtgraph as pg
from bec_lib.logger import bec_logger
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from bec_widgets.utils import Colors
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty
from bec_widgets.utils.settings_dialog import SettingsDialog
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.progress.ring_progress_bar.ring import Ring
from bec_widgets.widgets.progress.ring_progress_bar.ring_progress_settings_cards import RingSettings

logger = bec_logger.logger


class RingProgressContainerWidget(QWidget):
    """
    A container widget for the Ring Progress Bar widget.
    It holds the rings and manages their layout and painting.
    """

    def __init__(self, parent: QWidget | None = None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.rings: list[Ring] = []
        self.gap = 20  # Gap between rings
        self.color_map: str = "turbo"
        self.setLayout(QHBoxLayout())
        self.initialize_bars()
        self.initialize_center_label()

    @property
    def num_bars(self) -> int:
        return len(self.rings)

    def initialize_bars(self):
        """
        Initialize the progress bars.
        """
        for _ in range(self.num_bars):
            self.add_ring()

        if self.color_map:
            self.set_colors_from_map(self.color_map)

    def add_ring(self, config: dict | None = None) -> Ring:
        """
        Add a new ring to the container.

        Args:
            config(dict | None): Optional configuration dictionary for the ring.

        Returns:
            Ring: The newly added ring object.
        """
        ring = Ring(parent=self)
        ring.setGeometry(self.rect())
        ring.gap = self.gap * len(self.rings)
        ring.set_value(0)
        self.rings.append(ring)
        if config:
            # We have to first get the link_colors property before loading the settings
            # While this is an ugly hack, we do not have control over the order of properties
            # being set when loading.
            ring.link_colors = config.pop("link_colors", True)
            ring.load_settings(config)
        if self.color_map:
            self.set_colors_from_map(self.color_map)
        ring.show()
        ring.raise_()
        self.update()
        return ring

    def remove_ring(self, index: int | None = None):
        """
        Remove a ring from the container.

        Args:
            index(int | None): Index of the ring to remove. If None, removes the last ring.
        """
        if self.num_bars == 0:
            return
        if index is None:
            index = self.num_bars - 1
        index = self._validate_index(index)
        ring = self.rings[index]
        ring.cleanup()
        ring.close()
        ring.deleteLater()
        self.rings.pop(index)
        # Update gaps for remaining rings
        for i, r in enumerate(self.rings):
            r.gap = self.gap * i
        self.update()

    def initialize_center_label(self):
        """
        Initialize the center label.
        """
        layout = self.layout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.center_label = QLabel("", parent=self)
        self.center_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.center_label)

    def _calculate_minimum_size(self):
        """
        Calculate the minimum size of the widget.
        """
        if not self.rings:
            return QSize(10, 10)
        ring_widths = self.get_ring_line_widths()
        total_width = sum(ring_widths) + self.gap * (self.num_bars - 1)
        diameter = max(total_width * 2, 50)

        return QSize(diameter, diameter)

    def get_ring_line_widths(self):
        """
        Get the line widths of the rings.
        """
        if not self.rings:
            return [10]
        ring_widths = [ring.config.line_width for ring in self.rings]
        return ring_widths

    def get_max_ring_size(self) -> int:
        """
        Get the size of the rings.
        """
        if not self.rings:
            return 10
        ring_widths = self.get_ring_line_widths()
        return max(ring_widths)

    def sizeHint(self):
        min_size = self._calculate_minimum_size()
        return min_size

    def resizeEvent(self, event):
        """
        Handle resize events to update ring geometries.
        """
        super().resizeEvent(event)
        for ring in self.rings:
            ring.setGeometry(self.rect())

    def set_colors_from_map(self, colormap, color_format: Literal["RGB", "HEX"] = "RGB"):
        """
        Set the colors for the progress bars from a colormap.

        Args:
            colormap(str): Name of the colormap.
            color_format(Literal["RGB","HEX"]): Format of the returned colors ('RGB', 'HEX').
        """
        if colormap not in pg.colormap.listMaps():
            raise ValueError(
                f"Colormap '{colormap}' not found in the current installation of pyqtgraph"
            )
        colors = Colors.golden_angle_color(colormap, self.num_bars, color_format)
        self.set_colors_directly(colors)
        self.color_map = colormap
        self.update()

    def set_colors_directly(
        self, colors: list[str | tuple] | str | tuple, bar_index: int | None = None
    ):
        """
        Set the colors for the progress bars directly.

        Args:
            colors(list[str | tuple] | str | tuple): Color(s) for the progress bars. If multiple progress bars are displayed, provide a list of colors for each progress bar.
            bar_index(int): Index of the progress bar to set the color for. If provided, only a single color can be set.
        """
        if bar_index is not None and isinstance(colors, (str, tuple)):
            bar_index = self._validate_index(bar_index)
            self.rings[bar_index].set_color(colors)
        else:
            if isinstance(colors, (str, tuple)):
                colors = [colors]
            colors = self._adjust_list_to_bars(colors)
            for ring, color in zip(self.rings, colors):
                ring.set_color(color)
        self.update()

    def _adjust_list_to_bars(self, items: list) -> list:
        """
        Utility method to adjust the list of parameters to match the number of progress bars.

        Args:
            items(list): List of parameters for the progress bars.

        Returns:
            list: List of parameters for the progress bars.
        """
        if items is None:
            raise ValueError(
                "Items cannot be None. Please provide a list for parameters for the progress bars."
            )
        if not isinstance(items, list):
            items = [items]
        if len(items) < self.num_bars:
            last_item = items[-1]
            items.extend([last_item] * (self.num_bars - len(items)))
        elif len(items) > self.num_bars:
            items = items[: self.num_bars]
        return items

    def _validate_index(self, index: int) -> int:
        """
        Check if the provided index is valid for the number of bars.

        Args:
            index(int): Index to check.
        Returns:
            int: Validated index.
        """
        try:
            self.rings[index]
        except IndexError:
            raise IndexError(f"Index {index} is out of range for {self.num_bars} rings.")
        return index

    def clear_all(self):
        """
        Clear all rings from the widget.
        """
        for ring in self.rings:
            ring.close()
            ring.deleteLater()
        self.rings = []
        self.update()


class RingProgressBar(BECWidget, QWidget):
    ICON_NAME = "track_changes"
    PLUGIN = True
    RPC = True

    USER_ACCESS = [
        *BECWidget.USER_ACCESS,
        "screenshot",
        "rings",
        "add_ring",
        "remove_ring",
        "set_gap",
        "set_center_label",
    ]

    def __init__(self, parent: QWidget | None = None, client=None, **kwargs):
        super().__init__(parent=parent, client=client, theme_update=True, **kwargs)

        self.setWindowTitle("Ring Progress Bar")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(self.layout)

        self.toolbar = ModularToolBar(self)
        self._init_toolbar()
        self.layout.addWidget(self.toolbar)

        # Placeholder for the actual ring progress bar widget
        self.ring_progress_bar = RingProgressContainerWidget(self)
        self.layout.addWidget(self.ring_progress_bar)

        self.settings_dialog = None

        self.toolbar.show_bundles(["rpb_settings"])

    def apply_theme(self, theme: str):
        super().apply_theme(theme)
        if self.ring_progress_bar.color_map:
            self.ring_progress_bar.set_colors_from_map(self.ring_progress_bar.color_map)

    def _init_toolbar(self):
        settings_action = MaterialIconAction(
            icon_name="settings",
            tooltip="Show Ring Progress Bar Settings",
            checkable=True,
            parent=self,
        )
        self.toolbar.add_action("rpb_settings", settings_action)
        settings_action.action.triggered.connect(self._open_settings_dialog)

    def _open_settings_dialog(self):
        """ "
        Open the settings dialog for the ring progress bar.
        """
        settings_action = self.toolbar.components.get_action("rpb_settings").action
        if self.settings_dialog is None or not self.settings_dialog.isVisible():
            settings = RingSettings(parent=self, target_widget=self, popup=True)
            self.settings_dialog = SettingsDialog(
                self,
                settings_widget=settings,
                window_title="Ring Progress Bar Settings",
                modal=False,
            )
            self.settings_dialog.resize(900, 500)
            self.settings_dialog.finished.connect(self._settings_dialog_closed)
            self.settings_dialog.show()

            settings_action.setChecked(True)
        else:
            # Dialog is already open, raise it
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            settings_action.setChecked(True)

    def _settings_dialog_closed(self):
        """
        Handle the settings dialog being closed.
        """
        settings_action = self.toolbar.components.get_action("rpb_settings").action
        settings_action.setChecked(False)
        self.settings_dialog = None

    #################################################
    ###### RPC User Access Methods ##################
    #################################################

    def add_ring(self, config: dict | None = None) -> Ring:
        """
        Add a new ring to the ring progress bar.
        Optionally, a configuration dictionary can be provided but the ring
        can also be configured later. The config dictionary must provide
        the qproperties of the Qt Ring object.

        Args:
            config(dict | None): Optional configuration dictionary for the ring.

        Returns:
            Ring: The newly added ring object.
        """
        return self.ring_progress_bar.add_ring(config=config)

    def remove_ring(self, index: int | None = None):
        """
        Remove a ring from the ring progress bar.
        Args:
            index(int | None): Index of the ring to remove. If None, removes the last ring.
        """
        if self.ring_progress_bar.num_bars == 0:
            return
        self.ring_progress_bar.remove_ring(index=index)

    def set_gap(self, value: int):
        """
        Set the gap between rings.

        Args:
            value(int): Gap value in pixels.
        """
        self.gap = value

    def set_center_label(self, text: str):
        """
        Set the center label text.

        Args:
            text(str): Text for the center label.
        """
        self.center_label = text

    @property
    def rings(self) -> list[Ring]:
        return self.ring_progress_bar.rings

    ###############################################
    ####### QProperties ###########################
    ###############################################

    @SafeProperty(int)
    def gap(self) -> int:
        return self.ring_progress_bar.gap

    @gap.setter
    def gap(self, value: int):
        self.ring_progress_bar.gap = value
        self.ring_progress_bar.update()

    @SafeProperty(str)
    def color_map(self) -> str:
        return self.ring_progress_bar.color_map or ""

    @color_map.setter
    def color_map(self, colormap: str):
        if colormap == "":
            self.ring_progress_bar.color_map = ""
            return
        if colormap not in pg.colormap.listMaps():
            return
        self.ring_progress_bar.set_colors_from_map(colormap)
        self.ring_progress_bar.color_map = colormap

    @SafeProperty(str)
    def center_label(self) -> str:
        return self.ring_progress_bar.center_label.text()

    @center_label.setter
    def center_label(self, text: str):
        self.ring_progress_bar.center_label.setText(text)

    @SafeProperty(str, designable=False, popup_error=True)
    def ring_json(self) -> str:
        """
        A JSON string property that serializes all ring pydantic configs.
        """
        raw_list = []
        for ring in self.rings:
            cfg_dict = ring.config.model_dump()
            raw_list.append(cfg_dict)
        return json.dumps(raw_list, indent=2)

    @ring_json.setter
    def ring_json(self, json_data: str):
        """
        Load rings from a JSON string and add them to the ring progress bar.
        """
        try:
            ring_configs = json.loads(json_data)
            self.ring_progress_bar.clear_all()
            for cfg_dict in ring_configs:
                self.add_ring(config=cfg_dict)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON: {e}")

    def cleanup(self):
        self.ring_progress_bar.clear_all()
        self.ring_progress_bar.close()
        self.ring_progress_bar.deleteLater()
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = RingProgressBar()
    widget.show()
    sys.exit(app.exec_())
