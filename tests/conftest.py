import pytest
import qtpy.QtCore
from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtCore import QTimer


class TestableQTimer(QTimer):
    _instances: list[tuple[QTimer, str]] = []
    _current_test_name: str = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        TestableQTimer._instances.append((self, TestableQTimer._current_test_name))

    @classmethod
    def check_all_stopped(cls, qtbot):
        def _is_done_or_deleted(t: QTimer):
            try:
                return not t.isActive()
            except RuntimeError as e:
                return "already deleted" in e.args[0]

        try:
            qtbot.waitUntil(lambda: all(_is_done_or_deleted(timer) for timer, _ in cls._instances))
        except QtBotTimeoutError as exc:
            active_timers = list(filter(lambda t: t[0].isActive(), cls._instances))
            (t.stop() for t, _ in cls._instances)
            raise TimeoutError(f"Failed to stop all timers: {active_timers}") from exc
        cls._instances = []


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
