"""QWidget version of the error dialog.

The QML twin lives in :mod:`bec_widgets.utils.error_dialog.error_dialog_qml`; both render
:meth:`ErrorDialogController.view_state` and share the controller, so they look and behave the same.
"""

from __future__ import annotations

from html import escape

from bec_qthemes import material_icon
from qtpy.QtCore import QSize, Qt, QTimer, Signal
from qtpy.QtGui import QFont, QFontDatabase, QKeySequence, QShortcut
from qtpy.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_dialog.error_dialog_common import (
    ErrorDialogController,
    ErrorDialogWindowMixin,
)
from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import IconButton, TextButton, ToggleSwitch, refresh_kit_theme, rgba


def _mono_font(pixel_size: int = 12) -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPixelSize(pixel_size)
    return font


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        elif item.layout() is not None:
            _clear_layout(item.layout())


class _ElidedLabel(QLabel):
    """Plain-text label that elides in the middle instead of growing the layout."""

    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(40)
        self.set_full_text(text)

    def set_full_text(self, text: str) -> None:
        """Set the text; the tooltip always shows it in full."""
        self._full = text
        self.setToolTip(text)
        self._elide()

    def resizeEvent(self, event):  # pylint: disable=invalid-name
        """Re-elide for the new width."""
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        self.setText(
            self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideMiddle, self.width())
        )


