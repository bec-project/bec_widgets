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
    timeout: float = 10000,
    exists: bool = True,
):
    """
    Utility method to wait for the namespace to be created in the widget.

    Args:
        qtbot: The qtbot fixture.
        gui: The client_utils.BECGuiClient 'gui' object from the CLI.
        parent_widget: The widget that creates a new widget.
        object_name: The name of the widget that was created. Must appear as attribute in namespace of parent.
        widget_gui_id: The gui_id of the created widget.
        timeout: The timeout in milliseconds for the qtbot to wait for changes to appear.
        exists: If True, wait for the object to be created. If False, wait for the object to be removed.
    """
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
    # Number of top level widgets, should be 4
    top_level_widgets_count = 4
    assert len(gui._server_registry) == top_level_widgets_count
    # Number of widgets with parent_id == None, should be 2
    widgets = [
        widget for widget in gui._server_registry.values() if widget["config"]["parent_id"] is None
    ]
    assert len(widgets) == 2

    # Test all relevant widgets
    for object_name in gui.available_widgets.__dict__:
        # Skip private attributes
        if object_name.startswith("_"):
            continue
        # Skip VSCode widget as Code server is not available in the Docker image
        if object_name == "VSCodeEditor":
            continue

        #############################
        ######### Add widget ########
        #############################

        # Create widget the widget and wait for the widget to be registered in the ipython registry
        dock, widget = create_widget(
            qtbot, gui, dock_area, getattr(gui.available_widgets, object_name)
        )
        # Check that the widget is indeed registered on the server and the client
        assert gui._ipython_registry.get(widget._gui_id, None) is not None
        assert gui._server_registry.get(widget._gui_id, None) is not None
        # Check that namespace was updated
        assert hasattr(dock_area, dock.object_name)
        assert hasattr(dock, widget.object_name)

        # Check that no additional top level widgets were created without a parent_id
        widgets = [
            widget
            for widget in gui._server_registry.values()
            if widget["config"]["parent_id"] is None
        ]
        assert len(widgets) == 2

        #############################
        ####### Remove widget #######
        #############################

        # Now we remove the widget again
        dock_name = dock.object_name
        dock_id = dock._gui_id
        widget_id = widget._gui_id
        dock_area.delete(dock.object_name)
        # Wait for namespace to change
        wait_for_namespace_change(qtbot, gui, dock_area, dock_name, dock_id, exists=False)
        # Assert that dock and widget are removed from the ipython registry and the namespace
        assert hasattr(dock_area, dock_name) is False
        # Client registry
        assert gui._ipython_registry.get(dock_id, None) is None
        assert gui._ipython_registry.get(widget_id, None) is None
        # Server registry
        assert gui._server_registry.get(dock_id, None) is None
        assert gui._server_registry.get(widget_id, None) is None

        # Check that the number of top level widgets is still the same. As the cleanup is done by the
        # qt event loop, we need to wait for the qtbot to finish the cleanup
        qtbot.waitUntil(lambda: len(gui._server_registry) == top_level_widgets_count)
        # Number of widgets with parent_id == None, should be 2
        widgets = [
            widget
            for widget in gui._server_registry.values()
            if widget["config"]["parent_id"] is None
        ]
        assert len(widgets) == 2
