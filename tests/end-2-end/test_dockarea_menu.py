import pytest
from qtpy.QtCore import Qt

from bec_widgets.widgets.containers.dock.dock_area import BECDockArea


@pytest.fixture
def dock_area(qtbot):

    dock = BECDockArea()
    qtbot.addWidget(dock)
    qtbot.waitExposed(dock)
    dock.show()
    qtbot.wait(500)

    yield dock

    dock.remove()
    dock.deleteLater()


def test_sequence_of_add_and_remove(qtbot, dock_area):

    add_sc_action = dock_area.toolbar.widgets["menu_devices"].widgets["scan_control"]
    add_pb_action = dock_area.toolbar.widgets["menu_devices"].widgets["positioner_box"]

    add_pb_action.trigger()
    qtbot.wait(1000)

    add_sc_action.trigger()
    qtbot.wait(1000)

    assert all(w in dock_area.panels for w in ["positioner_box_0", "scan_control_0"])

    dock_area.panels["positioner_box_0"].remove()
    qtbot.wait(1000)

    dock_area.panels["scan_control_0"].remove()
    qtbot.wait(1000)

    add_pb_action.trigger()
    qtbot.wait(1000)
