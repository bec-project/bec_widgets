"""Dialog to choose config loading method: replace, add or cancel."""

from enum import IntEnum

from qtpy.QtWidgets import QDialog, QDialogButtonBox, QLabel, QSizePolicy, QVBoxLayout


class ConfigChoiceDialog(QDialog):
    class Result(IntEnum):
        CANCEL = QDialog.Rejected
        ADD = 2
        REPLACE = 3

    def __init__(
        self,
        parent=None,
        custom_label: str = "Do you want to replace the current config or add to it?",
    ):
        super().__init__(parent)
        self.setWindowTitle("Load Config")

        layout = QVBoxLayout(self)

        label = QLabel(custom_label)
        label.setWordWrap(True)
        layout.addWidget(label)

        # Use QDialogButtonBox for native layout
        self.button_box = QDialogButtonBox(self)
        self.cancel_btn = self.button_box.addButton(
            "Cancel", QDialogButtonBox.ButtonRole.ActionRole  # RejectRole will be next to Accept...
        )
        self.replace_btn = self.button_box.addButton(
            "Replace", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.add_btn = self.button_box.addButton("Add", QDialogButtonBox.ButtonRole.AcceptRole)

        layout.addWidget(self.button_box)

        for btn in [self.replace_btn, self.add_btn, self.cancel_btn]:
            btn.setMinimumWidth(80)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Connections using native done(int)
        self.replace_btn.clicked.connect(lambda: self.done(self.Result.REPLACE))
        self.add_btn.clicked.connect(lambda: self.done(self.Result.ADD))
        self.cancel_btn.clicked.connect(lambda: self.done(self.Result.CANCEL))

        self.replace_btn.setFocus()
