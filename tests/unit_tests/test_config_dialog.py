# pylint: disable = no-name-in-module,missing-class-docstring, missing-module-docstring
import os
from unittest.mock import MagicMock

import pytest
import yaml
from qtpy.QtWidgets import QTableWidgetItem, QTabWidget

from bec_widgets.widgets.monitor.config_dialog import ConfigDialog

from .client_mocks import mocked_client


def load_test_config(config_name):
    """Helper function to load config from yaml file."""
    config_path = os.path.join(os.path.dirname(__file__), "test_configs", f"{config_name}.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config


@pytest.fixture(scope="function")
def config_dialog(qtbot, mocked_client):
    client = mocked_client
    widget = ConfigDialog(client=client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.mark.parametrize("config_name", ["config_device", "config_scan"])
def test_load_config(config_dialog, config_name):
    config = load_test_config(config_name)
    config_dialog.load_config(config)

    assert (
        config_dialog.comboBox_appearance.currentText()
        == config["plot_settings"]["background_color"]
    )
    assert config_dialog.spinBox_n_column.value() == config["plot_settings"]["num_columns"]
    assert config_dialog.comboBox_colormap.currentText() == config["plot_settings"]["colormap"]


@pytest.mark.parametrize(
    "config_name, scan_mode",
    [
        ("config_device", False),
        ("config_scan", True),
        ("config_device_no_entry", False),
    ],
)
def test_initialization(config_dialog, config_name, scan_mode):
    config = load_test_config(config_name)
    config_dialog.load_config(config)

    assert isinstance(config_dialog, ConfigDialog)
    assert (
        config_dialog.comboBox_appearance.currentText()
        == config["plot_settings"]["background_color"]
    )
    assert config_dialog.spinBox_n_column.value() == config["plot_settings"]["num_columns"]
    assert (config_dialog.comboBox_scanTypes.currentText() == "Enabled") == scan_mode
    assert (
        config_dialog.tabWidget_scan_types.count() > 0
    )  # Ensures there's at least one tab created

    # If there's a need to check the contents of the first tab (there has to be always at least one tab)
    first_tab = config_dialog.tabWidget_scan_types.widget(0)
    if scan_mode:
        assert (
            first_tab.findChild(QTabWidget, "tabWidget_plots") is not None
        )  # Ensures plot tab widget exists in scan mode
    else:
        assert (
            first_tab.findChild(QTabWidget) is not None
        )  # Ensures plot tab widget exists in default mode


def test_edit_and_apply_config(config_dialog):
    config_device = load_test_config("config_device")
    config_dialog.load_config(config_device)

    config_dialog.comboBox_appearance.setCurrentText("white")
    config_dialog.spinBox_n_column.setValue(2)
    config_dialog.comboBox_colormap.setCurrentText("viridis")

    applied_config = config_dialog.apply_config()

    assert applied_config["plot_settings"]["background_color"] == "white"
    assert applied_config["plot_settings"]["num_columns"] == 2
    assert applied_config["plot_settings"]["colormap"] == "viridis"


def test_edit_and_apply_config_scan_mode(config_dialog):
    config_scan = load_test_config("config_scan")
    config_dialog.load_config(config_scan)

    config_dialog.comboBox_appearance.setCurrentText("white")
    config_dialog.spinBox_n_column.setValue(2)
    config_dialog.comboBox_colormap.setCurrentText("viridis")
    config_dialog.comboBox_scanTypes.setCurrentText("Enabled")

    applied_config = config_dialog.apply_config()

    assert applied_config["plot_settings"]["background_color"] == "white"
    assert applied_config["plot_settings"]["num_columns"] == 2
    assert applied_config["plot_settings"]["colormap"] == "viridis"
    assert applied_config["plot_settings"]["scan_types"] is True


def test_add_new_scan(config_dialog):
    # Ensure the tab count is initially 1 (from the default config)
    assert config_dialog.tabWidget_scan_types.count() == 1

    # Add a new scan tab
    config_dialog.add_new_scan_tab(config_dialog.tabWidget_scan_types, "Test Scan Tab")

    # Ensure the tab count is now 2
    assert config_dialog.tabWidget_scan_types.count() == 2

    # Ensure the new tab has the correct name
    assert config_dialog.tabWidget_scan_types.tabText(1) == "Test Scan Tab"


def test_add_new_plot_and_modify(config_dialog):
    # Ensure the tab count is initially 1 and it is called "Default"
    assert config_dialog.tabWidget_scan_types.count() == 1
    assert config_dialog.tabWidget_scan_types.tabText(0) == "Default"

    # Get the first tab (which should be a scan tab)
    scan_tab = config_dialog.tabWidget_scan_types.widget(0)

    # Ensure the plot tab count is initially 1 and it is called "Plot 1"
    tabWidget_plots = scan_tab.findChild(QTabWidget)
    assert tabWidget_plots.count() == 1
    assert tabWidget_plots.tabText(0) == "Plot 1"

    # Add a new plot tab
    config_dialog.add_new_plot_tab(scan_tab)

    # Ensure the plot tab count is now 2
    assert tabWidget_plots.count() == 2

    # Ensure the new tab has the correct name
    assert tabWidget_plots.tabText(1) == "Plot 2"

    # Access the new plot tab
    new_plot_tab = tabWidget_plots.widget(1)

    # Modify the line edits within the new plot tab
    new_plot_tab.ui.lineEdit_plot_title.setText("Modified Plot Title")
    new_plot_tab.ui.lineEdit_x_label.setText("Modified X Label")
    new_plot_tab.ui.lineEdit_y_label.setText("Modified Y Label")
    new_plot_tab.ui.lineEdit_x_name.setText("Modified X Name")
    new_plot_tab.ui.lineEdit_x_entry.setText("Modified X Entry")

    # Modify the table for signals
    config_dialog.add_new_signal(new_plot_tab.ui.tableWidget_y_signals)

    table = new_plot_tab.ui.tableWidget_y_signals
    assert table.rowCount() == 1  # Ensure the new row is added

    row_position = table.rowCount() - 1

    # Modify the first row
    table.setItem(row_position, 0, QTableWidgetItem("New Signal Name"))
    table.setItem(row_position, 1, QTableWidgetItem("New Signal Entry"))

    # Apply the configuration
    config = config_dialog.apply_config()

    # Check if the modifications are reflected in the configuration
    modified_plot_config = config["plot_data"][1]  # Access the second plot in the plot_data list
    sources = modified_plot_config["sources"][0]  # Access the first source in the sources list

    assert modified_plot_config["plot_name"] == "Modified Plot Title"
    assert modified_plot_config["x_label"] == "Modified X Label"
    assert modified_plot_config["y_label"] == "Modified Y Label"
    assert sources["signals"]["x"][0]["name"] == "Modified X Name"
    assert sources["signals"]["x"][0]["entry"] == "Modified X Entry"
    assert sources["signals"]["y"][0]["name"] == "New Signal Name"
    assert sources["signals"]["y"][0]["entry"] == "New Signal Entry"
