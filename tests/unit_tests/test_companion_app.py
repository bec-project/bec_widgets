"""Unit tests for GUI-server startup and redirected logging."""

from __future__ import annotations

import asyncio
import io
import sys
import threading
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from loguru._logger import Core, Logger

from bec_widgets.applications import companion_app


def _server(**overrides):
    args = SimpleNamespace(
        config=None, id="test", gui_class=None, gui_class_id="bec", hide=False, **overrides
    )
    return companion_app.GUIServer(args)


def test_notify_server_ready_resolves_launcher(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "bec_widgets.utils.launcher_ready.notify_launcher_ready",
        lambda app_name, window: calls.append((app_name, window)) or True,
    )
    marks = []
    monkeypatch.setattr(
        companion_app.startup_profiler, "mark", lambda stage, **kw: marks.append((stage, kw))
    )

    server = _server()
    sentinel_window = object()
    server.launcher_window = sentinel_window
    server._notify_server_ready()

    # The GUI-server path sends the ready edge itself (safety net for launches with no
    # auto-launched gui_class window) and records the final startup stage.
    assert calls == [("bec-gui-server", sentinel_window)]
    assert ("interactive", {"final": True}) in marks


def test_log_output_flush_preserves_partial_lines():
    messages = []
    stream = companion_app.SimpleFileLikeFromLogOutputFunc(messages.append)

    stream.write("first")
    stream.flush()
    assert messages == []

    stream.write("\nsecond\npar")
    assert messages == []
    stream.flush()
    stream.flush()
    assert messages == ["first\nsecond"]

    stream.write("tial\n")
    stream.flush()
    assert messages == ["first\nsecond", "partial"]


def test_log_output_reentrant_writes_use_original_stdout(monkeypatch):
    fallback = io.StringIO()
    monkeypatch.setattr(sys, "__stdout__", fallback)
    messages = []

    def log(message):
        messages.append(message)
        stream.write("sink diagnostic\n")
        stream.flush()

    stream = companion_app.SimpleFileLikeFromLogOutputFunc(log, fallback_stream=sys.__stdout__)
    # Capture the original stream when creating the adapter, before redirection.
    monkeypatch.setattr(sys, "__stdout__", io.StringIO())
    stream.write("first\npartial")
    stream.flush()
    stream.flush()

    assert messages == ["first"]
    assert fallback.getvalue() == "sink diagnostic\n"

    stream.write(" line\n")
    stream.flush()
    assert messages == ["first", "partial line"]
    assert fallback.getvalue() == "sink diagnostic\nsink diagnostic\n"


def test_log_output_callback_failure_falls_back_and_recovers():
    fallback = io.StringIO()
    messages = []

    def log(message):
        messages.append(message)
        if len(messages) == 1:
            raise RuntimeError("logger failed")

    stream = companion_app.SimpleFileLikeFromLogOutputFunc(log, fallback_stream=fallback)
    stream.write("first\nsecond\npartial")
    stream.flush()
    stream.flush()

    assert messages == ["first\nsecond"]
    assert fallback.getvalue() == "first\nsecond\n"

    stream.write(" line\n")
    stream.flush()
    assert messages == ["first\nsecond", "partial line"]
    assert fallback.getvalue() == "first\nsecond\n"


@pytest.mark.parametrize("fallback_state", ["missing", "closed", "write_fails", "flush_fails"])
def test_log_output_recovers_when_fallback_is_unavailable(monkeypatch, fallback_state):
    original_stdout = io.StringIO()
    monkeypatch.setattr(sys, "__stdout__", original_stdout)
    fallback = None
    if fallback_state == "closed":
        fallback = io.StringIO()
        fallback.close()
    elif fallback_state in ("write_fails", "flush_fails"):
        fallback = Mock(spec=io.TextIOBase)
        getattr(fallback, fallback_state.removesuffix("_fails")).side_effect = BrokenPipeError(
            "parent pipe closed"
        )
    messages = []

    def log(message):
        messages.append(message)
        if message == "first":
            stream.write("logger diagnostic\n")
            stream.flush()
            raise RuntimeError("logger failed")

    stream = companion_app.SimpleFileLikeFromLogOutputFunc(log, fallback_stream=fallback)
    stream.write("first\n")
    stream.flush()
    stream.write("second\n")
    stream.flush()

    assert messages == ["first", "second"]
    # An unavailable stderr must not accidentally use stdout as its fallback.
    assert original_stdout.getvalue() == ""
    if fallback_state in ("write_fails", "flush_fails"):
        assert fallback.write.call_count == 2
        assert fallback.flush.call_count == (2 if fallback_state == "flush_fails" else 0)


def test_log_output_reentrancy_guard_is_thread_local():
    fallback = io.StringIO()
    messages = []

    def write_from_worker():
        stream.write("worker\n")
        stream.flush()

    worker = threading.Thread(target=write_from_worker, daemon=True)

    def log(message):
        messages.append(message)
        if message == "main":
            worker.start()
            worker.join(timeout=2)

    stream = companion_app.SimpleFileLikeFromLogOutputFunc(log, fallback_stream=fallback)
    stream.write("main\n")
    stream.flush()

    assert not worker.is_alive()
    assert messages == ["main", "worker"]
    assert fallback.getvalue() == ""


def test_log_output_accepts_reentrant_writes_while_buffering():
    messages = []
    stream = companion_app.SimpleFileLikeFromLogOutputFunc(messages.append)

    class ReentrantBuffer(list):
        def append(self, chunk):
            # Simulate a Python signal handler writing while append holds the lock.
            if chunk == "outer\n":
                stream.write("inner\n")
            super().append(chunk)

    stream._buffer = ReentrantBuffer()
    worker = threading.Thread(target=stream.write, args=("outer\n",), daemon=True)
    worker.start()
    worker.join(timeout=2)

    assert not worker.is_alive()
    stream.flush()
    assert messages == ["inner\nouter"]


