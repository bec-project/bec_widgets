""" Module for a LogPanel widget to display BEC log messages """

from __future__ import annotations

import operator
import os
import re
from collections import deque
from functools import partial, reduce
from re import Pattern
from typing import TYPE_CHECKING, Literal

from bec_lib.client import BECClient
from bec_lib.connector import ConnectorBase
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import LogLevel, bec_logger
from bec_lib.messages import LogMessage, StatusMessage
from qtpy.QtCore import QDateTime, Qt, Signal  # type: ignore
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.utils.colors import get_theme_palette, set_theme
from bec_widgets.widgets.editors.text_box.text_box import TextBox
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECServiceStatusMixin
from bec_widgets.widgets.utility.logpanel._util import (
    LineFilter,
    LineFormatter,
    LinesHtmlFormatter,
    create_formatter,
    level_filter,
    log_svc,
    log_time,
    log_txt,
    noop_format,
    simple_color_format,
)

if TYPE_CHECKING:
    from qtpy.QtCore import pyqtBoundSignal  # type: ignore

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# TODO: improve log color handling
DEFAULT_LOG_COLORS = {
    LogLevel.INFO: "#FFFFFF",
    LogLevel.SUCCESS: "#00FF00",
    LogLevel.WARNING: "#FFCC00",
    LogLevel.ERROR: "#FF0000",
    LogLevel.DEBUG: "#0000CC",
}


class BecLogsQueue:
    """Manages getting logs from BEC Redis and formatting them for display"""

    def __init__(
        self,
        conn: ConnectorBase,
        new_message_signal: pyqtBoundSignal,
        maxlen: int = 1000,
        line_formatter: LineFormatter = noop_format,
    ) -> None:
        self._timestamp_start: QDateTime | None = None
        self._timestamp_end: QDateTime | None = None
        self._conn = conn
        self._new_message_signal: pyqtBoundSignal | None = new_message_signal
        self._max_length = maxlen
        self._data: deque[LogMessage] = deque([], self._max_length)
        self._display_queue: deque[str] = deque([], self._max_length)
        self._log_level: str | None = None
        self._search_query: Pattern | str | None = None
        self._selected_services: set[str] | None = None
        self._set_formatter_and_update_filter(line_formatter)
        self._conn.register([MessageEndpoints.log()], None, self._process_incoming_log_msg)

    def disconnect(self):
        self._conn.unregister([MessageEndpoints.log()], None, self._process_incoming_log_msg)
        self._new_message_signal = None

    def _process_incoming_log_msg(self, msg: dict):
        _msg: LogMessage = msg["data"]
        self._data.append(_msg)
        if self.filter is None or self.filter(_msg):
            self._display_queue.append(self._line_formatter(_msg))
            if self._new_message_signal:
                self._new_message_signal.emit()

    def _set_formatter_and_update_filter(self, line_formatter: LineFormatter = noop_format):
        self._line_formatter: LineFormatter = line_formatter
        self._queue_formatter: LinesHtmlFormatter = create_formatter(
            self._line_formatter, self.filter
        )

    def _combine_filters(self, *args: LineFilter):
        return lambda msg: reduce(operator.and_, [filt(msg) for filt in args if filt is not None])

    def _create_re_filter(self) -> LineFilter:
        if self._search_query is None:
            return None
        elif isinstance(self._search_query, str):
            return lambda line: self._search_query in log_txt(line)
        return lambda line: self._search_query.match(log_txt(line)) is not None

    def _create_service_filter(self):
        return (
            lambda line: self._selected_services is None or log_svc(line) in self._selected_services
        )

    def _create_timestamp_filter(self) -> LineFilter:
        s, e = self._timestamp_start, self._timestamp_end
        if s is e is None:
            return lambda msg: True

        def _time_filter(msg):
            msg_time = log_time(msg)
            if s is None:
                return msg_time <= e
            if e is None:
                return s <= msg_time
            return s <= msg_time <= e

        return _time_filter

    @property
    def filter(self) -> LineFilter:
        thresh = LogLevel[self._log_level].value if self._log_level is not None else 0
        return self._combine_filters(
            partial(level_filter, thresh=thresh),
            self._create_re_filter(),
            self._create_timestamp_filter(),
            self._create_service_filter(),
        )

    def update_level_filter(self, level: str):
        if level not in [l.name for l in LogLevel]:
            logger.error(f"Logging level {level} unrecognized for filter!")
            return
        self._log_level = level
        self._set_formatter_and_update_filter(self._line_formatter)

    def update_search_filter(self, search_query: Pattern | str | None = None):
        self._search_query = search_query
        self._set_formatter_and_update_filter(self._line_formatter)

    def update_time_filter(self, start: QDateTime | None, end: QDateTime | None):
        self._timestamp_start = start
        self._timestamp_end = end
        self._set_formatter_and_update_filter(self._line_formatter)

    def update_service_filter(self, services: set[str]):
        self._selected_services = services
        self._set_formatter_and_update_filter(self._line_formatter)

    def update_line_formatter(self, line_formatter: LineFormatter):
        self._set_formatter_and_update_filter(line_formatter)

    def display_all(self) -> str:
        return "\n".join(self._queue_formatter(self._data.copy()))

    def format_new(self):
        res = "\n".join(self._display_queue)
        self._display_queue = deque([], self._max_length)
        return res

    def clear_logs(self):
        self._data = deque([])
        self._display_queue = deque([])

    def fetch_history(self):
        self._data = deque(
            item["data"]
            for item in self._conn.xread(
                MessageEndpoints.log().endpoint, from_start=True, count=self._max_length
            )
        )

    def unique_service_names_from_history(self) -> set[str]:
        return set(msg.log_msg["service_name"] for msg in self._data)


