"""Unit tests for device_manager_components module."""

from threading import Event
from typing import Generator
from unittest import mock

import pytest
import yaml
from bec_lib.atlas_models import Device as DeviceModel
from ophyd_devices.interfaces.device_config_templates.ophyd_templates import (
    OPHYD_DEVICE_TEMPLATES,
    EpicsMotorDeviceConfigTemplate,
)
from ophyd_devices.utils.static_device_test import TestResult
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.utils.bec_list import BECList
from bec_widgets.utils.colors import get_accent_colors
from bec_widgets.widgets.control.device_manager import DeviceTable, DMConfigView, DocstringView
from bec_widgets.widgets.control.device_manager.components import docstring_to_markdown
from bec_widgets.widgets.control.device_manager.components.constants import HEADERS_HELP_MD
from bec_widgets.widgets.control.device_manager.components.device_config_template.device_config_template import (
    DeviceConfigTemplate,
)
from bec_widgets.widgets.control.device_manager.components.device_config_template.template_items import (
    DEVICE_CONFIG_FIELDS,
    DEVICE_FIELDS,
    DeviceConfigField,
    DeviceTagsWidget,
    InputLineEdit,
    LimitInputWidget,
    OnFailureComboBox,
    ParameterValueWidget,
    ReadoutPriorityComboBox,
    _try_literal_eval,
)
from bec_widgets.widgets.control.device_manager.components.device_table.device_table_row import (
    DeviceTableRow,
)
from bec_widgets.widgets.control.device_manager.components.ophyd_validation.ophyd_validation import (
    DeviceTest,
    LegendLabel,
    OphydValidation,
    ThreadPoolManager,
)
from bec_widgets.widgets.control.device_manager.components.ophyd_validation.ophyd_validation_utils import (
    ConfigStatus,
    ConnectionStatus,
    DeviceTestModel,
    format_error_to_md,
    get_validation_icons,
)
from bec_widgets.widgets.control.device_manager.components.ophyd_validation.validation_list_item import (
    ValidationButton,
    ValidationDialog,
    ValidationListItem,
)
from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch

from .client_mocks import mocked_client


class TestConstants:
    """Test class for constants and configuration values."""

    def test_headers_help_md(self):
        """Test that HEADERS_HELP_MD is a dictionary with expected keys and markdown format."""
        assert isinstance(HEADERS_HELP_MD, dict)
        expected_keys = {
            "valid",
            "connect",
            "name",
            "deviceClass",
            "readoutPriority",
            "deviceTags",
            "enabled",
            "readOnly",
            "onFailure",
            "softwareTrigger",
            "description",
        }
        assert set(HEADERS_HELP_MD.keys()) == expected_keys
        for _, value in HEADERS_HELP_MD.items():
            assert isinstance(value["long"], str)
            assert isinstance(value["short"], str)
            assert value["long"].startswith("## ")  # Each entry should start with a markdown header


# Test utility classes for docstring testing
class NumPyStyleClass:
    """Perform simple signal operations.

    Parameters
    ----------
    data : numpy.ndarray
        Input signal data.

    Attributes
    ----------
    data : numpy.ndarray
        The original signal data.

    Returns
    -------
    SignalProcessor
        An initialized signal processor instance.
    """


class GoogleStyleClass:
    """Analyze spectral properties of a signal.

    Args:
        frequencies (list[float]): Frequency bins.
        amplitudes (list[float]): Corresponding amplitude values.

    Returns:
        dict: A dictionary with spectral analysis results.

    Raises:
        ValueError: If input lists are of unequal length.
    """


class TestDocstringView:
    """Test class for DocstringView component."""

    @pytest.fixture
    def docstring_view(self, qtbot):
        """Fixture to create a DocstringView instance."""
        view = DocstringView()
        qtbot.addWidget(view)
        qtbot.waitExposed(view)
        yield view

    def test_docstring_to_markdown(self):
        """Test the docstring_to_markdown function with a sample class."""
        numpy_md = docstring_to_markdown(NumPyStyleClass)
        assert "# NumPyStyleClass" in numpy_md
        assert "### Parameters" in numpy_md
        assert "### Attributes" in numpy_md
        assert "### Returns" in numpy_md
        assert "```" in numpy_md  # Check for code block formatting

        google_md = docstring_to_markdown(GoogleStyleClass)
        assert "# GoogleStyleClass" in google_md
        assert "### Args" in google_md
        assert "### Returns" in google_md
        assert "### Raises" in google_md
        assert "```" in google_md  # Check for code block formatting

    def test_on_select_config(self, docstring_view: DocstringView):
        """Test the on_select_config method with a sample configuration."""
        with (
            mock.patch.object(docstring_view, "set_device_class") as mock_set_device_class,
            mock.patch.object(docstring_view, "_set_text") as mock_set_text,
        ):
            # Test with single device
            docstring_view.on_select_config([{"test": {"deviceClass": "NumPyStyleClass"}}])
            mock_set_device_class.assert_called_once_with("NumPyStyleClass")

            mock_set_device_class.reset_mock()
            # Test with multiple devices, should not show anything
            docstring_view.on_select_config(
                [
                    {"test": {"deviceClass": "NumPyStyleClass"}},
                    {"test": {"deviceClass": "GoogleStyleClass"}},
                ]
            )
            mock_set_device_class.assert_not_called()
            mock_set_text.assert_called_once_with("")

    def test_set_device_class(self, docstring_view: DocstringView):
        """Test the set_device_class method."""
        with mock.patch(
            "bec_widgets.widgets.control.device_manager.components.dm_docstring_view.get_plugin_class"
        ) as mock_get_plugin_class:

            # Mock a valid class retrieval
            mock_get_plugin_class.return_value = NumPyStyleClass
            docstring_view.set_device_class("NumPyStyleClass")
            assert "NumPyStyleClass" in docstring_view.toPlainText()
            assert "Parameters" in docstring_view.toPlainText()

            # Mock an invalid class retrieval
            mock_get_plugin_class.side_effect = ImportError("Class not found")
            docstring_view.set_device_class("NonExistentClass")
            assert "Error retrieving docstring for NonExistentClass" == docstring_view.toPlainText()

            # Test if READY_TO_VIEW is False
            with mock.patch(
                "bec_widgets.widgets.control.device_manager.components.dm_docstring_view.READY_TO_VIEW",
                False,
            ):
                call_count = mock_get_plugin_class.call_count
                docstring_view.set_device_class("NumPyStyleClass")  # Should do nothing
                assert mock_get_plugin_class.call_count == call_count  # No new calls made


class TestDMConfigView:
    """Test class for DMConfigView component."""

    @pytest.fixture
    def dm_config_view(self, qtbot):
        """Fixture to create a DMConfigView instance."""
        view = DMConfigView()
        qtbot.addWidget(view)
        qtbot.waitExposed(view)
        yield view

    def test_initialization(self, dm_config_view: DMConfigView):
        """Test DMConfigView proper initialization."""
        # Check that the stacked layout is set up correctly
        assert dm_config_view.stacked_layout is not None
        assert dm_config_view.stacked_layout.count() == 2
        # Assert Monaco editor is initialized
        assert dm_config_view.monaco_editor.get_language() == "yaml"
        assert dm_config_view.monaco_editor.editor._readonly is True

        # Check overlay widget
        assert dm_config_view._overlay_widget is not None
        assert dm_config_view._overlay_widget.text() == "Select a single device to view its config."

        # Check that overlay is initially shown
        assert dm_config_view.stacked_layout.currentWidget() == dm_config_view._overlay_widget

    def test_on_select_config(self, dm_config_view: DMConfigView):
        """Test DMConfigView on_select_config with empty selection."""
        # Test with empty list of configs
        dm_config_view.on_select_config([])
        assert dm_config_view.stacked_layout.currentWidget() == dm_config_view._overlay_widget

        # Test with a single config
        cfgs = [{"name": "test_device", "deviceClass": "TestClass", "enabled": True}]
        dm_config_view.on_select_config(cfgs)
        assert dm_config_view.stacked_layout.currentWidget() == dm_config_view.monaco_editor
        text = yaml.dump(cfgs[0], default_flow_style=False)
        assert text.strip("\n") == dm_config_view.monaco_editor.get_text().strip("\n")

        # Test with multiple configs
        cfgs = 2 * [{"name": "test_device", "deviceClass": "TestClass", "enabled": True}]
        dm_config_view.on_select_config(cfgs)
        assert dm_config_view.stacked_layout.currentWidget() == dm_config_view._overlay_widget
        assert dm_config_view.monaco_editor.get_text() == ""  # Should remain unchanged


