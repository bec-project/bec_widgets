import yaml
from PyQt5.QtWidgets import QFileDialog

# TODO add pydantic/json scheme validation for config files as an optional argument


def load_yaml(instance) -> dict:
    """
    Load a YAML file and update the settings
    Args:
        instance: parent instance (named instance to avoid conflict with keyword in QFileDialog)

    Returns:
        config(dict): dictionary of settings
    """
    options = QFileDialog.Options()

    options |= QFileDialog.DontUseNativeDialog
    file_path, _ = QFileDialog.getOpenFileName(
        instance, "Load Settings", "", "YAML Files (*.yaml);;All Files (*)", options=options
    )

    if file_path:
        try:
            with open(file_path, "r") as file:
                config = yaml.safe_load(file)
            return config

        except FileNotFoundError:
            print(f"The file {file_path} was not found.")
        except Exception as e:
            print(f"An error occurred while loading the settings from {file_path}: {e}")
            return None  # Return None on exception to indicate failure

    if not file_path:
        return None


def save_yaml(instance, config: dict) -> None:
    """
    Save the settings to a YAML file
    Args:
        instance: parent instance (named instance to avoid conflict with keyword in QFileDialog)
        config(dict): dictionary of settings to save to .yaml file
    """

    options = QFileDialog.Options()
    options |= QFileDialog.DontUseNativeDialog
    file_path, _ = QFileDialog.getSaveFileName(
        instance, "Save Settings", "", "YAML Files (*.yaml);;All Files (*)", options=options
    )

    if file_path:
        try:
            if not file_path.endswith(".yaml"):
                file_path += ".yaml"

            with open(file_path, "w") as file:
                yaml.dump(config, file)
                print(f"Settings saved to {file_path}")
        except Exception as e:
            print(f"An error occurred while saving the settings to {file_path}: {e}")

    if not file_path:
        return None
