"""Unit tests for the device manager view"""

# pylint: disable=protected-access,redefined-outer-name

from typing import Any
from unittest import mock

import pytest
from bec_lib.atlas_models import Device as DeviceModel
from ophyd_devices.interfaces.device_config_templates.ophyd_templates import OPHYD_DEVICE_TEMPLATES
from qtpy import QtCore, QtWidgets

from bec_widgets.applications.views.device_manager_view.device_manager_dialogs.config_choice_dialog import (
    ConfigChoiceDialog,
)
from bec_widgets.applications.views.device_manager_view.device_manager_dialogs.device_form_dialog import (
    DeviceFormDialog,
    DeviceManagerOphydValidationDialog,
)
from bec_widgets.applications.views.device_manager_view.device_manager_dialogs.upload_redis_dialog import (
    DeviceStatusItem,
    UploadRedisDialog,
    ValidationSection,
)
from bec_widgets.applications.views.device_manager_view.device_manager_display_widget import (
    CustomBusyWidget,
    DeviceManagerDisplayWidget,
)
from bec_widgets.applications.views.device_manager_view.device_manager_view import (
    DeviceManagerView,
    DeviceManagerWidget,
)
from bec_widgets.widgets.control.device_manager.components import (
    DeviceTable,
    DMConfigView,
    DocstringView,
    OphydValidation,
)
from bec_widgets.widgets.control.device_manager.components.ophyd_validation.ophyd_validation import (
    ConfigStatus,
    ConnectionStatus,
    OphydValidation,
)

from .client_mocks import mocked_client


@pytest.fixture
def device_config() -> dict:
    """Fixture for a sample device configuration."""
    return DeviceModel(
        name="TestDevice", enabled=True, deviceClass="TestClass", readoutPriority="baseline"
    ).model_dump()


