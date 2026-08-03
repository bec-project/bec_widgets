"""Module for a LogPanel widget to display BEC log messages"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from functools import partial
from typing import Iterable, Literal, NamedTuple

from bec_lib.client import BECClient
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import LogLevel, bec_logger
from bec_lib.messages import LogMessage, StatusMessage
from bec_qthemes import material_icon
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
from qtpy.QtGui import QPalette
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
    QStyle,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from thefuzz import fuzz

from bec_widgets.utils.bec_connector import BECConnector
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import apply_theme, get_accent_colors
from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


@dataclass(frozen=True)
class _Constants:
    FUZZ_THRESHOLD = 80
    UPDATE_INTERVAL_MS = 500
    TRIM_CHUNK = 250
    headers = ["level", "timestamp", "service_name", "message", "function"]


_CONST = _Constants()


class TimestampUpdate:
    def __init__(self, value: QDateTime | None, update_type: Literal["start", "end"]) -> None:
        self.value = value
        self.update_type = update_type


class _LogRec(NamedTuple):
    """A log message flattened for display and filtering. The first five fields are the
    table columns in `_Constants.headers` order, so `rec[column]` is the display value."""

    level: str
    timestamp: str
    service_name: str | None
    message: str
    function: str | None
    level_num: int | None
    ts: float
    message_lower: str
    raw: LogMessage


def _to_record(msg: LogMessage) -> _LogRec:
    """Flatten a LogMessage once at ingest so paint and filter passes never re-traverse it.

    This is the trust boundary for external Redis data: LogMessage.log_msg is typed
    `dict | str` with no inner-shape validation, so every field is coerced to a stable
    type here. The filter comparisons, the service-set membership check, and the
    delegate's text painting all rely on that - an exception raised later inside a Qt
    override (filterAcceptsRow, paint) is crash-class on PySide 6.10+.
    """
    level = msg.log_type.upper()
    try:
        level_num = LogLevel[level].value
    except KeyError:
        level_num = None
    log_msg = msg.log_msg
    if isinstance(log_msg, str):
        return _LogRec(level, "", None, log_msg, None, level_num, 0.0, log_msg.lower(), msg)
    record = log_msg.get("record")
    if not isinstance(record, dict):
        record = {}
    time_info = record.get("time")
    if not isinstance(time_info, dict):
        time_info = {}
    message = record.get("message")
    if not isinstance(message, str):
        message = "" if message is None else str(message)
    service = log_msg.get("service_name")
    if service is not None and not isinstance(service, str):
        service = str(service)
    function = record.get("function")
    if function is not None and not isinstance(function, str):
        function = str(function)
    ts_repr = time_info.get("repr")
    if not isinstance(ts_repr, str):
        ts_repr = ""
    try:
        ts = float(time_info.get("timestamp") or 0.0)
    except (TypeError, ValueError):
        ts = 0.0
    return _LogRec(level, ts_repr, service, message, function, level_num, ts, message.lower(), msg)


class BecLogsQueue(BECConnector, QObject):
    """Manages getting logs from BEC Redis and formatting them for display"""

    RPC = False
    new_records = Signal(list)
    paused = Signal(bool)
    _instance: BecLogsQueue | None = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls(QCoreApplication.instance())
        return cls._instance

    def __init__(self, parent: QObject | None, maxlen: int = 2500, **kwargs) -> None:
        if BecLogsQueue._instance:
            raise RuntimeError("Create no more than one BecLogsQueue - use BecLogsQueue.instance()")
        super().__init__(parent=parent, **kwargs)
        self._max_length = maxlen
        self._paused = False
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
        # register here rather than only in instance() so direct construction cannot
        # create a second, duplicate ingestion pipeline
        BecLogsQueue._instance = self

    def __len__(self):
        return len(self._data)

    @property
    def max_length(self) -> int:
        return self._max_length

    def snapshot_records(self) -> list[_LogRec]:
        """Convert the current history for a newly attached model."""
        return [_to_record(msg) for msg in self._data]

    @SafeSlot()
    def toggle_pause(self):
        self._paused = not self._paused
        self.paused.emit(self._paused)

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
        if self._paused or len(self._incoming) == 0:
            return
        batch = list(self._incoming)
        self._incoming.clear()
        self._data.extend(batch)
        self.new_records.emit([_to_record(msg) for msg in batch])


class BecLogsTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.log_queue = BecLogsQueue.instance()
        self._headers = _CONST.headers
        self._max_length = self.log_queue.max_length
        self._rows: list[_LogRec] = self.log_queue.snapshot_records()
        self.log_queue.new_records.connect(self._on_new_records)

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section, orientation, role=int(Qt.ItemDataRole.DisplayRole)):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section]
        return None

    def record(self, row: int) -> _LogRec:
        return self._rows[row]

    def get_row_data(self, index: QModelIndex) -> LogMessage | None:
        """Return the row data for the given index."""
        if not index.isValid():
            return None
        return self._rows[index.row()].raw

    def data(self, index, role=int(Qt.ItemDataRole.DisplayRole)):
        """Return data for the given index and role."""
        if not index.isValid():
            return
        if role in [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.ToolTipRole]:
            return self._rows[index.row()][index.column()]
        if role in [Qt.ItemDataRole.ForegroundRole]:
            return self._map_log_level_color(self._rows[index.row()].level)

    def _map_log_level_color(self, level: str):
        """Resolve the display color for a log level from the current theme. INFO and
        unmapped levels return None so the view uses the default palette text color."""
        accent_colors = get_accent_colors()
        return {
            LogLevel.SUCCESS.name: accent_colors.success,
            LogLevel.WARNING.name: accent_colors.warning,
            LogLevel.ERROR.name: accent_colors.emergency,
            LogLevel.DEBUG.name: QApplication.palette().color(QPalette.ColorRole.PlaceholderText),
        }.get(level)

    @SafeSlot(list)
    def _on_new_records(self, batch: list[_LogRec]):
        """Append a batch with proper model bracketing so views and proxies update
        incrementally instead of re-evaluating the whole buffer. The buffer is trimmed
        in chunks of TRIM_CHUNK (so it may transiently exceed max_length by up to that
        amount) to keep most ticks append-only."""
        overflow = len(self._rows) + len(batch) - self._max_length
        if overflow >= len(self._rows):
            # the batch alone fills (or overfills) the buffer: replace everything
            self.beginResetModel()
            self._rows = list(batch[-self._max_length :])
            self.endResetModel()
            return
        if overflow >= _CONST.TRIM_CHUNK:
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            del self._rows[:overflow]
            self.endRemoveRows()
        first = len(self._rows)
        self.beginInsertRows(QModelIndex(), first, first + len(batch) - 1)
        self._rows.extend(batch)
        self.endInsertRows()


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
        self._level_num: int | None = level_filter.value if level_filter is not None else None
        self._filter_text: str = ""
        self._fuzzy_search: bool = False
        self._ts_start: float | None = None
        self._ts_end: float | None = None

    def get_row_data(self, rows: Iterable[QModelIndex]) -> Iterable[LogMessage | None]:
        return (self.sourceModel().get_row_data(self.mapToSource(idx)) for idx in rows)

    def sourceModel(self) -> BecLogsTableModel:
        return super().sourceModel()  # type: ignore

    @SafeSlot(None)
    @SafeSlot(set)
    def update_service_filter(self, filter: set[str]):
        """Filter to the selected services (show any service in the provided set)

        Args:
            filter (set[str] | None): set of services for which to show logs"""
        self.beginFilterChange()
        self._service_filter = filter
        self.show_service_column.emit(len(filter) != 1)
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    @SafeSlot(None)
    @SafeSlot(LogLevel)
    def update_level_filter(self, filter: LogLevel | None):
        """Filter to the selected log level

        Args:
            filter (str | None): lowest log level to show"""
        self.beginFilterChange()
        self._level_num = filter.value if filter is not None else None
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    @SafeSlot(str)
    def update_filter_text(self, filter: str):
        """Filter messages based on text

        Args:
            filter (str | None): set of services for which to show logs"""
        self.beginFilterChange()
        self._filter_text = filter.lower()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    @SafeSlot(bool)
    def update_fuzzy(self, state: bool):
        """Set text filter to fuzzy search or not

        Args:
            state (bool): fuzzy search on"""
        self.beginFilterChange()
        self._fuzzy_search = state
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    @SafeSlot(TimestampUpdate)
    def update_timestamp(self, update: TimestampUpdate):
        self.beginFilterChange()
        ts = update.value.toMSecsSinceEpoch() / 1000 if update.value is not None else None
        if update.update_type == "start":
            self._ts_start = ts
        else:
            self._ts_end = ts
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:
        rec = self.sourceModel().record(source_row)
        if self._service_filter and rec.service_name not in self._service_filter:
            return False
        if (
            self._level_num is not None
            and rec.level_num is not None
            and rec.level_num < self._level_num
        ):
            return False
        if self._ts_start is not None and rec.ts < self._ts_start:
            return False
        if self._ts_end is not None and rec.ts > self._ts_end:
            return False
        # Filter message text - must go last because this can return True
        if self._filter_text:
            if self._fuzzy_search:
                return fuzz.partial_ratio(self._filter_text, rec.message_lower) >= (
                    _CONST.FUZZ_THRESHOLD
                )
            return self._filter_text in rec.message_lower
        return True


class _LogCellDelegate(QStyledItemDelegate):
    """Paints cells directly instead of going through QStyle's CE_ItemViewItem machinery,
    which is several times more expensive under a QSS-themed style. Log cells only need
    selection background, level color, and elided single-line text."""

    def paint(self, painter, option, index):
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            painter.setPen(option.palette.highlightedText().color())
        else:
            foreground = index.data(Qt.ItemDataRole.ForegroundRole)
            painter.setPen(foreground if foreground is not None else option.palette.text().color())
        text = index.data(Qt.ItemDataRole.DisplayRole)
        if text:
            rect = option.rect.adjusted(4, 0, -4, 0)
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
                painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, rect.width()),
            )


class BecLogTableView(QTableView):
    def __init__(self, *args, max_message_width: int = 1000, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setItemDelegate(_LogCellDelegate(self))
        header = QHeaderView(Qt.Orientation.Horizontal, parent=self)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setMaximumSectionSize(max_message_width)
        header.setResizeContentsPrecision(50)
        self.setHorizontalHeader(header)
        self.verticalHeader().hide()
        self.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerItem)
        self._rows_removed_above = 0
        self._was_at_bottom = False
        self._update_latched = False

    def model(self) -> LogMsgProxyModel:
        return super().model()  # type: ignore

    def setModel(self, model):
        super().setModel(model)
        model.rowsAboutToBeInserted.connect(self._on_rows_about_to_change)
        model.rowsAboutToBeRemoved.connect(self._on_rows_about_to_be_removed)
        model.rowsInserted.connect(self._on_update_finished)
        model.modelAboutToBeReset.connect(self._latch_scroll_state)
        model.modelReset.connect(self._finish_update)

    def _latch_scroll_state(self):
        """Capture, once per update cycle, whether the view is pinned to the bottom.
        A cycle is an optional top-trim followed by an insert (or a model reset)."""
        if self._update_latched:
            return
        self._update_latched = True
        scrollbar = self.verticalScrollBar()
        self._was_at_bottom = scrollbar.value() >= scrollbar.maximum()

    def _finish_update(self):
        """Restore the scroll position after an update cycle: follow the tail when the
        view was pinned to the bottom, otherwise keep the content anchored by shifting
        the position by the number of rows trimmed above it."""
        if not self._update_latched:
            return
        if self._was_at_bottom:
            self.scrollToBottom()
        elif self._rows_removed_above:
            scrollbar = self.verticalScrollBar()
            scrollbar.setValue(max(0, scrollbar.value() - self._rows_removed_above))
        self._update_latched = False
        self._rows_removed_above = 0

    @SafeSlot(QModelIndex, int, int)
    def _on_rows_about_to_change(self, *_):
        self._latch_scroll_state()

    @SafeSlot(QModelIndex, int, int)
    def _on_rows_about_to_be_removed(self, _parent, first: int, last: int):
        self._latch_scroll_state()
        if first == 0:
            self._rows_removed_above = last - first + 1

    @SafeSlot(QModelIndex, int, int)
    def _on_update_finished(self, *_):
        self._finish_update()


class LogPanel(BECWidget, QWidget):
    """Live display of the BEC logs in a table view."""

    PLUGIN = True
    ICON_NAME = "browse_activity"

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
        self._table.scrollToBottom()

    def _setup_models(self, service_filter: set[str] | None, level_filter: LogLevel | None):
        self._model = BecLogsTableModel(parent=self)
        self._proxy = LogMsgProxyModel(
            parent=self, service_filter=service_filter, level_filter=level_filter
        )
        self._proxy.setSourceModel(self._model)

    def _setup_table_view(self, max_message_width: int) -> None:
        """Setup the table view."""
        self._table = BecLogTableView(self, max_message_width=max_message_width)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(self._table)
        self._table.setModel(self._proxy)
        self._table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self._table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._table.setWordWrap(False)
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
        self._toolbar.pause_button.clicked.connect(self._model.log_queue.toggle_pause)
        self._model.log_queue.paused.connect(self._toolbar._update_pause_button_icon)

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

    def cleanup(self):
        """Detach from the shared log queue so a closed panel stops receiving updates."""
        self._model.log_queue.new_records.disconnect(self._model._on_new_records)
        super().cleanup()


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
        self._services_selected: set[str] | None = None

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

        self.pause_button = QToolButton()
        self.pause_button.setIcon(material_icon("pause", size=(20, 20), convert_to_pixmap=False))
        self._PLAYING_TOOLTIP = "Pause live log updates."
        self._PAUSED_TOOLTIP = "Continue live log updates."
        self.pause_button.setToolTip(self._PLAYING_TOOLTIP)
        self._layout.addWidget(self.pause_button)

    @SafeSlot(bool)
    def _update_pause_button_icon(self, paused):
        if paused:
            icon = "play_arrow"
            tooltip = self._PAUSED_TOOLTIP
        else:
            icon = "pause"
            tooltip = self._PLAYING_TOOLTIP
        self.pause_button.setIcon(material_icon(icon, size=(20, 20), convert_to_pixmap=False))
        self.pause_button.setToolTip(tooltip)

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
        [box.addItem(level.name) for level in LogLevel]
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
        if len(self._unique_service_names) == 0:
            return
        if self._services_selected is None:
            self._services_selected = set(self._unique_service_names)
        self._svc_dialog = QDialog(self)
        self._svc_dialog.setWindowTitle("Select services to show logs from")
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
    layout = QVBoxLayout(panel)
    layout.addWidget(QLabel("All logs, no filters:"))
    layout.addWidget(LogPanel())
    layout.addWidget(QLabel("All services, level filter WARNING preapplied:"))
    layout.addWidget(LogPanel(level_filter=LogLevel.WARNING))
    layout.addWidget(QLabel('All services, service filter {"DeviceServer"} preapplied:'))
    layout.addWidget(LogPanel(service_filter={"DeviceServer"}))

    panel.show()
    sys.exit(app.exec())
