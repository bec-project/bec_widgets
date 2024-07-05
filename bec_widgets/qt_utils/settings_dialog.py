from qtpy.QtCore import Slot
from qtpy.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QWidget


class SettingWidget(QWidget):
    """
    Abstract class for a settings widget to enforce the implementation of the accept_changes and display_current_settings.
    Can be used for toolbar actions to display the settings of a widget.

    Args:
        target_widget (QWidget): The widget that the settings will be taken from and applied to.
    """

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.target_widget = None

    def set_target_widget(self, target_widget: QWidget):
        self.target_widget = target_widget

    @Slot()
    def accept_changes(self):
        """
        Accepts the changes made in the settings widget and applies them to the target widget.
        """
        pass

    @Slot(dict)
    def display_current_settings(self, config_dict: dict):
        """
        Displays the current settings of the target widget in the settings widget.

        Args:
            config_dict(dict): The current settings of the target widget.
        """
        pass


class SettingsDialog(QDialog):
    """
    Dialog to display and edit the settings of a widget with accept and cancel buttons.

    Args:
        parent (QWidget): The parent widget of the dialog.
        target_widget (QWidget): The widget that the settings will be taken from and applied to.
        settings_widget (SettingWidget): The widget that will display the settings.
    """

    def __init__(
        self,
        parent=None,
        settings_widget: SettingWidget = None,
        window_title: str = "Settings",
        *args,
        **kwargs,
    ):
        super().__init__(parent, *args, **kwargs)

        self.setModal(False)

        self.setWindowTitle(window_title)

        self.widget = settings_widget
        self.widget.set_target_widget(parent)
        self.widget.display_current_settings(parent.get_config())
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.widget)
        self.layout.addWidget(self.button_box)

    @Slot()
    def accept(self):
        """
        Accept the changes made in the settings widget and close the dialog.
        """
        self.widget.accept_changes()
        super().accept()
