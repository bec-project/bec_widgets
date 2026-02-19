"""
Login dialog for user authentication.
The Login Widget is styled in a Material Design style and emits
the entered credentials through a signal for further processing.
"""

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget


class BECLogin(QWidget):
    """Login dialog for user authentication in Material Design style."""

    credentials_entered = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        # Only displayed if this widget as standalone widget, and not embedded in another widget
        self.setWindowTitle("Login")

        title = QLabel("Sign in", parent=self)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            """
            #QLabel
                {
                    font-size: 18px;
                    font-weight: 600;
                }
            """
        )

        self.username = QLineEdit(parent=self)
        self.username.setPlaceholderText("Username")

        self.password = QLineEdit(parent=self)
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        self.ok_btn = QPushButton("Sign in", parent=self)
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._emit_credentials)
        # If the user presses Enter in the password field, trigger the OK button click
        self.password.returnPressed.connect(self.ok_btn.click)

        # Build Layout
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

        self.setStyleSheet(
            """
            QLineEdit {
                padding: 8px;
            }
            """
        )

    def _clear_password(self):
        """Clear the password field."""
        self.password.clear()

    def _emit_credentials(self):
        """Emit credentials and clear the password field."""
        self.credentials_entered.emit(self.username.text().strip(), self.password.text())
        self._clear_password()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    apply_theme("light")

    dialog = BECLogin()

    dialog.credentials_entered.connect(lambda u, p: print(f"Username: {u}, Password: {p}"))
    dialog.show()
    sys.exit(app.exec_())
