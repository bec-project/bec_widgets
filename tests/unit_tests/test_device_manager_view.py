"""Unit tests for the device manager view"""

from unittest import mock

import pytest
from qtpy import QtCore

from bec_widgets.applications.views.device_manager_view.device_manager_view import DeviceManagerView
from bec_widgets.widgets.control.device_manager.components import (
    DeviceTableView,
    DMConfigView,
    DMOphydTest,
    DocstringView,
)


@pytest.fixture
def dm_view(qtbot):
    """Fixture for DeviceManagerView."""
    widget = DeviceManagerView()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_device_manager_view_initialization(dm_view):
    """Test the basic layout of QtAds DockManager."""
    assert isinstance(dm_view.dock_manager.centralWidget().widget(), DeviceTableView)
    assert any(
        isinstance(dock.widget(), DMConfigView) for dock in dm_view.dock_manager.dockWidgets()
    )
    assert any(
        isinstance(dock.widget(), DMOphydTest) for dock in dm_view.dock_manager.dockWidgets()
    )
    assert any(
        isinstance(dock.widget(), DocstringView) for dock in dm_view.dock_manager.dockWidgets()
    )


def test_device_manager_view_toolbar_components(qtbot, dm_view):
    """Test that the toolbar components exist for the device_manager_view."""
    # Load from disk action
    for bundle_name in ["IO", "Table"]:
        assert bundle_name in dm_view.toolbar.bundles

    # Load File action
    assert dm_view.toolbar.components.exists("load")
    with mock.patch.object(dm_view, "_load_file_action") as mock_load_action:
        dm_view.toolbar.components._components["load"].action.action.triggered.emit()
        mock_load_action.assert_called_once()

    # Save file action
    assert dm_view.toolbar.components.exists("save_to_disk")
    with mock.patch.object(dm_view, "_save_to_disk_action") as mock_save_action:
        dm_view.toolbar.components._components["save_to_disk"].action.action.triggered.emit()
        mock_save_action.assert_called_once()

    # Load Redis action
    assert dm_view.toolbar.components.exists("load_redis")
    with mock.patch.object(dm_view, "_load_redis_action") as mock_load_redis:
        dm_view.toolbar.components._components["load_redis"].action.action.triggered.emit()
        mock_load_redis.assert_called_once()

    # Update Config
    assert dm_view.toolbar.components.exists("update_config_redis")
    with mock.patch.object(dm_view, "_update_redis_action") as mock_update_redis:
        dm_view.toolbar.components._components["update_config_redis"].action.action.triggered.emit()
        mock_update_redis.assert_called_once()

    # Reset Composed View
    assert dm_view.toolbar.components.exists("reset_composed")
    with mock.patch.object(dm_view, "_reset_composed_view") as mock_reset:
        dm_view.toolbar.components._components["reset_composed"].action.action.triggered.emit()
        mock_reset.assert_called_once()

    # Add Device
    assert dm_view.toolbar.components.exists("add_device")
    with mock.patch.object(dm_view, "_add_device_action") as mock_add_device:
        dm_view.toolbar.components._components["add_device"].action.action.triggered.emit()
        mock_add_device.assert_called_once()

    # Remove Device
    assert dm_view.toolbar.components.exists("remove_device")
    with mock.patch.object(dm_view, "_remove_device_action") as mock_remove_device:
        dm_view.toolbar.components._components["remove_device"].action.action.triggered.emit()
        mock_remove_device.assert_called_once()

    # Rerun Validation
    assert dm_view.toolbar.components.exists("rerun_validation")
    with mock.patch.object(dm_view, "_rerun_validation_action") as mock_rerun:
        dm_view.toolbar.components._components["rerun_validation"].action.action.triggered.emit()
        mock_rerun.assert_called_once()
