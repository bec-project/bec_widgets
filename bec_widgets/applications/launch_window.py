from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

from bec_lib.logger import bec_logger
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QPainter, QPainterPath, QPixmap
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)

import bec_widgets
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.plugin_utils import get_plugin_auto_updates
from bec_widgets.utils.round_frame import RoundedFrame
from bec_widgets.utils.toolbar import ModularToolBar
from bec_widgets.utils.ui_loader import UILoader
from bec_widgets.widgets.containers.auto_update.auto_updates import AutoUpdates
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow, UILaunchWindow
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtCore import QObject

logger = bec_logger.logger
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class LaunchTile(RoundedFrame):
    open_signal = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        icon_path: str | None = None,
        top_label: str | None = None,
        main_label: str | None = None,
        description: str | None = None,
        show_selector: bool = False,
    ):
        super().__init__(parent=parent, orientation="vertical")

        self.icon_label = QLabel(parent=self)
        self.icon_label.setFixedSize(100, 100)
        self.icon_label.setScaledContents(True)
        pixmap = QPixmap(icon_path)
        if not pixmap.isNull():
            size = 100
            circular_pixmap = QPixmap(size, size)
            circular_pixmap.fill(Qt.transparent)

            painter = QPainter(circular_pixmap)
            painter.setRenderHints(QPainter.Antialiasing, True)
            path = QPainterPath()
            path.addEllipse(0, 0, size, size)
            painter.setClipPath(path)
            pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()

            self.icon_label.setPixmap(circular_pixmap)
        self.layout.addWidget(self.icon_label, alignment=Qt.AlignCenter)

        # Top label
        self.top_label = QLabel(top_label.upper())
        font_top = self.top_label.font()
        font_top.setPointSize(10)
        self.top_label.setFont(font_top)
        self.layout.addWidget(self.top_label, alignment=Qt.AlignCenter)

        # Main label
        self.main_label = QLabel(main_label)
        font_main = self.main_label.font()
        font_main.setPointSize(14)
        font_main.setBold(True)
        self.main_label.setFont(font_main)
        self.main_label.setWordWrap(True)
        self.main_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.main_label)

        self.spacer_top = QSpacerItem(0, 10, QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.layout.addItem(self.spacer_top)

        # Description
        self.description_label = QLabel(description)
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.description_label)

        # Selector
        if show_selector:
            self.selector = QComboBox(self)
            self.layout.addWidget(self.selector)
        else:
            self.selector = None

        self.spacer_bottom = QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.layout.addItem(self.spacer_bottom)

        # Action button
        self.action_button = QPushButton("Open")
        self.action_button.setStyleSheet(
            """
        QPushButton {
            background-color: #007AFF;
            border: none;
            padding: 8px 16px;
            color: white;
            border-radius: 6px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #005BB5;
        }
        """
        )
        self.layout.addWidget(self.action_button, alignment=Qt.AlignCenter)


