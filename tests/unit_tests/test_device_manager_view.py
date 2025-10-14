"""Unit tests for the device manager view"""

# pylint: disable=protected-access,redefined-outer-name

from unittest import mock

import pytest
from qtpy import QtCore
from qtpy.QtWidgets import QFileDialog, QMessageBox

from bec_widgets.applications.views.device_manager_view.device_manager_view import (
    ConfigChoiceDialog,
    DeviceManagerView,
)
from bec_widgets.utils.help_inspector.help_inspector import HelpInspector
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


@pytest.fixture
def config_choice_dialog(qtbot, dm_view):
    """Fixture for ConfigChoiceDialog."""
    dialog = ConfigChoiceDialog(dm_view)
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog)
    yield dialog


def test_device_manager_view_config_choice_dialog(qtbot, dm_view, config_choice_dialog):
    """Test the configuration choice dialog."""
    assert config_choice_dialog is not None
    assert config_choice_dialog.parent() == dm_view

    # Test dialog components
    with (
        mock.patch.object(config_choice_dialog, "accept") as mock_accept,
        mock.patch.object(config_choice_dialog, "reject") as mock_reject,
    ):

        # Replace
        qtbot.mouseClick(config_choice_dialog.replace_btn, QtCore.Qt.LeftButton)
        mock_accept.assert_called_once()
        mock_reject.assert_not_called()
        mock_accept.reset_mock()
        assert config_choice_dialog.result() == config_choice_dialog.REPLACE
        # Add
        qtbot.mouseClick(config_choice_dialog.add_btn, QtCore.Qt.LeftButton)
        mock_accept.assert_called_once()
        mock_reject.assert_not_called()
        mock_accept.reset_mock()
        assert config_choice_dialog.result() == config_choice_dialog.ADD
        # Cancel
        qtbot.mouseClick(config_choice_dialog.cancel_btn, QtCore.Qt.LeftButton)
        mock_accept.assert_not_called()
        mock_reject.assert_called_once()
        assert config_choice_dialog.result() == config_choice_dialog.CANCEL


class TestDeviceManagerViewInitialization:
    """Test class for DeviceManagerView initialization and basic components."""

    def test_dock_manager_initialization(self, dm_view):
        """Test that the QtAds DockManager is properly initialized."""
        assert dm_view.dock_manager is not None
        assert dm_view.dock_manager.centralWidget() is not None

    def test_central_widget_is_device_table_view(self, dm_view):
        """Test that the central widget is DeviceTableView."""
        central_widget = dm_view.dock_manager.centralWidget().widget()
        assert isinstance(central_widget, DeviceTableView)
        assert central_widget is dm_view.device_table_view

    def test_dock_widgets_exist(self, dm_view):
        """Test that all required dock widgets are created."""
        dock_widgets = dm_view.dock_manager.dockWidgets()

        # Check that we have the expected number of dock widgets
        assert len(dock_widgets) >= 4

        # Check for specific widget types
        widget_types = [dock.widget().__class__ for dock in dock_widgets]

        assert DMConfigView in widget_types
        assert DMOphydTest in widget_types
        assert DocstringView in widget_types

    def test_toolbar_initialization(self, dm_view):
        """Test that the toolbar is properly initialized with expected bundles."""
        assert dm_view.toolbar is not None
        assert "IO" in dm_view.toolbar.bundles
        assert "Table" in dm_view.toolbar.bundles

    def test_toolbar_components_exist(self, dm_view):
        """Test that all expected toolbar components exist."""
        expected_components = [
            "load",
            "save_to_disk",
            "load_redis",
            "update_config_redis",
            "reset_composed",
            "add_device",
            "remove_device",
            "rerun_validation",
        ]

        for component in expected_components:
            assert dm_view.toolbar.components.exists(component)

    def test_signal_connections(self, dm_view):
        """Test that signals are properly connected between components."""
        # Test that device_table_view signals are connected
        assert dm_view.device_table_view.selected_devices is not None
        assert dm_view.device_table_view.device_configs_changed is not None

        # Test that ophyd_test_view signals are connected
        assert dm_view.ophyd_test_view.device_validated is not None


