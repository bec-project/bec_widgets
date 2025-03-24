# pylint: skip-file
from unittest import mock

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from bec_widgets.utils.compact_popup import CompactPopupWidget


class ContainedWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)


class TestCompactPopupWidget(CompactPopupWidget):
    def __init__(self):
        super().__init__(layout=QVBoxLayout)

        self.contained = QWidget(self)
        self.addWidget(self.contained)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)


@pytest.fixture
def compact_popup(qtbot):
    widget = TestCompactPopupWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait_until(widget.isVisible)
    yield widget


def test_widget_closing(qtbot, compact_popup):
    with mock.patch.object(compact_popup.contained, "close") as close_method:
        compact_popup.close()
    qtbot.waitUntil(lambda: not compact_popup.isVisible(), timeout=1000)
    close_method.assert_called_once()


def test_size_policy(compact_popup):
    csp = compact_popup.sizePolicy()
    assert csp.horizontalPolicy() == QSizePolicy.Expanding
    assert csp.verticalPolicy() == QSizePolicy.Minimum
    compact_popup.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
    csp = compact_popup.sizePolicy()
    assert csp.horizontalPolicy() == QSizePolicy.Minimum
    assert csp.verticalPolicy() == QSizePolicy.Expanding
    compact_popup.compact_view = True
    csp = compact_popup.sizePolicy()
    assert csp.horizontalPolicy() == QSizePolicy.Fixed
    assert csp.verticalPolicy() == QSizePolicy.Fixed
    compact_popup.compact_view = False
    csp = compact_popup.sizePolicy()
    assert csp.horizontalPolicy() == QSizePolicy.Minimum
    assert csp.verticalPolicy() == QSizePolicy.Expanding


def test_open_full_view(qtbot, compact_popup):
    qtbot.waitUntil(compact_popup.container.isVisible, timeout=1000)
    compact_popup.compact_view = True
    qtbot.waitUntil(compact_popup.compact_view_widget.isVisible, timeout=1000)
    qtbot.mouseClick(compact_popup.compact_show_popup, Qt.LeftButton)
    qtbot.waitUntil(compact_popup.container.isVisible, timeout=1000)
    compact_popup._popup_window.close()
    qtbot.waitUntil(lambda: not compact_popup.container.isVisible(), timeout=1000)
