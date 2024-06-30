# pylint: disable=no-name-in-module

from typing import Union

import yaml
from qtpy.QtWidgets import QFileDialog


def load_yaml_gui(instance) -> Union[dict, None]:
    """
    Load YAML file from disk.

    Args:
        instance: Instance of the calling widget.

    Returns:
        dict: Configuration data loaded from the YAML file.
    """
    options = QFileDialog.Options()
    file_path, _ = QFileDialog.getOpenFileName(
        instance, "Load Settings", "", "YAML Files (*.yaml *.yml);;All Files (*)", options=options
    )
    config = load_yaml(file_path)
    return config


def load_yaml(file_path: str) -> Union[dict, None]:
    """
    Load YAML file from disk.

    Args:
        file_path(str): Path to the YAML file.

    Returns:
        dict: Configuration data loaded from the YAML file.
    """
    if not file_path:
        return None
    try:
        with open(file_path, "r") as file:
            config = yaml.load(file, Loader=yaml.FullLoader)
        return config

    except FileNotFoundError:
        print(f"The file {file_path} was not found.")
    except PermissionError:
        print(f"Permission denied for file {file_path}.")
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {file_path}: {e}")
    except Exception as e:
        print(f"An error occurred while loading the settings from {file_path}: {e}")


def save_yaml_gui(instance, config: dict) -> None:
    """
    Save YAML file to disk.

    Args:
        instance: Instance of the calling widget.
        config: Configuration data to be saved.
    """
    options = QFileDialog.Options()
    file_path, _ = QFileDialog.getSaveFileName(
        instance, "Save Settings", "", "YAML Files (*.yaml *.yml);;All Files (*)", options=options
    )

    save_yaml(file_path, config)


def save_yaml(file_path: str, config: dict) -> None:
    """
    Save YAML file to disk.

    Args:
        file_path(str): Path to the YAML file.
        config(dict): Configuration data to be saved.
    """
    if not file_path:
        return
    try:
        if not (file_path.endswith(".yaml") or file_path.endswith(".yml")):
            file_path += ".yaml"

        with open(file_path, "w") as file:
            yaml.dump(config, file)
            print(f"Settings saved to {file_path}")
    except Exception as e:
        print(f"An error occurred while saving the settings to {file_path}: {e}")
