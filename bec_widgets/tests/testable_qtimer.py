"""
QTimer replacement used to detect timers that are still running at the end of a test.

This module deliberately imports nothing but Qt and pytest-qt: it has to be patched over
``qtpy.QtCore.QTimer`` before any module that does ``from qtpy.QtCore import QTimer`` is imported.
"""

import traceback

from pytestqt.exceptions import TimeoutError as QtBotTimeoutError
from qtpy.QtCore import QTimer


class TestableQTimer(QTimer):
    """
    QTimer that records every instance, so that timers left running after a test can be reported.
    Patch it over ``qtpy.QtCore.QTimer`` before the widgets under test are imported.
    """

    _instances: list[tuple[QTimer, str, str]] = []
    _current_test_name: str = ""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tb = traceback.format_stack()
        init_line = list(filter(lambda msg: "QTimer(" in msg, tb))[-1]
        TestableQTimer._instances.append((self, TestableQTimer._current_test_name, init_line))

    @classmethod
    def check_all_stopped(cls, qtbot):
        def _is_done_or_deleted(t: QTimer):
            try:
                return not t.isActive()
            except RuntimeError as e:
                return "already deleted" in e.args[0]

        def _format_timers(timers: list[tuple[QTimer, str, str]]):
            return "\n".join(
                f"Timer: {t[0]}\n    in test: {t[1]}\n    created at:{t[2]}" for t in timers
            )

        try:
            qtbot.waitUntil(
                lambda: all(_is_done_or_deleted(timer) for timer, _, _ in cls._instances)
            )
        except QtBotTimeoutError as exc:
            active_timers = list(filter(lambda t: t[0].isActive(), cls._instances))
            (t.stop() for t, _, _ in cls._instances)
            raise TimeoutError(
                f"Failed to stop all timers:\n{_format_timers(active_timers)}"
            ) from exc
        cls._instances = []
