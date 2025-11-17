import pytest
import qtpy.QtCore

from bec_widgets.tests.utils import TestableQTimer

# To support 'from qtpy.QtCore import QTimer' syntax we just replace this completely for the test session
# see: https://docs.python.org/3/library/unittest.mock.html#where-to-patch
qtpy.QtCore.QTimer = TestableQTimer


@pytest.fixture(autouse=True)
def _capture_test_name_in_qtimer(request):
    TestableQTimer._current_test_name = request.node.name
    yield
    TestableQTimer._current_test_name = ""


@pytest.fixture
def testable_qtimer_class():
    return TestableQTimer