class LogPanelToolbar(QWidget):

    services_selected: pyqtBoundSignal = Signal(set)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # in unix time
        self._timestamp_start: QDateTime | None = None
        self._timestamp_end: QDateTime | None = None

        self._unique_service_names: set[str] = set()
        self._services_selected: set[str] | None = None

        self.layout = QHBoxLayout(self)  # type: ignore

        self.service_choice_button = QPushButton("Select services", self)
        self.layout.addWidget(self.service_choice_button)
        self.service_choice_button.clicked.connect(self._open_service_filter_dialog)

        self.filter_level_dropdown = self._log_level_box()
        self.layout.addWidget(self.filter_level_dropdown)

        self.clear_button = QPushButton("Clear all", self)
        self.layout.addWidget(self.clear_button)
        self.fetch_button = QPushButton("Fetch history", self)
        self.layout.addWidget(self.fetch_button)

        self._string_search_box()

        self.timerange_button = QPushButton("Set time range", self)
        self.layout.addWidget(self.timerange_button)

    @property
    def time_start(self):
        return self._timestamp_start

    @property
    def time_end(self):
        return self._timestamp_end

    def _string_search_box(self):
        self.layout.addWidget(QLabel("Search: "))
        self.search_textbox = QLineEdit()
        self.layout.addWidget(self.search_textbox)
        self.layout.addWidget(QLabel("Use regex: "))
        self.regex_enabled = QCheckBox()
        self.layout.addWidget(self.regex_enabled)
        self.update_re_button = QPushButton("Update search", self)
        self.layout.addWidget(self.update_re_button)

    def _log_level_box(self):
        box = QComboBox()
        box.setToolTip("Display logs with equal or greater significance to the selected level.")
        [box.addItem(l.name) for l in LogLevel]
        return box

    def _current_ts(self, selection_type: Literal["start", "end"]):
        if selection_type == "start":
            return self._timestamp_start
        elif selection_type == "end":
            return self._timestamp_end
        else:
            raise ValueError(f"timestamps can only be for the start or end, not {selection_type}")

    def _open_datetime_dialog(self):
        """Open dialog window for timestamp filter selection"""
        self._dt_dialog = QDialog(self)
        self._dt_dialog.setWindowTitle("Time range selection")
        layout = QVBoxLayout()

        label_start = QLabel()
        label_end = QLabel()

        def date_button_set(selection_type: Literal["start", "end"], label: QLabel):
            dt = self._current_ts(selection_type)
            _layout = QHBoxLayout()
            layout.addLayout(_layout)
            date_button = QPushButton(f"Time {selection_type}")
            _layout.addWidget(date_button)
            label.setText(dt.toString() if dt else "not selected")
            _layout.addWidget(label)
            date_button.clicked.connect(partial(self._open_cal_dialog, selection_type, label))
            date_clear_button = QPushButton("clear")
            date_clear_button.clicked.connect(
                lambda: (
                    partial(self._update_time, selection_type)(None),
                    label.setText("not selected"),
                )
            )
            _layout.addWidget(date_clear_button)

        for v in [("start", label_start), ("end", label_end)]:
            date_button_set(*v)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self._dt_dialog.accept)
        layout.addWidget(close_button)
        self._dt_dialog.setLayout(layout)
        self._dt_dialog.exec()
        self._dt_dialog = None

    def _open_cal_dialog(self, selection_type: Literal["start", "end"], label: QLabel):
        """Open dialog window for timestamp filter selection"""
        dt = self._current_ts(selection_type) or QDateTime.currentDateTime()
        label.setText(dt.toString() if dt else "not selected")
        if selection_type == "start":
            self._timestamp_start = dt
        else:
            self._timestamp_end = dt
        self._cal_dialog = QDialog(self)
        self._cal_dialog.setWindowTitle(f"Select time range {selection_type}")
        layout = QVBoxLayout()
        cal = QDateTimeEdit()
        cal.setCalendarPopup(True)
        cal.setDateTime(dt)
        cal.setDisplayFormat("yyyy-MM-dd HH:mm:ss.zzz")
        cal.dateTimeChanged.connect(partial(self._update_time, selection_type))
        layout.addWidget(cal)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self._cal_dialog.accept)
        layout.addWidget(close_button)
        self._cal_dialog.setLayout(layout)
        self._cal_dialog.exec()
        self._cal_dialog = None

    def _update_time(self, selection_type: Literal["start", "end"], dt: QDateTime | None):
        if selection_type == "start":
            self._timestamp_start = dt
        else:
            self._timestamp_end = dt

    @SafeSlot(dict, set)
    def service_list_update(
        self, services_info: dict[str, StatusMessage], services_from_history: set[str], *_, **__
    ):
        self._unique_service_names = set([s.split("/")[0] for s in services_info.keys()])
        self._unique_service_names |= services_from_history
        if self._services_selected is None:
            self._services_selected = self._unique_service_names

    @SafeSlot()
    def _open_service_filter_dialog(self):
        if len(self._unique_service_names) == 0 or self._services_selected is None:
            return
        self._svc_dialog = QDialog(self)
        self._svc_dialog.setWindowTitle(f"Select services to show logs from")
        layout = QVBoxLayout()
        service_cb_grid = QGridLayout(parent=self)
        layout.addLayout(service_cb_grid)

        def check_box(name: str, checked: Qt.CheckState):
            if checked == Qt.CheckState.Checked:
                self._services_selected.add(name)
            else:
                if name in self._services_selected:
                    self._services_selected.remove(name)
            self.services_selected.emit(self._services_selected)

        for i, svc in enumerate(self._unique_service_names):
            service_cb_grid.addWidget(QLabel(svc), i, 0)
            cb = QCheckBox()
            cb.setChecked(svc in self._services_selected)
            cb.checkStateChanged.connect(partial(check_box, svc))
            service_cb_grid.addWidget(cb, i, 1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self._svc_dialog.accept)
        layout.addWidget(close_button)
        self._svc_dialog.setLayout(layout)
        self._svc_dialog.exec()
        self._svc_dialog = None