class TestDeviceTableRow:
    """Test class for DeviceTableRow component."""

    @pytest.fixture
    def sample_device_data(self) -> dict:
        """Sample device data for testing."""
        return {
            "name": "test_motor",
            "deviceClass": "ophyd.EpicsMotor",
            "readoutPriority": "baseline",
            "onFailure": "retry",
            "deviceTags": {"motors", "positioning"},
            "description": "X-axis positioning motor",
            "enabled": True,
            "readOnly": False,
            "softwareTrigger": False,
        }

    @pytest.fixture
    def device_table_row(self, sample_device_data: dict):
        """Fixture to create a DeviceTableRow instance."""
        row = DeviceTableRow(data=sample_device_data)
        yield row

    def test_initialization(self, device_table_row: DeviceTableRow, sample_device_data: dict):
        """Test DeviceTableRow initialization with sample data."""
        expected_keys = list(DeviceModel.model_fields.keys())
        for key in expected_keys:
            assert key in device_table_row.data
            if key in sample_device_data:
                assert device_table_row.data[key] == sample_device_data[key]
        assert device_table_row.validation_status == (
            ConfigStatus.UNKNOWN,
            ConnectionStatus.UNKNOWN,
        )
        device_table_row.set_validation_status(ConfigStatus.VALID, ConnectionStatus.CONNECTED)
        assert device_table_row.validation_status == (
            ConfigStatus.VALID,
            ConnectionStatus.CONNECTED,
        )
        new_data = sample_device_data.copy()
        new_data["name"] = "updated_motor"
        device_table_row.set_data(new_data)
        assert device_table_row.data["name"] == new_data.get("name", "")
        assert device_table_row.validation_status == (
            ConfigStatus.UNKNOWN,
            ConnectionStatus.UNKNOWN,
        )