class LaunchWindow(BECMainWindow):
    RPC = True
    TILE_SIZE = (250, 300)
    USER_ACCESS = ["show_launcher", "hide_launcher"]

    def __init__(
        self, parent=None, gui_id: str = None, window_title="BEC Launcher", *args, **kwargs
    ):
        super().__init__(parent=parent, gui_id=gui_id, window_title=window_title, **kwargs)

        self.app = QApplication.instance()

        # Toolbar
        self.dark_mode_button = DarkModeButton(parent=self, toolbar=True)
        self.toolbar = ModularToolBar(parent=self)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)
        self.spacer = QWidget()
        self.spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar.addWidget(self.spacer)
        self.toolbar.addWidget(self.dark_mode_button)

        # Main Widget
        self.central_widget = QWidget(self)
        self.central_widget.layout = QHBoxLayout(self.central_widget)
        self.setCentralWidget(self.central_widget)

        self.tile_dock_area = LaunchTile(
            icon_path=os.path.join(MODULE_PATH, "assets", "app_icons", "bec_widgets_icon.png"),
            top_label="Get started",
            main_label="BEC Dock Area",
            description="Highly flexible and customizable dock area application with modular widgets.",
        )
        self.tile_dock_area.setFixedSize(*self.TILE_SIZE)

        self.tile_auto_update = LaunchTile(
            icon_path=os.path.join(MODULE_PATH, "assets", "app_icons", "auto_update.png"),
            top_label="Get automated",
            main_label="BEC Auto Update Dock Area",
            description="Dock area with auto update functionality for BEC widgets plotting.",
            show_selector=True,
        )
        self.tile_auto_update.setFixedSize(*self.TILE_SIZE)

        self.tile_ui_file = LaunchTile(
            icon_path=os.path.join(MODULE_PATH, "assets", "app_icons", "ui_loader_tile.png"),
            top_label="Get customized",
            main_label="Launch Custom UI File",
            description="GUI application with custom UI file.",
        )
        self.tile_ui_file.setFixedSize(*self.TILE_SIZE)

        # Add tiles to the main layout
        self.central_widget.layout.addWidget(self.tile_dock_area)
        self.central_widget.layout.addWidget(self.tile_auto_update)
        self.central_widget.layout.addWidget(self.tile_ui_file)

        # hacky solution no time to waste
        self.tiles = [self.tile_dock_area, self.tile_auto_update, self.tile_ui_file]

        # Connect signals
        self.tile_dock_area.action_button.clicked.connect(lambda: self.launch("dock_area"))
        self.tile_auto_update.action_button.clicked.connect(self._open_auto_update)
        self.tile_ui_file.action_button.clicked.connect(self._open_custom_ui_file)
        self._update_theme()

        # Auto updates
        self.available_auto_updates: dict[str, type[AutoUpdates]] = (
            self._update_available_auto_updates()
        )
        if self.tile_auto_update.selector is not None:
            self.tile_auto_update.selector.addItems(
                list(self.available_auto_updates.keys()) + ["Default"]
            )

    def launch(
        self,
        launch_script: str,
        name: str | None = None,
        geometry: tuple[int, int, int, int] | None = None,
        **kwargs,
    ) -> QWidget:
        """Launch the specified script. If the launch script creates a QWidget, it will be
        embedded in a BECMainWindow. If the launch script creates a BECMainWindow, it will be shown
        as a separate window.

        Args:
            launch_script(str): The name of the script to be launched.
            name(str): The name of the dock area.
            geometry(tuple): The geometry parameters to be passed to the dock area.
        Returns:
            QWidget: The created dock area.
        """
        from bec_widgets.applications import bw_launch

        with RPCRegister.delayed_broadcast() as rpc_register:
            existing_dock_areas = rpc_register.get_names_of_rpc_by_class_type(BECDockArea)
            if name is not None:
                if name in existing_dock_areas:
                    raise ValueError(
                        f"Name {name} must be unique for dock areas, but already exists: {existing_dock_areas}."
                    )
            else:
                name = "dock_area"
                name = WidgetContainerUtils.generate_unique_name(name, existing_dock_areas)

            if launch_script is None:
                launch_script = "dock_area"
            if not isinstance(launch_script, str):
                raise ValueError(f"Launch script must be a string, but got {type(launch_script)}.")

            if launch_script == "custom_ui_file":
                ui_file = kwargs.pop("ui_file", None)
                return self._launch_custom_ui_file(ui_file)

            if launch_script == "auto_update":
                auto_update = kwargs.pop("auto_update", None)
                return self._launch_auto_update(auto_update)

            launch = getattr(bw_launch, launch_script, None)
            if launch is None:
                raise ValueError(f"Launch script {launch_script} not found.")

            result_widget = launch(name)
            result_widget.resize(result_widget.minimumSizeHint())
            # TODO Should we simply use the specified name as title here?
            result_widget.window().setWindowTitle(f"BEC - {name}")
            logger.info(f"Created new dock area: {name}")

            if geometry is not None:
                result_widget.setGeometry(*geometry)
            if isinstance(result_widget, BECMainWindow):
                result_widget.show()
            else:
                window = BECMainWindow()
                window.setCentralWidget(result_widget)
                window.show()
            return result_widget

    def _launch_custom_ui_file(self, ui_file: str | None) -> BECMainWindow:
        # Load the custom UI file
        if ui_file is None:
            raise ValueError("UI file must be provided for custom UI file launch.")
        filename = os.path.basename(ui_file).split(".")[0]

        tree = ET.parse(ui_file)
        root = tree.getroot()
        # Check if the top-level widget is a QMainWindow
        widget = root.find("widget")
        if widget is None:
            raise ValueError("No widget found in the UI file.")

        if widget.attrib.get("class") == "QMainWindow":
            raise ValueError(
                "Loading a QMainWindow from a UI file is currently not supported. "
                "If you need this, please contact the BEC team or create a ticket on gitlab.psi.ch/bec/bec_widgets."
            )

        window = UILaunchWindow(object_name=filename)
        QApplication.processEvents()
        result_widget = UILoader(window).loader(ui_file)
        window.setCentralWidget(result_widget)
        window.setWindowTitle(f"BEC - {window.object_name}")
        window.show()
        logger.info(f"Object name of new instance: {result_widget.objectName()}, {window.gui_id}")
        return window

    def _launch_auto_update(self, auto_update: str) -> AutoUpdates:
        if auto_update in self.available_auto_updates:
            auto_update_cls = self.available_auto_updates[auto_update]
            window = auto_update_cls()
        else:

            auto_update = "auto_updates"
            window = AutoUpdates()

        window.resize(window.minimumSizeHint())
        QApplication.processEvents()
        window.setWindowTitle(f"BEC - {window.objectName()}")
        window.show()
        return window

    def apply_theme(self, theme: str):
        """
        Change the theme of the application.
        """
        for tile in self.tiles:
            tile.apply_theme(theme)

        super().apply_theme(theme)

    def _open_auto_update(self):
        """
        Open the auto update window.
        """
        if self.tile_auto_update.selector is None:
            auto_update = None
        else:
            auto_update = self.tile_auto_update.selector.currentText()
            if auto_update == "Default":
                auto_update = None
        self.launch("auto_update", auto_update=auto_update)

    @SafeSlot(popup_error=True)
    def _open_custom_ui_file(self):
        """
        Open a file dialog to select a custom UI file and launch it.
        """
        ui_file, _ = QFileDialog.getOpenFileName(
            self, "Select UI File", "", "UI Files (*.ui);;All Files (*)"
        )
        self.launch("custom_ui_file", ui_file=ui_file)

    @staticmethod
    def _update_available_auto_updates() -> dict[str, type[AutoUpdates]]:
        """
        Load all available auto updates from the plugin repository.
        """
        try:
            auto_updates = get_plugin_auto_updates()
            logger.info(f"Available auto updates: {auto_updates.keys()}")
        except Exception as exc:
            logger.error(f"Failed to load auto updates: {exc}")
            return {}
        return auto_updates

    def show_launcher(self):
        """
        Show the launcher window.
        """
        self.show()

    def hide_launcher(self):
        """
        Hide the launcher window.
        """
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.setFixedSize(self.size())


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    launcher = LaunchWindow()
    launcher.show()
    sys.exit(app.exec())