class _Clickable(QFrame):  # pylint: disable=too-few-public-methods
    """Frame that emits ``clicked`` and shows a hover background."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def mouseReleaseEvent(self, event):  # pylint: disable=invalid-name
        """Emit ``clicked`` on a left click released inside the frame."""
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def _code_block(context: list[dict], tokens: ThemeTokens, parent: QWidget) -> QLabel:
    """Source lines with line numbers; the current line is tinted with the error colour."""
    width = max((len(str(row["no"])) for row in context), default=1)
    lines = []
    for row in context:
        number = str(row["no"]).rjust(width).replace(" ", "&nbsp;")
        text = escape(row["text"]).replace(" ", "&nbsp;") or "&nbsp;"
        if row["current"]:
            tint = tokens.soft(tokens.danger, 0.2).name()
            lines.append(
                f"<tr><td width='1%' style='color:{tokens.danger.name()}; background:{tint};"
                f" padding:0 10px 0 4px'>{number}</td>"
                f"<td style='color:{tokens.fg.name()}; background:{tint}'>{text}</td></tr>"
            )
        else:
            lines.append(
                f"<tr><td width='1%' style='color:{tokens.fg_subtle.name()};"
                f" padding:0 10px 0 4px'>{number}</td>"
                f"<td style='color:{tokens.fg_muted.name()}'>{text}</td></tr>"
            )
    label = QLabel(
        f"<table cellspacing=0 cellpadding=1 width='100%'>{''.join(lines)}</table>", parent
    )
    label.setFont(_mono_font())
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setObjectName("codeBlock")
    label.setStyleSheet(
        f"QLabel#codeBlock {{ background: {tokens.field.name()}; border: 1px solid"
        f" {tokens.border.name()}; border-radius: 6px; padding: 6px 8px; }}"
    )
    return label


# pylint: disable=too-many-instance-attributes, too-many-locals, too-many-statements
class ErrorDialogWidget(ErrorDialogWindowMixin, QDialog):
    """Resizable error dialog with summary, navigable traceback and an error list (QWidget)."""

    def __init__(self, parent: QWidget | None = None, controller: ErrorDialogController = None):
        super().__init__(parent)
        self.controller = controller or ErrorDialogController(self)
        self._tokens = ThemeTokens()
        self._state: dict = {}
        self._rendered_error: str | None = None
        self._build()
        self.init_window()
        self.controller.changed.connect(self.sync)
        self.sync()

    # ------------------------------------------------------------------ construction

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # error list, only shown with more than one error
        self.sidebar = QFrame(self)
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(264)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(12, 14, 12, 12)
        side.setSpacing(8)
        side_head = QHBoxLayout()
        self.list_title = QLabel(self.sidebar)
        self.list_title.setObjectName("sectionTitle")
        side_head.addWidget(self.list_title, 1)
        self.clear_button = TextButton("Clear all", "ghost", "delete_sweep", self.sidebar)
        self.clear_button.setToolTip("Remove every error from the list")
        self.clear_button.clicked.connect(self.controller.clear)
        side_head.addWidget(self.clear_button)
        side.addLayout(side_head)
        self.list_scroll = QScrollArea(self.sidebar)
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.list_host = QWidget()
        self.list_host.setObjectName("transparent")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(4)
        self.list_scroll.setWidget(self.list_host)
        side.addWidget(self.list_scroll, 1)
        root.addWidget(self.sidebar)

        main = QVBoxLayout()
        main.setContentsMargins(20, 18, 20, 16)
        main.setSpacing(14)
        root.addLayout(main, 1)

        # summary
        header = QHBoxLayout()
        header.setSpacing(14)
        self.badge = QLabel(self)
        self.badge.setFixedSize(40, 40)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        summary = QVBoxLayout()
        summary.setSpacing(4)
        self.type_label = QLabel(self)
        self.type_label.setObjectName("typeLabel")
        self.type_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary.addWidget(self.type_label)
        self.message_label = QLabel(self)
        self.message_label.setObjectName("messageLabel")
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary.addWidget(self.message_label)
        self.message_more = QPlainTextEdit(self)
        self.message_more.setObjectName("messageMore")
        self.message_more.setReadOnly(True)
        self.message_more.setFont(_mono_font())
        self.message_more.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.message_more.setMaximumHeight(132)
        summary.addWidget(self.message_more)
        self.meta_label = QLabel(self)
        self.meta_label.setObjectName("metaLabel")
        self.meta_label.setTextFormat(Qt.TextFormat.RichText)
        summary.addWidget(self.meta_label)
        header.addLayout(summary, 1)
        pager = QHBoxLayout()
        pager.setSpacing(2)
        self.prev_button = IconButton("chevron_left", "Newer error (Alt+Up)", self)
        self.prev_button.clicked.connect(lambda: self.controller.step(-1))
        self.pager_label = QLabel(self)
        self.pager_label.setObjectName("metaLabel")
        self.next_button = IconButton("chevron_right", "Older error (Alt+Down)", self)
        self.next_button.clicked.connect(lambda: self.controller.step(1))
        for widget in (self.prev_button, self.pager_label, self.next_button):
            pager.addWidget(widget)
        self.pager = QWidget(self)
        self.pager.setLayout(pager)
        pager.setContentsMargins(0, 0, 0, 0)
        header.addWidget(self.pager, 0, Qt.AlignmentFlag.AlignTop)
        main.addLayout(header)

        # where it happened
        self.location_card = QFrame(self)
        self.location_card.setObjectName("card")
        loc = QVBoxLayout(self.location_card)
        loc.setContentsMargins(14, 10, 10, 12)
        loc.setSpacing(6)
        loc_head = QHBoxLayout()
        loc_head.setSpacing(8)
        caption = QLabel("WHERE IT HAPPENED", self.location_card)
        caption.setObjectName("caption")
        loc_head.addWidget(caption)
        self.location_func = QLabel(self.location_card)
        self.location_func.setFont(_mono_font(13))
        self.location_func.setObjectName("locationFunc")
        loc_head.addWidget(self.location_func)
        self.location_label = _ElidedLabel("", self.location_card)
        self.location_label.setObjectName("metaLabel")
        loc_head.addWidget(self.location_label, 1)
        self.copy_location_button = IconButton(
            "content_copy", "Copy file path and line", self.location_card, size=16
        )
        self.copy_location_button.clicked.connect(self._copy_location)
        loc_head.addWidget(self.copy_location_button)
        loc.addLayout(loc_head)
        self.location_code = QVBoxLayout()
        loc.addLayout(self.location_code)
        main.addWidget(self.location_card)

        # traceback
        tb_head = QHBoxLayout()
        tb_head.setSpacing(10)
        tb_title = QLabel("Traceback", self)
        tb_title.setObjectName("sectionTitle")
        tb_head.addWidget(tb_title)
        self.tb_hint = QLabel(self)
        self.tb_hint.setObjectName("metaLabel")
        tb_head.addWidget(self.tb_hint, 1)
        self.library_switch = ToggleSwitch(self)
        self.library_switch.toggled.connect(self.controller.set_show_library)
        library_label = QLabel("Library frames", self)
        library_label.setObjectName("metaLabel")
        tb_head.addWidget(library_label)
        tb_head.addWidget(self.library_switch)
        self.segment = QFrame(self)
        self.segment.setObjectName("segment")
        seg = QHBoxLayout(self.segment)
        seg.setContentsMargins(2, 2, 2, 2)
        seg.setSpacing(2)
        self.frames_tab = TextButton("Frames", "ghost", "", self.segment)
        self.raw_tab = TextButton("Raw text", "ghost", "", self.segment)
        for button, mode in ((self.frames_tab, "frames"), (self.raw_tab, "raw")):
            button.setMinimumHeight(26)
            button.clicked.connect(lambda _=False, m=mode: self.controller.set_mode(m))
            seg.addWidget(button)
        tb_head.addWidget(self.segment)
        main.addLayout(tb_head)

        self.stack = QStackedWidget(self)
        self.frames_scroll = QScrollArea(self)
        self.frames_scroll.setObjectName("framesScroll")
        self.frames_scroll.setWidgetResizable(True)
        self.frames_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frames_host = QWidget()
        self.frames_host.setObjectName("framesHost")
        self.frames_layout = QVBoxLayout(self.frames_host)
        self.frames_layout.setContentsMargins(6, 6, 6, 6)
        self.frames_layout.setSpacing(2)
        self.frames_scroll.setWidget(self.frames_host)
        self.stack.addWidget(self.frames_scroll)
        self.raw_text = QPlainTextEdit(self)
        self.raw_text.setReadOnly(True)
        self.raw_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.raw_text.setFont(_mono_font())
        self.stack.addWidget(self.raw_text)
        main.addWidget(self.stack, 1)

        # actions
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.copy_button = TextButton("Copy report", "neutral", "content_copy", self)
        self.copy_button.setToolTip("Copy error, location, versions and traceback (Ctrl+Shift+C)")
        self.copy_button.clicked.connect(self._copy_report)
        self.report_button = TextButton("Report issue", "neutral", "bug_report", self)
        self.report_button.setToolTip("Open a pre-filled issue in the browser")
        self.report_button.clicked.connect(self.controller.report_issue)
        footer.addWidget(self.copy_button)
        footer.addWidget(self.report_button)
        footer.addStretch(1)
        self.dismiss_button = TextButton("Dismiss", "ghost", "", self)
        self.dismiss_button.setToolTip("Remove this error from the list")
        self.dismiss_button.clicked.connect(self.controller.dismiss)
        self.close_button = TextButton("Close", "primary", "", self)
        self.close_button.clicked.connect(self.close)
        footer.addWidget(self.dismiss_button)
        footer.addWidget(self.close_button)
        main.addLayout(footer)

        QShortcut(QKeySequence("Alt+Up"), self, activated=lambda: self.controller.step(-1))
        QShortcut(QKeySequence("Alt+Down"), self, activated=lambda: self.controller.step(1))
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self._copy_report)

        self._copied_timer = QTimer(self)
        self._copied_timer.setSingleShot(True)
        self._copied_timer.setInterval(1500)
        self._copied_timer.timeout.connect(self._reset_copied)

    # ------------------------------------------------------------------ actions

    def _copy_report(self) -> None:
        if self.controller.copy_report():
            self.copy_button.setText("Copied")
            self._copied_timer.start()

    def _copy_location(self) -> None:
        if self.controller.copy_location():
            self.copy_location_button.set_icon_name("check")
            self._copied_timer.start()

    def _reset_copied(self) -> None:
        self.copy_button.setText("Copy report")
        self.copy_location_button.set_icon_name("content_copy")

    # ------------------------------------------------------------------ theme

    def apply_theme(self) -> None:
        """Re-read the theme tokens and restyle everything."""
        self._tokens = tokens = refresh_kit_theme(self)
        self.setStyleSheet(f"""
            ErrorDialogWidget {{ background: {tokens.bg.name()}; }}
            QFrame#sidebar {{ background: {tokens.card.name()};
                border-right: 1px solid {tokens.border.name()}; }}
            QWidget#transparent, QScrollArea {{ background: transparent; }}
            QLabel {{ color: {tokens.fg.name()}; background: transparent; }}
            QLabel#typeLabel {{ font-size: 19px; font-weight: 700; }}
            QLabel#messageLabel {{ font-size: 14px; }}
            QLabel#metaLabel {{ color: {tokens.fg_muted.name()}; font-size: 12px; }}
            QLabel#sectionTitle {{ font-size: 13px; font-weight: 600; }}
            QLabel#locationFunc {{ font-weight: 600; }}
            QPlainTextEdit#messageMore {{ background: {tokens.field.name()};
                color: {tokens.fg_muted.name()}; border: 1px solid {tokens.border.name()};
                border-radius: 6px; padding: 2px 4px; }}
            QLabel#caption {{ color: {tokens.fg_subtle.name()}; font-size: 11px;
                font-weight: 600; letter-spacing: 1px; }}
            QFrame#card {{ background: {tokens.card.name()};
                border: 1px solid {tokens.border.name()}; border-radius: 10px; }}
            QFrame#segment {{ background: {tokens.field.name()};
                border: 1px solid {tokens.border.name()}; border-radius: 7px; }}
            QScrollArea#framesScroll {{ background: {tokens.card.name()};
                border: 1px solid {tokens.border.name()}; border-radius: 10px; }}
            QWidget#framesHost {{ background: {tokens.card.name()}; }}
            QPlainTextEdit {{ background: {tokens.card.name()}; color: {tokens.fg.name()};
                border: 1px solid {tokens.border.name()}; border-radius: 10px; padding: 6px;
                selection-background-color: {tokens.primary.name()}; }}
            """)
        self.badge.setPixmap(
            material_icon("error", size=(24, 24), color=tokens.danger, filled=True)
        )
        self.badge.setStyleSheet(
            f"background: {tokens.soft(tokens.danger, 0.18).name()}; border-radius: 20px;"
        )
        self.sync()

    # ------------------------------------------------------------------ rendering

    def sync(self) -> None:
        """Render the controller state."""
        state = self.controller.view_state()
        tokens = self._tokens
        current = state["current"]
        many = state["count"] > 1
        self.sidebar.setVisible(many)
        self.pager.setVisible(many)
        self.dismiss_button.setVisible(many)
        self.clear_button.setVisible(many)
        self.list_title.setText(f"Errors ({state['count']})")
        self.pager_label.setText(f"{state['index'] + 1} of {state['count']}")
        self.prev_button.setEnabled(state["index"] > 0)
        self.next_button.setEnabled(0 <= state["index"] < state["count"] - 1)
        if many:
            self._render_list(state)
        self._state = state
        if current is None:
            self.type_label.setText("No errors")
            self.message_label.setText("")
            self.meta_label.setText("")
            self.location_card.hide()
            _clear_layout(self.frames_layout)
            self.raw_text.clear()
            return

        self.setWindowTitle(f"{current['type']} · {current['title']}")
        self.type_label.setText(current["type"])
        self.type_label.setToolTip(current["qualified_type"])
        self.message_label.setText(current["headline"] or "(no message)")
        self.message_more.setVisible(bool(current["message_more"]))
        if self.message_more.toPlainText() != current["message_more"]:
            self.message_more.setPlainText(current["message_more"])
            lines = current["message_more"].count("\n") + 1
            self.message_more.setFixedHeight(min(132, 14 + lines * 17))
        meta = [
            f"<span style='color:{tokens.danger.name()}; font-weight:600'>"
            f"{escape(current['title'])}</span>"
        ]
        if current["source"]:
            meta.append(f"in <b style='color:{tokens.fg.name()}'>{escape(current['source'])}</b>")
        meta.append(f"<span title='{current['time']}'>{current['time'][11:]}</span>")
        if current["count"] > 1:
            meta.append(
                f"<span style='color:{tokens.warning.name()}; font-weight:600'>"
                f"{current['count']}× since {current['first_time'][11:]}</span>"
            )
        self.meta_label.setText("&nbsp;&nbsp;·&nbsp;&nbsp;".join(meta))

        location = current["location"]
        self.location_card.setVisible(location is not None)
        _clear_layout(self.location_code)
        if location is not None:
            self.location_func.setText(location["func"])
            self.location_label.set_full_text(f"{location['file_short']}:{location['line']}")
            if location["context"]:
                self.location_code.addWidget(
                    _code_block(location["context"], tokens, self.location_card)
                )

        hidden = current["library_frame_count"] if not state["show_library"] else 0
        hint = f"{current['frame_count']} frames, newest first"
        if hidden:
            hint += f" · {hidden} folded"
        self.tb_hint.setText(hint)
        self.library_switch.blockSignals(True)
        self.library_switch.setChecked(state["show_library"])
        self.library_switch.blockSignals(False)
        raw = state["mode"] == "raw"
        self.frames_tab.set_variant("ghost" if raw else "primary")
        self.raw_tab.set_variant("primary" if raw else "ghost")
        self.stack.setCurrentIndex(1 if raw else 0)
        if self.raw_text.toPlainText() != current["raw"]:
            self.raw_text.setPlainText(current["raw"])
        self._render_rows(current["rows"])

    def _render_list(self, state: dict) -> None:
        tokens = self._tokens
        _clear_layout(self.list_layout)
        for row in state["errors"]:
            selected = state["current"] is not None and row["id"] == state["current"]["id"]
            item = _Clickable(self.list_host)
            item.setObjectName("listRow")
            bg = tokens.soft(tokens.primary, 0.16).name() if selected else "transparent"
            item.setStyleSheet(
                f"QFrame#listRow {{ background: {bg}; border-radius: 8px; }}"
                f"QFrame#listRow:hover {{ background: "
                f"{tokens.soft(tokens.primary, 0.16).name() if selected else tokens.hover.name()};"
                f" }}"
            )
            lay = QVBoxLayout(item)
            lay.setContentsMargins(10, 8, 10, 8)
            lay.setSpacing(2)
            top = QHBoxLayout()
            top.setSpacing(6)
            dot = QLabel("●" if not row["seen"] else "", item)
            dot.setStyleSheet(f"color: {tokens.primary.name()}; font-size: 9px;")
            dot.setVisible(not row["seen"])
            top.addWidget(dot)
            title = QLabel(row["type"], item)
            title.setStyleSheet("font-weight: 600; font-size: 13px;")
            top.addWidget(title, 1)
            if row["count"] > 1:
                count = QLabel(f"{row['count']}×", item)
                count.setStyleSheet(
                    f"color: {tokens.warning.name()}; font-weight: 600; font-size: 12px;"
                )
                top.addWidget(count)
            when = QLabel(row["time"], item)
            when.setStyleSheet(f"color: {tokens.fg_subtle.name()}; font-size: 12px;")
            top.addWidget(when)
            lay.addLayout(top)
            message = QLabel(item)
            message.setStyleSheet(f"color: {tokens.fg_muted.name()}; font-size: 12px;")
            message.setText(
                message.fontMetrics().elidedText(row["message"], Qt.TextElideMode.ElideRight, 220)
            )
            message.setToolTip(row["message"])
            lay.addWidget(message)
            item.clicked.connect(lambda error_id=row["id"]: self.controller.select(error_id))
            self.list_layout.addWidget(item)
        self.list_layout.addStretch(1)

    def _render_rows(self, rows: list[dict]) -> None:
        tokens = self._tokens
        scroll = self.frames_scroll.verticalScrollBar().value()
        same_error = self._rendered_error == self._state["current"]["id"]
        self.frames_host.setUpdatesEnabled(False)
        _clear_layout(self.frames_layout)
        for row in rows:
            if row["kind"] == "section":
                self.frames_layout.addWidget(self._section_row(row, tokens))
            elif row["kind"] == "group":
                self.frames_layout.addWidget(self._group_row(row, tokens))
            else:
                self.frames_layout.addWidget(self._frame_row(row, tokens))
        self.frames_layout.addStretch(1)
        self.frames_host.setUpdatesEnabled(True)
        self._rendered_error = self._state["current"]["id"]
        if same_error:
            QTimer.singleShot(0, lambda: self.frames_scroll.verticalScrollBar().setValue(scroll))

    def _section_row(self, row: dict, tokens: ThemeTokens) -> QWidget:
        widget = QFrame(self.frames_host)
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(8, 6 if row["first"] else 14, 8, 4)
        lay.setSpacing(2)
        label = QLabel(row["label"].upper(), widget)
        color = tokens.danger if row["first"] else tokens.fg_subtle
        label.setStyleSheet(
            f"color: {color.name()}; font-size: 11px; font-weight: 600; letter-spacing: 1px;"
        )
        lay.addWidget(label)
        text = QLabel(widget)
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        message = escape(row["message"].splitlines()[0] if row["message"] else "")
        text.setText(
            f"<b>{escape(row['type'])}</b><span style='color:{tokens.fg_muted.name()}'>"
            f"{': ' + message if message else ''}</span>"
        )
        text.setStyleSheet("font-size: 13px;")
        lay.addWidget(text)
        return widget

    def _group_row(self, row: dict, tokens: ThemeTokens) -> QWidget:
        widget = _Clickable(self.frames_host)
        widget.setObjectName("groupRow")
        widget.setStyleSheet(
            f"QFrame#groupRow {{ border: 1px dashed {tokens.border.name()}; border-radius: 6px; }}"
            f"QFrame#groupRow:hover {{ background: {tokens.hover.name()}; }}"
        )
        lay = QHBoxLayout(widget)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)
        icon = QLabel(widget)
        icon.setPixmap(
            material_icon(
                "expand_less" if row["open"] else "unfold_more",
                size=(16, 16),
                color=tokens.fg_subtle,
            )
        )
        lay.addWidget(icon)
        label = QLabel(row["label"], widget)
        label.setStyleSheet(f"color: {tokens.fg_subtle.name()}; font-size: 12px;")
        lay.addWidget(label, 1)
        widget.setToolTip("Hide these frames" if row["open"] else "Show these frames")
        widget.clicked.connect(lambda key=row["key"]: self.controller.toggle_group(key))
        return widget

    def _frame_row(self, row: dict, tokens: ThemeTokens) -> QWidget:
        widget = QFrame(self.frames_host)
        widget.setObjectName("frameRow")
        accent = tokens.danger.name() if row["focus"] else "transparent"
        widget.setStyleSheet(
            f"QFrame#frameRow {{ border-left: 3px solid {accent}; border-radius: 0px;"
            f" background: {rgba(tokens.danger, 0.06) if row['focus'] else 'transparent'}; }}"
        )
        outer = QVBoxLayout(widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        head = _Clickable(widget)
        head.setObjectName("frameHead")
        head.setStyleSheet(
            f"QFrame#frameHead {{ border-radius: 6px; }}"
            f"QFrame#frameHead:hover {{ background: {tokens.hover.name()}; }}"
        )
        lay = QHBoxLayout(head)
        lay.setContentsMargins(6, 5, 8, 5)
        lay.setSpacing(6)
        chevron = QLabel(head)
        chevron.setPixmap(
            material_icon(
                "expand_more" if row["expanded"] else "chevron_right",
                size=(16, 16),
                color=tokens.fg_subtle,
            )
        )
        lay.addWidget(chevron, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(1)
        top = QHBoxLayout()
        top.setSpacing(8)
        func = QLabel(row["func"], head)
        func.setFont(_mono_font(13))
        fg = tokens.fg if row["bec"] else tokens.fg_muted
        func.setStyleSheet(f"color: {fg.name()}; font-weight: 600;")
        top.addWidget(func)
        if row["focus"]:
            pill = QLabel("raised here", head)
            pill.setStyleSheet(
                f"color: {tokens.danger.name()}; background: {rgba(tokens.danger, 0.14)};"
                f" border-radius: 8px; padding: 1px 7px; font-size: 11px; font-weight: 600;"
            )
            top.addWidget(pill)
        where = _ElidedLabel(f"{row['file_short']}:{row['line']}", head)
        where.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        where.setStyleSheet(f"color: {tokens.fg_subtle.name()}; font-size: 12px;")
        top.addWidget(where, 1)
        text.addLayout(top)
        if row["code"] and not row["expanded"]:
            code = QLabel(row["code"], head)
            code.setFont(_mono_font())
            code.setStyleSheet(f"color: {tokens.fg_muted.name()};")
            code.setTextFormat(Qt.TextFormat.PlainText)
            code.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            text.addWidget(code)
        lay.addLayout(text, 1)
        head.setToolTip("Hide source" if row["expanded"] else "Show source")
        head.clicked.connect(lambda key=row["key"]: self.controller.toggle_frame(key))
        outer.addWidget(head)
        if row["expanded"] and row["context"]:
            holder = QHBoxLayout()
            holder.setContentsMargins(28, 0, 8, 6)
            holder.addWidget(_code_block(row["context"], tokens, widget))
            outer.addLayout(holder)
        return widget

    def cleanup(self) -> None:
        """Stop the "Copied" feedback timer."""
        self._copied_timer.stop()

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Default size of the dialog."""
        return QSize(960, 680)