class TestDeviceManagerViewDialogs:
    """Test class for DeviceManagerView dialog interactions."""

    @pytest.fixture
    def mock_dm_view(self, qtbot):
        """Fixture for DeviceManagerView."""
        widget = DeviceManagerDisplayWidget()
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        yield widget

    @pytest.fixture
    def config_choice_dialog(self, qtbot, mock_dm_view):
        """Fixture for ConfigChoiceDialog."""
        try:
            dialog = ConfigChoiceDialog(mock_dm_view)
            qtbot.addWidget(dialog)
            qtbot.waitExposed(dialog)
            yield dialog
        finally:
            dialog.close()

    def test_config_choice_dialog(self, mock_dm_view, config_choice_dialog, qtbot):
        """Test the configuration choice dialog."""
        assert config_choice_dialog is not None
        assert config_choice_dialog.parent() == mock_dm_view

        # Test dialog components
        with (mock.patch.object(config_choice_dialog, "done") as mock_done,):

            # Replace
            qtbot.mouseClick(config_choice_dialog.replace_btn, QtCore.Qt.LeftButton)
            mock_done.assert_called_once_with(config_choice_dialog.Result.REPLACE)
            mock_done.reset_mock()
            # Add
            qtbot.mouseClick(config_choice_dialog.add_btn, QtCore.Qt.LeftButton)
            mock_done.assert_called_once_with(config_choice_dialog.Result.ADD)
            mock_done.reset_mock()
            # Cancel
            qtbot.mouseClick(config_choice_dialog.cancel_btn, QtCore.Qt.LeftButton)
            mock_done.assert_called_once_with(config_choice_dialog.Result.CANCEL)

    @pytest.fixture
    def device_manager_ophyd_test_dialog(self, qtbot):
        """Fixture for DeviceManagerOphydValidationDialog."""
        dialog = DeviceManagerOphydValidationDialog()
        try:
            qtbot.addWidget(dialog)
            qtbot.waitExposed(dialog)
            yield dialog
        finally:
            dialog.close()

    def test_device_manager_ophyd_test_dialog(
        self, device_manager_ophyd_test_dialog: DeviceManagerOphydValidationDialog, qtbot
    ):
        """Test the DeviceManagerOphydValidationDialog."""
        dialog = device_manager_ophyd_test_dialog
        assert dialog.text_box.toPlainText() == ""

        dialog._on_device_validated(
            {"name": "TestDevice", "enabled": True},
            config_status=0,
            connection_status=0,
            validation_msg="All good",
        )
        assert dialog.validation_result == (
            {"name": "TestDevice", "enabled": True},
            0,
            0,
            "All good",
        )
        assert dialog.text_box.toPlainText() != ""

    @pytest.fixture
    def device_form_dialog(self, qtbot):
        """Fixture for DeviceFormDialog."""
        dialog = DeviceFormDialog()
        try:
            qtbot.addWidget(dialog)
            qtbot.waitExposed(dialog)
            yield dialog
        finally:
            dialog.close()

    def test_device_form_dialog(self, device_form_dialog: DeviceFormDialog, qtbot):
        """Test the DeviceFormDialog."""
        # Initial state
        dialog = device_form_dialog
        group_combo: QtWidgets.QComboBox = dialog._control_widgets["group_combo"]
        assert group_combo.count() == len(OPHYD_DEVICE_TEMPLATES)

        # Test select a group from available templates
        variant_combo = dialog._control_widgets["variant_combo"]
        assert variant_combo.isEnabled() is False

        with qtbot.waitSignal(group_combo.currentTextChanged):
            epics_signal_index = group_combo.findText("EpicsSignal")
            group_combo.setCurrentIndex(epics_signal_index)  # Select "EpicsSignal" group

        assert variant_combo.count() == len(OPHYD_DEVICE_TEMPLATES["EpicsSignal"])
        assert variant_combo.isEnabled() is True

        # Check that numb of widgets in connection settings box is correct
        fields_in_config = len(
            OPHYD_DEVICE_TEMPLATES["EpicsSignal"].get(variant_combo.currentText(), {})
        )  # At this point this should be read_pv & write_pv
        connection_settings_layout: QtWidgets.QGridLayout = (
            dialog._device_config_template.connection_settings_box.layout()
        )
        assert (
            connection_settings_layout.count() == fields_in_config * 2
        )  # Each field has a label and a widget

    def test_device_form_dialog_help_methods(
        self, device_form_dialog: DeviceFormDialog, device_config, qtbot
    ):
        """Test help methods in DeviceFormDialog."""
        # Test handle devices already in session results
        dialog = device_form_dialog

        # Test _handle_devices_already_in_session_results
        with mock.patch.object(dialog, "_handle_validation_result") as mock_handle_validation:
            dialog._handle_devices_already_in_session_results([(device_config, 0, 0, "")])
            mock_handle_validation.assert_called_once_with(device_config, 0, 0, "")
            mock_handle_validation.reset_mock()
            dialog._handle_devices_already_in_session_results([])
            mock_handle_validation.assert_not_called()
            mock_handle_validation.reset_mock()
            dialog._handle_devices_already_in_session_results(
                [(device_config, 1, 0, ""), (device_config, 0, 0, "")]
            )
            mock_handle_validation.assert_called_once_with(
                device_config, 1, 0, ""
            )  # Should be called with first

        # Test _handle_validation_result
        # I. No wait dialog present
        dialog._handle_validation_result(device_config, 1, 3, "All good")
        assert dialog._validation_result == (device_config, 1, 3, "All good")

        # II. No previous validation, but wait dialog present
        with mock.patch.object(dialog, "_wait_dialog") as mock_wait_dialog:
            dialog._handle_validation_result(device_config, 1, 3, "All good")
            assert dialog.config_validation_result == (device_config, 1, 3, "All good")
            mock_wait_dialog.accept.assert_called_once()
            mock_wait_dialog.close.assert_called_once()
            mock_wait_dialog.deleteLater.assert_called_once()

            mock_wait_dialog.reset_mock()
            assert dialog._wait_dialog is None

        # III. Previous validation present and the same config, wait dialog present
        with mock.patch.object(dialog, "_wait_dialog") as mock_wait_dialog:
            dialog._validation_result = (device_config, 1, 1, "Previous bad")
            dialog._handle_validation_result(device_config, 1, 3, "All good")
            assert dialog.config_validation_result == (device_config, 1, 1, "Previous bad")
            mock_wait_dialog.accept.assert_called_once()
            mock_wait_dialog.close.assert_called_once()
            mock_wait_dialog.deleteLater.assert_called_once()

            mock_wait_dialog.reset_mock()
            assert dialog._wait_dialog is None

        # IV. Previous validation present but different config, wait dialog present
        with mock.patch.object(dialog, "_wait_dialog") as mock_wait_dialog:
            different_config = device_config.copy()
            different_config["deviceClass"] = "DifferentClass"
            dialog._validation_result = (different_config, 1, 1, "Previous bad")
            dialog._handle_validation_result(device_config, 1, 3, "All good")
            assert dialog.config_validation_result == (device_config, 1, 3, "All good")
            mock_wait_dialog.accept.assert_called_once()
            mock_wait_dialog.close.assert_called_once()
            mock_wait_dialog.deleteLater.assert_called_once()

    def test_set_device_config(self, device_form_dialog: DeviceFormDialog, qtbot):
        """Test setting device configuration in DeviceFormDialog."""
        dialog = device_form_dialog
        sample_config = {
            "name": "TestDevice",
            "enabled": True,
            "deviceClass": "ophyd.EpicsSignal",
            "readoutPriority": "baseline",
            "deviceConfig": {"read_pv": "X25DA-ES1-MOT:GET"},
        }
        DeviceModel.model_validate(sample_config)
        dialog.set_device_config(sample_config)

        group_combo: QtWidgets.QComboBox = dialog._control_widgets["group_combo"]
        assert group_combo.currentText() == "EpicsSignal"
        variant_combo: QtWidgets.QComboBox = dialog._control_widgets["variant_combo"]
        assert variant_combo.currentText() == "EpicsSignal"
        config = dialog._device_config_template.get_config_fields()
        assert config["name"] == "TestDevice"
        assert config["deviceClass"] == "ophyd.EpicsSignal"
        assert config["deviceConfig"]["read_pv"] == "X25DA-ES1-MOT:GET"

        # Test now to add the device config with different validation results
        # For this we have to mock the additional ophyd_validation checks
        with (
            mock.patch.object(dialog, "_create_validation_dialog") as mock_create_dialog,
            mock.patch.object(dialog, "_create_and_run_ophyd_validation") as mock_create_validation,
        ):

            # Set the validation results, assume that test was running
            dialog.config_validation_result = (
                dialog._device_config_template.get_config_fields(),
                ConfigStatus.VALID.value,
                0,
                "",
            )
            with mock.patch.object(dialog, "_create_warning_message_box") as mock_warning_box:
                with qtbot.waitSignal(dialog.accepted_data) as sig_blocker:
                    qtbot.mouseClick(dialog.add_btn, QtCore.Qt.LeftButton)
                    config, _, _, _, _ = sig_blocker.args
                mock_warning_box.assert_not_called()

                mock_create_dialog.assert_called_once()
                mock_create_validation.assert_called_once()
                mock_create_dialog.reset_mock()
                mock_create_validation.reset_mock()

            # Called with config_status invalid should show warning
            dialog.config_validation_result = (
                dialog._device_config_template.get_config_fields(),
                ConfigStatus.INVALID.value,
                0,
                "",
            )
            with mock.patch.object(dialog, "_create_warning_message_box") as mock_warning_box:
                qtbot.mouseClick(dialog.add_btn, QtCore.Qt.LeftButton)
                mock_warning_box.assert_called_once()
                mock_create_dialog.assert_called_once()
                mock_create_validation.assert_called_once()
                mock_create_dialog.reset_mock()
                mock_create_validation.reset_mock()

            # Set to random config without name

            random_config = {"deviceClass": "Unknown"}
            dialog.set_device_config(random_config)
            dialog.config_validation_result = (
                dialog._device_config_template.get_config_fields(),
                0,
                0,
                "",
            )
            assert group_combo.currentText() == "CustomDevice"
            assert variant_combo.currentText() == "CustomDevice"
            with mock.patch.object(dialog, "_create_warning_message_box") as mock_warning_box:
                qtbot.mouseClick(dialog.add_btn, QtCore.Qt.LeftButton)
                mock_warning_box.assert_called_once_with(
                    "Invalid Device Name",
                    f"Device is invalid, cannot be empty or contain spaces. Please provide a valid name. {dialog._device_config_template.get_config_fields().get('name', '')!r}",
                )
                mock_create_dialog.assert_not_called()
                mock_create_validation.assert_not_called()

    def test_device_status_item(self, device_config: dict, qtbot):
        """Test the DeviceStatusItem widget."""
        item = DeviceStatusItem(device_config=device_config, config_status=0, connection_status=0)
        qtbot.addWidget(item)
        qtbot.waitExposed(item)
        assert item.device_config == device_config
        assert item.device_name == device_config.get("name", "")
        assert item.config_status == 0
        assert item.connection_status == 0
        assert "config_status" in item.icons
        assert "connection_status" in item.icons

        # Update status
        item.update_status(config_status=1, connection_status=2)
        assert item.config_status == 1
        assert item.connection_status == 2

    def test_validation_section(self, device_config: dict, qtbot):
        """Test the validation section."""
        device_config_2 = device_config.copy()
        device_config_2["name"] = "device_2"

        # Create section
        section = ValidationSection(title="Validation Results")
        qtbot.addWidget(section)
        qtbot.waitExposed(section)
        assert section.title() == "Validation Results"
        initial_widget_in_container = section.table.rowCount()

        # Add widgets
        section.add_device(device_config=device_config, config_status=0, connection_status=0)
        assert initial_widget_in_container + 1 == section.table.rowCount()
        # Should be the first index, so rowCount - 1
        assert section._find_row_by_name(device_config["name"]) == section.table.rowCount() - 1

        # Add another device
        section.add_device(device_config=device_config_2, config_status=1, connection_status=1)
        assert initial_widget_in_container + 2 == section.table.rowCount()
        # Should be the first index, so rowCount - 1
        assert section._find_row_by_name(device_config_2["name"]) == section.table.rowCount() - 1

        # Clear devices
        section.clear_devices()
        assert section.table.rowCount() == 0

        # Update test summary label
        section.update_summary("2 devices validated, 1 failed.")
        assert section.summary_label.text() == "2 devices validated, 1 failed."

    @pytest.fixture
    def device_configs_valid(self, device_config: dict):
        """Fixture for multiple device configurations."""
        return_dict = {}
        for i in range(4):
            name = f"Device_{i}"
            dev_config_copy = device_config.copy()
            dev_config_copy["name"] = name
            return_dict[name] = (dev_config_copy, ConfigStatus.VALID.value, i)
        return return_dict

    @pytest.fixture
    def device_configs_invalid(self, device_config: dict):
        return_dict = {}
        for i in range(4):
            name = f"Device_{i}"
            dev_config_copy = device_config.copy()
            dev_config_copy["name"] = name
            return_dict[name] = (dev_config_copy, ConfigStatus.INVALID.value, i)
        return return_dict

    @pytest.fixture
    def device_configs_unknown(self, device_config: dict):
        return_dict = {}
        for i in range(4):
            name = f"Device_{i}"
            dev_config_copy = device_config.copy()
            dev_config_copy["name"] = name
            return_dict[name] = (dev_config_copy, ConfigStatus.UNKNOWN.value, i)
        return return_dict

    @pytest.fixture
    def upload_redis_dialog(self, qtbot):
        """Fixture for UploadRedisDialog."""
        dialog = UploadRedisDialog(parent=None, device_configs={})
        try:
            qtbot.addWidget(dialog)
            qtbot.waitExposed(dialog)
            yield dialog
        finally:
            dialog.close()

    def test_upload_redis_valid_config(
        self, upload_redis_dialog: UploadRedisDialog, device_configs_valid, qtbot
    ):
        """
        Test the UploadRedisDialog with a valid device configuration.
        """
        dialog = upload_redis_dialog
        configs = device_configs_valid
        dialog.set_device_config(configs)

        n_invalid = len([True for _, cs, _ in configs.values() if cs == ConfigStatus.INVALID.value])
        n_untested = len(
            [True for _, cs, conn in configs.values() if conn == ConnectionStatus.UNKNOWN.value]
        )
        n_has_cannot_connect = len(
            [
                True
                for _, cs, conn in configs.values()
                if conn == ConnectionStatus.CANNOT_CONNECT.value
            ]
        )

        # Check the initial states
        assert dialog.has_invalid_configs == n_invalid
        assert dialog.has_untested_connections == n_untested
        assert dialog.has_cannot_connect == n_has_cannot_connect

        num_devices = len(configs)
        expected_text = ""
        if n_invalid > 0:
            expected_text = f"{n_invalid} of {num_devices} device configurations are invalid."
        else:
            expected_text = f"All {num_devices} device configurations are valid."
        if n_untested > 0:
            expected_text += f"{n_untested} device connections are not tested."
        if n_has_cannot_connect > 0:
            expected_text += f"{n_has_cannot_connect} device connections cannot be established."

        assert dialog.config_section.summary_label.text() == expected_text

    def test_upload_redis_unknown_config(
        self, upload_redis_dialog: UploadRedisDialog, device_configs_unknown, qtbot
    ):
        """
        Test the UploadRedisDialog with a valid device configuration.
        """
        dialog = upload_redis_dialog
        configs = device_configs_unknown
        dialog.set_device_config(configs)

        n_invalid = len([True for _, cs, _ in configs.values() if cs == ConfigStatus.INVALID.value])
        n_untested = len(
            [True for _, cs, conn in configs.values() if conn == ConnectionStatus.UNKNOWN.value]
        )
        n_has_cannot_connect = len(
            [
                True
                for _, cs, conn in configs.values()
                if conn == ConnectionStatus.CANNOT_CONNECT.value
            ]
        )

        # Check the initial states
        assert dialog.has_invalid_configs == n_invalid
        assert dialog.has_untested_connections == n_untested
        assert dialog.has_cannot_connect == n_has_cannot_connect

        num_devices = len(configs)
        expected_text = ""
        if n_invalid > 0:
            expected_text = f"{n_invalid} of {num_devices} device configurations are invalid."
        else:
            expected_text = f"All {num_devices} device configurations are valid."
        if n_untested > 0:
            expected_text += f"{n_untested} device connections are not tested."
        if n_has_cannot_connect > 0:
            expected_text += f"{n_has_cannot_connect} device connections cannot be established."

        assert dialog.config_section.summary_label.text() == expected_text

    def test_upload_redis_invalid_config(
        self, upload_redis_dialog: UploadRedisDialog, device_configs_invalid, qtbot
    ):
        """
        Test the UploadRedisDialog with a valid device configuration.
        """
        dialog = upload_redis_dialog
        configs = device_configs_invalid
        dialog.set_device_config(configs)

        n_invalid = len([True for _, cs, _ in configs.values() if cs == ConfigStatus.INVALID.value])
        n_untested = len(
            [True for _, cs, conn in configs.values() if conn == ConnectionStatus.UNKNOWN.value]
        )
        n_has_cannot_connect = len(
            [
                True
                for _, cs, conn in configs.values()
                if conn == ConnectionStatus.CANNOT_CONNECT.value
            ]
        )

        # Check the initial states
        assert dialog.has_invalid_configs == n_invalid
        assert dialog.has_untested_connections == n_untested
        assert dialog.has_cannot_connect == n_has_cannot_connect

        num_devices = len(configs)
        expected_text = ""
        if n_invalid > 0:
            expected_text = f"{n_invalid} of {num_devices} device configurations are invalid."
        else:
            expected_text = f"All {num_devices} device configurations are valid."
        if n_untested > 0:
            expected_text += f"{n_untested} device connections are not tested."
        if n_has_cannot_connect > 0:
            expected_text += f"{n_has_cannot_connect} device connections cannot be established."

        assert dialog.config_section.summary_label.text() == expected_text


