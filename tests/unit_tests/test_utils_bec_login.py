"""Test the BEC Login widget"""

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLineEdit

from bec_widgets.utils.bec_login import BECLogin


@pytest.fixture
def login_dialog(qtbot):
    """Fixture to create a BECLogin instance."""
    dialog = BECLogin()
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog)  # Ensure the dialog is fully shown before running tests
    return dialog


def test_utils_login_dialog_initialization(login_dialog, qtbot):
    """Test that the BECLogin initializes correctly."""
    assert login_dialog.windowTitle() == "Login"
    assert login_dialog.username.placeholderText() == "Username"
    assert login_dialog.password.placeholderText() == "Password"
    assert login_dialog.password.echoMode() == QLineEdit.EchoMode.Password
    assert login_dialog.ok_btn.text() == "Sign in"

    # Initially, this should be empty
    with qtbot.waitSignal(login_dialog.credentials_entered, timeout=5000) as blocker:
        qtbot.mouseClick(login_dialog.ok_btn, Qt.MouseButton.LeftButton)
    assert blocker.args == ["", ""]


def test_utils_login_dialog_emit_credentials(login_dialog, qtbot):
    """Test that the BECLogin emits credentials correctly."""
    test_username = "testuser "
    test_password = "testpass"

    login_dialog.username.setText(test_username)
    login_dialog.password.setText(test_password)

    with qtbot.waitSignal(login_dialog.credentials_entered, timeout=5000) as blocker:
        qtbot.mouseClick(login_dialog.ok_btn, Qt.MouseButton.LeftButton)

    assert blocker.args == [test_username.strip(), test_password]
    assert login_dialog.password.text() == ""  # Password should be cleared after emitting

    login_dialog.password.setText(test_password)
    with qtbot.waitSignal(login_dialog.credentials_entered, timeout=5000) as blocker:
        qtbot.keyClick(login_dialog.password, Qt.Key.Key_Return)

    assert blocker.args == [test_username.strip(), test_password]
    assert login_dialog.password.text() == ""  # Password should be cleared after emitting
