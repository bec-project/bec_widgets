from typing import TYPE_CHECKING

import pytest

from bec_widgets.cli.rpc.rpc_base import RPCBase, RPCReference

# pylint: disable=protected-access
# pylint: disable=used-before-assignment


def wait_for_namespace_change(
    qtbot,
    gui: RPCBase,
    parent_widget: RPCBase | RPCReference,
    object_name: str,
    widget_gui_id: str,
    timeout: int = 10000,
    exists: bool = True,
):
    """Utility method to wait for the namespace to be created in the widget."""
    # GUI object is not registered in the registry (yet)
    if parent_widget is gui:

        def check_reference_registered():
            # Check that the widget is in ipython registry
            obj = gui._ipython_registry.get(widget_gui_id, None)
            if obj is None:
                if not exists:
                    return True
                return False
            # _rpc_references do not exist on BECGuiClient class somehow..

    else:

        def check_reference_registered():
            obj = gui._ipython_registry.get(widget_gui_id, None)
            if obj is None:
                if not exists:
                    return True
                return False
            ref = parent_widget._rpc_references.get(widget_gui_id, None)
            if exists:
                return ref is not None
            return ref is None

    try:
        qtbot.waitUntil(check_reference_registered, timeout=timeout)
    except Exception as e:
        raise RuntimeError(
            f"Timeout waiting for {parent_widget.object_name}.{object_name} to be created."
        ) from e


def create_widget(
    qtbot, gui: RPCBase, dock_area: RPCReference, widget_cls_name: str
) -> tuple[RPCReference, RPCReference, RPCReference]:
    """Utility method to create a widget and wait for the namespaces to be created."""
    dock = dock_area.new(widget=widget_cls_name)
    wait_for_namespace_change(qtbot, gui, dock_area, dock.object_name, dock._gui_id)
    widget = dock.element_list[-1]
    wait_for_namespace_change(qtbot, gui, dock, widget.object_name, widget._gui_id)
    return dock, widget


@pytest.mark.timeout(100)
def test_available_widgets(qtbot, connected_client_gui_obj):
    """This test checks that all widgets that are available via gui.available_widgets can be created and removed."""
    gui = connected_client_gui_obj
    dock_area = gui.bec
    for object_name in gui.available_widgets.__dict__:
        # Skip private attributes
        if object_name.startswith("_"):
            continue
        # Skip VSCode widget as Code server is not available in the Docker image
        if object_name == "VSCodeEditor":
            continue
        # Create widget the widget
        dock, widget = create_widget(
            qtbot, gui, dock_area, getattr(gui.available_widgets, object_name)
        )
        # The create_widget method already waits for the widget to be created
        # and added to the ipython registry. We can here assert if the dock_area
        # has the dock and the widget
        assert gui._ipython_registry.get(widget._gui_id, None) is not None
        assert hasattr(dock_area, dock.object_name)
        assert hasattr(dock, widget.object_name)
        # Now we remove the widget again
        dock_area.delete(dock.object_name)