class TestDeviceManagerView:
    """Test class for DeviceManagerView functionality."""

    @pytest.fixture
    def dm_view(self, qtbot, mocked_client):
        """Fixture for DeviceManagerView."""
        widget = DeviceManagerView()
        # Assign the mocked client
        widget.device_manager_widget.client = mocked_client
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        yield widget

    def test_dm_view_initialization(self, dm_view, qtbot):
        """Test DeviceManagerView initialization."""
        assert isinstance(dm_view.device_manager_widget, DeviceManagerWidget)
        # If on_enter is called, overlay should be shown initially
        dm_widget = dm_view.device_manager_widget
        dm_view.on_enter()
        assert dm_widget.stacked_layout.currentWidget() == dm_widget._overlay_widget

        with mock.patch.object(dm_widget.device_manager_display, "_load_file_action") as mock_load:
            # Simulate clicking "Load Config From File" button
            with qtbot.waitSignal(dm_widget.button_load_config_from_file.clicked):
                qtbot.mouseClick(dm_widget.button_load_config_from_file, QtCore.Qt.LeftButton)
                assert dm_widget._initialized is True
                assert dm_widget.stacked_layout.currentWidget() == dm_widget.device_manager_display

        # Reset for test loading current config
        dm_widget._initialized = False
        dm_widget.stacked_layout.setCurrentWidget(dm_widget._overlay_widget)

        with mock.patch.object(
            dm_widget.client.device_manager, "_get_redis_device_config"
        ) as mock_get:
            mock_get.return_value = []
            # Simulate clicking "Load Current Config" button
            with mock.patch.object(
                dm_widget.device_manager_display.device_table_view, "set_device_config"
            ) as mock_set:
                with qtbot.waitSignal(dm_widget.button_load_current_config.clicked):
                    qtbot.mouseClick(dm_widget.button_load_current_config, QtCore.Qt.LeftButton)
                    assert dm_widget._initialized is True
                    assert (
                        dm_widget.stacked_layout.currentWidget() == dm_widget.device_manager_display
                    )
                    mock_set.assert_called_once_with([])

    @pytest.fixture
    def device_manager_display_widget(self, qtbot, mocked_client):
        """Fixture for DeviceManagerDisplayWidget within DeviceManagerView.
        We will patch the OphydValidation _thread_pool_poll_loop to avoid starting threads during tests,
        and the _is_device_in_redis_session method to avoid Redis dependencies
        """

        with (
            mock.patch(
                "bec_widgets.widgets.control.device_manager.components.ophyd_validation.ophyd_validation.OphydValidation._thread_pool_poll_loop",
                return_value=None,
            ),
            mock.patch(
                "bec_widgets.widgets.control.device_manager.components.ophyd_validation.ophyd_validation.OphydValidation._is_device_in_redis_session",
                return_value=False,
            ),
        ):
            widget = DeviceManagerDisplayWidget(client=mocked_client)
            qtbot.addWidget(widget)
            qtbot.waitExposed(widget)
            yield widget

    @pytest.fixture
    def custom_busy(self, qtbot, mocked_client):
        """Fixture for the custom busy widget of the DeviceManagerDisplayWidget."""
        widget = CustomBusyWidget(client=mocked_client)
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        yield widget

    @pytest.fixture
    def device_configs(self, device_config: dict):
        """Fixture for multiple device configurations."""
        cfg_iter = []
        for i in range(4):
            name = f"Device_{i}"
            dev_config_copy = device_config.copy()
            dev_config_copy["name"] = name
            cfg_iter.append(dev_config_copy)
        return cfg_iter

    def test_device_manager_view_add_remove_device(
        self, device_manager_display_widget: DeviceManagerDisplayWidget, device_config
    ):
        """Test adding a device via the DeviceManagerView."""
        dm_view = device_manager_display_widget
        dm_view._add_to_table_from_dialog(
            device_config, config_status=0, connection_status=0, msg=""
        )
        table_config_list = dm_view.device_table_view.get_device_config()
        assert table_config_list == [device_config]

        # Remove the device
        dm_view.device_table_view.table.selectRow(0)
        dm_view.toolbar.components._components["remove_device"].action.action.triggered.emit()
        table_config_list = dm_view.device_table_view.get_device_config()
        assert table_config_list == []

    def test_dock_widgets_exist(self, device_manager_display_widget: DeviceManagerDisplayWidget):
        """Test that all required dock widgets are created."""
        dm_view = device_manager_display_widget
        dock_widgets = dm_view.dock_manager.dockWidgets()

        # Check that we have the expected number of dock widgets
        assert len(dock_widgets) == 4

        # Check for specific widget types
        widget_types = [dock.widget().__class__ for dock in dock_widgets]

        # OphydValidation is used in a layout with a QWidget
        assert DMConfigView in widget_types
        assert DocstringView in widget_types
        assert DeviceTable in widget_types

    def test_toolbar_initialization(
        self, device_manager_display_widget: DeviceManagerDisplayWidget
    ):
        """Test that the toolbar is properly initialized with expected bundles."""
        dm_view = device_manager_display_widget
        assert dm_view.toolbar is not None
        assert "IO" in dm_view.toolbar.bundles
        assert "Table" in dm_view.toolbar.bundles

    def test_io_bundle_exists(self, device_manager_display_widget: DeviceManagerDisplayWidget):
        """Test that IO bundle exists and contains expected actions."""
        dm_view = device_manager_display_widget
        assert "IO" in dm_view.toolbar.bundles
        io_actions = ["load", "save_to_disk", "flush_redis", "load_redis", "update_config_redis"]
        for action in io_actions:
            assert dm_view.toolbar.components.exists(action)

    def test_load_file_action_triggered(
        self, tmp_path, device_manager_display_widget: DeviceManagerDisplayWidget
    ):
        """Test load file action trigger mechanism."""
        dm_view = device_manager_display_widget
        with (
            mock.patch.object(dm_view, "_get_config_base_path", return_value=tmp_path),
            mock.patch.object(
                dm_view, "_get_file_path", return_value=str(tmp_path)
            ) as mock_get_file,
            mock.patch.object(dm_view, "_load_config_from_file") as mock_load_config,
        ):
            # Setup dialog mock
            dm_view.toolbar.components._components["load"].action.action.triggered.emit()
            mock_get_file.assert_called_once_with(str(tmp_path), "open_file")
            mock_load_config.assert_called_once_with(str(tmp_path))

    def test_table_bundle_exists(self, device_manager_display_widget: DeviceManagerDisplayWidget):
        """Test that Table bundle exists and contains expected actions."""
        dm_view = device_manager_display_widget
        assert "Table" in dm_view.toolbar.bundles
        table_actions = ["reset_composed", "add_device", "remove_device", "rerun_validation"]
        for action in table_actions:
            assert dm_view.toolbar.components.exists(action)

    @mock.patch(
        "bec_widgets.applications.views.device_manager_view.device_manager_display_widget._yes_no_question"
    )
    def test_reset_composed_view(
        self, mock_question, device_manager_display_widget: DeviceManagerDisplayWidget
    ):
        """Test reset composed view when user confirms."""
        dm_view = device_manager_display_widget
        with mock.patch.object(dm_view.device_table_view, "clear_device_configs") as mock_clear:
            mock_question.return_value = QtWidgets.QMessageBox.StandardButton.Yes
            dm_view.toolbar.components._components["reset_composed"].action.action.triggered.emit()
            mock_clear.assert_called_once()
            mock_clear.reset_mock()
            mock_question.return_value = QtWidgets.QMessageBox.StandardButton.No
            dm_view.toolbar.components._components["reset_composed"].action.action.triggered.emit()
            mock_clear.assert_not_called()

    def test_add_device_action_connected(
        self, device_manager_display_widget: DeviceManagerDisplayWidget
    ):
        """Test add device action opens dialog correctly."""
        dm_view = device_manager_display_widget
        with mock.patch.object(dm_view, "_add_device_action") as mock_add:
            dm_view.toolbar.components._components["add_device"].action.action.triggered.emit()
            mock_add.assert_called_once()

    def test_run_validate_connection_action_connected(
        self, device_manager_display_widget: DeviceManagerDisplayWidget, device_configs: dict, qtbot
    ):
        """Test run validate connection action is connected."""
        dm_view = device_manager_display_widget

        with mock.patch.object(
            dm_view.ophyd_test_view, "change_device_configs"
        ) as mock_change_configs:
            # First, add device configs to the table
            with qtbot.waitSignal(dm_view.device_table_view.device_configs_changed) as sig_blocker:
                dm_view.device_table_view.add_device_configs(device_configs)
                cfgs, added, skip_validation = sig_blocker.args
                assert cfgs == device_configs
                assert added is True
                assert skip_validation is False
            mock_change_configs.assert_called_once_with(
                device_configs=device_configs, added=True, skip_validation=False
            )  # Configs were added
            mock_change_configs.reset_mock()

            # Trigger the validate connection action without selection, should validate all
            dm_view.toolbar.components._components[
                "rerun_validation"
            ].action.action.triggered.emit()
            assert len(mock_change_configs.call_args[0][0]) == len(device_configs)
            mock_change_configs.assert_called_once_with(
                device_configs, True, True
            )  # Configs were added with connect=True
            mock_change_configs.reset_mock()

            # Select a single row and trigger again, should only validate that one
            dm_view.device_table_view.table.selectRow(0)
            dm_view.toolbar.components._components[
                "rerun_validation"
            ].action.action.triggered.emit()
            assert len(mock_change_configs.call_args[0][0]) == 1
