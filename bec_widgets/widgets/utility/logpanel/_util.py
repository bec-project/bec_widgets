""" Utilities for filtering and formatting in the LogPanel"""

from __future__ import annotations

import re
from collections import deque
from typing import Callable, Iterator

from bec_lib.logger import LogLevel
from bec_lib.messages import LogMessage
from qtpy.QtCore import QDateTime

LinesHtmlFormatter = Callable[[deque[LogMessage]], Iterator[str]]
LineFormatter = Callable[[LogMessage], str]
LineFilter = Callable[[LogMessage], bool] | None

ANSI_ESCAPE_REGEX = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def replace_escapes(s: str):
    s = ANSI_ESCAPE_REGEX.sub("", s)
    return s.replace(" ", "&nbsp;").replace("\n", "<br />").replace("\t", "    ")


def level_filter(msg: LogMessage, thresh: int):
    return LogLevel[msg.content["log_type"].upper()].value >= thresh


def noop_format(line: LogMessage):
    _textline = line.log_msg if isinstance(line.log_msg, str) else line.log_msg["text"]
    return replace_escapes(_textline.strip()) + "<br />"


def simple_color_format(line: LogMessage, colors: dict[LogLevel, str]):
    color = colors.get(LogLevel[line.content["log_type"].upper()]) or colors[LogLevel.INFO]
    return f'<font color="{color}">{noop_format(line)}</font>'


def create_formatter(line_format: LineFormatter, line_filter: LineFilter) -> LinesHtmlFormatter:
    def _formatter(data: deque[LogMessage]):
        if line_filter is not None:
            return (line_format(line) for line in data if line_filter(line))
        else:
            return (line_format(line) for line in data)

    return _formatter


def log_txt(line):
    return line.log_msg if isinstance(line.log_msg, str) else line.log_msg["text"]


def log_time(line):
    return QDateTime.fromMSecsSinceEpoch(int(line.log_msg["record"]["time"]["timestamp"] * 1000))


def log_svc(line):
    return line.log_msg["service_name"]
