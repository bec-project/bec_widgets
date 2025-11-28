"""Module for a LogPanel widget to display BEC log messages"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from functools import partial
from typing import Iterable, Literal

from bec_lib.client import BECClient
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import LogLevel, bec_logger
from bec_lib.messages import LogMessage, StatusMessage
from qtpy.QtCore import Signal  # type: ignore
from qtpy.QtCore import (
    QAbstractTableModel,
    QCoreApplication,
    QDateTime,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QSize,
    QSortFilterProxyModel,
    Qt,
    QTimer,
)
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from thefuzz import fuzz

from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme
from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

_DEFAULT_LOG_COLORS = {
    LogLevel.INFO.name: QColor("#FFFFFF"),
    LogLevel.SUCCESS.name: QColor("#00FF00"),
    LogLevel.WARNING.name: QColor("#FFCC00"),
    LogLevel.ERROR.name: QColor("#FF0000"),
    LogLevel.DEBUG.name: QColor("#0000CC"),
}


@dataclass(frozen=True)
class _Constants:
    FUZZ_THRESHOLD = 80
    UPDATE_INTERVAL_MS = 200
    headers = ["level", "timestamp", "service_name", "message", "function"]


_CONST = _Constants()


class TimestampUpdate:
    def __init__(self, value: QDateTime | None, update_type: Literal["start", "end"]) -> None:
        self.value = value
        self.update_type = update_type


class BecLogsQueue(BECConnector, QObject):
    """Manages getting logs from BEC Redis and formatting them for display"""

    RPC = False
    new_messages = Signal()
    _instance: BecLogsQueue | None = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls(QCoreApplication.instance())
        return cls._instance

    def __init__(self, parent: QObject | None, maxlen: int = 1000, **kwargs) -> None:
        if BecLogsQueue._instance:
            raise RuntimeError("Create no more than one BecLogsQueue - use BecLogsQueue.instance()")
        super().__init__(parent=parent, **kwargs)
        self._max_length = maxlen
        self._data = deque(
            (
                item["data"]
                for item in self.bec_dispatcher.client.connector.xread(
                    MessageEndpoints.log(), count=self._max_length, id="0"
                )
            ),
            maxlen=self._max_length,
        )
        self._incoming: deque[LogMessage] = deque([], maxlen=self._max_length)
        self.bec_dispatcher.connect_slot(self._process_incoming_log_msg, MessageEndpoints.log())

        self._update_timer = QTimer(self, interval=_CONST.UPDATE_INTERVAL_MS)
        self._update_timer.timeout.connect(self._proc_update)
        QCoreApplication.instance().aboutToQuit.connect(self.cleanup)  # type: ignore
        self._update_timer.start()

    def __len__(self):
        return len(self._data)

    def row_data(self, index: int) -> LogMessage | None:
        if index < 0 or index > (len(self._data) - 1):
            return None
        return self._data[index]

    def cell_data(self, row: int, key: str):
        if key == "level":
            return self._data[row].log_type.upper()

        msg_item = self._data[row].log_msg
        if isinstance(msg_item, str):
            return msg_item
        if key == "service_name":
            return msg_item.get(key)
        elif key in ["service_name", "function", "message"]:
            return msg_item.get("record", {}).get(key)
        elif key == "timestamp":
            return msg_item.get("record", {}).get("time", {}).get("repr")

    def log_timestamp(self, row: int) -> float:
        msg_item = self._data[row].log_msg
        if isinstance(msg_item, str):
            return 0
        return msg_item.get("record", {}).get("time", {}).get("timestamp")

    def cleanup(self, *_):
        """Stop listening to the Redis log stream"""
        self.bec_dispatcher.disconnect_slot(
            self._process_incoming_log_msg, [MessageEndpoints.log()]
        )
        self._update_timer.stop()
        BecLogsQueue._instance = None

    @SafeSlot(verify_sender=True)
    def _process_incoming_log_msg(self, msg: dict, _metadata: dict):
        try:
            _msg = LogMessage(**msg)
            self._incoming.append(_msg)
        except Exception as e:
            if "Internal C++ object (BecLogsQueue) already deleted." in e.args:
                return
            logger.warning(f"Error in LogPanel incoming message callback: {e}")

    @SafeSlot(verify_sender=True)
    def _proc_update(self):
        if len(self._incoming) == 0:
            return
        self._data.extend(self._incoming)
        self._incoming.clear()
        self.new_messages.emit()


class BecLogsTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.log_queue = BecLogsQueue.instance()
        self.log_queue.new_messages.connect(self.handle_new_messages)
        self._headers = _CONST.headers

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self.log_queue)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section, orientation, role=int(Qt.ItemDataRole.DisplayRole)):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def get_row_data(self, index: QModelIndex) -> LogMessage | None:
        """Return the row data for the given index."""
        if not index.isValid():
            return None
        return self.log_queue.row_data(index.row())

    def timestamp(self, row: int):
        return QDateTime.fromMSecsSinceEpoch(int(self.log_queue.log_timestamp(row) * 1000))

    def data(self, index, role=int(Qt.ItemDataRole.DisplayRole)):
        """Return data for the given index and role."""
        if not index.isValid():
            return
        if role in [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole]:
            return self.log_queue.cell_data(index.row(), self._headers[index.column()])
        if role in [Qt.ItemDataRole.ForegroundRole]:
            return self._map_log_level_color(self.log_queue.cell_data(index.row(), "level"))

    def _map_log_level_color(self, data):
        return _DEFAULT_LOG_COLORS.get(data)

    def handle_new_messages(self):
        self.dataChanged.emit(
            self.index(0, 0), self.index(self.rowCount() - 1, self.columnCount() - 1)
        )


class LogMsgProxyModel(QSortFilterProxyModel):

    show_service_column = Signal(bool)

    def __init__(
        self,
        parent=None,
        service_filter: set[str] | None = None,
        level_filter: LogLevel | None = None,
    ):
        super().__init__(parent)
        self._service_filter = service_filter or set()
        self._level_filter: LogLevel | None = level_filter
        self._filter_text: str = ""
        self._fuzzy_search: bool = False
        self._time_filter_start: QDateTime | None = None
        self._time_filter_end: QDateTime | None = None

    def get_row_data(self, rows: Iterable[QModelIndex]) -> Iterable[LogMessage | None]:
        return (self.sourceModel().get_row_data(self.mapToSource(idx)) for idx in rows)

    def sourceModel(self) -> BecLogsTableModel:
        return super().sourceModel()  # type: ignore

    @SafeSlot(int, int)
    def refresh(self, *_):
        self.invalidateRowsFilter()

    @SafeSlot(None)
    @SafeSlot(set)
    def update_service_filter(self, filter: set[str]):
        """Filter to the selected services (show any service in the provided set)

        Args:
            filter (set[str] | None): set of services for which to show logs"""
        self._service_filter = filter
        self.show_service_column.emit(len(filter) != 1)
        self.invalidateRowsFilter()

    @SafeSlot(None)
    @SafeSlot(LogLevel)
    def update_level_filter(self, filter: LogLevel | None):
        """Filter to the selected log level

        Args:
            filter (str | None): lowest log level to show"""
        self._level_filter = filter
        self.invalidateRowsFilter()

    @SafeSlot(str)
    def update_filter_text(self, filter: str):
        """Filter messages based on text

        Args:
            filter (str | None): set of services for which to show logs"""
        self._filter_text = filter
        self.invalidateRowsFilter()

    @SafeSlot(bool)
    def update_fuzzy(self, state: bool):
        """Set text filter to fuzzy search or not

        Args:
            state (bool): fuzzy search on"""
        self._fuzzy_search = state
        self.invalidateRowsFilter()

    @SafeSlot(TimestampUpdate)
    def update_timestamp(self, update: TimestampUpdate):
        if update.update_type == "start":
            self._time_filter_start = update.value
        else:
            self._time_filter_end = update.value
        self.invalidateRowsFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        # No service filter, and no filter text, display everything
        possible_filters = [
            self._service_filter,
            self._level_filter,
            self._filter_text,
            self._time_filter_start,
            self._time_filter_end,
        ]
        if not any(map(bool, possible_filters)):
            return True
        model = self.sourceModel()
        # Filter out services
        if self._service_filter:
            col = _CONST.headers.index("service_name")
            if model.data(model.index(source_row, col, source_parent)) not in self._service_filter:
                return False
        # Filter out levels
        if self._level_filter:
            col = _CONST.headers.index("level")
            level: str = model.data(model.index(source_row, col, source_parent))  # type: ignore
            if LogLevel[level] < self._level_filter:
                return False
        # Filter time
        if self._time_filter_start:
            if model.timestamp(source_row) < self._time_filter_start:
                return False
        if self._time_filter_end:
            if model.timestamp(source_row) > self._time_filter_end:
                return False
        # Filter message text - must go last because this can return True
        if self._filter_text:
            col = _CONST.headers.index("message")
            msg: str = model.data(model.index(source_row, col, source_parent)).lower()  # type: ignore
            if self._fuzzy_search:
                if fuzz.partial_ratio(self._filter_text.lower(), msg) >= _CONST.FUZZ_THRESHOLD:
                    return True
            else:
                return self._filter_text.lower() in msg.lower()
        return True


class BecLogTableView(QTableView):
    def __init__(self, *args, max_message_width: int = 1000, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        header = QHeaderView(Qt.Orientation.Horizontal, parent=self)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(True)
        header.setMaximumSectionSize(max_message_width)
        self.setHorizontalHeader(header)

    def model(self) -> LogMsgProxyModel:
        return super().model()  # type: ignore


class LogPanel(BECWidget, QWidget):
    """Live display of the BEC logs in a table view."""

    PLUGIN = True

    def __init__(
        self,
        parent: QWidget | None = None,
        max_message_width: int = 1000,
        show_toolbar: bool = True,
        service_filter: set[str] | None = None,
        level_filter: LogLevel | None = None,
        **kwargs,
    ) -> None:
        super().__init__(parent=parent, **kwargs)
        self._setup_models(service_filter=service_filter, level_filter=level_filter)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        if show_toolbar:
            self._setup_toolbar(client=self.client)
        self._setup_table_view(max_message_width=max_message_width)
        self._update_service_filter(service_filter or set())
        if show_toolbar:
            self._connect_toolbar()
        self._proxy.show_service_column.connect(self._show_service_column)
        colors = QApplication.instance().theme.accent_colors  # type: ignore
        dict_colors = QApplication.instance().theme.colors  # type: ignore
        _DEFAULT_LOG_COLORS.update(
            {
                LogLevel.INFO.name: dict_colors["FG"],
                LogLevel.SUCCESS.name: colors.success,
                LogLevel.WARNING.name: colors.warning,
                LogLevel.ERROR.name: colors.emergency,
                LogLevel.DEBUG.name: dict_colors["BORDER"],
            }
        )
        self._table.scrollToBottom()

    def _setup_models(self, service_filter: set[str] | None, level_filter: LogLevel | None):
        self._model = BecLogsTableModel(parent=self)
        self._proxy = LogMsgProxyModel(
            parent=self, service_filter=service_filter, level_filter=level_filter
        )
        self._proxy.setSourceModel(self._model)
        self._model.log_queue.new_messages.connect(self._proxy.refresh)

    def _setup_table_view(self, max_message_width: int) -> None:
        """Setup the table view."""
        self._table = BecLogTableView(self, max_message_width=max_message_width)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._table)
        self._table.setModel(self._proxy)
        self._table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self._table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._table.resizeColumnsToContents()

    def _setup_toolbar(self, client: BECClient):
        self._toolbar = LogPanelToolbar(self, client)
        self._layout.addWidget(self._toolbar)

    def _connect_toolbar(self):
        self._toolbar.services_selected.connect(self._proxy.update_service_filter)
        self._toolbar.search_textbox.textChanged.connect(self._proxy.update_filter_text)
        self._toolbar.level_changed.connect(self._proxy.update_level_filter)
        self._toolbar.fuzzy_changed.connect(self._proxy.update_fuzzy)
        self._toolbar.timestamp_update.connect(self._proxy.update_timestamp)

    def _update_service_filter(self, filter: set[str]):
        self._service_filter = filter
        self._proxy.update_service_filter(filter)
        self._table.setColumnHidden(
            _CONST.headers.index("service_name"), len(self._service_filter) == 1
        )

    @SafeSlot(bool)
    def _show_service_column(self, show: bool):
        self._table.setColumnHidden(_CONST.headers.index("service_name"), not show)

    def sizeHint(self) -> QSize:
        return QSize(600, 300)


class LogPanelToolbar(QWidget):

    services_selected = Signal(set)
    level_changed = Signal(LogLevel)
    fuzzy_changed = Signal(bool)
    timestamp_update = Signal(TimestampUpdate)

    def __init__(self, parent: QWidget | None = None, client: BECClient | None = None) -> None:
        """A toolbar for the logpanel, mainly used for managing the states of filters"""
        super().__init__(parent)

        # in unix time
        self._timestamp_start: QDateTime | None = None
        self._timestamp_end: QDateTime | None = None

        self._unique_service_names: set[str] = set()
        self._services_selected: set[str] = set()

        self._layout = QHBoxLayout(self)

        if client is not None:
            self.client = client
            self.service_choice_button = QPushButton("Select services", self)
            self._layout.addWidget(self.service_choice_button)
            self.service_choice_button.clicked.connect(self._open_service_filter_dialog)

        self.filter_level_dropdown = self._log_level_box()
        self._layout.addWidget(self.filter_level_dropdown)
        self.filter_level_dropdown.currentTextChanged.connect(self._emit_level)

        self._string_search_box()

        self.timerange_button = QPushButton("Set time range", self)
        self._layout.addWidget(self.timerange_button)
        self.timerange_button.clicked.connect(self._open_datetime_dialog)

    def _string_search_box(self):
        self._layout.addWidget(QLabel("Search: "))
        self.search_textbox = QLineEdit()
        self._layout.addWidget(self.search_textbox)
        self._layout.addWidget(QLabel("Fuzzy: "))
        self.fuzzy = QCheckBox()
        self._layout.addWidget(self.fuzzy)
        self.fuzzy.checkStateChanged.connect(self._emit_fuzzy)

    def _log_level_box(self):
        box = QComboBox()
        box.setToolTip("Display logs with equal or greater significance to the selected level.")
        [box.addItem(l.name) for l in LogLevel]
        return box

    @SafeSlot(str)
    def _emit_level(self, level: str):
        self.level_changed.emit(LogLevel[level])

    @SafeSlot(Qt.CheckState)
    def _emit_fuzzy(self, state: Qt.CheckState):
        self.fuzzy_changed.emit(state == Qt.CheckState.Checked)

    def _current_ts(self, selection_type: Literal["start", "end"]):
        if selection_type == "start":
            return self._timestamp_start
        elif selection_type == "end":
            return self._timestamp_end
        else:
            raise ValueError(f"timestamps can only be for the start or end, not {selection_type}")

    @SafeSlot()
    def _open_datetime_dialog(self):
        """Open dialog window for timestamp filter selection"""
        self._dt_dialog = QDialog(self)
        self._dt_dialog.setWindowTitle("Time range selection")
        layout = QVBoxLayout()
        self._dt_dialog.setLayout(layout)

        label_start = QLabel(parent=self._dt_dialog)
        label_end = QLabel(parent=self._dt_dialog)

        def date_button_set(selection_type: Literal["start", "end"], label: QLabel):
            dt = self._current_ts(selection_type)
            _layout = QHBoxLayout()
            layout.addLayout(_layout)
            date_button = QPushButton(f"Time {selection_type}", parent=self._dt_dialog)
            _layout.addWidget(date_button)
            label.setText(dt.toString() if dt else "not selected")
            _layout.addWidget(label)
            date_button.clicked.connect(partial(self._open_cal_dialog, selection_type, label))
            date_clear_button = QPushButton("clear", parent=self._dt_dialog)
            date_clear_button.clicked.connect(
                lambda: (
                    partial(self._update_time, selection_type)(None),
                    label.setText("not selected"),
                )
            )
            _layout.addWidget(date_clear_button)

        date_button_set("start", label_start)
        date_button_set("end", label_end)

        close_button = QPushButton("Close", parent=self._dt_dialog)
        close_button.clicked.connect(self._dt_dialog.accept)
        layout.addWidget(close_button)

        self._dt_dialog.exec()
        self._dt_dialog.deleteLater()

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
        self._cal_dialog.setLayout(layout)
        cal = QDateTimeEdit(parent=self._cal_dialog)
        cal.setCalendarPopup(True)
        cal.setDateTime(dt)
        cal.setDisplayFormat("yyyy-MM-dd HH:mm:ss.zzz")
        cal.dateTimeChanged.connect(partial(self._update_time, selection_type))
        layout.addWidget(cal)
        close_button = QPushButton("Close", parent=self._cal_dialog)
        close_button.clicked.connect(self._cal_dialog.accept)
        layout.addWidget(close_button)

        self._cal_dialog.exec()
        self._cal_dialog.deleteLater()

    def _update_time(self, selection_type: Literal["start", "end"], dt: QDateTime | None):
        if selection_type == "start":
            self._timestamp_start = dt
        else:
            self._timestamp_end = dt
        self.timestamp_update.emit(TimestampUpdate(value=dt, update_type=selection_type))

    def service_list_update(self, services_info: dict[str, StatusMessage]):
        """Change the list of services which can be selected"""
        self._unique_service_names = set([s.split("/")[0] for s in services_info.keys()])

    @SafeSlot()
    def _open_service_filter_dialog(self):
        self.service_list_update(self.client.service_status)
        if len(self._unique_service_names) == 0 or self._services_selected is None:
            return
        self._svc_dialog = QDialog(self)
        self._svc_dialog.setWindowTitle(f"Select services to show logs from")
        layout = QVBoxLayout()
        self._svc_dialog.setLayout(layout)

        service_cb_grid = QGridLayout()
        layout.addLayout(service_cb_grid)

        def check_box(name: str, checked: Qt.CheckState):
            if checked == Qt.CheckState.Checked:
                self._services_selected.add(name)
            else:
                if name in self._services_selected:
                    self._services_selected.remove(name)
            self.services_selected.emit(self._services_selected)

        for i, svc in enumerate(self._unique_service_names):
            service_cb_grid.addWidget(QLabel(svc, parent=self._svc_dialog), i, 0)
            cb = QCheckBox(parent=self._svc_dialog)
            cb.setChecked(svc in self._services_selected)
            cb.checkStateChanged.connect(partial(check_box, svc))
            service_cb_grid.addWidget(cb, i, 1)

        close_button = QPushButton("Close", parent=self._svc_dialog)
        close_button.clicked.connect(self._svc_dialog.accept)
        layout.addWidget(close_button)

        self._svc_dialog.exec()
        self._svc_dialog.deleteLater()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication  # pylint: disable=ungrouped-imports

    app = QApplication(sys.argv)
    apply_theme("dark")
    panel = QWidget()
    queue = BecLogsQueue(panel)
    layout = QVBoxLayout(panel)
    layout.addWidget(QLabel("All logs, no filters:"))
    layout.addWidget(LogPanel())
    layout.addWidget(QLabel("All services, level filter WARNING preapplied:"))
    layout.addWidget(LogPanel(level_filter=LogLevel.WARNING))
    layout.addWidget(QLabel('All services, service filter {"DeviceServer"} preapplied:'))
    layout.addWidget(LogPanel(service_filter={"DeviceServer"}))

    panel.show()
    sys.exit(app.exec())
