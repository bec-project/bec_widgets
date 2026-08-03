"""Module for a LogPanel widget to display BEC log messages"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass
from datetime import datetime
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
from qtpy.QtGui import (
    QAction,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QKeySequence,
    QPalette,
    QShortcut,
)
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
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
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot

logger = bec_logger.logger

MODULE_PATH = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


@dataclass(frozen=True)
class _Constants:
    FUZZ_THRESHOLD = 80
    UPDATE_INTERVAL_MS = 500
    TRIM_CHUNK = 250
    SEARCH_DEBOUNCE_MS = 200
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
    timestamp_full: str


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
        return _LogRec(level, "", None, log_msg, None, level_num, 0.0, log_msg.lower(), msg, "")
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
    if ts:
        moment = datetime.fromtimestamp(ts)
        ts_short = f"{moment:%H:%M:%S}.{moment.microsecond // 1000:03d}"
    else:
        ts_short = ts_repr
    return _LogRec(
        level, ts_short, service, message, function, level_num, ts, message.lower(), msg, ts_repr
    )


class BecLogsQueue(BECConnector, QObject):
    """Manages getting logs from BEC Redis and formatting them for display"""

    RPC = False
    new_records = Signal(list)
    paused = Signal(bool)
    buffered = Signal(int)
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
        if self._paused:
            self.buffered.emit(len(self._incoming))
            return
        if len(self._incoming) == 0:
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
        # True only while a live batch is being appended - views use this to distinguish
        # newly arrived logs from filter-change re-insertions
        self._live_append = False
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
        if role == Qt.ItemDataRole.DisplayRole:
            return self._rows[index.row()][index.column()]
        if role == Qt.ItemDataRole.ToolTipRole:
            rec = self._rows[index.row()]
            if index.column() == self._headers.index("timestamp"):
                return rec.timestamp_full or rec.timestamp
            return rec[index.column()]
        if role in [Qt.ItemDataRole.ForegroundRole]:
            return self._map_log_level_color(self._rows[index.row()].level)

    def _map_log_level_color(self, level: str):
        """Resolve the display color for a log level from the current theme. INFO and
        unmapped levels return None so the view uses the default palette text color."""
        accent_colors = get_accent_colors()
        placeholder = QApplication.palette().color(QPalette.ColorRole.PlaceholderText)
        return {
            LogLevel.SUCCESS.name: accent_colors.success,
            LogLevel.WARNING.name: accent_colors.warning,
            LogLevel.ERROR.name: accent_colors.emergency,
            LogLevel.CRITICAL.name: accent_colors.emergency,
            LogLevel.DEBUG.name: placeholder,
            LogLevel.TRACE.name: placeholder,
        }.get(level)

    @SafeSlot()
    def clear(self):
        """Clear this panel's view. The shared BecLogsQueue history is untouched, so
        sibling panels and future snapshots are unaffected."""
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    @SafeSlot(list)
    def _on_new_records(self, batch: list[_LogRec]):
        """Append a batch with proper model bracketing so views and proxies update
        incrementally instead of re-evaluating the whole buffer. The buffer is trimmed
        in chunks of TRIM_CHUNK (so it may transiently exceed max_length by up to that
        amount) to keep most ticks append-only."""
        self._live_append = True
        try:
            self._append_records(batch)
        finally:
            self._live_append = False

    def _append_records(self, batch: list[_LogRec]):
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
        # None means "no service filter"; an explicit set (possibly empty) is an include-list
        self._service_filter: set[str] | None = service_filter
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
    def update_service_filter(self, filter: set[str] | None):
        """Filter to the selected services.

        Args:
            filter (set[str] | None): include-list of services to show. None shows every
                service; an empty set shows nothing."""
        self.beginFilterChange()
        self._service_filter = filter
        self.show_service_column.emit(filter is None or len(filter) != 1)
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
        if self._service_filter is not None and rec.service_name not in self._service_filter:
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bold_font: QFont | None = None

    def reset_font_cache(self):
        self._bold_font = None

    def paint(self, painter, option, index):
        if index.column() == 0:
            if self._bold_font is None:
                self._bold_font = QFont(option.font)
                self._bold_font.setBold(True)
            painter.setFont(self._bold_font)
        else:
            painter.setFont(option.font)
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
        header.setMaximumSectionSize(max_message_width)
        header.setResizeContentsPrecision(50)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._show_header_menu)
        self.setHorizontalHeader(header)
        self.verticalHeader().hide()
        self.setShowGrid(False)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.apply_font(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerItem)
        self._rows_removed_above = 0
        self._was_at_bottom = False
        self._update_latched = False
        self._new_below = 0
        self._jump_button = QToolButton(self.viewport())
        self._jump_button.setIcon(
            material_icon("vertical_align_bottom", size=(16, 16), convert_to_pixmap=False)
        )
        self._jump_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._jump_button.setToolTip("Jump to the newest logs and follow them")
        # palette-driven pill so it stands out over rows in both themes
        self._jump_button.setStyleSheet(
            "QToolButton { background-color: palette(highlight);"
            " color: palette(highlighted-text);"
            " border: none; border-radius: 10px; padding: 3px 12px; }"
        )
        self._jump_button.hide()
        self._jump_button.clicked.connect(self.scrollToBottom)
        self.verticalScrollBar().valueChanged.connect(self._on_scrolled)

    def apply_font(self, font: QFont):
        """Apply a new base font and recompute the row metrics that depend on it."""
        self.setFont(font)
        self.verticalHeader().setDefaultSectionSize(self.fontMetrics().height() + 4)
        delegate = self.itemDelegate()
        if isinstance(delegate, _LogCellDelegate):
            delegate.reset_font_cache()

    def model(self) -> LogMsgProxyModel:
        return super().model()  # type: ignore

    def setModel(self, model):
        super().setModel(model)
        model.rowsAboutToBeInserted.connect(self._on_rows_about_to_change)
        model.rowsAboutToBeRemoved.connect(self._on_rows_about_to_be_removed)
        model.rowsInserted.connect(self._on_rows_inserted)
        model.rowsRemoved.connect(self._on_rows_removed)
        model.modelAboutToBeReset.connect(self._latch_scroll_state)
        model.modelReset.connect(self._on_model_reset)

    def _source_model(self) -> BecLogsTableModel:
        model = self.model()
        return model.sourceModel() if isinstance(model, QSortFilterProxyModel) else model

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_jump_button()

    def _place_jump_button(self):
        viewport = self.viewport()
        self._jump_button.adjustSize()
        self._jump_button.move(
            (viewport.width() - self._jump_button.width()) // 2,
            viewport.height() - self._jump_button.height() - 8,
        )
        self._jump_button.raise_()

    @SafeSlot(int)
    def _on_scrolled(self, value: int):
        if self._new_below and value >= self.verticalScrollBar().maximum():
            self._new_below = 0
            self._jump_button.hide()

    def _latch_scroll_state(self):
        """Capture, once per update cycle, whether the view is pinned to the bottom.
        A cycle is an optional top-trim followed by an insert (or a model reset)."""
        if self._update_latched:
            return
        self._update_latched = True
        scrollbar = self.verticalScrollBar()
        self._was_at_bottom = scrollbar.value() >= scrollbar.maximum()

    def _finish_update(self, inserted: int = 0):
        """Restore the scroll position after an update cycle: follow the tail when the
        view was pinned to the bottom, otherwise keep the content anchored by shifting
        the position by the number of rows trimmed above it and show how many new rows
        arrived below the current view."""
        if not self._update_latched:
            return
        if self._was_at_bottom:
            self.scrollToBottom()
        else:
            if self._rows_removed_above:
                scrollbar = self.verticalScrollBar()
                scrollbar.setValue(max(0, scrollbar.value() - self._rows_removed_above))
            if inserted:
                self._new_below += inserted
                self._jump_button.setText(f"{self._new_below} new")
                self._place_jump_button()
                self._jump_button.show()
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
    def _on_rows_inserted(self, _parent, first: int, last: int):
        # only count rows arriving from a live batch - filter relaxations re-insert
        # previously hidden rows and must not read as "new logs"
        inserted = last - first + 1 if self._source_model()._live_append else 0
        self._finish_update(inserted=inserted)

    @SafeSlot(QModelIndex, int, int)
    def _on_rows_removed(self, *_):
        # close removal-only cycles (e.g. a filter tightening) so the latch cannot go
        # stale and yank the scroll position on a later, unrelated insert
        self._finish_update()

    @SafeSlot()
    def _on_model_reset(self):
        self._new_below = 0
        self._jump_button.hide()
        self._finish_update()

    def _show_header_menu(self, pos):
        menu = QMenu(self)
        for col, name in enumerate(_CONST.headers):
            if name == "message":
                continue
            action = QAction(name.replace("_", " "), menu)
            action.setCheckable(True)
            action.setChecked(not self.isColumnHidden(col))
            action.toggled.connect(partial(self.set_column_shown, col))
            menu.addAction(action)
        menu.exec(self.horizontalHeader().mapToGlobal(pos))
        menu.deleteLater()

    def set_column_shown(self, col: int, shown: bool):
        self.setColumnHidden(col, not shown)


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
        self._font_size = 0
        self._setup_models(service_filter=service_filter, level_filter=level_filter)
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        if show_toolbar:
            self._setup_toolbar(client=self.client)
        self._setup_table_view(max_message_width=max_message_width)
        self._setup_detail_pane()
        self._update_service_filter(service_filter)
        if show_toolbar:
            self._connect_toolbar()
            if level_filter is not None:
                self._toolbar.set_level(level_filter)
            if service_filter is not None:
                self._toolbar.set_service_selection(service_filter)
        self._proxy.show_service_column.connect(self._show_service_column)
        self._setup_shortcuts(show_toolbar)
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
        self._table.setModel(self._proxy)
        self._table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self._table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self._table.setWordWrap(False)
        self._apply_table_widths()
        self._table.horizontalHeader().setSectionResizeMode(
            _CONST.headers.index("message"), QHeaderView.ResizeMode.Stretch
        )
        self._table.setColumnHidden(_CONST.headers.index("function"), True)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_table_context_menu)
        self._table.doubleClicked.connect(self._show_details)

    def _setup_detail_pane(self) -> None:
        """A collapsible pane under the table showing the full text of the selected record."""
        self._detail = QWidget(self)
        detail_layout = QVBoxLayout(self._detail)
        detail_layout.setContentsMargins(4, 2, 4, 2)
        header_layout = QHBoxLayout()
        self._detail_header = QLabel(self._detail)
        header_layout.addWidget(self._detail_header)
        header_layout.addStretch()
        copy_button = QToolButton(self._detail)
        copy_button.setIcon(material_icon("content_copy", size=(16, 16), convert_to_pixmap=False))
        copy_button.setToolTip("Copy the full message")
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self._detail_text.toPlainText())
        )
        header_layout.addWidget(copy_button)
        close_button = QToolButton(self._detail)
        close_button.setIcon(material_icon("close", size=(16, 16), convert_to_pixmap=False))
        close_button.setToolTip("Close details (Esc)")
        close_button.clicked.connect(self._hide_details)
        header_layout.addWidget(close_button)
        detail_layout.addLayout(header_layout)
        self._detail_text = QPlainTextEdit(self._detail)
        self._detail_text.setReadOnly(True)
        self._detail_text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        detail_layout.addWidget(self._detail_text)
        self._detail.hide()
        self._detail_record: _LogRec | None = None
        # set when the shown record was trimmed out of the buffer: the pane keeps its
        # content instead of silently swapping to a neighboring row
        self._detail_frozen = False

        self._splitter = QSplitter(Qt.Orientation.Vertical, self)
        self._splitter.addWidget(self._table)
        self._splitter.addWidget(self._detail)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)
        self._layout.addWidget(self._splitter)
        self._table.selectionModel().currentRowChanged.connect(self._on_current_row_changed)
        self._table.clicked.connect(self._on_row_clicked)

    def _setup_toolbar(self, client: BECClient):
        self._toolbar = LogPanelToolbar(self, client)
        self._layout.addWidget(self._toolbar)

    def _connect_toolbar(self):
        self._toolbar.services_selected.connect(self._on_services_selected)
        self._toolbar.text_filter_changed.connect(self._proxy.update_filter_text)
        self._toolbar.level_changed.connect(self._on_level_changed)
        self._toolbar.fuzzy_changed.connect(self._proxy.update_fuzzy)
        self._toolbar.timestamp_update.connect(self._proxy.update_timestamp)
        self._toolbar.pause_button.clicked.connect(self._model.log_queue.toggle_pause)
        self._toolbar.clear_button.clicked.connect(self._clear_view)
        self._model.log_queue.paused.connect(self._toolbar.set_paused)
        self._model.log_queue.buffered.connect(self._toolbar.set_buffered)
        # model signals too: source inserts that are entirely filtered out emit nothing
        # on the proxy, and the "/ total" side must not go stale
        for signal_model in (self._proxy, self._model):
            signal_model.rowsInserted.connect(self._refresh_match_label)
            signal_model.rowsRemoved.connect(self._refresh_match_label)
            signal_model.modelReset.connect(self._refresh_match_label)
        self._proxy.layoutChanged.connect(self._refresh_match_label)
        self._refresh_match_label()

    def _setup_shortcuts(self, has_toolbar: bool):
        copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self._table)
        copy_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        copy_shortcut.activated.connect(self._copy_selection)
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            details_shortcut = QShortcut(QKeySequence(key), self._table)
            details_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
            details_shortcut.activated.connect(self._show_details)
        escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        escape_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape_shortcut.activated.connect(self._hide_details)
        if has_toolbar:
            find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
            find_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            find_shortcut.activated.connect(self._focus_search)

    @SafeSlot()
    def _focus_search(self):
        self._toolbar.search_textbox.setFocus()
        self._toolbar.search_textbox.selectAll()

    @SafeSlot(object)
    def _on_services_selected(self, services: set[str] | None):
        self._proxy.update_service_filter(services)

    @SafeSlot(object)
    def _on_level_changed(self, level: LogLevel | None):
        self._proxy.update_level_filter(level)

    @SafeSlot()
    def _refresh_match_label(self, *_):
        self._toolbar.set_match_counts(self._proxy.rowCount(), self._model.rowCount())

    @SafeSlot()
    def _clear_view(self):
        self._model.clear()
        self._hide_details()

    def _current_record(self) -> _LogRec | None:
        index = self._table.currentIndex()
        if not index.isValid():
            return None
        return self._model.record(self._proxy.mapToSource(index).row())

    @SafeSlot()
    @SafeSlot(QModelIndex)
    def _show_details(self, *_):
        rec = self._current_record()
        if rec is None:
            return
        self._populate_detail(rec)
        if self._detail.isHidden():
            self._detail.show()
            total = self._splitter.height()
            self._splitter.setSizes([(total * 3) // 4, total // 4])

    @SafeSlot()
    def _hide_details(self):
        self._detail.hide()
        self._detail_record = None
        self._detail_frozen = False

    @SafeSlot(QModelIndex)
    def _on_row_clicked(self, *_):
        """A click is definitively user-driven: follow the selection, even out of a freeze."""
        if self._detail.isHidden():
            return
        rec = self._current_record()
        if rec is not None:
            self._populate_detail(rec)

    @SafeSlot(QModelIndex, QModelIndex)
    def _on_current_row_changed(self, *_):
        if self._detail.isHidden():
            return
        # defer: when the current row moves because of a buffer trim, this signal fires
        # while the trimmed rows are still present - only after the update settles can we
        # tell a user-driven move from the selection model relocating a removed row
        QTimer.singleShot(0, self._sync_detail_to_selection)

    @SafeSlot()
    def _sync_detail_to_selection(self):
        if self._detail.isHidden() or self._detail_frozen:
            return
        rec = self._current_record()
        if rec is None or rec is self._detail_record:
            return
        shown = self._detail_record
        if shown is not None and not any(r is shown for r in self._model._rows):
            # the shown record was trimmed out of the buffer: keep the content visible
            # instead of silently swapping to a neighboring row
            self._detail_frozen = True
            self._detail_header.setText(self._detail_header.text() + "  (no longer in buffer)")
            return
        self._populate_detail(rec)

    def _populate_detail(self, rec: _LogRec):
        self._detail_record = rec
        self._detail_frozen = False
        parts = [rec.level, rec.service_name, rec.timestamp_full or rec.timestamp, rec.function]
        self._detail_header.setText("  |  ".join(p for p in parts if p))
        self._detail_text.setPlainText(rec.message)

    @SafeSlot()
    def _copy_selection(self):
        rows = sorted(self._table.selectionModel().selectedRows(), key=lambda i: i.row())
        records = [self._model.record(self._proxy.mapToSource(index).row()) for index in rows]
        if not records:
            return
        QApplication.clipboard().setText(
            "\n".join(
                f"{r.timestamp} [{r.level}] {r.service_name or ''} {r.message}" for r in records
            )
        )

    def _show_table_context_menu(self, pos):
        index = self._table.indexAt(pos)
        menu = QMenu(self._table)
        if index.isValid():
            self._table.setCurrentIndex(index)
            rec = self._current_record()
            menu.addAction("Copy message", lambda: QApplication.clipboard().setText(rec.message))
            menu.addAction("Copy selected rows", self._copy_selection)
            menu.addAction("Show details", self._show_details)
            if rec.service_name:
                menu.addSeparator()
                menu.addAction(
                    f"Only logs from {rec.service_name}",
                    partial(self._filter_service_only, rec.service_name),
                )
                menu.addAction(
                    f"Hide {rec.service_name}", partial(self._filter_service_hide, rec.service_name)
                )
        menu.addSeparator()
        menu.addAction("Jump to bottom", self._table.scrollToBottom)
        menu.addAction("Clear view", self._clear_view)
        menu.exec(self._table.viewport().mapToGlobal(pos))
        menu.deleteLater()

    def _buffered_services(self) -> set[str]:
        return {r.service_name for r in self._model._rows if r.service_name}

    def _filter_service_only(self, service: str):
        if hasattr(self, "_toolbar"):
            self._toolbar.add_known_services(self._buffered_services())
            self._toolbar.set_service_selection({service})
        else:
            self._proxy.update_service_filter({service})

    def _filter_service_hide(self, service: str):
        if hasattr(self, "_toolbar"):
            # seed the toolbar with the services actually present in the buffer so hiding
            # one service cannot collaterally hide services unknown to service_status
            self._toolbar.add_known_services(self._buffered_services())
            self._toolbar.hide_service(service)
        else:
            known = self._buffered_services()
            current = self._proxy._service_filter
            base = known if current is None else set(current)
            self._proxy.update_service_filter(base - {service})

    def _update_service_filter(self, filter: set[str] | None):
        self._service_filter = filter
        self._proxy.update_service_filter(filter)
        self._table.setColumnHidden(
            _CONST.headers.index("service_name"), filter is not None and len(filter) == 1
        )

    @SafeSlot(bool)
    def _show_service_column(self, show: bool):
        self._table.setColumnHidden(_CONST.headers.index("service_name"), not show)

    def _apply_table_widths(self):
        bold_font = QFont(self._table.font())
        bold_font.setBold(True)
        bold_metrics = QFontMetrics(bold_font)
        metrics = self._table.fontMetrics()
        self._table.setColumnWidth(0, bold_metrics.horizontalAdvance("CRITICAL") + 14)
        self._table.setColumnWidth(1, metrics.horizontalAdvance("00:00:00.000") + 12)
        self._table.setColumnWidth(2, metrics.horizontalAdvance("DeviceServerXX") + 12)

    @SafeProperty(int, default=0)
    def font_size(self) -> int:
        """Point size of the log table and detail pane text. 0 uses the system default,
        so profiles that never touched the property restore unchanged."""
        return self._font_size

    @font_size.setter
    def font_size(self, size: int):
        self._font_size = max(0, int(size))
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        if self._font_size > 0:
            font.setPointSize(self._font_size)
        self._table.apply_font(font)
        self._apply_table_widths()
        self._detail_text.setFont(font)

    def sizeHint(self) -> QSize:
        return QSize(600, 300)

    def cleanup(self):
        """Detach from the shared log queue so a closed panel stops receiving updates."""
        self._model.log_queue.new_records.disconnect(self._model._on_new_records)
        if hasattr(self, "_toolbar"):
            self._model.log_queue.paused.disconnect(self._toolbar.set_paused)
            self._model.log_queue.buffered.disconnect(self._toolbar.set_buffered)
        super().cleanup()


class _StayOpenMenu(QMenu):
    """A menu whose checkable actions toggle without closing it, for multi-select filters.
    Plain checkable QActions only - layouted QWidgetAction containers paint shifted or
    clipped inside menus on macOS Qt 6.9+."""

    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.pos())
        if action is not None and action.isCheckable():
            action.trigger()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        action = self.activeAction()
        if (
            event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and action is not None
            and action.isCheckable()
        ):
            action.trigger()
            return
        super().keyPressEvent(event)


class LogPanelToolbar(QWidget):
    services_selected = Signal(object)  # set[str] | None (None = all services)
    level_changed = Signal(object)  # LogLevel | None (None = all levels)
    fuzzy_changed = Signal(bool)
    timestamp_update = Signal(TimestampUpdate)
    text_filter_changed = Signal(str)

    _TIME_PRESETS = [
        ("Last 1 min", 60),
        ("Last 5 min", 300),
        ("Last 15 min", 900),
        ("Last 1 h", 3600),
    ]

    def __init__(self, parent: QWidget | None = None, client: BECClient | None = None) -> None:
        """A toolbar for the logpanel, managing the states of all log filters."""
        super().__init__(parent)
        self.client = client
        self._known_services: set[str] = set()
        # None means "all services" - the include-list has not been narrowed
        self._checked_services: set[str] | None = None
        self._active_start: QDateTime | None = None
        self._active_end: QDateTime | None = None

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        if client is not None:
            self.service_button = QToolButton(self)
            self.service_button.setText("All services")
            self.service_button.setIcon(
                material_icon("dns", size=(20, 20), convert_to_pixmap=False)
            )
            self.service_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            self.service_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            self.service_button.setToolTip("Choose which services' logs to show")
            self._service_menu = _StayOpenMenu(self.service_button)
            self._service_menu.aboutToShow.connect(self._rebuild_service_menu)
            self.service_button.setMenu(self._service_menu)
            self._layout.addWidget(self.service_button)

        self.filter_level_dropdown = self._log_level_box()
        self._layout.addWidget(self.filter_level_dropdown)
        self.filter_level_dropdown.currentIndexChanged.connect(self._emit_level)

        self.timerange_button = QToolButton(self)
        self.timerange_button.setText("All time")
        self.timerange_button.setIcon(
            material_icon("schedule", size=(20, 20), convert_to_pixmap=False)
        )
        self.timerange_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.timerange_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.timerange_button.setToolTip("Show only logs from a time range")
        self._time_menu = QMenu(self.timerange_button)
        for label, seconds in self._TIME_PRESETS:
            self._time_menu.addAction(label, partial(self._apply_time_preset, label, seconds))
        self._time_menu.addAction("All time", partial(self._apply_time_preset, "All time", None))
        self._time_menu.addSeparator()
        self._time_menu.addAction("Custom range...", self._open_custom_range_dialog)
        self.timerange_button.setMenu(self._time_menu)
        self._layout.addWidget(self.timerange_button)

        self.search_textbox = QLineEdit(self)
        self.search_textbox.setPlaceholderText("Filter messages...")
        self.search_textbox.setClearButtonEnabled(True)
        self.search_textbox.addAction(
            material_icon("search", size=(16, 16), convert_to_pixmap=False),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search_textbox.setMinimumWidth(120)
        self._search_debounce = QTimer(self, singleShot=True, interval=_CONST.SEARCH_DEBOUNCE_MS)
        self._search_debounce.timeout.connect(self._emit_search_text)
        self.search_textbox.textChanged.connect(self._on_search_edited)
        self._layout.addWidget(self.search_textbox, 1)

        self.fuzzy_button = QToolButton(self)
        self.fuzzy_button.setText("Fuzzy")
        self.fuzzy_button.setCheckable(True)
        self.fuzzy_button.setToolTip("Approximate (fuzzy) message matching")
        self.fuzzy_button.toggled.connect(self.fuzzy_changed)
        self._layout.addWidget(self.fuzzy_button)

        self.match_label = QLabel(self)
        self._layout.addWidget(self.match_label)

        self.pause_button = QToolButton(self)
        self.pause_button.setCheckable(True)
        self.pause_button.setIcon(material_icon("pause", size=(20, 20), convert_to_pixmap=False))
        self.pause_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._PLAYING_TOOLTIP = "Pause live log updates."
        self._PAUSED_TOOLTIP = "Continue live log updates."
        self.pause_button.setToolTip(self._PLAYING_TOOLTIP)
        self._layout.addWidget(self.pause_button)

        self.clear_button = QToolButton(self)
        self.clear_button.setIcon(
            material_icon("delete_sweep", size=(20, 20), convert_to_pixmap=False)
        )
        self.clear_button.setToolTip("Clear the view (log history is kept)")
        self._layout.addWidget(self.clear_button)

    # ---------------------------------------------------------------- level filter

    def _log_level_box(self) -> QComboBox:
        box = QComboBox(self)
        box.setToolTip("Show logs at or above the selected level.")
        box.addItem("All levels", None)
        for level in [
            LogLevel.TRACE,
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.SUCCESS,
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]:
            box.addItem(level.name, level)
        return box

    @SafeSlot(int)
    def _emit_level(self, index: int):
        self.level_changed.emit(self.filter_level_dropdown.itemData(index))

    def set_level(self, level: LogLevel | None):
        """Set the level dropdown to the given threshold (None = all levels). Levels not
        listed in the dropdown (CONSOLE_LOG*) leave the dropdown untouched so a
        preapplied proxy filter is not wiped."""
        index = self.filter_level_dropdown.findData(level)
        if index != -1:
            self.filter_level_dropdown.setCurrentIndex(index)

    # ---------------------------------------------------------------- service filter

    def service_list_update(self, services_info: dict[str, StatusMessage]):
        """Extend the list of known services (dead services stay filterable)."""
        self._known_services |= {s.split("/")[0] for s in services_info.keys()}

    def _rebuild_service_menu(self):
        self._service_menu.clear()
        if self.client is not None:
            self.service_list_update(self.client.service_status)
        self._service_menu.addAction("All services", self._select_all_services)
        self._service_menu.addSeparator()
        checked = self._known_services if self._checked_services is None else self._checked_services
        for service in sorted(self._known_services):
            action = QAction(service, self._service_menu)
            action.setCheckable(True)
            action.setChecked(service in checked)
            action.toggled.connect(partial(self._on_service_toggled, service))
            self._service_menu.addAction(action)

    def add_known_services(self, services: set[str]):
        """Extend the known-service list with names observed outside service_status
        (e.g. services present in buffered log records)."""
        self._known_services |= services

    def _on_service_toggled(self, service: str, checked: bool):
        current = (
            set(self._known_services) if self._checked_services is None else self._checked_services
        )
        if checked:
            current.add(service)
        else:
            current.discard(service)
        # everything re-checked = no filter, robust to new services appearing later; only
        # meaningful here, where the open menu has just populated _known_services
        if self._known_services and current >= self._known_services:
            current = None
        self._set_checked_services(current)

    def _select_all_services(self):
        self._set_checked_services(None)

    def set_service_selection(self, services: set[str] | None):
        """Select exactly the given services (None = all). Used by the panel context menu."""
        if services:
            self._known_services |= services
        self._set_checked_services(None if services is None else set(services))

    def hide_service(self, service: str):
        """Remove one service from the current selection. Callers should first extend the
        known services via add_known_services with what is actually visible."""
        self._known_services.add(service)
        base = (
            set(self._known_services)
            if self._checked_services is None
            else set(self._checked_services)
        )
        base.discard(service)
        self._set_checked_services(base)

    def _set_checked_services(self, services: set[str] | None):
        self._checked_services = services
        if services is None:
            self.service_button.setText("All services")
        elif len(services) == 0:
            self.service_button.setText("No services")
        elif len(services) == 1:
            self.service_button.setText(next(iter(services)))
        else:
            self.service_button.setText(f"{len(services)} services")
        self.services_selected.emit(services)

    # ---------------------------------------------------------------- time filter

    def _apply_time_preset(self, label: str, seconds: int | None):
        if seconds is None:
            self._set_time_range(None, None)
            return
        self._set_time_range(QDateTime.currentDateTime().addSecs(-seconds), None)

    def _set_time_range(self, start: QDateTime | None, end: QDateTime | None):
        """Apply both bounds, remember them for the custom dialog, and label the button."""
        self._active_start = start
        self._active_end = end
        self.timestamp_update.emit(TimestampUpdate(value=start, update_type="start"))
        self.timestamp_update.emit(TimestampUpdate(value=end, update_type="end"))
        if start and end:
            text = f"{start.toString('HH:mm')} - {end.toString('HH:mm')}"
        elif start:
            text = f">= {start.toString('HH:mm:ss')}"
        elif end:
            text = f"<= {end.toString('HH:mm:ss')}"
        else:
            text = "All time"
        self.timerange_button.setText(text)

    def _build_custom_range_dialog(
        self,
    ) -> tuple[QDialog, dict[str, tuple[QCheckBox, QDateTimeEdit]]]:
        """Build the custom range dialog, prefilled with the currently active bounds."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Time range")
        layout = QGridLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)
        bounds: dict[str, tuple[QCheckBox, QDateTimeEdit]] = {}
        rows = [
            ("start", "From", self._active_start, QDateTime.currentDateTime().addSecs(-3600)),
            ("end", "Until", self._active_end, QDateTime.currentDateTime()),
        ]
        for row, (bound, label, active, default) in enumerate(rows):
            enable = QCheckBox(label, dialog)
            edit = QDateTimeEdit(active or default, dialog)
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            edit.setMinimumWidth(220)
            edit.setEnabled(active is not None)
            enable.setChecked(active is not None)
            enable.toggled.connect(edit.setEnabled)
            layout.addWidget(enable, row, 0)
            layout.addWidget(edit, row, 1)
            bounds[bound] = (enable, edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons, len(rows), 0, 1, 2)
        return dialog, bounds

    @SafeSlot()
    def _open_custom_range_dialog(self):
        """One dialog with both bounds - replaces the former nested calendar dialogs."""
        dialog, bounds = self._build_custom_range_dialog()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_custom_range(bounds)
        dialog.deleteLater()

    def _apply_custom_range(self, bounds: dict[str, tuple[QCheckBox, QDateTimeEdit]]):
        start_enable, start_edit = bounds["start"]
        end_enable, end_edit = bounds["end"]
        self._set_time_range(
            start_edit.dateTime() if start_enable.isChecked() else None,
            end_edit.dateTime() if end_enable.isChecked() else None,
        )

    # ---------------------------------------------------------------- search

    @SafeSlot(str)
    def _on_search_edited(self, text: str):
        if not text:
            self._search_debounce.stop()
            self.text_filter_changed.emit("")
            return
        self._search_debounce.start()

    @SafeSlot()
    def _emit_search_text(self):
        self.text_filter_changed.emit(self.search_textbox.text())

    # ---------------------------------------------------------------- status

    def set_match_counts(self, shown: int, total: int):
        self.match_label.setText(f"{shown} / {total}" if shown != total else str(total))

    @SafeSlot(bool)
    def set_paused(self, paused: bool):
        self.pause_button.setChecked(paused)
        if paused:
            icon = "play_arrow"
            tooltip = self._PAUSED_TOOLTIP
        else:
            icon = "pause"
            tooltip = self._PLAYING_TOOLTIP
            self.pause_button.setText("")
        self.pause_button.setIcon(material_icon(icon, size=(20, 20), convert_to_pixmap=False))
        self.pause_button.setToolTip(tooltip)

    @SafeSlot(int)
    def set_buffered(self, count: int):
        if self.pause_button.isChecked():
            self.pause_button.setText(str(count))


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
