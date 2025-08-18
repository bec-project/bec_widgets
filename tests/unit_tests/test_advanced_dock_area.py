# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import os
import tempfile
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from qtpy.QtCore import QSettings
from qtpy.QtWidgets import QDialog, QMessageBox

from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import (
    AdvancedDockArea,
    DockSettingsDialog,
    SaveProfileDialog,
    _profile_path,
    _profiles_dir,
    is_profile_readonly,
    list_profiles,
    open_settings,
    read_manifest,
    set_profile_readonly,
    write_manifest,
)

from .client_mocks import mocked_client


@pytest.fixture
def advanced_dock_area(qtbot, mocked_client):
    """Create an AdvancedDockArea instance for testing."""
    widget = AdvancedDockArea(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def temp_profile_dir():
    """Create a temporary directory for profile testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch.dict(os.environ, {"BECWIDGETS_PROFILE_DIR": temp_dir}):
            yield temp_dir


class TestAdvancedDockAreaInit:
    """Test initialization and basic properties."""

    def test_init(self, advanced_dock_area):
        assert advanced_dock_area is not None
        assert isinstance(advanced_dock_area, AdvancedDockArea)
        assert advanced_dock_area.mode == "developer"
        assert hasattr(advanced_dock_area, "dock_manager")
        assert hasattr(advanced_dock_area, "toolbar")
        assert hasattr(advanced_dock_area, "dark_mode_button")
        assert hasattr(advanced_dock_area, "state_manager")

    def test_rpc_and_plugin_flags(self):
        assert AdvancedDockArea.RPC is True
        assert AdvancedDockArea.PLUGIN is False

    def test_user_access_list(self):
        expected_methods = [
            "new",
            "widget_map",
            "widget_list",
            "lock_workspace",
            "attach_all",
            "delete_all",
        ]
        for method in expected_methods:
            assert method in AdvancedDockArea.USER_ACCESS


class TestDockManagement:
    """Test dock creation, management, and manipulation."""

    def test_new_widget_string(self, advanced_dock_area, qtbot):
        """Test creating a new widget from string."""
        initial_count = len(advanced_dock_area.dock_list())

        # Create a widget by string name
        widget = advanced_dock_area.new("Waveform")

        # Wait for the dock to be created (since it's async)
        qtbot.wait(200)

        # Check that dock was actually created
        assert len(advanced_dock_area.dock_list()) == initial_count + 1

        # Check widget was returned
        assert widget is not None
        assert hasattr(widget, "name_established")

    def test_new_widget_instance(self, advanced_dock_area, qtbot):
        """Test creating dock with existing widget instance."""
        from bec_widgets.widgets.plots.waveform.waveform import Waveform

        initial_count = len(advanced_dock_area.dock_list())

        # Create widget instance
        widget_instance = Waveform(parent=advanced_dock_area, client=advanced_dock_area.client)
        widget_instance.setObjectName("test_widget")

        # Add it to dock area
        result = advanced_dock_area.new(widget_instance)

        # Should return the same instance
        assert result == widget_instance

        qtbot.wait(200)

        assert len(advanced_dock_area.dock_list()) == initial_count + 1

    def test_dock_map(self, advanced_dock_area, qtbot):
        """Test dock_map returns correct mapping."""
        # Initially empty
        dock_map = advanced_dock_area.dock_map()
        assert isinstance(dock_map, dict)
        initial_count = len(dock_map)

        # Create a widget
        advanced_dock_area.new("Waveform")
        qtbot.wait(200)

        # Check dock map updated
        new_dock_map = advanced_dock_area.dock_map()
        assert len(new_dock_map) == initial_count + 1

    def test_dock_list(self, advanced_dock_area, qtbot):
        """Test dock_list returns list of docks."""
        dock_list = advanced_dock_area.dock_list()
        assert isinstance(dock_list, list)
        initial_count = len(dock_list)

        # Create a widget
        advanced_dock_area.new("Waveform")
        qtbot.wait(200)

        # Check dock list updated
        new_dock_list = advanced_dock_area.dock_list()
        assert len(new_dock_list) == initial_count + 1

    def test_widget_map(self, advanced_dock_area, qtbot):
        """Test widget_map returns widget mapping."""
        widget_map = advanced_dock_area.widget_map()
        assert isinstance(widget_map, dict)
        initial_count = len(widget_map)

        # Create a widget
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        # Check widget map updated
        new_widget_map = advanced_dock_area.widget_map()
        assert len(new_widget_map) == initial_count + 1

    def test_widget_list(self, advanced_dock_area, qtbot):
        """Test widget_list returns list of widgets."""
        widget_list = advanced_dock_area.widget_list()
        assert isinstance(widget_list, list)
        initial_count = len(widget_list)

        # Create a widget
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        # Check widget list updated
        new_widget_list = advanced_dock_area.widget_list()
        assert len(new_widget_list) == initial_count + 1

    def test_delete_all(self, advanced_dock_area, qtbot):
        """Test delete_all functionality."""
        # Create multiple widgets
        advanced_dock_area.new("DarkModeButton")
        advanced_dock_area.new("DarkModeButton")

        # Wait for docks to be created
        qtbot.wait(200)

        initial_count = len(advanced_dock_area.dock_list())
        assert initial_count >= 2

        # Delete all
        advanced_dock_area.delete_all()

        # Wait for deletion to complete
        qtbot.wait(200)

        # Should have no docks
        assert len(advanced_dock_area.dock_list()) == 0


class TestWorkspaceLocking:
    """Test workspace locking functionality."""

    def test_lock_workspace_property_getter(self, advanced_dock_area):
        """Test lock_workspace property getter."""
        # Initially unlocked
        assert advanced_dock_area.lock_workspace is False

        # Set locked state directly
        advanced_dock_area._locked = True
        assert advanced_dock_area.lock_workspace is True

    def test_lock_workspace_property_setter(self, advanced_dock_area, qtbot):
        """Test lock_workspace property setter."""
        # Create a dock first
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        # Initially unlocked
        assert advanced_dock_area.lock_workspace is False

        # Lock workspace
        advanced_dock_area.lock_workspace = True
        assert advanced_dock_area._locked is True
        assert advanced_dock_area.lock_workspace is True

        # Unlock workspace
        advanced_dock_area.lock_workspace = False
        assert advanced_dock_area._locked is False
        assert advanced_dock_area.lock_workspace is False


class TestDeveloperMode:
    """Test developer mode functionality."""

    def test_developer_mode_toggle(self, advanced_dock_area):
        """Test developer mode toggle functionality."""
        # Check initial state
        initial_editable = advanced_dock_area._editable

        # Toggle developer mode
        advanced_dock_area._on_developer_mode_toggled(True)
        assert advanced_dock_area._editable is True
        assert advanced_dock_area.lock_workspace is False

        advanced_dock_area._on_developer_mode_toggled(False)
        assert advanced_dock_area._editable is False
        assert advanced_dock_area.lock_workspace is True

    def test_set_editable(self, advanced_dock_area):
        """Test _set_editable functionality."""
        # Test setting editable to True
        advanced_dock_area._set_editable(True)
        assert advanced_dock_area.lock_workspace is False
        assert advanced_dock_area._editable is True

        # Test setting editable to False
        advanced_dock_area._set_editable(False)
        assert advanced_dock_area.lock_workspace is True
        assert advanced_dock_area._editable is False


class TestToolbarFunctionality:
    """Test toolbar setup and functionality."""

    def test_toolbar_setup(self, advanced_dock_area):
        """Test toolbar is properly set up."""
        assert hasattr(advanced_dock_area, "toolbar")
        assert hasattr(advanced_dock_area, "_ACTION_MAPPINGS")

        # Check that action mappings are properly set
        assert "menu_plots" in advanced_dock_area._ACTION_MAPPINGS
        assert "menu_devices" in advanced_dock_area._ACTION_MAPPINGS
        assert "menu_utils" in advanced_dock_area._ACTION_MAPPINGS

    def test_toolbar_plot_actions(self, advanced_dock_area):
        """Test plot toolbar actions trigger widget creation."""
        plot_actions = [
            "waveform",
            "scatter_waveform",
            "multi_waveform",
            "image",
            "motor_map",
            "heatmap",
        ]

        for action_name in plot_actions:
            with patch.object(advanced_dock_area, "new") as mock_new:
                menu_plots = advanced_dock_area.toolbar.components.get_action("menu_plots")
                action = menu_plots.actions[action_name].action

                # Get the expected widget type from the action mappings
                widget_type = advanced_dock_area._ACTION_MAPPINGS["menu_plots"][action_name][2]

                action.trigger()
                mock_new.assert_called_once_with(widget=widget_type)

    def test_toolbar_device_actions(self, advanced_dock_area):
        """Test device toolbar actions trigger widget creation."""
        device_actions = ["scan_control", "positioner_box"]

        for action_name in device_actions:
            with patch.object(advanced_dock_area, "new") as mock_new:
                menu_devices = advanced_dock_area.toolbar.components.get_action("menu_devices")
                action = menu_devices.actions[action_name].action

                # Get the expected widget type from the action mappings
                widget_type = advanced_dock_area._ACTION_MAPPINGS["menu_devices"][action_name][2]

                action.trigger()
                mock_new.assert_called_once_with(widget=widget_type)

    def test_toolbar_utils_actions(self, advanced_dock_area):
        """Test utils toolbar actions trigger widget creation."""
        utils_actions = ["queue", "vs_code", "status", "progress_bar", "sbb_monitor"]

        for action_name in utils_actions:
            with patch.object(advanced_dock_area, "new") as mock_new:
                menu_utils = advanced_dock_area.toolbar.components.get_action("menu_utils")
                action = menu_utils.actions[action_name].action

                # Skip log_panel as it's disabled
                if action_name == "log_panel":
                    assert not action.isEnabled()
                    continue

                # Get the expected widget type from the action mappings
                widget_type = advanced_dock_area._ACTION_MAPPINGS["menu_utils"][action_name][2]

                action.trigger()
                mock_new.assert_called_once_with(widget=widget_type)

    def test_attach_all_action(self, advanced_dock_area, qtbot):
        """Test attach_all toolbar action."""
        # Create floating docks
        advanced_dock_area.new("DarkModeButton", start_floating=True)
        advanced_dock_area.new("DarkModeButton", start_floating=True)

        qtbot.wait(200)

        initial_floating = len(advanced_dock_area.dock_manager.floatingWidgets())

        # Trigger attach all action
        action = advanced_dock_area.toolbar.components.get_action("attach_all").action
        action.trigger()

        # Wait a bit for the operation
        qtbot.wait(200)

        # Should have fewer or same floating widgets
        final_floating = len(advanced_dock_area.dock_manager.floatingWidgets())
        assert final_floating <= initial_floating

    def test_screenshot_action(self, advanced_dock_area, tmpdir):
        """Test screenshot toolbar action."""
        # Create a test screenshot file path in tmpdir
        screenshot_path = tmpdir.join("test_screenshot.png")

        # Mock the QFileDialog.getSaveFileName to return a test filename
        with mock.patch("bec_widgets.utils.bec_widget.QFileDialog.getSaveFileName") as mock_dialog:
            mock_dialog.return_value = (str(screenshot_path), "PNG Files (*.png)")

            # Mock the screenshot.save method
            with mock.patch.object(advanced_dock_area, "grab") as mock_grab:
                mock_screenshot = mock.MagicMock()
                mock_grab.return_value = mock_screenshot

                # Trigger the screenshot action
                action = advanced_dock_area.toolbar.components.get_action("screenshot").action
                action.trigger()

                # Verify the dialog was called
                mock_dialog.assert_called_once()

                # Verify grab was called
                mock_grab.assert_called_once()

                # Verify save was called with the filename
                mock_screenshot.save.assert_called_once_with(str(screenshot_path))


class TestDockSettingsDialog:
    """Test dock settings dialog functionality."""

    def test_dock_settings_dialog_init(self, advanced_dock_area):
        """Test DockSettingsDialog initialization."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create a real widget
        mock_widget = DarkModeButton(parent=advanced_dock_area)
        dialog = DockSettingsDialog(advanced_dock_area, mock_widget)

        assert dialog.windowTitle() == "Dock Settings"
        assert dialog.isModal()
        assert hasattr(dialog, "prop_editor")

    def test_open_dock_settings_dialog(self, advanced_dock_area, qtbot):
        """Test opening dock settings dialog."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create real widget and dock
        widget = DarkModeButton(parent=advanced_dock_area)
        widget.setObjectName("test_widget")

        # Create a real dock
        dock = advanced_dock_area._make_dock(widget, closable=True, floatable=True, movable=True)

        # Mock dialog exec to avoid blocking
        with patch.object(DockSettingsDialog, "exec") as mock_exec:
            mock_exec.return_value = QDialog.Accepted

            # Call the method
            advanced_dock_area._open_dock_settings_dialog(dock, widget)

            # Verify dialog was created and exec called
            mock_exec.assert_called_once()


class TestSaveProfileDialog:
    """Test save profile dialog functionality."""

    def test_save_profile_dialog_init(self, qtbot):
        """Test SaveProfileDialog initialization."""
        dialog = SaveProfileDialog(None, "test_profile")
        qtbot.addWidget(dialog)

        assert dialog.windowTitle() == "Save Workspace Profile"
        assert dialog.isModal()
        assert dialog.name_edit.text() == "test_profile"
        assert hasattr(dialog, "readonly_checkbox")

    def test_save_profile_dialog_get_values(self, qtbot):
        """Test getting values from SaveProfileDialog."""
        dialog = SaveProfileDialog(None)
        qtbot.addWidget(dialog)

        dialog.name_edit.setText("my_profile")
        dialog.readonly_checkbox.setChecked(True)

        assert dialog.get_profile_name() == "my_profile"
        assert dialog.is_readonly() is True

    def test_save_button_enabled_state(self, qtbot):
        """Test save button is enabled/disabled based on name input."""
        dialog = SaveProfileDialog(None)
        qtbot.addWidget(dialog)

        # Initially should be disabled (empty name)
        assert not dialog.save_btn.isEnabled()

        # Should be enabled when name is entered
        dialog.name_edit.setText("test")
        assert dialog.save_btn.isEnabled()

        # Should be disabled when name is cleared
        dialog.name_edit.setText("")
        assert not dialog.save_btn.isEnabled()


class TestProfileManagement:
    """Test profile management functionality."""

    def test_profiles_dir_creation(self, temp_profile_dir):
        """Test that profiles directory is created."""
        profiles_dir = _profiles_dir()
        assert os.path.exists(profiles_dir)
        assert profiles_dir == temp_profile_dir

    def test_profile_path(self, temp_profile_dir):
        """Test profile path generation."""
        path = _profile_path("test_profile")
        expected = os.path.join(temp_profile_dir, "test_profile.ini")
        assert path == expected

    def test_open_settings(self, temp_profile_dir):
        """Test opening settings for a profile."""
        settings = open_settings("test_profile")
        assert isinstance(settings, QSettings)

    def test_list_profiles_empty(self, temp_profile_dir):
        """Test listing profiles when directory is empty."""
        profiles = list_profiles()
        assert profiles == []

    def test_list_profiles_with_files(self, temp_profile_dir):
        """Test listing profiles with existing files."""
        # Create some test profile files
        profile_names = ["profile1", "profile2", "profile3"]
        for name in profile_names:
            settings = open_settings(name)
            settings.setValue("test", "value")
            settings.sync()

        profiles = list_profiles()
        assert sorted(profiles) == sorted(profile_names)

    def test_readonly_profile_operations(self, temp_profile_dir):
        """Test read-only profile functionality."""
        profile_name = "readonly_profile"

        # Initially should not be read-only
        assert not is_profile_readonly(profile_name)

        # Set as read-only
        set_profile_readonly(profile_name, True)
        assert is_profile_readonly(profile_name)

        # Unset read-only
        set_profile_readonly(profile_name, False)
        assert not is_profile_readonly(profile_name)

    def test_write_and_read_manifest(self, temp_profile_dir, advanced_dock_area, qtbot):
        """Test writing and reading dock manifest."""
        settings = open_settings("test_manifest")

        # Create real docks
        advanced_dock_area.new("DarkModeButton")
        advanced_dock_area.new("DarkModeButton")
        advanced_dock_area.new("DarkModeButton")

        # Wait for docks to be created
        qtbot.wait(1000)

        docks = advanced_dock_area.dock_list()

        # Write manifest
        write_manifest(settings, docks)
        settings.sync()

        # Read manifest
        items = read_manifest(settings)

        assert len(items) >= 3
        for item in items:
            assert "object_name" in item
            assert "widget_class" in item
            assert "closable" in item
            assert "floatable" in item
            assert "movable" in item


class TestWorkspaceProfileOperations:
    """Test workspace profile save/load/delete operations."""

    def test_save_profile_with_name(self, advanced_dock_area, temp_profile_dir, qtbot):
        """Test saving profile with provided name."""
        profile_name = "test_save_profile"

        # Create some docks
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        # Save profile
        advanced_dock_area.save_profile(profile_name)

        # Check that profile file was created
        profile_path = _profile_path(profile_name)
        assert os.path.exists(profile_path)

    def test_save_profile_readonly_conflict(self, advanced_dock_area, temp_profile_dir):
        """Test saving profile when read-only profile exists."""
        profile_name = "readonly_profile"

        # Create a read-only profile
        set_profile_readonly(profile_name, True)
        settings = open_settings(profile_name)
        settings.setValue("test", "value")
        settings.sync()

        with patch(
            "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.SaveProfileDialog"
        ) as mock_dialog_class:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = QDialog.Accepted
            mock_dialog.get_profile_name.return_value = profile_name
            mock_dialog.is_readonly.return_value = False
            mock_dialog_class.return_value = mock_dialog

            with patch(
                "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.QMessageBox.warning"
            ) as mock_warning:
                mock_warning.return_value = QMessageBox.No

                advanced_dock_area.save_profile()

                mock_warning.assert_called_once()

    def test_load_profile_with_manifest(self, advanced_dock_area, temp_profile_dir, qtbot):
        """Test loading profile with widget manifest."""
        profile_name = "test_load_profile"

        # Create a profile with manifest
        settings = open_settings(profile_name)
        settings.beginWriteArray("manifest/widgets", 1)
        settings.setArrayIndex(0)
        settings.setValue("object_name", "test_widget")
        settings.setValue("widget_class", "DarkModeButton")
        settings.setValue("closable", True)
        settings.setValue("floatable", True)
        settings.setValue("movable", True)
        settings.endArray()
        settings.sync()

        initial_count = len(advanced_dock_area.widget_map())

        # Load profile
        advanced_dock_area.load_profile(profile_name)

        # Wait for widget to be created
        qtbot.wait(1000)

        # Check widget was created
        widget_map = advanced_dock_area.widget_map()
        assert "test_widget" in widget_map

    def test_delete_profile_readonly(self, advanced_dock_area, temp_profile_dir):
        """Test deleting read-only profile shows warning."""
        profile_name = "readonly_profile"

        # Create read-only profile
        set_profile_readonly(profile_name, True)
        settings = open_settings(profile_name)
        settings.setValue("test", "value")
        settings.sync()

        with patch.object(advanced_dock_area.toolbar.components, "get_action") as mock_get_action:
            mock_combo = MagicMock()
            mock_combo.currentText.return_value = profile_name
            mock_get_action.return_value.widget = mock_combo

            with patch(
                "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.QMessageBox.warning"
            ) as mock_warning:
                advanced_dock_area.delete_profile()

                mock_warning.assert_called_once()
                # Profile should still exist
                assert os.path.exists(_profile_path(profile_name))

    def test_delete_profile_success(self, advanced_dock_area, temp_profile_dir):
        """Test successful profile deletion."""
        profile_name = "deletable_profile"

        # Create regular profile
        settings = open_settings(profile_name)
        settings.setValue("test", "value")
        settings.sync()

        with patch.object(advanced_dock_area.toolbar.components, "get_action") as mock_get_action:
            mock_combo = MagicMock()
            mock_combo.currentText.return_value = profile_name
            mock_get_action.return_value.widget = mock_combo

            with patch(
                "bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area.QMessageBox.question"
            ) as mock_question:
                mock_question.return_value = QMessageBox.Yes

                with patch.object(advanced_dock_area, "_refresh_workspace_list") as mock_refresh:
                    advanced_dock_area.delete_profile()

                    mock_question.assert_called_once()
                    mock_refresh.assert_called_once()
                    # Profile should be deleted
                    assert not os.path.exists(_profile_path(profile_name))

    def test_refresh_workspace_list(self, advanced_dock_area, temp_profile_dir):
        """Test refreshing workspace list."""
        # Create some profiles
        for name in ["profile1", "profile2"]:
            settings = open_settings(name)
            settings.setValue("test", "value")
            settings.sync()

        with patch.object(advanced_dock_area.toolbar.components, "get_action") as mock_get_action:
            mock_combo = MagicMock()
            mock_combo.refresh_profiles = MagicMock()
            mock_get_action.return_value.widget = mock_combo

            advanced_dock_area._refresh_workspace_list()

            mock_combo.refresh_profiles.assert_called_once()


class TestCleanupAndMisc:
    """Test cleanup and miscellaneous functionality."""

    def test_delete_dock(self, advanced_dock_area, qtbot):
        """Test _delete_dock functionality."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create a real widget and dock
        widget = DarkModeButton(parent=advanced_dock_area)
        widget.setObjectName("test_widget")

        dock = advanced_dock_area._make_dock(widget, closable=True, floatable=True, movable=True)

        initial_count = len(advanced_dock_area.dock_list())

        # Delete the dock
        advanced_dock_area._delete_dock(dock)

        # Wait for deletion to complete
        qtbot.wait(200)

        # Verify dock was removed
        assert len(advanced_dock_area.dock_list()) == initial_count - 1

    def test_apply_dock_lock(self, advanced_dock_area, qtbot):
        """Test _apply_dock_lock functionality."""
        # Create a dock first
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        # Test locking
        advanced_dock_area._apply_dock_lock(True)
        # No assertion needed - just verify it doesn't crash

        # Test unlocking
        advanced_dock_area._apply_dock_lock(False)
        # No assertion needed - just verify it doesn't crash

    def test_make_dock(self, advanced_dock_area):
        """Test _make_dock functionality."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create a real widget
        widget = DarkModeButton(parent=advanced_dock_area)
        widget.setObjectName("test_widget")

        initial_count = len(advanced_dock_area.dock_list())

        # Create dock
        dock = advanced_dock_area._make_dock(widget, closable=True, floatable=True, movable=True)

        # Verify dock was created
        assert dock is not None
        assert len(advanced_dock_area.dock_list()) == initial_count + 1
        assert dock.widget() == widget

    def test_install_dock_settings_action(self, advanced_dock_area):
        """Test _install_dock_settings_action functionality."""
        from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import (
            DarkModeButton,
        )

        # Create real widget and dock
        widget = DarkModeButton(parent=advanced_dock_area)
        widget.setObjectName("test_widget")

        dock = advanced_dock_area._make_dock(widget, closable=True, floatable=True, movable=True)

        # Verify dock has settings action
        assert hasattr(dock, "setting_action")
        assert dock.setting_action is not None

        # Verify title bar actions were set
        title_bar_actions = dock.titleBarActions()
        assert len(title_bar_actions) >= 1


class TestModeSwitching:
    """Test mode switching functionality."""

    def test_mode_property_setter_valid_modes(self, advanced_dock_area):
        """Test setting valid modes."""
        valid_modes = ["plot", "device", "utils", "developer", "user"]

        for mode in valid_modes:
            advanced_dock_area.mode = mode
            assert advanced_dock_area.mode == mode

    def test_mode_changed_signal_emission(self, advanced_dock_area, qtbot):
        """Test that mode_changed signal is emitted when mode changes."""
        # Set up signal spy
        with qtbot.waitSignal(advanced_dock_area.mode_changed, timeout=1000) as blocker:
            advanced_dock_area.mode = "plot"

        # Check signal was emitted with correct argument
        assert blocker.args == ["plot"]


class TestToolbarModeBundles:
    """Test toolbar bundle creation and visibility for different modes."""

    def test_flat_bundles_created(self, advanced_dock_area):
        """Test that flat bundles are created during toolbar setup."""
        # Check that flat bundles exist
        assert "flat_plots" in advanced_dock_area.toolbar.bundles
        assert "flat_devices" in advanced_dock_area.toolbar.bundles
        assert "flat_utils" in advanced_dock_area.toolbar.bundles

    def test_plot_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in plot mode."""
        advanced_dock_area.mode = "plot"

        # Should show only flat_plots bundle (and essential bundles in real implementation)
        shown_bundles = advanced_dock_area.toolbar.shown_bundles
        assert "flat_plots" in shown_bundles

        # Should not show other flat bundles
        assert "flat_devices" not in shown_bundles
        assert "flat_utils" not in shown_bundles

        # Should not show menu bundles
        assert "menu_plots" not in shown_bundles
        assert "menu_devices" not in shown_bundles
        assert "menu_utils" not in shown_bundles

    def test_device_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in device mode."""
        advanced_dock_area.mode = "device"

        shown_bundles = advanced_dock_area.toolbar.shown_bundles
        assert "flat_devices" in shown_bundles

        # Should not show other flat bundles
        assert "flat_plots" not in shown_bundles
        assert "flat_utils" not in shown_bundles

    def test_utils_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in utils mode."""
        advanced_dock_area.mode = "utils"

        shown_bundles = advanced_dock_area.toolbar.shown_bundles
        assert "flat_utils" in shown_bundles

        # Should not show other flat bundles
        assert "flat_plots" not in shown_bundles
        assert "flat_devices" not in shown_bundles

    def test_developer_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in developer mode."""
        advanced_dock_area.mode = "developer"

        shown_bundles = advanced_dock_area.toolbar.shown_bundles

        # Should show menu bundles
        assert "menu_plots" in shown_bundles
        assert "menu_devices" in shown_bundles
        assert "menu_utils" in shown_bundles

        # Should show essential bundles
        assert "spacer_bundle" in shown_bundles
        assert "workspace" in shown_bundles
        assert "dock_actions" in shown_bundles

    def test_user_mode_toolbar_visibility(self, advanced_dock_area):
        """Test toolbar bundle visibility in user mode."""
        advanced_dock_area.mode = "user"

        shown_bundles = advanced_dock_area.toolbar.shown_bundles

        # Should show only essential bundles
        assert "spacer_bundle" in shown_bundles
        assert "workspace" in shown_bundles
        assert "dock_actions" in shown_bundles

        # Should not show any widget creation bundles
        assert "menu_plots" not in shown_bundles
        assert "menu_devices" not in shown_bundles
        assert "menu_utils" not in shown_bundles
        assert "flat_plots" not in shown_bundles
        assert "flat_devices" not in shown_bundles
        assert "flat_utils" not in shown_bundles


class TestFlatToolbarActions:
    """Test flat toolbar actions functionality."""

    def test_flat_plot_actions_created(self, advanced_dock_area):
        """Test that flat plot actions are created."""
        plot_actions = [
            "flat_waveform",
            "flat_scatter_waveform",
            "flat_multi_waveform",
            "flat_image",
            "flat_motor_map",
            "flat_heatmap",
        ]

        for action_name in plot_actions:
            assert advanced_dock_area.toolbar.components.exists(action_name)

    def test_flat_device_actions_created(self, advanced_dock_area):
        """Test that flat device actions are created."""
        device_actions = ["flat_scan_control", "flat_positioner_box"]

        for action_name in device_actions:
            assert advanced_dock_area.toolbar.components.exists(action_name)

    def test_flat_utils_actions_created(self, advanced_dock_area):
        """Test that flat utils actions are created."""
        utils_actions = [
            "flat_queue",
            "flat_vs_code",
            "flat_status",
            "flat_progress_bar",
            "flat_log_panel",
            "flat_sbb_monitor",
        ]

        for action_name in utils_actions:
            assert advanced_dock_area.toolbar.components.exists(action_name)

    def test_flat_plot_actions_trigger_widget_creation(self, advanced_dock_area):
        """Test flat plot actions trigger widget creation."""
        plot_action_mapping = {
            "flat_waveform": "Waveform",
            "flat_scatter_waveform": "ScatterWaveform",
            "flat_multi_waveform": "MultiWaveform",
            "flat_image": "Image",
            "flat_motor_map": "MotorMap",
            "flat_heatmap": "Heatmap",
        }

        for action_name, widget_type in plot_action_mapping.items():
            with patch.object(advanced_dock_area, "new") as mock_new:
                action = advanced_dock_area.toolbar.components.get_action(action_name).action
                action.trigger()
                mock_new.assert_called_once_with(widget=widget_type)

    def test_flat_device_actions_trigger_widget_creation(self, advanced_dock_area):
        """Test flat device actions trigger widget creation."""
        device_action_mapping = {
            "flat_scan_control": "ScanControl",
            "flat_positioner_box": "PositionerBox",
        }

        for action_name, widget_type in device_action_mapping.items():
            with patch.object(advanced_dock_area, "new") as mock_new:
                action = advanced_dock_area.toolbar.components.get_action(action_name).action
                action.trigger()
                mock_new.assert_called_once_with(widget=widget_type)

    def test_flat_utils_actions_trigger_widget_creation(self, advanced_dock_area):
        """Test flat utils actions trigger widget creation."""
        utils_action_mapping = {
            "flat_queue": "BECQueue",
            "flat_vs_code": "VSCodeEditor",
            "flat_status": "BECStatusBox",
            "flat_progress_bar": "RingProgressBar",
            "flat_sbb_monitor": "SBBMonitor",
        }

        for action_name, widget_type in utils_action_mapping.items():
            with patch.object(advanced_dock_area, "new") as mock_new:
                action = advanced_dock_area.toolbar.components.get_action(action_name).action

                # Skip log_panel as it's disabled
                if action_name == "flat_log_panel":
                    assert not action.isEnabled()
                    continue

                action.trigger()
                mock_new.assert_called_once_with(widget=widget_type)

    def test_flat_log_panel_action_disabled(self, advanced_dock_area):
        """Test that flat log panel action is disabled."""
        action = advanced_dock_area.toolbar.components.get_action("flat_log_panel").action
        assert not action.isEnabled()


class TestModeTransitions:
    """Test mode transitions and state consistency."""

    def test_mode_transition_sequence(self, advanced_dock_area, qtbot):
        """Test sequence of mode transitions."""
        modes = ["plot", "device", "utils", "developer", "user"]

        for mode in modes:
            with qtbot.waitSignal(advanced_dock_area.mode_changed, timeout=1000) as blocker:
                advanced_dock_area.mode = mode

            assert advanced_dock_area.mode == mode
            assert blocker.args == [mode]

    def test_mode_consistency_after_multiple_changes(self, advanced_dock_area):
        """Test mode consistency after multiple rapid changes."""
        # Rapidly change modes
        advanced_dock_area.mode = "plot"
        advanced_dock_area.mode = "device"
        advanced_dock_area.mode = "utils"
        advanced_dock_area.mode = "developer"
        advanced_dock_area.mode = "user"

        # Final state should be consistent
        assert advanced_dock_area.mode == "user"

        # Toolbar should show correct bundles for user mode
        shown_bundles = advanced_dock_area.toolbar.shown_bundles
        assert "spacer_bundle" in shown_bundles
        assert "workspace" in shown_bundles
        assert "dock_actions" in shown_bundles

    def test_toolbar_refresh_on_mode_change(self, advanced_dock_area):
        """Test that toolbar is properly refreshed when mode changes."""
        initial_bundles = set(advanced_dock_area.toolbar.shown_bundles)

        # Change to a different mode
        advanced_dock_area.mode = "plot"
        plot_bundles = set(advanced_dock_area.toolbar.shown_bundles)

        # Bundles should be different
        assert initial_bundles != plot_bundles
        assert "flat_plots" in plot_bundles

    def test_mode_switching_preserves_existing_docks(self, advanced_dock_area, qtbot):
        """Test that mode switching doesn't affect existing docked widgets."""
        # Create some widgets
        advanced_dock_area.new("DarkModeButton")
        advanced_dock_area.new("DarkModeButton")
        qtbot.wait(200)

        initial_dock_count = len(advanced_dock_area.dock_list())
        initial_widget_count = len(advanced_dock_area.widget_list())

        # Switch modes
        advanced_dock_area.mode = "plot"
        advanced_dock_area.mode = "device"
        advanced_dock_area.mode = "user"

        # Dock and widget counts should remain the same
        assert len(advanced_dock_area.dock_list()) == initial_dock_count
        assert len(advanced_dock_area.widget_list()) == initial_widget_count


class TestModeProperty:
    """Test mode property getter and setter behavior."""

    def test_mode_property_getter(self, advanced_dock_area):
        """Test mode property getter returns correct value."""
        # Set internal mode directly and test getter
        advanced_dock_area._mode = "plot"
        assert advanced_dock_area.mode == "plot"

        advanced_dock_area._mode = "device"
        assert advanced_dock_area.mode == "device"

    def test_mode_property_setter_updates_internal_state(self, advanced_dock_area):
        """Test mode property setter updates internal state."""
        advanced_dock_area.mode = "plot"
        assert advanced_dock_area._mode == "plot"

        advanced_dock_area.mode = "utils"
        assert advanced_dock_area._mode == "utils"

    def test_mode_property_setter_triggers_toolbar_update(self, advanced_dock_area):
        """Test mode property setter triggers toolbar update."""
        with patch.object(advanced_dock_area.toolbar, "show_bundles") as mock_show_bundles:
            advanced_dock_area.mode = "plot"
            mock_show_bundles.assert_called_once()

    def test_multiple_mode_changes(self, advanced_dock_area, qtbot):
        """Test multiple rapid mode changes."""
        modes = ["plot", "device", "utils", "developer", "user"]

        for i, mode in enumerate(modes):
            with qtbot.waitSignal(advanced_dock_area.mode_changed, timeout=1000) as blocker:
                advanced_dock_area.mode = mode

            assert advanced_dock_area.mode == mode
            assert blocker.args == [mode]
