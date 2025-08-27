from qtpy import QtCore, QtWidgets

from bec_widgets.examples.device_manager_view.device_manager_view import DeviceManagerView
from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import AdvancedDockArea


class BECMainApp(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget as central area
        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setTabPosition(QtWidgets.QTabWidget.West)  # Tabs on the left side

        layout.addWidget(self.tabs)
        # Add DM
        self._add_device_manager_view()

        # Add Plot area
        self._add_ad_dockarea()

        # Adjust size of tab bar
        # TODO not yet properly working, tabs a spread across the full length, to be checked!
        tab_bar = self.tabs.tabBar()
        tab_bar.setFixedWidth(tab_bar.sizeHint().width())

    def _add_device_manager_view(self) -> None:
        self.device_manager_view = DeviceManagerView(parent=self)
        self.add_tab(self.device_manager_view, "Device Manager")

    def _add_ad_dockarea(self) -> None:
        self.advanced_dock_area = AdvancedDockArea(parent=self)
        self.add_tab(self.advanced_dock_area, "Plot Area")

    def add_tab(self, widget: QtWidgets.QWidget, title: str):
        """Add a custom QWidget as a tab."""
        tab_container = QtWidgets.QWidget()
        tab_layout = QtWidgets.QVBoxLayout(tab_container)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        tab_layout.addWidget(widget)
        self.tabs.addTab(tab_container, title)


if __name__ == "__main__":
    import sys

    from bec_lib.bec_yaml_loader import yaml_load
    from bec_qthemes import apply_theme

    app = QtWidgets.QApplication(sys.argv)
    apply_theme("light")
    win = BECMainApp()
    config_path = "/Users/appel_c/work_psi_awi/bec_workspace/csaxs_bec/csaxs_bec/device_configs/first_light.yaml"
    cfg = yaml_load(config_path)
    cfg.update({"device_will_fail": {"name": "device_will_fail", "some_param": 1}})
    win.device_manager_view.device_table_view.set_device_config(cfg)
    win.resize(1920, 1080)
    win.show()
    sys.exit(app.exec_())
