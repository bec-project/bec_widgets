import yaml
from PyQt5.QtWidgets import QFileDialog


def load_yaml(instance) -> dict:
    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog
    file_path, _ = QFileDialog.getOpenFileName(
        instance, "Load Settings", "", "YAML Files (*.yaml *.yml);;All Files (*)", options=options
    )

    if not file_path:
        return None
    try:
        with open(file_path, "r") as file:
            config = yaml.safe_load(file)
        return config

    except FileNotFoundError:
        print(f"The file {file_path} was not found.")
    except Exception as e:
        print(f"An error occurred while loading the settings from {file_path}: {e}")
        return None  # Return None on exception to indicate failure


def save_yaml(instance, config: dict) -> None:
    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog
    file_path, _ = QFileDialog.getSaveFileName(
        instance, "Save Settings", "", "YAML Files (*.yaml *.yml);;All Files (*)", options=options
    )

    if not file_path:
        return None
    try:
        if not (file_path.endswith(".yaml") or file_path.endswith(".yml")):
            file_path += ".yaml"

        with open(file_path, "w") as file:
            yaml.dump(config, file)
            print(f"Settings saved to {file_path}")
    except Exception as e:
        print(f"An error occurred while saving the settings to {file_path}: {e}")
