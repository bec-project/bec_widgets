from typing import List

import PySide6QtAds as QtAds
import yaml
from bec_qthemes import material_icon
from PySide6QtAds import CDockManager, CDockWidget
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import (
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedLayout,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import AdvancedDockArea
from bec_widgets.widgets.control.device_manager.components.device_table_view import DeviceTableView
from bec_widgets.widgets.control.device_manager.components.dm_config_view import DMConfigView
from bec_widgets.widgets.control.device_manager.components.dm_ophyd_test import (
    DeviceManagerOphydTest,
)
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
from bec_widgets.widgets.editors.web_console.web_console import WebConsole
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECStatusBox
from bec_widgets.widgets.utility.ide_explorer.ide_explorer import IDEExplorer


def set_splitter_weights(splitter: QSplitter, weights: List[float]) -> None:
    """
    Apply initial sizes to a splitter using weight ratios, e.g. [1,3,2,1].
    Works for horizontal or vertical splitters and sets matching stretch factors.
    """

    def apply():
        n = splitter.count()
        if n == 0:
            return
        w = list(weights[:n]) + [1] * max(0, n - len(weights))
        w = [max(0.0, float(x)) for x in w]
        tot_w = sum(w)
        if tot_w <= 0:
            w = [1.0] * n
            tot_w = float(n)
        total_px = (
            splitter.width() if splitter.orientation() == Qt.Horizontal else splitter.height()
        )
        if total_px < 2:
            QTimer.singleShot(0, apply)
            return
        sizes = [max(1, int(total_px * (wi / tot_w))) for wi in w]
        diff = total_px - sum(sizes)
        if diff != 0:
            idx = max(range(n), key=lambda i: w[i])
            sizes[idx] = max(1, sizes[idx] + diff)
        splitter.setSizes(sizes)
        for i, wi in enumerate(w):
            splitter.setStretchFactor(i, max(1, int(round(wi * 100))))

    QTimer.singleShot(0, apply)


class DeviceManagerView(BECWidget, QWidget):

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        # Top-level layout hosting a toolbar and the dock manager
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)
        self.dock_manager = CDockManager(self)
        self._root_layout.addWidget(self.dock_manager)

        # Initialize the widgets
        self.explorer = IDEExplorer(self)  # TODO will be replaced by explorer widget
        self.device_table_view = DeviceTableView(self)
        # Placeholder
        self.dm_config_view = DMConfigView(self)

        # Placeholder for ophyd test
        WebConsole.startup_cmd = "ipython"
        self.ophyd_test = DeviceManagerOphydTest(self)
        self.ophyd_test_dock = QtAds.CDockWidget("Ophyd Test", self)
        self.ophyd_test_dock.setWidget(self.ophyd_test)

        # Create the dock widgets
        self.explorer_dock = QtAds.CDockWidget("Explorer", self)
        self.explorer_dock.setWidget(self.explorer)

        self.device_table_view_dock = QtAds.CDockWidget("Device Table", self)
        self.device_table_view_dock.setWidget(self.device_table_view)

        # Device Table will be central widget
        self.dock_manager.setCentralWidget(self.device_table_view_dock)

        self.dm_config_view_dock = QtAds.CDockWidget("YAML Editor", self)
        self.dm_config_view_dock.setWidget(self.dm_config_view)

        # Add the dock widgets to the dock manager
        self.dock_manager.addDockWidget(QtAds.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock)
        monaco_yaml_area = self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.RightDockWidgetArea, self.dm_config_view_dock
        )
        self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.BottomDockWidgetArea, self.ophyd_test_dock, monaco_yaml_area
        )

        for dock in self.dock_manager.dockWidgets():
            # dock.setFeature(CDockWidget.DockWidgetDeleteOnClose, True)#TODO implement according to MonacoDock or AdvancedDockArea
            # dock.setFeature(CDockWidget.CustomCloseHandling, True) #TODO same
            dock.setFeature(CDockWidget.DockWidgetClosable, False)
            dock.setFeature(CDockWidget.DockWidgetFloatable, False)
            dock.setFeature(CDockWidget.DockWidgetMovable, False)

        # Fetch all dock areas of the dock widgets (on our case always one dock area)
        for dock in self.dock_manager.dockWidgets():
            area = dock.dockAreaWidget()
            area.titleBar().setVisible(False)

        # Apply stretch after the layout is done
        self.set_default_view([2, 5, 3], [5, 5])

        # Connect slots
        self.device_table_view.selected_device.connect(self.dm_config_view.on_select_config)

    ####### Default view has to be done with setting up splitters ########
    def set_default_view(self, horizontal_weights: list, vertical_weights: list):
        """Apply initial weights to every horizontal and vertical splitter.

        Examples:
            horizontal_weights = [1, 3, 2, 1]
            vertical_weights   = [3, 7]  # top:bottom = 30:70
        """
        splitters_h = []
        splitters_v = []
        for splitter in self.findChildren(QSplitter):
            if splitter.orientation() == Qt.Horizontal:
                splitters_h.append(splitter)
            elif splitter.orientation() == Qt.Vertical:
                splitters_v.append(splitter)

        def apply_all():
            for s in splitters_h:
                set_splitter_weights(s, horizontal_weights)
            for s in splitters_v:
                set_splitter_weights(s, vertical_weights)

        QTimer.singleShot(0, apply_all)

    def set_stretch(self, *, horizontal=None, vertical=None):
        """Update splitter weights and re-apply to all splitters.

        Accepts either a list/tuple of weights (e.g., [1,3,2,1]) or a role dict
        for convenience: horizontal roles = {"left","center","right"},
        vertical roles = {"top","bottom"}.
        """

        def _coerce_h(x):
            if x is None:
                return None
            if isinstance(x, (list, tuple)):
                return list(map(float, x))
            if isinstance(x, dict):
                return [
                    float(x.get("left", 1)),
                    float(x.get("center", x.get("middle", 1))),
                    float(x.get("right", 1)),
                ]
            return None

        def _coerce_v(x):
            if x is None:
                return None
            if isinstance(x, (list, tuple)):
                return list(map(float, x))
            if isinstance(x, dict):
                return [float(x.get("top", 1)), float(x.get("bottom", 1))]
            return None

        h = _coerce_h(horizontal)
        v = _coerce_v(vertical)
        if h is None:
            h = [1, 1, 1]
        if v is None:
            v = [1, 1]
        self.set_default_view(h, v)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    device_manager_view = DeviceManagerView()
    config = device_manager_view.client.device_manager._get_redis_device_config()
    device_manager_view.device_table_view.set_device_config(config)
    device_manager_view.show()
    device_manager_view.setWindowTitle("Device Manager View")
    device_manager_view.resize(1200, 800)
    # developer_view.set_stretch(horizontal=[1, 3, 2], vertical=[5, 5]) #can be set during runtime
    sys.exit(app.exec_())