class TestDeviceTable:
    """Test class for DeviceTable component."""

    @pytest.fixture
    def device_table(self, qtbot, mocked_client) -> Generator[DeviceTable, None, None]:
        """Fixture to create a DeviceTable instance."""
        table = DeviceTable(client=mocked_client)
        qtbot.addWidget(table)
        qtbot.waitExposed(table)
        yield table

    @pytest.fixture
    def sample_devices(self):
        """Sample device configurations for testing."""
        return [
            {
                "name": "motor_x",
                "deviceClass": "EpicsMotor",
                "readoutPriority": "baseline",
                "onFailure": "retry",
                "deviceTags": ["motors"],
                "description": "X-axis motor",
                "enabled": True,
                "readOnly": False,
                "softwareTrigger": False,
            },
            {
                "name": "detector_main",
                "deviceClass": "ophyd.EpicsSignal",
                "readoutPriority": "async",
                "onFailure": "buffer",
                "deviceTags": ["detectors", "main"],
                "description": "Main area detector",
                "enabled": True,
                "readOnly": False,
                "softwareTrigger": True,
            },
        ]

    def test_initialization(self, device_table: DeviceTable):
        """Test DeviceTable initialization."""
        # Check table setup
        assert device_table.table.columnCount() == 11
        assert device_table.table.rowCount() == 0

        # Check headers
        expected_headers = [
            "Valid",
            "Connect",
            "Name",
            "Device Class",
            "Readout Priority",
            "On Failure",
            "Device Tags",
            "Description",
            "Enabled",
            "Read Only",
            "Software Trigger",
        ]
        for i, expected_header in enumerate(expected_headers):
            actual_header = device_table.table.horizontalHeaderItem(i).text()
            assert actual_header == expected_header

        # Check search functionality is set up
        assert device_table.search_input is not None
        assert device_table.fuzzy_is_disabled.isChecked() is False
        assert device_table.table.selectionBehavior() == QtWidgets.QAbstractItemView.SelectRows
        assert hasattr(device_table, "client_callback_id")

    def test_device_table_client_device_update_callback(
        self, device_table: DeviceTable, mocked_client, qtbot
    ):
        """
        Test that runs the client device update callback. This should update the status of devices in the table
        that are in sync with the client.

        I. First test will run a callback when no devices are in the table, should do nothing.
        II. Second test will add devices all devices from the mocked_client, then remove one
        device from the client and run the callback. The table should update the status of the
        removed device to CAN_CONNECT and all others to CONNECTED.
        """
        device_configs_changed_calls = []
        requested_update_for_multiple_device_validations = []

        def _device_configs_changed_cb(cfgs: list[dict], added: bool, skip_validation: bool):
            """Callback to capture device config changes."""
            device_configs_changed_calls.append((cfgs, added, skip_validation))

        def _requested_update_for_multiple_device_validations_cb(device_names: list):
            """Callback to capture requests for multiple device validations."""
            requested_update_for_multiple_device_validations.append(device_names)

        device_table.device_configs_changed.connect(_device_configs_changed_cb)
        device_table.request_update_multiple_device_validations.connect(
            _requested_update_for_multiple_device_validations_cb
        )

        # I. First test case with no devices in the table
        with qtbot.waitSignal(device_table.request_update_after_client_device_update) as blocker:
            device_table.request_update_after_client_device_update.emit()
            assert blocker.signal_triggered is True
            # Table should remain empty, and no updates should have occurred
            assert not device_configs_changed_calls
            assert not requested_update_for_multiple_device_validations

        # II. Second test case, add all devices from mocked client to table
        # Add all devices from mocked client to table.
        device_configs = mocked_client.device_manager._get_redis_device_config()
        device_table.add_device_configs(device_configs, skip_validation=True)
        mocked_client.device_manager.devices.pop("samx")  # Remove samx from client
        with qtbot.waitSignal(device_table.request_update_after_client_device_update) as blocker:
            validation_results = {
                cfg.get("name"): (
                    DeviceModel.model_validate(cfg).model_dump(),
                    ConfigStatus.VALID,
                    ConnectionStatus.CONNECTED,
                )
                for cfg in device_configs
            }
            with mock.patch.object(
                device_table, "get_validation_results", return_value=validation_results
            ):
                device_table.request_update_after_client_device_update.emit()
                assert blocker.signal_triggered is True
                # Table should remain empty, and no updates should have occurred
                # One for add_device_configs, one for the update
                assert len(device_configs_changed_calls) == 2
                # The first call should have one more device than the second
                assert (
                    len(device_configs_changed_calls[0][0])
                    - len(device_configs_changed_calls[1][0])
                    == 1
                )
                # Only one device should have been marked for validation update
                assert len(requested_update_for_multiple_device_validations) == 1
                assert len(requested_update_for_multiple_device_validations[0]) == 1

    def test_add_row(self, device_table: DeviceTable, sample_devices: dict):
        """Test adding a single device row."""
        device_table.add_device_configs([sample_devices[0]])

        # Verify row was added
        assert device_table.table.rowCount() == 1
        assert len(device_table.row_data) == 1
        assert "motor_x" in device_table.row_data

        # If row is added again, it should overwrite
        sample_devices[0]["deviceClass"] = "UpdateClass"
        device_table.add_device_configs([sample_devices[0]])
        assert device_table.table.rowCount() == 1
        assert len(device_table.row_data) == 1
        row_data = device_table.row_data["motor_x"]
        assert row_data is not None
        assert row_data.data.get("deviceClass") == "UpdateClass"
        assert device_table._get_cell_data(0, 3) == "UpdateClass"  # DeviceClass column
        assert device_table._get_cell_data(0, 2) == "motor_x"  # Name column
        assert device_table._get_cell_data(0, 0) == ""  # Icon column, no text
        assert device_table._get_cell_data(0, 9) == False  # Check Enabled column
        assert device_table.table.item(0, 9).checkState() == QtCore.Qt.CheckState.Unchecked
        config_status_item = device_table.table.item(0, 0)
        assert (
            config_status_item.data(QtCore.Qt.ItemDataRole.UserRole) == ConfigStatus.UNKNOWN.value
        )

    def test_update_row(self, device_table: DeviceTable, sample_devices: dict):
        """Test updating an existing device row."""
        device_table.add_device_configs([sample_devices[0]])

        assert "motor_x" in device_table.row_data
        # Update the existing row
        row: DeviceTableRow = device_table.row_data["motor_x"]
        assert row.data["description"] == "X-axis motor"
        # Change description
        sample_devices[0]["description"] = "Updated X-axis motor"
        device_table._update_row(sample_devices[0])
        row: DeviceTableRow = device_table.row_data["motor_x"]
        assert row.data["description"] == "Updated X-axis motor"
        assert row.validation_status == (ConfigStatus.UNKNOWN, ConnectionStatus.UNKNOWN)
        # Update validation status
        device_table.update_device_validation(
            sample_devices[0],
            ConfigStatus.VALID.value,
            ConnectionStatus.CONNECTED.value,
            validation_msg="",
        )
        assert row.validation_status == (ConfigStatus.VALID.value, ConnectionStatus.CONNECTED.value)
        config_status_item = device_table.table.item(0, 0)
        assert config_status_item.data(QtCore.Qt.ItemDataRole.UserRole) == ConfigStatus.VALID.value

    #####################
    ##### Test public API
    #####################

    def test_set_device_config(self, device_table: DeviceTable, sample_devices: dict, qtbot):
        """Test set device configs methods, must also emit the appropriate signal."""
        with mock.patch.object(device_table, "clear_device_configs") as mock_clear_configs:
            ###########
            # Test cases I.
            # First use case, adding new configs to empty table
            device_table.set_device_config(sample_devices)

            assert device_table.table.rowCount() == 2
            assert mock_clear_configs.call_count == 1

            # II.
            # Second use case, replacing existing configs
            device_table.set_device_config(sample_devices)
            assert device_table.table.rowCount() == 2
            assert mock_clear_configs.call_count == 2

    def test_clear_device_configs(self, device_table: DeviceTable, sample_devices: dict, qtbot):
        """Test clearing device configurations."""
        device_table.add_device_configs(sample_devices)
        assert device_table.table.rowCount() == 2
        ##########
        # Callbacks
        container = []

        def _config_changed_cb(*args, **kwargs):
            container.append((args, kwargs))

        device_table.device_configs_changed.connect(_config_changed_cb)

        ###########
        # Test cases
        # I.
        # First use case, adding new configs to empty table
        expected_calls = 1
        with qtbot.waitSignals([device_table.device_configs_changed] * expected_calls):
            device_table.clear_device_configs()

        assert len(container) == 1
        assert device_table.table.rowCount() == 0

    def test_add_device_configs(self, device_table: DeviceTable, sample_devices: dict, qtbot):
        """Test add device configs method under various scenarios."""

        ##########
        # Callbacks
        container = []

        def _config_changed_cb(*args, **kwargs):
            container.append((args, kwargs))

        device_table.device_configs_changed.connect(_config_changed_cb)

        ###########
        # Test cases
        # I.
        # First use case, adding new configs to empty table
        expected_calls = 1
        with qtbot.waitSignals([device_table.device_configs_changed] * expected_calls):
            device_table.add_device_configs(sample_devices)

        assert len(container) == 1
        assert container[0][0][0] == sample_devices
        assert container[0][0][1] is True
        assert device_table.table.rowCount() == 2

        # II.
        # If added again, old configs should be removed first, and new ones added
        # Reset container
        container = []
        expected_calls = 2
        with qtbot.waitSignals([device_table.device_configs_changed] * expected_calls):
            device_table.add_device_configs(sample_devices)

        assert len(container) == 2
        assert container[0][0][1] is False
        assert container[1][0][0] == sample_devices
        assert container[1][0][1] is True

        # Verify rows were added
        assert device_table.table.rowCount() == 2
        assert len(device_table.row_data) == 2
        assert "motor_x" in device_table.row_data
        assert "detector_main" in device_table.row_data

    def test_update_device_configs(self, device_table: DeviceTable, sample_devices: dict, qtbot):
        """Test updating device configurations."""

        # Callbacks
        container = []

        def _config_changed_cb(*args, **kwargs):
            container.append((args, kwargs))

        device_table.device_configs_changed.connect(_config_changed_cb)

        # First case I.
        # Update to empty table should add rows, and emit signal with added=True
        expected_calls = 1

        with qtbot.waitSignals([device_table.device_configs_changed] * expected_calls) as blocker:
            device_table.update_device_configs(sample_devices)

        # Verify signal emission
        assert len(container) == 1
        assert container[0][0][0] == sample_devices
        assert container[0][0][1] is True

        # Second case II.
        # Update existing configs should modify rows, and change the validation status to unknown
        # for the device that was changed
        container = []
        sample_devices[0]["description"] = "Modified description"
        expected_calls = 1
        with qtbot.waitSignals([device_table.device_configs_changed] * expected_calls):
            device_table.update_device_configs(sample_devices)

        # Verify signal emission
        assert len(container) == 1
        assert container[0][0][0] == [sample_devices[0]]
        assert container[0][0][1] is True

    def test_get_device_config(self, device_table: DeviceTable, sample_devices: dict):
        """Test retrieving device configurations."""
        device_table.add_device_configs(sample_devices)

        retrieved_configs = device_table.get_device_config()
        assert len(retrieved_configs) == 2

        # Check that we can find our test devices
        device_names = [config["name"] for config in retrieved_configs]
        assert "motor_x" in device_names
        assert "detector_main" in device_names

    def test_search_functionality(self, device_table: DeviceTable, sample_devices: dict, qtbot):
        """Test search/filter functionality."""
        device_table.add_device_configs(sample_devices)

        # Test filtering by name
        qtbot.keyClicks(device_table.search_input, "motor")
        qtbot.wait(100)  # Allow filter to apply

        # Should show only motor device
        visible_rows = 0
        for row in range(device_table.table.rowCount()):
            if not device_table.table.isRowHidden(row):
                visible_rows += 1
        assert visible_rows == 1

    def test_remove_device_configs(self, device_table: DeviceTable, sample_devices: dict, qtbot):
        """Test removing device configurations."""
        device_table.add_device_configs(sample_devices)
        assert device_table.table.rowCount() == 2

        # Remove one device
        with qtbot.waitSignal(device_table.device_configs_changed) as blocker:
            device_table.remove_device_configs([sample_devices[0]])

        # Verify signal emission
        emitted_configs, added, skip_validation = blocker.args
        assert len(emitted_configs) == 1
        assert added is False
        assert skip_validation is True

        # Verify row was removed
        assert device_table.table.rowCount() == 1
        assert "motor_x" not in device_table.row_data
        assert "detector_main" in device_table.row_data

    def test_validation_status_update(self, device_table: DeviceTable, sample_devices: dict):
        """Test updating validation status."""
        device_table: DeviceTable
        device_table.add_device_configs(sample_devices)

        # Update validation status for one device
        device_table.update_device_validation(
            sample_devices[0],
            ConfigStatus.VALID,
            ConnectionStatus.CONNECTED,
            validation_msg="Test passed",
        )

        # Verify status was updated in the row
        motor_row = device_table.row_data["motor_x"]
        assert motor_row.validation_status == (ConfigStatus.VALID, ConnectionStatus.CONNECTED)

    def test_selection_handling(self, device_table: DeviceTable, sample_devices: dict, qtbot):
        """Test device selection and signal emission."""
        device_table.add_device_configs(sample_devices)

        # Select first row
        with qtbot.waitSignal(device_table.selected_devices) as blocker:
            device_table.table.selectRow(0)

        # Verify selection signal was emitted
        selected_configs = blocker.args[0]
        assert len(selected_configs) == 1
        assert list(selected_configs[0].keys())[0] in ["motor_x", "detector_main"]


