from qtpy.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from bec_widgets.qt_utils.error_popups import SafeSlot as Slot


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
        config: dict = None,
        *args,
        **kwargs,
    ):
        super().__init__(parent, *args, **kwargs)

        self.setModal(False)

        self.setWindowTitle(window_title)

        self.widget = settings_widget
        self.widget.set_target_widget(parent)
        if config is None:
            config = parent.get_config()

        self.widget.display_current_settings(config)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        self.apply_button = QPushButton("Apply")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.button_box.button(QDialogButtonBox.Cancel))
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.button_box.button(QDialogButtonBox.Ok))

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.apply_button.clicked.connect(self.apply_changes)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.addWidget(self.widget)
        self.layout.addLayout(button_layout)

        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        ok_button.setDefault(True)
        ok_button.setAutoDefault(True)

    @Slot()
    def accept(self):
        """
        Accept the changes made in the settings widget and close the dialog.
        """
        self.widget.accept_changes()
        super().accept()

    @Slot()
    def apply_changes(self):
        """
        Apply the changes made in the settings widget without closing the dialog.
        """
        self.widget.accept_changes()
