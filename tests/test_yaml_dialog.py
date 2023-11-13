import os
import tempfile
from unittest.mock import patch
import pytest
import yaml
from qtpy.QtWidgets import QWidget, QVBoxLayout, QPushButton

from bec_widgets.qt_utils.yaml_dialog import load_yaml, save_yaml


@pytest.fixture(scope="function")
def example_widget(qtbot):
    main_widget = QWidget()
    layout = QVBoxLayout(main_widget)
    main_widget.import_button = QPushButton("Import", main_widget)
    main_widget.export_button = QPushButton("Export", main_widget)
    layout.addWidget(main_widget.import_button)
    layout.addWidget(main_widget.export_button)

    main_widget.config = {}  # Dictionary to store the loaded configuration
    main_widget.saved_config = None  # To store the saved configuration

    qtbot.addWidget(main_widget)
    qtbot.waitExposed(main_widget)
    yield main_widget


def test_load_yaml(qtbot, example_widget):
    # Create a temporary file with YAML content
    with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as temp_file:
        temp_file.write(b"name: test\nvalue: 42")

    def load_yaml_wrapper():
        config = load_yaml(example_widget)
        if config:
            example_widget.config.update(config)

    example_widget.import_button.clicked.connect(load_yaml_wrapper)

    # Mock user selecting the file in the dialog
    with patch("qtpy.QtWidgets.QFileDialog.getOpenFileName", return_value=(temp_file.name, "")):
        example_widget.import_button.click()

    assert example_widget.config == {"name": "test", "value": 42}
    os.remove(temp_file.name)  # Clean up


def test_save_yaml(qtbot, example_widget):
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".yaml") as temp_file:
        temp_file_path = temp_file.name

    # Prepare data to be saved
    example_widget.saved_config = {"name": "test", "value": 42}

    def save_yaml_wrapper():
        save_yaml(example_widget, example_widget.saved_config)

    example_widget.export_button.clicked.connect(save_yaml_wrapper)

    # Mock user selecting the file in the dialog
    with patch("qtpy.QtWidgets.QFileDialog.getSaveFileName", return_value=(temp_file_path, "")):
        example_widget.export_button.click()

    # Check if the data was saved correctly
    with open(temp_file_path, "r") as file:
        saved_config = yaml.safe_load(file)
    assert saved_config == {"name": "test", "value": 42}

    os.remove(temp_file_path)  # Clean up