class TestOphydValidation:
    """
    Test class for the Ophyd test module. This tests the OphydValidation widget,
    the validation list items and dialog, and the utility functions related to
    device testing and validation.
    """

    ################
    ### Ophyd_test_utils tests
    ################

    def test_format_error_to_md(self):
        """Test the format_error_to_md utility function."""
        device_name = "non_existing_device"
        error_msg = """ERROR: non_existing_device is not valid: 3 validation errors for Device\nenabled\n  Field required [type=missing, input_value={'name': 'non_existing_de...e': 'NonExistingDevice'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.11/v/missing\ndeviceClass\n  Field required [type=missing, input_value={'name': 'non_existing_de...e': 'NonExistingDevice'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.11/v/missing\nreadoutPriority\n  Field required [type=missing, input_value={'name': 'non_existing_de...e': 'NonExistingDevice'}, input_type=dict]\n    For further information visit https://errors.pydantic.dev/2.11/v/missing\nERROR: non_existing_device is not valid: 'deviceClass'"""
        md_output = format_error_to_md(device_name, error_msg)
        assert f"## Error for {device_name}\n\n**{device_name} is not valid**" in md_output
        assert "3 validation errors for Device" in md_output

    def test_description_validation_status(self):
        """Test descriptions for ConfigStatus enum values."""
        # ConfigStatus descriptions
        assert ConfigStatus.VALID.description() == "Valid Configuration"
        assert ConfigStatus.INVALID.description() == "Invalid Configuration"
        assert ConfigStatus.UNKNOWN.description() == "Unknown"

        # ConnectionStatus descriptions
        assert ConnectionStatus.CANNOT_CONNECT.description() == "Cannot Connect"
        assert ConnectionStatus.CAN_CONNECT.description() == "Can Connect"
        assert ConnectionStatus.CONNECTED.description() == "Connected and Loaded"
        assert ConnectionStatus.UNKNOWN.description() == "Unknown"

    def test_device_test_model(self):
        """Test the DeviceTestModel"""
        data = {
            "uuid": "1234",
            "device_name": "test_device",
            "device_config": {"name": "test_device", "deviceClass": "TestClass"},
            "config_status": ConfigStatus.VALID.value,
            "connection_status": ConnectionStatus.CONNECTED.value,
            "validation_messages": "All good",
        }
        model = DeviceTestModel.model_validate(data)
        assert model.uuid == "1234"
        assert model.device_name == "test_device"

    def test_get_validation_icons(self):
        """Test the get_validation_icons utility function."""
        colors = get_accent_colors()
        icons = get_validation_icons(colors, (16, 16))

        # Check that icons for all statuses are present
        for status in ConfigStatus:
            assert status in icons["config_status"]
            assert isinstance(icons["config_status"][status], QtGui.QIcon)

        for status in ConnectionStatus:
            assert status in icons["connection_status"]
            assert isinstance(icons["connection_status"][status], QtGui.QIcon)

    ################
    ### ValidationListItem tests
    ################

    @pytest.fixture
    def validation_button(self, qtbot):
        """Fixture to create a ValidationButton instance."""
        colors = get_accent_colors()
        icons = get_validation_icons(colors, (16, 16))
        icon = icons["config_status"][ConfigStatus.VALID.value]
        button = ValidationButton(icon=icon)

        qtbot.addWidget(button)
        qtbot.waitExposed(button)
        yield button

    def test_validation_button_initialization(self, validation_button: ValidationButton):
        """Test ValidationButton initialization."""
        assert validation_button.isFlat() is True
        assert validation_button.isEnabled() is True
        assert isinstance(validation_button.icon(), QtGui.QIcon)
        assert validation_button.styleSheet() == ""
        validation_button.setEnabled(False)
        assert validation_button.styleSheet() == ""

    @pytest.fixture
    def validation_dialog(self, qtbot):
        """Fixture for ValidationDialog."""
        dialog = ValidationDialog()
        qtbot.addWidget(dialog)
        qtbot.waitExposed(dialog)
        yield dialog

    def test_validation_dialog(self, validation_dialog: ValidationDialog, qtbot):
        """Test ValidationDialog initialization."""
        assert validation_dialog.timeout_spin.value() == 5
        assert validation_dialog.connect_checkbox.isChecked() is False
        assert validation_dialog.force_connect_checkbox.isChecked() is False

        # Change timeout
        validation_dialog.timeout_spin.setValue(10)
        # Result should not update yet
        assert validation_dialog.result() == (5, False, False)
        # Click accept
        with qtbot.waitSignal(validation_dialog.accepted):
            qtbot.mouseClick(
                validation_dialog.button_box.button(QtWidgets.QDialogButtonBox.Ok),
                QtCore.Qt.LeftButton,
            )
        assert validation_dialog.result() == (10, False, False)

    @pytest.fixture
    def device_model(self):
        """Fixture to create a sample DeviceTestModel instance."""
        config = DeviceModel(
            name="test_device", deviceClass="TestClass", readoutPriority="baseline", enabled=True
        )
        data = {
            "uuid": "1234",
            "device_name": config.name,
            "device_config": config.model_dump(),
            "config_status": ConfigStatus.VALID.value,
            "connection_status": ConnectionStatus.CONNECTED.value,
            "validation_messages": "All good",
        }
        model = DeviceTestModel.model_validate(data)
        yield model

    @pytest.fixture
    def validation_list_item(self, device_model, qtbot):
        """Fixture to create a ValidationListItem instance."""
        colors = get_accent_colors()
        icons = get_validation_icons(colors, (16, 16))
        item = ValidationListItem(device_model=device_model, validation_icons=icons)
        qtbot.addWidget(item)
        qtbot.waitExposed(item)
        yield item

    def test_update_validation_status(self, validation_list_item: ValidationListItem):
        """Test updating status in ValidationListItem."""
        # Update to invalid config status
        validation_list_item._update_validation_status(
            validation_msg="Error occurred",
            config_status=ConfigStatus.INVALID.value,
            connection_status=ConnectionStatus.CANNOT_CONNECT.value,
        )
        assert validation_list_item.device_model.config_status == ConfigStatus.INVALID.value
        assert (
            validation_list_item.device_model.connection_status
            == ConnectionStatus.CANNOT_CONNECT.value
        )
        assert validation_list_item.device_model.validation_msg == "Error occurred"

    def test_validation_logic(self, validation_list_item: ValidationListItem):
        """Test starting and stopping validation spinner."""
        # Schedule validation
        validation_list_item.validation_scheduled()
        assert validation_list_item.status_button.isEnabled() is False
        assert validation_list_item.connection_button.isEnabled() is False
        assert validation_list_item.is_running is False

        # Start validation
        with mock.patch.object(validation_list_item._spinner, "start") as mock_spinner_start:
            validation_list_item.start_validation()
            assert validation_list_item.is_running is True
            mock_spinner_start.assert_called_once()

        # Finish validation

        with mock.patch.object(validation_list_item._spinner, "stop") as mock_spinner_stop:

            # I. successful validation
            validation_list_item.on_validation_finished(
                validation_msg="Finished",
                config_status=ConfigStatus.VALID.value,
                connection_status=ConnectionStatus.CAN_CONNECT.value,
            )
            assert validation_list_item.is_running is False
            assert (
                validation_list_item.device_model.connection_status
                == ConnectionStatus.CAN_CONNECT.value
            )
            mock_spinner_stop.assert_called_once()
            # Buttons should be disabled after validation finished good
            assert validation_list_item.connection_button.isEnabled() is False
            assert validation_list_item.status_button.isEnabled() is False

            # Restart validation
            validation_list_item.start_validation()
            mock_spinner_stop.reset_mock()

            # II. failed validation
            validation_list_item.on_validation_finished(
                validation_msg="Finished",
                config_status=ConfigStatus.INVALID.value,
                connection_status=ConnectionStatus.UNKNOWN.value,
            )
            assert validation_list_item.is_running is False
            mock_spinner_stop.assert_called_once()
            assert validation_list_item.connection_button.isEnabled() is True
            assert validation_list_item.status_button.isEnabled() is True

    ####################
    ### OphydValidation widget tests
    ####################

    @pytest.fixture
    def device_test_runnable(self, device_model, qtbot):
        """Fixture to create a DeviceTest instance."""
        widget = QtWidgets.QWidget()  # Create a widget because the runnable is not a widget itself
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        widget._runnable_test = DeviceTest(
            device_model=device_model, timeout=5, enable_connect=True, force_connect=False
        )
        yield widget

    def test_device_test(self, device_test_runnable, qtbot):
        """Test DeviceTest runnable initialization."""
        runnable: DeviceTest = device_test_runnable._runnable_test
        assert runnable.device_config.get("name") == "test_device"
        assert runnable.timeout == 5
        assert runnable.enable_connect is True
        assert runnable._cancelled is False

        # Callback validation
        container = []

        def _runnable_callback(
            config: dict, config_is_valid: bool, connection_status: bool, error_msg: str
        ):
            container.append((config, config_is_valid, connection_status, error_msg))

        runnable.signals.device_validated.connect(_runnable_callback)

        # Callback started
        started_container = []

        def _runnable_started_callback():
            started_container.append(True)

        runnable.signals.device_validation_started.connect(_runnable_started_callback)

        # Should resolve without running test if cancelled
        runnable.cancel()
        with qtbot.waitSignals(
            [runnable.signals.device_validation_started, runnable.signals.device_validated]
        ):
            runnable.run()
            assert len(started_container) == 1
            assert len(container) == 1
            config, config_is_valid, connection_status, error_msg = container[0]
            assert config == runnable.device_config
            assert config_is_valid == ConfigStatus.UNKNOWN.value
            assert connection_status == ConnectionStatus.UNKNOWN.value
            assert error_msg == f"{runnable.device_config.get('name', '')} was cancelled by user."

        # Now we run it without cancelling

        # Reset containers
        container = []
        started_container = []
        runnable._cancelled = False
        with mock.patch.object(
            runnable.tester, "run_with_list_output"
        ) as mock_run_with_list_output:
            mock_run_with_list_output.return_value = [
                TestResult(
                    name="test_device",
                    config_is_valid=ConfigStatus.VALID.value,
                    success=ConnectionStatus.CANNOT_CONNECT.value,
                    message="All good",
                )
            ]
            with qtbot.waitSignals(
                [runnable.signals.device_validation_started, runnable.signals.device_validated]
            ):
                runnable.run()
                assert len(started_container) == 1
                assert len(container) == 1
                config, config_is_valid, connection_status, error_msg = container[0]
                assert config == runnable.device_config
                assert config_is_valid == ConfigStatus.VALID.value
                assert connection_status == ConnectionStatus.CANNOT_CONNECT.value
                assert error_msg == "All good"

    @pytest.fixture
    def thread_pool_manager(self, qtbot):
        """Fixture to create a ThreadPoolManager instance."""
        widget = QtWidgets.QWidget()  # Create a widget because the manager is not a widget itself
        widget._pool_manager = ThreadPoolManager()
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        yield widget

    def test_thread_pool_manager(self, thread_pool_manager):
        """Test ThreadPoolManager initialization."""
        manager: ThreadPoolManager = thread_pool_manager._pool_manager
        assert manager.pool.maxThreadCount() == 4
        assert manager._timer.interval() == 100

        # Test submitting tasks
        device_test_mock_1 = mock.MagicMock()
        device_test_mock_2 = mock.MagicMock()
        manager.submit(device_name="test_device", device_test=device_test_mock_1)
        manager.submit(device_name="test_device_2", device_test=device_test_mock_2)
        assert len(manager.get_scheduled_tests()) == 2
        assert len(manager.get_active_tests()) == 0

        # Clear queue
        manager.clear_queue()
        assert device_test_mock_1.cancel.call_count == 1
        assert device_test_mock_2.cancel.call_count == 1
        assert device_test_mock_1.signals.device_validated.disconnect.call_count == 1
        assert device_test_mock_2.signals.device_validated.disconnect.call_count == 1
        assert len(manager.get_scheduled_tests()) == 0
        assert len(manager.get_active_tests()) == 0

    def test_thread_pool_process_queue(self, thread_pool_manager, qtbot):
        """Test ThreadPoolManager process queue logic."""
        # Submit 2 elements to the queue
        manager: ThreadPoolManager = thread_pool_manager._pool_manager
        device_test_mock_1 = mock.MagicMock()
        device_test_mock_2 = mock.MagicMock()
        manager.submit(device_name="test_device", device_test=device_test_mock_1)
        manager.submit(device_name="test_device_2", device_test=device_test_mock_2)

        # Validations running cb
        container = []

        def _validations_running_cb(is_true: bool):
            container.append(is_true)

        manager.validations_are_running.connect(_validations_running_cb)
        with mock.patch.object(manager.pool, "start") as mock_pool_start:
            with qtbot.waitSignal(manager.validations_are_running):
                # Process queue, should start both tasks
                manager._process_queue()
                assert mock_pool_start.call_count == 2
                assert len(manager.get_scheduled_tests()) == 0
                assert len(manager.get_active_tests()) == 2
                assert len(container) == 1
                assert container[0] is True
                device_test_mock_1.signals.device_validated.connect.assert_called_with(
                    manager._on_task_finished
                )
                device_test_mock_2.signals.device_validated.connect.assert_called_with(
                    manager._on_task_finished
                )

            # Simulate one task finished
            manager._on_task_finished({"name": "test_device"}, True, True, "All good")
            assert len(manager.get_active_tests()) == 1

            # Process queue again, nothing should happen as queue is empty
            mock_pool_start.reset_mock()
            manager._process_queue()
            assert mock_pool_start.call_count == 0
            assert len(manager.get_active_tests()) == 1

    @pytest.fixture
    def legend_label(self, qtbot):
        """Fixture to create a TestLegendLabel instance."""
        label = LegendLabel()
        qtbot.addWidget(label)
        qtbot.waitExposed(label)
        yield label

    def test_legend_label(self, legend_label: LegendLabel):
        """Test LegendLabel."""
        layout: QtWidgets.QGridLayout = legend_label.layout()
        # Verify layout structure
        assert layout.rowCount() == 2
        assert layout.columnCount() == 6
        # Assert labels and icons are present
        label = layout.itemAtPosition(0, 0).widget()
        assert label.text() == "Config Legend:"
        label = layout.itemAtPosition(1, 0).widget()
        assert label.text() == "Connect Legend:"

    @pytest.fixture
    def ophyd_test(self, qtbot, mocked_client):
        """Fixture to create an OphydValidation instance. We patch the method that starts the polling loop to avoid side effects."""
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
            widget = OphydValidation(client=mocked_client)
            qtbot.addWidget(widget)
            qtbot.waitExposed(widget)
            yield widget

    def test_ophyd_test_initialization(self, ophyd_test: OphydValidation, qtbot):
        """Test OphydValidation widget initialization."""
        assert isinstance(ophyd_test.list_widget, BECList)
        assert isinstance(ophyd_test.thread_pool_manager, ThreadPoolManager)
        layout = ophyd_test.layout()
        # Widget with layout + legend label
        assert isinstance(layout.itemAt(1).widget(), LegendLabel)

        # Test clicking the stop validation button
        click_event = Event()

        def _stop_validation_button_clicked():
            click_event.set()

        ophyd_test._stop_validation_button.clicked.connect(_stop_validation_button_clicked)
        with qtbot.waitSignal(ophyd_test._stop_validation_button.clicked):
            # Simulate click
            qtbot.mouseClick(ophyd_test._stop_validation_button, QtCore.Qt.LeftButton)
        assert click_event.is_set()

    def test_ophyd_test_keep_visible_after_validation(self, ophyd_test: OphydValidation, qtbot):
        """Test the keep visible after validation logic."""
        # Initially false
        assert len(ophyd_test._keep_visible_after_validation) == 0

        # Add device to keep visible
        ophyd_test.add_device_to_keep_visible_after_validation("device_1")
        assert "device_1" in ophyd_test._keep_visible_after_validation
        # Add second device
        ophyd_test.add_device_to_keep_visible_after_validation("device_2")
        assert "device_2" in ophyd_test._keep_visible_after_validation
        assert len(ophyd_test._keep_visible_after_validation) == 2

        # Remove device
        ophyd_test.remove_device_to_keep_visible_after_validation("device_1")
        assert "device_1" not in ophyd_test._keep_visible_after_validation
        assert "device_2" in ophyd_test._keep_visible_after_validation

        # Change config with skip validation and device in keep visible list
        with (
            mock.patch.object(
                ophyd_test, "_is_device_in_redis_session", return_value=True
            ) as mock_is_device_in_redis_session,
            mock.patch.object(ophyd_test, "_add_device_config") as mock_add_device_config,
            mock.patch.object(ophyd_test.list_widget, "get_widget") as mock_get_widget,
        ):
            ophyd_test.change_device_configs(
                [{"name": "device_2", "deviceClass": "TestClass"}],
                added=True,
                skip_validation=False,
            )
            mock_add_device_config.assert_called_once()
            mock_get_widget.assert_called_once_with("device_2")

    def test_ophyd_test_adding_devices(self, ophyd_test: OphydValidation, qtbot):
        """Test adding devices to OphydValidation widget."""
        sample_devices = [
            {
                "name": "motor_x",
                "deviceClass": "EpicsMotor",
                "readoutPriority": "baseline",
                "onFailure": "retry",
                "deviceTags": ["motors"],
                "description": "X-axis motor",
                "enabled": True,
                "readOnly": False,
                "softwareTrigger": False,
            },
            {
                "name": "detector_main",
                "deviceClass": "ophyd.EpicsSignal",
                "readoutPriority": "async",
                "onFailure": "buffer",
                "deviceTags": ["detectors", "main"],
                "description": "Main area detector",
                "enabled": True,
                "readOnly": False,
                "softwareTrigger": True,
            },
        ]
        # Initially empty, add devices
        with mock.patch.object(ophyd_test, "__delayed_submit_test") as mock_submit_test:
            ophyd_test.change_device_configs(sample_devices, added=True)
            assert len(ophyd_test.get_device_configs()) == 2

            # Adding again should overwrite existing ones
            with mock.patch.object(ophyd_test, "_remove_device_config") as mock_remove_configs:
                ophyd_test.change_device_configs(sample_devices, added=True)
                assert len(ophyd_test.get_device_configs()) == 2
                assert mock_remove_configs.call_count == 2  # Once for each device

            # Click item in list
            item = ophyd_test.list_widget.item(0)
            with qtbot.waitSignal(ophyd_test.item_clicked) as blocker:
                qtbot.mouseClick(
                    ophyd_test.list_widget.viewport(),
                    QtCore.Qt.LeftButton,
                    pos=ophyd_test.list_widget.visualItemRect(item).center(),
                )
                device_name = blocker.args[0]
                assert (
                    ophyd_test.list_widget.get_widget_for_item(item).device_model.device_name
                    == device_name
                )

            # Clear running validation
            with (
                mock.patch.object(
                    ophyd_test.thread_pool_manager, "clear_device_in_queue"
                ) as mock_clear,
                mock.patch.object(ophyd_test, "_on_device_test_completed") as mock_on_completed,
            ):
                ophyd_test.cancel_validation("motor_x")
                mock_clear.assert_called_once_with("motor_x")
                mock_on_completed.assert_called_once_with(
                    sample_devices[0],
                    ConfigStatus.UNKNOWN.value,
                    ConnectionStatus.UNKNOWN.value,
                    "motor_x was cancelled by user.",
                )

    def test_ophyd_test_submit_test(
        self, ophyd_test: OphydValidation, validation_list_item: ValidationListItem, qtbot
    ):
        """Test submitting a device test to the thread pool manager."""
        with (
            mock.patch.object(
                validation_list_item, "validation_scheduled"
            ) as mock_validation_scheduled,
            mock.patch.object(ophyd_test.thread_pool_manager, "submit") as mock_thread_pool_submit,
        ):
            ophyd_test._submit_test(
                validation_list_item, connect=True, force_connect=False, timeout=10
            )
            mock_validation_scheduled.assert_called_once()
            mock_thread_pool_submit.assert_called_once()

            mock_validation_scheduled.reset_mock()
            mock_thread_pool_submit.reset_mock()
            # Assume device is already in Redis
            with (
                mock.patch.object(ophyd_test, "_is_device_in_redis_session") as mock_in_redis,
                mock.patch.object(ophyd_test, "_remove_device_config") as mock_remove_device,
            ):
                mock_in_redis.return_value = True
                with qtbot.waitSignal(ophyd_test.validation_completed) as blocker:
                    ophyd_test._submit_test(
                        validation_list_item, connect=True, force_connect=False, timeout=10
                    )
                    mock_validation_scheduled.assert_not_called()
                    mock_thread_pool_submit.assert_not_called()
                    assert validation_list_item.device_model.device_config == blocker.args[0]
                    assert blocker.args[1] is ConfigStatus.VALID.value
                    assert blocker.args[2] is ConnectionStatus.CONNECTED.value

    def test_ophyd_test_compare_device_configs(self, ophyd_test: OphydValidation):
        """Test comparing device configurations."""
        device_config_1 = {
            "name": "motor_x",
            "deviceClass": "EpicsMotor",
            "readoutPriority": "baseline",
            "onFailure": "retry",
            "deviceTags": ["motors"],
            "description": "X-axis motor",
            "enabled": True,
            "readOnly": False,
            "softwareTrigger": False,
        }
        device_config_2 = device_config_1.copy()
        # Should be equal
        assert ophyd_test._compare_device_configs(device_config_1, device_config_2) is True

        # Change a field
        device_config_2["description"] = "Modified description"
        assert ophyd_test._compare_device_configs(device_config_1, device_config_2) is False

    @pytest.mark.parametrize(
        "config_status,connection_status, msg",
        [
            (ConfigStatus.VALID.value, ConnectionStatus.CONNECTED.value, "Validation successful"),
            (
                ConfigStatus.INVALID.value,
                ConnectionStatus.CANNOT_CONNECT.value,
                "Validation failed",
            ),
        ],
    )
    def test_ophyd_test_validation_succeeds(
        self, ophyd_test: OphydValidation, qtbot, config_status, connection_status, msg
    ):
        """Test handling of successful device validation."""
        sample_device = {
            "name": "motor_x",
            "deviceClass": "EpicsMotor",
            "readoutPriority": "baseline",
            "onFailure": "retry",
            "deviceTags": ["motors"],
            "description": "X-axis motor",
            "enabled": True,
            "readOnly": False,
            "softwareTrigger": False,
        }
        with (
            mock.patch.object(ophyd_test, "__delayed_submit_test") as mock_submit_test,
            mock.patch.object(ophyd_test, "_is_device_in_redis_session", return_value=False),
        ):
            ophyd_test.change_device_configs([sample_device], added=True)

            # Emit validation completed signal from thread pool manager
            with qtbot.waitSignal(ophyd_test.validation_completed) as blocker:
                validation_item = ophyd_test.list_widget.get_widget_for_item(
                    ophyd_test.list_widget.item(0)
                )
                with mock.patch.object(
                    validation_item, "on_validation_finished"
                ) as mock_on_validation_finished:
                    ophyd_test.thread_pool_manager.device_validated.emit(
                        sample_device, config_status, connection_status, msg
                    )
                    if config_status != ConfigStatus.VALID.value:
                        mock_on_validation_finished.assert_called_once_with(
                            validation_msg=msg,
                            config_status=config_status,
                            connection_status=connection_status,
                        )

                    assert blocker.args[0] == sample_device
                    assert blocker.args[1] == config_status
                    assert blocker.args[2] == connection_status
                    assert blocker.args[3] == msg


