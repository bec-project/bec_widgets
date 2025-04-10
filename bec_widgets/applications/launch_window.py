from __future__ import annotations

import os

from bec_lib.logger import bec_logger
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QPainter, QPainterPath, QPixmap
from qtpy.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

import bec_widgets
from bec_widgets.cli.rpc.rpc_register import RPCRegister
from bec_widgets.utils.container_utils import WidgetContainerUtils
from bec_widgets.utils.round_frame import RoundedFrame
from bec_widgets.utils.toolbar import ModularToolBar
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea
from bec_widgets.widgets.containers.main_window.main_window import BECMainWindow
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

logger = bec_logger.logger
MODULE_PATH = os.path.dirname(bec_widgets.__file__)


class LaunchTile(RoundedFrame):
    open_signal = Signal()

    def __init__(
        self, parent=None, icon_path=None, top_label=None, main_label=None, description=None
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

        # Description
        self.description_label = QLabel(description)
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.description_label)

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

        # self.apply_theme("dark")


class LaunchWindow(BECMainWindow):
    RPC = True

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
        self.tile_dock_area.setFixedSize(250, 300)

        self.tile_auto_update = LaunchTile(
            icon_path=os.path.join(MODULE_PATH, "assets", "app_icons", "auto_update.png"),
            top_label="Get automated",
            main_label="BEC Auto Update Dock Area",
            description="Dock area with auto update functionality for BEC widgets plotting.",
        )
        self.tile_auto_update.setFixedSize(250, 300)

        # Add tiles to the main layout
        self.central_widget.layout.addWidget(self.tile_dock_area)
        self.central_widget.layout.addWidget(self.tile_auto_update)
        # hacky solution no time to waste
        self.tiles = [self.tile_dock_area, self.tile_auto_update]

        # Connect signals
        self.tile_dock_area.action_button.clicked.connect(lambda: self.launch("dock_area"))
        self.tile_auto_update.action_button.clicked.connect(
            lambda: self.launch("auto_update_dock_area", "auto_updates")
        )
        self._update_theme()

    def launch(
        self,
        launch_script: str,
        name: str | None = None,
        geometry: tuple[int, int, int, int] | None = None,
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
            launch = getattr(bw_launch, launch_script, None)
            if launch is None:
                raise ValueError(f"Launch script {launch_script} not found.")

            result_widget = launch(name)
            result_widget.resize(result_widget.minimumSizeHint())
            # TODO Should we simply use the specified name as title here?
            result_widget.window().setWindowTitle(f"BEC - {name}")
            logger.info(f"Created new dock area: {name}")
            logger.info(f"Existing dock areas: {geometry}")
            if geometry is not None:
                result_widget.setGeometry(*geometry)
            if isinstance(result_widget, BECMainWindow):
                result_widget.show()
            else:
                window = BECMainWindow()
                window.setCentralWidget(result_widget)
                window.show()
            return result_widget

    def apply_theme(self, theme: str):
        """
        Change the theme of the application.
        """
        for tile in self.tiles:
            tile.apply_theme(theme)

        super().apply_theme(theme)

    def show_launcher(self):
        self.show()

    def hide_launcher(self):
        self.hide()

    def cleanup(self):
        super().close()

    def showEvent(self, event):
        super().showEvent(event)
        self.setFixedSize(self.size())


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    launcher = LaunchWindow()
    launcher.show()
    sys.exit(app.exec())
