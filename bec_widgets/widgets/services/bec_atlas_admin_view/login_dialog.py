"""Login dialog for user authentication."""

from bec_qthemes import apply_theme
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout


class LoginDialog(QDialog):
    credentials_entered = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle("Login")
        self.setModal(True)
        self.setFixedWidth(320)

        # Slightly increased padding
        self.setStyleSheet(
            """
            QLineEdit {
                padding: 8px;
            }
            """
        )

        title = QLabel("Sign in", parent=self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")

        self.username = QLineEdit(parent=self)
        self.username.setPlaceholderText("Username")

        self.password = QLineEdit(parent=self)
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)

        self.ok_btn = QPushButton("Sign in", parent=self)
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._emit_credentials)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        layout.addSpacing(12)
        layout.addWidget(self.ok_btn)

        self.username.setFocus()

    def _emit_credentials(self):
        self.credentials_entered.emit(self.username.text().strip(), self.password.text())
        self.accept()


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    apply_theme("light")

    dialog = LoginDialog()

    dialog.credentials_entered.connect(lambda u, p: print(f"Username: {u}, Password: {p}"))
    dialog.exec_()