class TestDeviceConfigTemplate:

    def test_try_literal_eval(self):
        """Test the _try_literal_eval static method."""
        # handle booleans
        assert _try_literal_eval("True") is True
        assert _try_literal_eval("False") is False
        assert _try_literal_eval("true") is True
        assert _try_literal_eval("false") is False
        # handle empty string
        assert _try_literal_eval("") == ""
        # Lists
        assert _try_literal_eval([0, 1, 2]) == [0, 1, 2]
        # Set and tuples
        assert _try_literal_eval((1, 2, 3)) == (1, 2, 3)
        # Numbers int and float
        assert _try_literal_eval("123") == 123
        assert _try_literal_eval("45.67") == 45.67
        # if literal eval fails, return original string
        assert _try_literal_eval(" invalid text,,, ") == " invalid text,,, "

    def _create_widget_for_device_field(self, field_name: str, qtbot) -> QtWidgets.QWidget:
        """Helper method to create a widget for a given device field."""
        field = DEVICE_FIELDS[field_name]
        widget = field.widget_cls()
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        return widget

    def test_device_fields_name(self, qtbot):
        """Test DEVICE_FIELDS content for 'name' field."""
        colors = get_accent_colors()
        name_field: DeviceConfigField = DEVICE_FIELDS["name"]
        assert name_field.label == "Name"
        assert name_field.widget_cls == InputLineEdit
        assert name_field.required is True
        # Create widget and test
        widget: InputLineEdit = self._create_widget_for_device_field("name", qtbot)
        if name_field.validation_callback is not None:
            for cb in name_field.validation_callback:
                widget.register_validation_callback(cb)
        # Empty input is invalid
        assert widget.styleSheet() == f"border: 1px solid {colors.emergency.name()};"
        # Valid input
        with qtbot.waitSignal(widget.textChanged):
            widget.setText("valid_device_name")
        assert widget.styleSheet() == ""
        # InValid input
        with qtbot.waitSignal(widget.textChanged):
            widget.setText("invalid _name")
        assert widget.styleSheet() == f"border: 1px solid {colors.emergency.name()};"

    def test_device_fields_device_class(self, qtbot):
        """Test DEVICE_FIELDS content for 'deviceClass' field."""
        colors = get_accent_colors()
        device_class_field: DeviceConfigField = DEVICE_FIELDS["deviceClass"]
        assert device_class_field.label == "Device Class"
        assert device_class_field.widget_cls == InputLineEdit
        assert device_class_field.required is True
        # Create widget and test
        widget: InputLineEdit = self._create_widget_for_device_field("deviceClass", qtbot)
        if device_class_field.validation_callback is not None:
            for cb in device_class_field.validation_callback:
                widget.register_validation_callback(cb)
        # Empty input is invalid
        assert widget.styleSheet() == f"border: 1px solid {colors.emergency.name()};"
        # Valid input
        with qtbot.waitSignal(widget.textChanged):
            widget.setText("EpicsMotor")
        assert widget.styleSheet() == ""
        # InValid input
        with qtbot.waitSignal(widget.textChanged):
            widget.setText("wrlong-sadnjkas:'&")
        assert widget.styleSheet() == f"border: 1px solid {colors.emergency.name()};"

    def test_device_fields_description(self, qtbot):
        """Test DEVICE_FIELDS content for 'description' field."""
        description_field: DeviceConfigField = DEVICE_FIELDS["description"]
        assert description_field.label == "Description"
        assert description_field.widget_cls == QtWidgets.QTextEdit
        assert description_field.required is False
        assert description_field.placeholder_text == "Short device description"
        # Create widget and test
        widget: QtWidgets.QTextEdit = self._create_widget_for_device_field("description", qtbot)

    def test_device_fields_toggle_fields(self, qtbot):
        """Test DEVICE_FIELDS content for 'enabled' and 'readOnly' fields."""
        for field_name in ["enabled", "readOnly", "softwareTrigger"]:
            field: DeviceConfigField = DEVICE_FIELDS[field_name]
            assert field.label in ["Enabled", "Read Only", "Software Trigger"]
            assert field.widget_cls == ToggleSwitch
            assert field.required is False
            if field_name == "enabled":
                assert field.default is True
            else:
                assert field.default is False

    @pytest.fixture
    def device_config_template(self, qtbot):
        """Fixture to create a DeviceConfigTemplate instance."""
        template = DeviceConfigTemplate()
        qtbot.addWidget(template)
        qtbot.waitExposed(template)
        yield template

    def test_device_config_teamplate_default_init(
        self, device_config_template: DeviceConfigTemplate, qtbot
    ):
        """Test DeviceConfigTemplate default initialization."""
        assert (
            device_config_template.template
            == OPHYD_DEVICE_TEMPLATES["CustomDevice"]["CustomDevice"]
        )

        # Check settings box, should have 3 labels, 2 InputLineEdit, 1 QTextEdit
        assert len(device_config_template.settings_box.findChildren(QtWidgets.QLabel)) == 3
        assert len(device_config_template.settings_box.findChildren(InputLineEdit)) == 2
        assert len(device_config_template.settings_box.findChildren(QtWidgets.QTextEdit)) == 1

        # Check advanced control box, should have 5 labels for
        # readoutPriority, onFailure, enabled, readOnly, softwareTrigger
        assert len(device_config_template.advanced_control_box.findChildren(QtWidgets.QLabel)) == 5
        assert len(device_config_template.advanced_control_box.findChildren(ToggleSwitch)) == 3
        assert (
            len(device_config_template.advanced_control_box.findChildren(ReadoutPriorityComboBox))
            == 1
        )
        assert len(device_config_template.advanced_control_box.findChildren(OnFailureComboBox)) == 1

        # Check connection box for CustomDevice, should be empty dict.
        assert isinstance(
            device_config_template.connection_settings_box.layout().itemAt(0).widget(),
            ParameterValueWidget,
        )

        # Check additional settings box for CustomDevice, should be empty dict.
        tool_box = device_config_template.additional_settings_box.layout().itemAt(0).widget()
        assert isinstance(tool_box, QtWidgets.QToolBox)
        assert isinstance(device_config_template._widgets["userParameter"], ParameterValueWidget)
        assert isinstance(device_config_template._widgets["deviceTags"], DeviceTagsWidget)

        # Check default values and proper widgets in _widgets dict
        for field_name, widget in device_config_template._widgets.items():
            if field_name == "deviceConfig":
                assert isinstance(widget, ParameterValueWidget)
                assert widget.parameters() == {}  # Default empty dict for CustomDevice template
                continue
            assert field_name in DEVICE_FIELDS
            field = DEVICE_FIELDS[field_name]
            assert isinstance(widget, field.widget_cls)
            # Check default values
            if field.default is not None:
                if isinstance(widget, InputLineEdit):
                    assert widget.text() == str(field.default)
                elif isinstance(widget, ToggleSwitch):
                    assert widget.isChecked() == field.default
                elif isinstance(widget, (ReadoutPriorityComboBox, OnFailureComboBox)):
                    assert widget.currentText() == field.default

    def test_device_config_template_epics_motor(
        self, device_config_template: DeviceConfigTemplate, qtbot
    ):
        """Test the DeviceConfigTemplate for the EpicsMotor device class."""
        device_config_template.change_template(OPHYD_DEVICE_TEMPLATES["EpicsMotor"]["EpicsMotor"])

        # Check that all widgets are created properly
        for field_name, widget in device_config_template._widgets.items():
            if field_name == "deviceConfig":
                for sub_field, sub_widget in widget.items():
                    if sub_field in DEVICE_CONFIG_FIELDS:
                        field = DEVICE_CONFIG_FIELDS[sub_field]
                        assert isinstance(sub_widget, field.widget_cls)
                        if sub_field == "limits":
                            # Limits is LimitInputWidget
                            sub_widget: LimitInputWidget
                            assert sub_widget.get_limits() == [0, 0]  # Default limits
                    else:
                        assert isinstance(widget, InputLineEdit)
                continue
            assert field_name in DEVICE_FIELDS
            field = DEVICE_FIELDS[field_name]
            assert isinstance(widget, field.widget_cls)
            # Check default values
            if field.default is not None:
                if isinstance(widget, InputLineEdit):
                    assert widget.text() == str(field.default)
                elif isinstance(widget, ToggleSwitch):
                    assert widget.isChecked() == field.default
                elif isinstance(widget, (ReadoutPriorityComboBox, OnFailureComboBox)):
                    assert widget.currentText() == field.default

    def test_device_config_template_get_set_config(
        self, device_config_template: DeviceConfigTemplate, qtbot
    ):
        # Test get config for default Custom Device template
        device_config_template.change_template(OPHYD_DEVICE_TEMPLATES["EpicsMotor"]["EpicsMotor"])
        config = device_config_template.get_config_fields()
        for k, v in OPHYD_DEVICE_TEMPLATES["EpicsMotor"]["EpicsMotor"].items():
            if k == "deviceConfig":
                v: EpicsMotorDeviceConfigTemplate
                v.model_validate(config["deviceConfig"])
                continue
            if isinstance(v, (list, tuple)):
                v = tuple(v)
            config_value = config[k]
            if isinstance(config_value, (list, tuple)):
                config_value = tuple(config_value)
            assert config_value == v

        # Set config from Model for custom EpicsMotor
        model = DeviceModel(
            name="motor_x",
            deviceClass="ophyd.EpicsMotor",
            readoutPriority="baseline",
            enabled=False,
            deviceConfig={"prefix": "MOTOR_X:", "limits": [-10, 10], "additional_field": 42},
            deviceTags=["motors", "x_axis"],
            userParameter={"param1": 100, "param2": "value2"},
        )
        device_config_template.set_config_fields(model.model_dump())
        # Check config
        config = device_config_template.get_config_fields()
        assert config["name"] == "motor_x"
        assert config["deviceClass"] == "ophyd.EpicsMotor"
        assert config["readoutPriority"] == "baseline"
        assert config["enabled"] is False
        assert config["deviceConfig"] == {
            "prefix": "MOTOR_X:",
            "limits": [-10, 10],
            "additional_field": 42,
        }
        assert set(config["deviceTags"]) == {"motors", "x_axis"}
        assert config["userParameter"] == {"param1": 100, "param2": "value2"}

    def test_limit_input_widget(self, qtbot):
        """Test LimitInputWidget functionality."""
        colors = get_accent_colors()
        widget = LimitInputWidget()
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)

        # Default limits should be [0, 0]
        assert widget.get_limits() == [0, 0]

        assert widget._is_valid_limit() is True
        assert widget.enable_toggle.isChecked() is False

        # Set limits externally
        widget.set_limits([-5, 5])
        assert widget.get_limits() == [-5, 5]
        assert widget._is_valid_limit() is True
        assert widget.enable_toggle.isChecked() is False

        # Enable toggle
        with qtbot.waitSignal(widget.enable_toggle.stateChanged):
            widget.enable_toggle.setChecked(True)

        assert widget.enable_toggle.isChecked() is True
        # Set invalid limits (min >= max)
        with qtbot.waitSignals([widget.min_input.valueChanged, widget.max_input.valueChanged]):
            widget.min_input.setValue(2)
            widget.max_input.setValue(1)

        assert widget._is_valid_limit() is False
        assert widget.min_input.styleSheet() == f"border: 1px solid {colors.emergency.name()};"
        assert widget.max_input.styleSheet() == f"border: 1px solid {colors.emergency.name()};"

        # Reset to default values
        with qtbot.waitSignals([widget.min_input.valueChanged, widget.max_input.valueChanged]):
            widget.min_input.setValue(0)
            widget.max_input.setValue(0)

        assert widget.get_limits() == [0, 0]
        assert widget.min_input.styleSheet() == ""
        assert widget.max_input.styleSheet() == ""

    def test_parameter_value_widget(self, qtbot):
        """Test ParameterValueWidget functionality."""
        widget = ParameterValueWidget()
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)

        # Initially no parameters
        assert widget.parameters() == {}

        # Add parameters
        sample_params = {"param1": 10, "param2": "value", "param3": True}
        for k, v in sample_params.items():
            widget.add_parameter_line(k, v)
        assert widget.parameters() == sample_params

        # Modify a parameter
        param1_widget: InputLineEdit = widget.tree_widget.itemWidget(
            widget.tree_widget.topLevelItem(0), 1
        )
        with qtbot.waitSignal(param1_widget.textChanged):
            param1_widget.setText("20")
        updated_params = widget.parameters()
        assert updated_params["param1"] == 20
        assert updated_params["param2"] == "value"
        assert updated_params["param3"] is True
        # Select top item
        widget.tree_widget.setCurrentItem(widget.tree_widget.topLevelItem(0))
        widget.remove_parameter_line()
        # Check that param1 is removed
        assert widget.parameters() == {"param2": "value", "param3": True}
        # Clear all parameters
        widget.clear_widget()
        assert widget.parameters() == {}

    def test_device_tags_widget(self, qtbot):
        """Test DeviceTagsWidget functionality."""
        widget = DeviceTagsWidget()
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)

        # Initially no tags
        assert widget.parameters() == []

        # Add tags
        with qtbot.waitSignal(widget._button_add.clicked):
            qtbot.mouseClick(widget._button_add, QtCore.Qt.LeftButton)
            qtbot.mouseClick(widget._button_add, QtCore.Qt.LeftButton)
            qtbot.wait(200)  # wait item to be added to tree widget

        assert widget.tree_widget.topLevelItemCount() == 2
        assert widget.parameters() == []  # No value yet means no parameters

        # set tag text
        widget_item = widget.tree_widget.topLevelItem(0)
        tag_widget: InputLineEdit = widget.tree_widget.itemWidget(widget_item, 0)
        with qtbot.waitSignal(tag_widget.textChanged):
            tag_widget.setText("motor")
        assert widget.parameters() == ["motor"]

        # Remove tag
        widget.tree_widget.setCurrentItem(widget.tree_widget.topLevelItem(0))
        with qtbot.waitSignal(widget._button_remove.clicked):
            qtbot.mouseClick(widget._button_remove, QtCore.Qt.LeftButton)
            qtbot.wait(200)  # wait item to be added to tree widget

        assert widget.tree_widget.topLevelItemCount() == 1

        # Clear all tags
        widget.clear_widget()
        assert widget.tree_widget.topLevelItemCount() == 0