class TestDeviceManagerViewIOBundle:
    """Test class for DeviceManagerView IO bundle actions."""

    def test_io_bundle_exists(self, dm_view):
        """Test that IO bundle exists and contains expected actions."""
        assert "IO" in dm_view.toolbar.bundles
        io_actions = ["load", "save_to_disk", "load_redis", "update_config_redis"]
        for action in io_actions:
            assert dm_view.toolbar.components.exists(action)

    def test_load_file_action_triggered(self, tmp_path, dm_view):
        """Test load file action trigger mechanism."""

        with (
            mock.patch.object(dm_view, "_get_file_path", return_value=tmp_path),
            mock.patch(
                "bec_widgets.applications.views.device_manager_view.device_manager_view.yaml_load"
            ) as mock_yaml_load,
            mock.patch.object(dm_view, "_open_config_choice_dialog") as mock_open_dialog,
        ):
            mock_yaml_data = {"device1": {"param1": "value1"}}
            mock_yaml_load.return_value = mock_yaml_data

            # Setup dialog mock
            dm_view.toolbar.components._components["load"].action.action.triggered.emit()
            mock_yaml_load.assert_called_once_with(tmp_path)
            mock_open_dialog.assert_called_once_with([{"name": "device1", "param1": "value1"}])

    def test_save_config_to_file(self, tmp_path, dm_view):
        """Test saving config to file."""
        yaml_path = tmp_path / "test_save.yaml"
        mock_config = [{"name": "device1", "param1": "value1"}]
        with (
            mock.patch.object(dm_view, "_get_file_path", return_value=tmp_path),
            mock.patch.object(dm_view, "_get_recovery_config_path", return_value=tmp_path),
            mock.patch.object(dm_view, "_get_file_path", return_value=yaml_path),
            mock.patch.object(
                dm_view.device_table_view, "get_device_config", return_value=mock_config
            ),
        ):
            dm_view.toolbar.components._components["save_to_disk"].action.action.triggered.emit()
            assert yaml_path.exists()


class TestDeviceManagerViewTableBundle:
    """Test class for DeviceManagerView Table bundle actions."""

    def test_table_bundle_exists(self, dm_view):
        """Test that Table bundle exists and contains expected actions."""
        assert "Table" in dm_view.toolbar.bundles
        table_actions = ["reset_composed", "add_device", "remove_device", "rerun_validation"]
        for action in table_actions:
            assert dm_view.toolbar.components.exists(action)

    @mock.patch(
        "bec_widgets.applications.views.device_manager_view.device_manager_view._yes_no_question"
    )
    def test_reset_composed_view(self, mock_question, dm_view):
        """Test reset composed view when user confirms."""
        with mock.patch.object(dm_view.device_table_view, "clear_device_configs") as mock_clear:
            mock_question.return_value = QMessageBox.StandardButton.Yes
            dm_view.toolbar.components._components["reset_composed"].action.action.triggered.emit()
            mock_clear.assert_called_once()
            mock_clear.reset_mock()
            mock_question.return_value = QMessageBox.StandardButton.No
            dm_view.toolbar.components._components["reset_composed"].action.action.triggered.emit()
            mock_clear.assert_not_called()

    def test_add_device_action_connected(self, dm_view):
        """Test add device action opens dialog correctly."""
        with mock.patch.object(dm_view, "_add_device_action") as mock_add:
            dm_view.toolbar.components._components["add_device"].action.action.triggered.emit()
            mock_add.assert_called_once()

    def test_remove_device_action(self, dm_view):
        """Test remove device action."""
        with mock.patch.object(dm_view.device_table_view, "remove_selected_rows") as mock_remove:
            dm_view.toolbar.components._components["remove_device"].action.action.triggered.emit()
            mock_remove.assert_called_once()

    def test_rerun_device_validation(self, dm_view):
        """Test rerun device validation action."""
        cfgs = [{"name": "device1", "param1": "value1"}]
        with (
            mock.patch.object(dm_view.ophyd_test_view, "change_device_configs") as mock_change,
            mock.patch.object(
                dm_view.device_table_view.table, "selected_configs", return_value=cfgs
            ),
        ):
            dm_view.toolbar.components._components[
                "rerun_validation"
            ].action.action.triggered.emit()
            mock_change.assert_called_once_with(cfgs, True, True)