class LogPanel(TextBox):
    """Displays a log panel"""

    ICON_NAME = "terminal"
    _new_messages = Signal()
    service_list_update = Signal(dict, set)

    def __init__(self, parent=None, client: BECClient | None = None, **kwargs):
        """Initialize the LogPanel widget."""
        super().__init__(parent=parent, client=client, **kwargs)
        self._update_colors()
        self._service_status = BECServiceStatusMixin(self, client=self.client)  # type: ignore
        self._log_manager = BecLogsQueue(
            self.client.connector,  # type: ignore
            new_message_signal=self._new_messages,
            line_formatter=partial(simple_color_format, colors=self._colors),
        )

        self.toolbar = LogPanelToolbar(parent=parent)
        self.toolbar_area = QScrollArea()
        self.toolbar_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.toolbar_area.setSizeAdjustPolicy(QScrollArea.SizeAdjustPolicy.AdjustToContents)
        self.toolbar_area.setFixedHeight(int(self.toolbar.clear_button.height() * 2))
        self.toolbar_area.setWidget(self.toolbar)

        self.layout.addWidget(self.toolbar_area)
        self.toolbar.clear_button.clicked.connect(self._on_clear)
        self.toolbar.fetch_button.clicked.connect(self._on_fetch)
        self.toolbar.update_re_button.clicked.connect(self._on_re_update)
        self.toolbar.search_textbox.returnPressed.connect(self._on_re_update)
        self.toolbar.regex_enabled.checkStateChanged.connect(self._on_re_update)
        self.toolbar.filter_level_dropdown.currentTextChanged.connect(self._set_level_filter)
        self._new_messages.connect(self._on_append)

        self.toolbar.timerange_button.clicked.connect(self._choose_datetime)
        self._service_status.services_update.connect(self._update_service_list)
        self.service_list_update.connect(self.toolbar.service_list_update)
        self.toolbar.services_selected.connect(self._update_service_filter)

        self.text_box_text_edit.setFont(QFont("monospace", 12))
        self.text_box_text_edit.setHtml("")
        self.text_box_text_edit.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)

        self._connect_to_theme_change()

    @SafeSlot(set)
    def _update_service_filter(self, services: set[str]):
        self._log_manager.update_service_filter(services)
        self._on_redraw()

    @SafeSlot(dict, dict)
    def _update_service_list(self, services_info: dict[str, StatusMessage], *_, **__):
        self.service_list_update.emit(
            services_info, self._log_manager.unique_service_names_from_history()
        )

    @SafeSlot()
    def _choose_datetime(self):
        self.toolbar._open_datetime_dialog()
        self._set_time_filter()

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self._on_redraw)  # type: ignore

    def _update_colors(self):
        self._colors = DEFAULT_LOG_COLORS.copy()
        self._colors.update({LogLevel.INFO: get_theme_palette().text().color().name()})

    def _cursor_to_end(self):
        c = self.text_box_text_edit.textCursor()
        c.movePosition(c.MoveOperation.End)
        self.text_box_text_edit.setTextCursor(c)

    @SafeSlot()
    @SafeSlot(str)
    def _on_redraw(self, *_):
        self._update_colors()
        self._log_manager.update_line_formatter(partial(simple_color_format, colors=self._colors))
        self.set_html_text(self._log_manager.display_all())
        self._cursor_to_end()

    @SafeSlot()
    def _on_append(self):
        self._cursor_to_end()
        self.text_box_text_edit.insertHtml(self._log_manager.format_new())

    @SafeSlot()
    def _on_clear(self):
        self._log_manager.clear_logs()
        self.set_html_text(self._log_manager.display_all())
        self._cursor_to_end()

    @SafeSlot()
    @SafeSlot(Qt.CheckState)
    def _on_re_update(self, *_):
        if self.toolbar.regex_enabled.isChecked():
            try:
                search_query = re.compile(self.toolbar.search_textbox.text())
            except Exception as e:
                logger.warning(f"Failed to compile search regex with error {e}")
                search_query = None
            logger.info(f"Setting LogPanel search regex to {search_query}")
        else:
            search_query = self.toolbar.search_textbox.text()
            logger.info(f'Setting LogPanel search string to "{search_query}"')
        self._log_manager.update_search_filter(search_query)
        self.set_html_text(self._log_manager.display_all())
        self._cursor_to_end()

    @SafeSlot()
    def _on_fetch(self):
        self._log_manager.fetch_history()
        self.set_html_text(self._log_manager.display_all())
        self._cursor_to_end()

    @SafeSlot(str)
    def _set_level_filter(self, level: str):
        self._log_manager.update_level_filter(level)
        self._on_redraw()

    @SafeSlot()
    def _set_time_filter(self):
        self._log_manager.update_time_filter(self.toolbar.time_start, self.toolbar.time_end)
        self._on_redraw()

    def cleanup(self):
        self._log_manager.disconnect()
        self._new_messages.disconnect(self._on_append)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication  # pylint: disable=ungrouped-imports

    app = QApplication(sys.argv)
    set_theme("dark")
    widget = LogPanel()

    widget.show()
    sys.exit(app.exec())