@pytest.fixture
def isolated_logger():
    # A separate core avoids changing or copying the application's active sinks.
    logger = Logger(
        core=Core(),
        exception=None,
        depth=0,
        record=False,
        lazy=False,
        colors=False,
        raw=False,
        capture=True,
        patchers=[],
        extra={},
    )
    yield logger
    logger.remove()


@pytest.mark.parametrize("run_raises", [False, True])
@pytest.mark.parametrize("enqueue", [False, True])
def test_server_start_logs_stderr_but_bypasses_logger_failures(
    monkeypatch, isolated_logger, run_raises, enqueue
):
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)
    monkeypatch.setattr(sys, "__stdout__", stdout)
    monkeypatch.setattr(sys, "__stderr__", stderr)
    monkeypatch.setattr(companion_app, "logger", isolated_logger)
    monkeypatch.setattr(
        companion_app,
        "bec_logger",
        SimpleNamespace(LOGLEVEL=SimpleNamespace(INFO="INFO"), level=None, disabled_modules=[]),
    )
    messages = []
    failures = []

    def collect(message):
        messages.append((message.record["level"].name, message.record["message"]))

    def broken_sink(message):
        failures.append(message.record["message"])
        # Bound the old feedback loop so this regression fails without hanging.
        if len(failures) <= 2:
            raise OSError("broken logger sink")

    isolated_logger.add(collect, format="{message}")
    isolated_logger.add(
        broken_sink, level="ERROR", backtrace=False, diagnose=False, catch=True, enqueue=enqueue
    )

    def run():
        isolated_logger.error("original error")
        isolated_logger.complete()
        sys.stderr.flush()
        print("forwarded stdout", flush=True)
        print("forwarded stderr", file=sys.stderr, flush=True)
        isolated_logger.complete()
        sys.stderr.flush()
        isolated_logger.complete()
        if run_raises:
            raise RuntimeError("server failed")

    server = _server()
    monkeypatch.setattr(server, "_run", run)
    with pytest.raises(RuntimeError, match="server failed") if run_raises else nullcontext():
        server.start()

    assert failures == ["original error", "forwarded stderr"]
    assert messages == [
        ("ERROR", "original error"),
        ("INFO", "forwarded stdout"),
        ("ERROR", "forwarded stderr"),
    ]
    assert "OSError: broken logger sink" in stderr.getvalue()
    assert stdout.getvalue() == ""
    assert sys.stdout is stdout
    assert sys.stderr is stderr


def test_log_output_preserves_pending_stderr_during_sink_flush(isolated_logger):
    fallback = io.StringIO()
    messages = []
    stream = companion_app.SimpleFileLikeFromLogOutputFunc(messages.append, fallback)

    def sink(_message):
        stream.write("sink diagnostic\n")
        stream.flush()

    isolated_logger.add(sink)
    stream.write("application stderr\n")
    isolated_logger.info("direct logger call")

    assert messages == []
    assert fallback.getvalue() == "sink diagnostic\n"
    stream.flush()
    assert messages == ["application stderr"]


@pytest.mark.parametrize("stream_name, log_level", [("stdout", "info"), ("stderr", "error")])
def test_log_output_from_logger_patcher_bypasses_logging(
    monkeypatch, isolated_logger, stream_name, log_level
):
    fallback = io.StringIO()
    messages = []
    patched_messages = []
    isolated_logger.add(lambda message: messages.append(message.record["message"]))

    def patcher(record):
        patched_messages.append(record["message"])
        # Bound regressions that feed this diagnostic through the same patcher.
        if len(patched_messages) <= 2:
            print("patcher diagnostic", file=getattr(sys, stream_name), flush=True)

    patched_logger = isolated_logger.patch(patcher)
    stream = companion_app.SimpleFileLikeFromLogOutputFunc(
        getattr(patched_logger, log_level), fallback
    )
    monkeypatch.setattr(sys, stream_name, stream)
    patched_logger.info("direct logger call")
    stream.flush()

    assert patched_messages == ["direct logger call"]
    assert messages == ["direct logger call"]
    assert fallback.getvalue() == "patcher diagnostic\n"


def test_log_output_bypasses_async_sink_failure(monkeypatch, isolated_logger):
    fallback = io.StringIO()
    messages = []
    failures = []
    isolated_logger.add(lambda message: messages.append(message.record["message"]))
    stream = companion_app.SimpleFileLikeFromLogOutputFunc(isolated_logger.error, fallback)
    monkeypatch.setattr(sys, "stderr", stream)

    async def broken_sink(message):
        failures.append(message.record["message"])
        if len(failures) <= 2:
            raise OSError("broken async sink")

    async def run():
        isolated_logger.add(broken_sink, backtrace=False, diagnose=False)
        isolated_logger.error("original error")
        await isolated_logger.complete()
        stream.flush()
        await isolated_logger.complete()

    asyncio.run(run())

    assert failures == ["original error"]
    assert messages == ["original error"]
    assert "OSError: broken async sink" in fallback.getvalue()


def test_log_output_inside_logger_catch_still_logs_stderr(isolated_logger):
    fallback = io.StringIO()
    messages = []
    isolated_logger.add(
        lambda message: messages.append((message.record["level"].name, str(message)))
    )
    stream = companion_app.SimpleFileLikeFromLogOutputFunc(isolated_logger.error, fallback)

    @isolated_logger.catch
    def application_code():
        stream.write("ordinary stderr\n")
        stream.flush()

    application_code()

    assert len(messages) == 1
    assert messages[0][0] == "ERROR"
    assert "ordinary stderr" in messages[0][1]
    assert fallback.getvalue() == ""
