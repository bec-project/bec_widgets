"""Admin view drawn with plain QWidgets.

Same UX as :mod:`admin_view_qml`; the state comes from
:class:`~.admin_ux_common.AdminViewBase`.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import Card, StatusPill, TextButton, field_qss, refresh_kit_theme
from bec_widgets.widgets.services.bec_atlas_admin_view.admin_ux.admin_ux_common import (
    DEFAULT_ATLAS_URL,
    HOW_IT_WORKS,
    AdminViewBase,
)


def _label(text: str = "", role: str = "", parent: QWidget | None = None, wrap=False) -> QLabel:
    label = QLabel(text, parent)
    if role:
        label.setProperty("role", role)
    label.setWordWrap(wrap)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return label


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget() is not None:
            item.widget().deleteLater()
        elif item.layout() is not None:
            _clear(item.layout())


def tone_color(tokens: ThemeTokens, tone: str):
    """Colour of a tone used by banners, chips and step markers."""
    return {
        "ok": tokens.success,
        "warning": tokens.warning,
        "danger": tokens.danger,
        "info": tokens.accent,
    }.get(tone, tokens.fg_muted)


class IconLabel(QLabel):
    """Material icon as a label."""

    def __init__(self, name: str, size: int = 18, parent: QWidget | None = None):
        super().__init__(parent)
        self._name = name
        self._size = size
        self.setFixedSize(size, size)

    def set_icon(self, name: str, color) -> None:
        """Draw ``name`` in ``color``."""
        self._name = name
        self.setPixmap(material_icon(name, size=(self._size, self._size), color=color))


class Banner(QFrame):
    """Tinted message box with an icon, a bold title and a text."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("banner")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        self.icon = IconLabel("info", 20, self)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(2)
        self.title = _label("", "strong", self, wrap=True)
        self.text = _label("", "muted", self, wrap=True)
        text.addWidget(self.title)
        text.addWidget(self.text)
        layout.addLayout(text, 1)
        self._tone = "info"
        self._key = None

    def set_message(self, tone: str, title: str, text: str, tokens: ThemeTokens) -> None:
        """Show a message in the colours of ``tone``."""
        key = (tone, title, text, tokens.name, tokens.card.name())
        if key == self._key:
            return
        self._key = key
        self._tone = tone
        color = tone_color(tokens, tone)
        icon = {"ok": "check_circle", "warning": "warning", "danger": "error"}.get(tone, "info")
        self.icon.set_icon(icon, color)
        self.title.setText(title)
        self.text.setText(text)
        self.text.setVisible(bool(text))
        self.setStyleSheet(
            f"QFrame#banner {{ background: {tokens.soft(color, 0.14).name()};"
            f" border: 1px solid {tokens.soft(color, 0.45).name()}; border-radius: 8px; }}"
        )


class ExperimentRow(QFrame):
    """One clickable experiment in the switch list."""

    clicked = Signal(str)

    def __init__(self, row: dict, selected: bool, tokens: ThemeTokens, parent=None):
        super().__init__(parent)
        self.pgroup = row["pgroup"]
        self.setObjectName("expRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", selected)
        layout = QGridLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(2)
        pgroup = _label(row["pgroup"], "rowKey", self)
        pgroup.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        title = _label(row["title"], "", self)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        meta = _label(f"{row['pi']}  ·  {row['beamtime']}", "muted", self)
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(pgroup, 0, 0)
        layout.addWidget(title, 0, 1)
        layout.addWidget(meta, 1, 1)
        if row["status"] in ("active", "now", "next", "past"):
            pill = StatusPill(self)
            tone = {"active": tokens.success, "now": tokens.warning, "next": tokens.primary}.get(
                row["status"], tokens.fg_subtle
            )
            pill.set_status(row["statusLabel"], tone)
            layout.addWidget(pill, 0, 2, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.setColumnStretch(1, 1)

    def mousePressEvent(self, event):  # pylint: disable=invalid-name
        """Select this experiment."""
        self.clicked.emit(self.pgroup)
        super().mousePressEvent(event)


class Stepper(QWidget):
    """Three numbered steps with labels; done steps show a tick."""

    def __init__(self, labels: list[str], parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._dots: list[QLabel] = []
        self._labels: list[QLabel] = []
        self._lines: list[QFrame] = []
        for i, text in enumerate(labels):
            if i:
                line = QFrame(self)
                line.setFixedHeight(2)
                line.setMinimumWidth(24)
                self._lines.append(line)
                layout.addWidget(line, 1)
            dot = QLabel(str(i + 1), self)
            dot.setFixedSize(24, 24)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label = QLabel(text, self)
            self._dots.append(dot)
            self._labels.append(label)
            layout.addWidget(dot)
            layout.addWidget(label)

    def set_step(self, step: int, done: bool, tokens: ThemeTokens) -> None:
        """Highlight ``step``; earlier steps (and ``step`` itself if ``done``) show a tick."""
        for i, (dot, label) in enumerate(zip(self._dots, self._labels)):
            finished = i < step or (done and i == step)
            current = i == step and not done
            if finished:
                fill, fg, text = tokens.success, "white", "✓"
            elif current:
                fill, fg, text = tokens.primary, "white", str(i + 1)
            else:
                fill, fg, text = tokens.track, tokens.fg_muted.name(), str(i + 1)
            dot.setText(text)
            dot.setStyleSheet(
                f"background: {fill.name()}; color: {fg}; border-radius: 12px;"
                f" font-size: 12px; font-weight: 700;"
            )
            weight = 600 if current or finished else 400
            color = tokens.fg if current or finished else tokens.fg_muted
            label.setStyleSheet(f"color: {color.name()}; font-size: 13px; font-weight: {weight};")
        for i, line in enumerate(self._lines):
            color = tokens.success if i < step or (done and i + 1 <= step) else tokens.border
            line.setStyleSheet(f"background: {color.name()};")


class AdminViewQWidget(AdminViewBase):
    """Admin view: sign in, see the active experiment and switch it with step-by-step guidance."""

    def __init__(self, parent=None, atlas_url: str = DEFAULT_ATLAS_URL, client=None, **kwargs):
        super().__init__(parent=parent, atlas_url=atlas_url, client=client, **kwargs)
        self._tokens = ThemeTokens()
        self._rows_key = None
        self._wizard_key = None
        self._nav_key = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        self._pages = QStackedWidget(self)
        self._pages.addWidget(self._build_signed_out())
        self._pages.addWidget(self._build_signed_in())
        root.addWidget(self._pages, 1)
        self._apply_styles()
        self.refresh()

    ########################
    ## Building
    ########################

    def _build_header(self) -> QWidget:
        header = QFrame(self)
        header.setObjectName("adminHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)
        self._header_icon = IconLabel("admin_panel_settings", 26, header)
        layout.addWidget(self._header_icon)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        self._header_title = _label("Beamline admin", "h2", header)
        self._header_sub = _label("", "muted", header)
        titles.addWidget(self._header_title)
        titles.addWidget(self._header_sub)
        layout.addLayout(titles, 1)
        self._session_pill = StatusPill(header)
        layout.addWidget(self._session_pill)
        self._sign_out = TextButton("Sign out", "neutral", "logout", header)
        self._sign_out.clicked.connect(self.logout)
        layout.addWidget(self._sign_out)
        return header

    def _active_card(self, parent: QWidget) -> tuple[Card, dict]:
        card = Card("Active experiment", parent, padding=16)
        widgets: dict = {}
        top = QHBoxLayout()
        widgets["pgroup"] = _label("", "h1", card)
        widgets["pill"] = StatusPill(card)
        top.addWidget(widgets["pgroup"])
        top.addWidget(widgets["pill"])
        top.addStretch(1)
        card.body.addLayout(top)
        widgets["title"] = _label("", "strong", card, wrap=True)
        card.body.addWidget(widgets["title"])
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        for i, (key, text) in enumerate(
            [
                ("pi", "PI"),
                ("linuxAccount", "Linux login"),
                ("dataAccount", "Data saved to"),
                ("beamtime", "Beamtime"),
            ]
        ):
            grid.addWidget(_label(text, "muted", card), i, 0)
            role = "chip" if key in ("linuxAccount", "dataAccount") else ""
            widgets[key] = _label("", role, card)
            row = QHBoxLayout()
            row.addWidget(widgets[key])
            row.addStretch(1)
            grid.addLayout(row, i, 1)
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)
        widgets["empty"] = _label("BEC reports no active experiment.", "muted", card)
        card.body.addWidget(widgets["empty"])
        return card, widgets

    def _build_signed_out(self) -> QWidget:
        page = QWidget(self)
        outer = QHBoxLayout(page)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)
        column = QHBoxLayout()
        column.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(12)
        self._out_notice = Banner(page)
        card, self._out_active = self._active_card(page)
        card.setMinimumWidth(380)
        left.addWidget(card)
        left.addWidget(self._out_notice)
        left.addStretch(1)
        column.addLayout(left, 1)

        sign_in = Card("Staff sign-in", page, padding=20)
        sign_in.setFixedWidth(360)
        self._sign_in_text = _label("", "muted", sign_in, wrap=True)
        sign_in.body.addWidget(self._sign_in_text)
        sign_in.body.addSpacing(4)
        self._username = QLineEdit(sign_in)
        self._username.setPlaceholderText("PSI username")
        self._password = QLineEdit(sign_in)
        self._password.setPlaceholderText("Password")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._username.returnPressed.connect(self._password.setFocus)
        self._password.returnPressed.connect(self._submit_login)
        sign_in.body.addWidget(self._username)
        sign_in.body.addWidget(self._password)
        self._sign_in_error_label = _label("", "error", sign_in, wrap=True)
        sign_in.body.addWidget(self._sign_in_error_label)
        self._sign_in_button = TextButton("Sign in", "primary", "login", sign_in)
        self._sign_in_button.clicked.connect(self._submit_login)
        sign_in.body.addWidget(self._sign_in_button)
        hint = _label(
            "Signing in does not change anything yet. Switching the experiment asks for "
            "confirmation first.",
            "subtle",
            sign_in,
            wrap=True,
        )
        sign_in.body.addWidget(hint)
        right = QVBoxLayout()
        right.addWidget(sign_in)
        right.addStretch(1)
        column.addLayout(right)

        holder = QWidget(page)
        holder.setLayout(column)
        holder.setMaximumWidth(980)
        outer.addWidget(holder, 100)
        outer.addStretch(1)
        return page

    def _build_signed_in(self) -> QWidget:
        page = QWidget(self)
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        nav = QFrame(page)
        nav.setObjectName("adminNav")
        nav.setFixedWidth(184)
        self._nav_layout = QVBoxLayout(nav)
        self._nav_layout.setContentsMargins(10, 14, 10, 14)
        self._nav_layout.setSpacing(4)
        layout.addWidget(nav)

        self._content = QStackedWidget(page)
        self._content.addWidget(self._build_browse())
        self._content.addWidget(self._build_wizard())
        layout.addWidget(self._content, 1)
        return page

    def _build_browse(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        top = QHBoxLayout()
        top.setSpacing(12)
        card, self._in_active = self._active_card(page)
        top.addWidget(card, 3, Qt.AlignmentFlag.AlignTop)
        self._in_notice = Banner(page)
        notice_col = QVBoxLayout()
        notice_col.setSpacing(12)
        notice_col.addWidget(self._in_notice)
        notice_col.addWidget(self._how_card(page))
        notice_col.addStretch(1)
        top.addLayout(notice_col, 2)
        layout.addLayout(top)

        switch = Card("Switch experiment", page, padding=16)
        switch.body.setSpacing(10)
        tools = QHBoxLayout()
        self._search = QLineEdit(switch)
        self._search.setPlaceholderText("Search p-group, title, PI or account")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self.set_query)
        tools.addWidget(self._search, 1)
        self._scope_group = QButtonGroup(switch)
        for scope, text in (("upcoming", "Upcoming"), ("all", "All")):
            button = QPushButton(text, switch)
            button.setCheckable(True)
            button.setProperty("segment", scope)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, s=scope: self.set_scope(s))
            self._scope_group.addButton(button)
            tools.addWidget(button)
        switch.body.addLayout(tools)

        split = QHBoxLayout()
        split.setSpacing(12)
        self._list_area = QScrollArea(switch)
        self._list_area.setWidgetResizable(True)
        self._list_area.setFrameShape(QFrame.Shape.NoFrame)
        holder = QWidget()
        holder.setObjectName("listHolder")
        self._list_layout = QVBoxLayout(holder)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(4)
        self._list_area.setWidget(holder)
        split.addWidget(self._list_area, 3)

        detail = QFrame(switch)
        detail.setObjectName("detail")
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(14, 12, 14, 12)
        detail_layout.setSpacing(6)
        self._detail = {
            "pgroup": _label("", "h2", detail),
            "title": _label("", "strong", detail, wrap=True),
            "pi": _label("", "muted", detail),
            "beamtime": _label("", "muted", detail, wrap=True),
            "account": _label("", "", detail, wrap=True),
            "abstract": _label("", "subtle", detail, wrap=True),
        }
        for widget in self._detail.values():
            detail_layout.addWidget(widget)
        detail_layout.addStretch(1)
        self._switch_button = TextButton("Switch…", "primary", "swap_horiz", detail)
        self._switch_button.clicked.connect(lambda: self.start_switch(""))
        detail_layout.addWidget(self._switch_button)
        self._detail_empty = _label("Select an experiment to see its details.", "muted", detail)
        detail_layout.addWidget(self._detail_empty)
        split.addWidget(detail, 2)
        switch.body.addLayout(split, 1)
        switch.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        layout.addWidget(switch, 1)
        return page

    def _how_card(self, parent: QWidget) -> Card:
        card = Card("How switching works", parent, padding=14)
        card.body.setSpacing(6)
        self._how_rows = []
        for i, step in enumerate(HOW_IT_WORKS, start=1):
            row = QHBoxLayout()
            row.setSpacing(8)
            number = QLabel(str(i), card)
            number.setFixedSize(20, 20)
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._how_rows.append(number)
            row.addWidget(number, 0, Qt.AlignmentFlag.AlignTop)
            row.addWidget(_label(step, "muted", card, wrap=True), 1)
            card.body.addLayout(row)
        return card

    def _build_wizard(self) -> QWidget:
        page = QWidget(self)
        outer = QHBoxLayout(page)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.addStretch(1)
        card = Card("", page, padding=20)
        card.setMaximumWidth(780)
        card.setMinimumWidth(560)
        card.body.setSpacing(14)
        head = QHBoxLayout()
        head_text = QVBoxLayout()
        head_text.setSpacing(2)
        self._wiz_title = _label("Switch experiment", "h2", card)
        self._wiz_sub = _label("", "muted", card)
        head_text.addWidget(self._wiz_title)
        head_text.addWidget(self._wiz_sub)
        head.addLayout(head_text, 1)
        card.body.addLayout(head)
        self._stepper = Stepper(["Review", "Confirm", "Log in"], card)
        card.body.addWidget(self._stepper)
        line = QFrame(card)
        line.setObjectName("rule")
        line.setFixedHeight(1)
        card.body.addWidget(line)
        self._wiz_body = QVBoxLayout()
        self._wiz_body.setSpacing(10)
        card.body.addLayout(self._wiz_body)
        self._ack = QCheckBox(card)
        self._ack.toggled.connect(self.set_acknowledged)
        card.body.addWidget(self._ack)
        self._wiz_error = Banner(card)
        card.body.addWidget(self._wiz_error)
        card.body.addStretch(1)
        footer = QHBoxLayout()
        self._wiz_cancel = TextButton("Cancel", "ghost", "", card)
        self._wiz_cancel.clicked.connect(self.close_wizard)
        self._wiz_back = TextButton("Back", "neutral", "arrow_back", card)
        self._wiz_back.clicked.connect(self.wizard_back)
        self._wiz_primary = TextButton("Next", "primary", "arrow_forward", card)
        self._wiz_primary.clicked.connect(self._wizard_primary)
        footer.addWidget(self._wiz_cancel)
        footer.addStretch(1)
        footer.addWidget(self._wiz_back)
        footer.addWidget(self._wiz_primary)
        card.body.addLayout(footer)
        column = QVBoxLayout()
        column.addWidget(card)
        column.addStretch(1)
        outer.addLayout(column, 100)
        outer.addStretch(1)
        return page

    ########################
    ## Actions
    ########################

    def _submit_login(self) -> None:
        self.login(self._username.text().strip(), self._password.text())
        self._password.clear()

    def _wizard_primary(self) -> None:
        step = self._wizard["step"]
        if step == 0:
            self.wizard_next()
        elif step == 1:
            self.confirm_switch()
        else:
            self.close_wizard()

    ########################
    ## Rendering
    ########################

    def apply_theme(self, theme: str):
        """Re-draw everything in the new theme."""
        self._tokens = refresh_kit_theme(self)
        self._rows_key = self._wizard_key = self._nav_key = None
        self._apply_styles()
        self.refresh()

    def _apply_styles(self) -> None:
        t = self._tokens
        mono = "'JetBrains Mono', 'DejaVu Sans Mono', monospace"
        self.setStyleSheet(field_qss(t) + f"""
            QLabel {{ color: {t.fg.name()}; font-size: 13px; background: transparent; }}
            QLabel[role="h1"] {{ font-size: 22px; font-weight: 700; }}
            QLabel[role="h2"] {{ font-size: 16px; font-weight: 650; }}
            QLabel[role="strong"] {{ font-weight: 600; }}
            QLabel[role="muted"] {{ color: {t.fg_muted.name()}; }}
            QLabel[role="subtle"] {{ color: {t.fg_subtle.name()}; font-size: 12px; }}
            QLabel[role="error"] {{ color: {t.danger.name()}; }}
            QLabel[role="rowKey"] {{ font-family: {mono}; font-weight: 600; }}
            QLabel[role="chip"] {{ font-family: {mono}; font-weight: 600;
                background: {t.soft(t.primary, 0.14).name()}; color: {t.fg.name()};
                border-radius: 4px; padding: 1px 6px; }}
            QLabel[role="bigChip"] {{ font-family: {mono}; font-weight: 700; font-size: 20px;
                background: {t.soft(t.primary, 0.18).name()}; color: {t.fg.name()};
                border: 1px solid {t.soft(t.primary, 0.5).name()};
                border-radius: 6px; padding: 4px 12px; }}
            QFrame#adminHeader {{ background: {t.card.name()};
                border-bottom: 1px solid {t.border.name()}; }}
            QFrame#adminNav {{ background: {t.card.name()};
                border-right: 1px solid {t.border.name()}; }}
            QFrame#detail {{ background: {t.field.name()}; border: 1px solid {t.border.name()};
                border-radius: 8px; }}
            QFrame#rule {{ background: {t.border.name()}; }}
            QWidget#listHolder {{ background: transparent; }}
            QScrollArea {{ background: transparent; }}
            QFrame#expRow {{ background: transparent; border: 1px solid transparent;
                border-radius: 8px; }}
            QFrame#expRow:hover {{ background: {t.hover.name()}; }}
            QFrame#expRow[selected="true"] {{ background: {t.soft(t.primary, 0.14).name()};
                border: 1px solid {t.soft(t.primary, 0.6).name()}; }}
            QPushButton[segment] {{ background: transparent; color: {t.fg_muted.name()};
                border: 1px solid {t.border.name()}; padding: 0 12px; min-height: 30px;
                font-size: 13px; }}
            QPushButton[segment="upcoming"] {{ border-top-left-radius: 6px;
                border-bottom-left-radius: 6px; }}
            QPushButton[segment="all"] {{ border-top-right-radius: 6px;
                border-bottom-right-radius: 6px; border-left: none; }}
            QPushButton[segment]:checked {{ background: {t.soft(t.primary, 0.18).name()};
                color: {t.fg.name()}; font-weight: 600; }}
            QPushButton[nav] {{ text-align: left; padding: 0 10px; min-height: 34px;
                border: none; border-radius: 6px; color: {t.fg.name()}; font-size: 13px;
                background: transparent; }}
            QPushButton[nav]:hover {{ background: {t.hover.name()}; }}
            QPushButton[nav]:checked {{ background: {t.soft(t.primary, 0.18).name()};
                font-weight: 600; }}
            QPushButton[nav]:disabled {{ color: {t.fg_subtle.name()}; }}
            QCheckBox {{ color: {t.fg.name()}; font-size: 13px; font-weight: 600;
                spacing: 8px; }}
            """)
        self._header_icon.set_icon("admin_panel_settings", t.primary)
        for number in getattr(self, "_how_rows", []):
            number.setStyleSheet(
                f"background: {t.soft(t.primary, 0.2).name()}; color: {t.fg.name()};"
                " border-radius: 10px; font-weight: 700; font-size: 11px;"
            )

    def _render(self, state: dict) -> None:
        if not hasattr(self, "_pages"):
            return  # called by the base class before the widgets exist
        t = self._tokens
        realm = f" · {state['realm']}" if state["realm"] else ""
        self._header_sub.setText(f"{state['deploymentName']}{realm}")
        if state["signedIn"]:
            self._session_pill.set_status(
                f"{state['email']} · {state['remaining']} left", t.success
            )
        else:
            self._session_pill.set_status("Not signed in", t.fg_subtle)
        self._sign_out.setVisible(state["signedIn"])
        page = 1 if state["signedIn"] else 0
        if page != self._pages.currentIndex():
            self._pages.setCurrentIndex(page)
            # do not drop the user into the search field (or keep focus on the password field)
            self._pages.currentWidget().setFocus()

        for widgets in (self._out_active, self._in_active):
            self._fill_active(widgets, state)
        for banner in (self._out_notice, self._in_notice):
            notice = state["notice"]
            banner.setVisible(bool(notice))
            if notice:
                banner.set_message(notice["tone"], notice["title"], notice["text"], t)

        self._sign_in_text.setText(
            "Sign in with your PSI account to switch the active experiment. Your account needs "
            f"owner rights on {state['deploymentName']}."
        )
        self._sign_in_error_label.setText(state["signInError"])
        self._sign_in_error_label.setVisible(bool(state["signInError"]))
        self._sign_in_button.setEnabled(not state["signingIn"])
        self._sign_in_button.setText("Signing in…" if state["signingIn"] else "Sign in")

        if state["signedIn"]:
            self._render_nav(state)
            self._render_browse(state)
            self._render_wizard(state)
            self._content.setCurrentIndex(1 if state["wizard"]["open"] else 0)

    def _render_session_time(self, remaining: str) -> None:
        """Only the session pill changes every second."""
        if self._auth is not None:
            self._session_pill.set_status(
                f"{self._auth.email} · {remaining} left", self._tokens.success
            )

    def _fill_active(self, widgets: dict, state: dict) -> None:
        active = state["active"]
        has = state["hasActive"]
        for key in ("pgroup", "pill", "title", "pi", "linuxAccount", "dataAccount", "beamtime"):
            widgets[key].setVisible(has)
        widgets["empty"].setVisible(not has)
        if not has:
            return
        widgets["pgroup"].setText(active["pgroup"])
        widgets["pill"].set_status("Active", self._tokens.success)
        widgets["title"].setText(active["title"])
        widgets["pi"].setText(active["pi"])
        widgets["linuxAccount"].setText(active["linuxAccount"] or "unknown")
        widgets["dataAccount"].setText(active["dataAccount"])
        widgets["beamtime"].setText(active["beamtime"])

    def _render_nav(self, state: dict) -> None:
        key = (state["section"], tuple(s["id"] for s in state["sections"]))
        if key == self._nav_key:
            return
        self._nav_key = key
        _clear(self._nav_layout)
        for section in state["sections"]:
            text = section["label"] + (f"   ·  {section['badge']}" if section["badge"] else "")
            button = QPushButton(text, self)
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.setChecked(section["id"] == state["section"])
            button.setEnabled(section["enabled"])
            color = self._tokens.fg if section["enabled"] else self._tokens.fg_subtle
            button.setIcon(
                material_icon(section["icon"], size=(32, 32), color=color, convert_to_pixmap=False)
            )
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda _=False, s=section["id"]: self.open_section(s))
            self._nav_layout.addWidget(button)
        self._nav_layout.addStretch(1)

    def _render_browse(self, state: dict) -> None:
        for button in self._scope_group.buttons():
            button.setChecked(button.property("segment") == state["scope"])
        if self._search.text() != state["query"]:
            self._search.setText(state["query"])
        selected = state["selected"]
        rows_key = (
            tuple((r["pgroup"], r["status"]) for r in state["rows"]),
            selected.get("pgroup", ""),
            state["loadingExperiments"],
        )
        if rows_key != self._rows_key:
            self._rows_key = rows_key
            _clear(self._list_layout)
            if state["loadingExperiments"]:
                self._list_layout.addWidget(_label("Loading experiments…", "muted"))
            elif not state["rows"]:
                text = (
                    "No experiment matches the search."
                    if state["totalCount"]
                    else "Atlas lists no experiments for this beamline."
                )
                self._list_layout.addWidget(_label(text, "muted"))
            for row in state["rows"]:
                widget = ExperimentRow(
                    row, row["pgroup"] == selected.get("pgroup"), self._tokens, self
                )
                widget.clicked.connect(self.select_experiment)
                self._list_layout.addWidget(widget)
            self._list_layout.addStretch(1)

        has = bool(selected)
        for widget in self._detail.values():
            widget.setVisible(has)
        self._switch_button.setVisible(has)
        self._detail_empty.setVisible(not has)
        if has:
            self._detail["pgroup"].setText(selected["pgroup"])
            self._detail["title"].setText(selected["title"])
            self._detail["pi"].setText(f"PI: {selected['pi']}")
            self._detail["beamtime"].setText(selected["beamtime"])
            self._detail["account"].setText(
                f"Group logs in as <b>{selected['linuxAccount'] or 'unknown'}</b>"
            )
            abstract = selected["abstract"]
            self._detail["abstract"].setText(
                abstract if len(abstract) < 260 else abstract[:257] + "…"
            )
            self._detail["abstract"].setVisible(bool(abstract))
            self._switch_button.setEnabled(state["canSwitch"])
            self._switch_button.setText(
                "This is the active experiment"
                if selected["isActive"]
                else f"Switch to {selected['pgroup']}…"
            )

    def _render_wizard(self, state: dict) -> None:
        wizard = state["wizard"]
        if not wizard["open"]:
            self._wizard_key = None
            return
        t = self._tokens
        target = wizard["targetInfo"]
        plan = wizard["plan"]
        step, phase = wizard["step"], wizard["phase"]
        self._wiz_title.setText("Experiment switched" if phase == "done" else "Switch experiment")
        self._wiz_sub.setText(f"{wizard['fromPgroup']} → {target.get('pgroup', '')}")
        self._stepper.set_step(step, phase == "done", t)

        key = (step, phase, target.get("pgroup"), state["queueBusy"])
        if key != self._wizard_key:
            self._wizard_key = key
            _clear(self._wiz_body)
            if step == 0:
                self._fill_review(plan)
            elif step == 1:
                self._fill_confirm(plan)
            else:
                self._fill_login(plan, state)

        self._ack.setVisible(step == 1)
        self._ack.setText(plan.get("ackText", ""))
        self._ack.blockSignals(True)
        self._ack.setChecked(wizard["ack"])
        self._ack.blockSignals(False)
        self._ack.setEnabled(phase != "switching")
        self._wiz_error.setVisible(bool(wizard["error"]))
        if wizard["error"]:
            self._wiz_error.set_message("danger", "The switch failed", wizard["error"], t)

        self._wiz_cancel.setVisible(phase not in ("done", "switching"))
        self._wiz_back.setVisible(step > 0 and phase not in ("done", "switching"))
        if step == 0:
            text, variant, icon, enabled = "Next", "primary", "arrow_forward", True
        elif step == 1:
            text = "Switching…" if phase == "switching" else f"Switch to {target.get('pgroup')}"
            variant, icon, enabled = "danger", "swap_horiz", wizard["canConfirm"]
        else:
            text, variant, icon, enabled = "Done", "primary", "check", True
        self._wiz_primary.setText(text)
        self._wiz_primary._icon_name = icon  # pylint: disable=protected-access
        self._wiz_primary.set_variant(variant)
        self._wiz_primary.setEnabled(enabled)

    def _fill_review(self, plan: dict) -> None:
        t = self._tokens
        intro = _label(
            "Check that this is the right experiment. Switching also changes which Linux account "
            "the group uses on this computer.",
            "muted",
            wrap=True,
        )
        self._wiz_body.addWidget(intro)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(0)
        for col, text in ((1, "Now"), (3, "After switching")):
            grid.addWidget(_label(text, "subtle"), 0, col)
        for i, change in enumerate(plan["changes"], start=1):
            row_frame = QFrame()
            row_frame.setStyleSheet(
                f"background: {t.soft(t.warning, 0.16).name()}; border-radius: 6px;"
                if change["key"]
                else "background: transparent;"
            )
            grid.addWidget(row_frame, i, 0, 1, 4)
            role = "chip" if change["key"] else ""
            label = _label(change["label"], "strong" if change["key"] else "muted")
            label.setContentsMargins(8, 7, 0, 7)
            grid.addWidget(label, i, 0)
            before = _label(change["before"], "muted")
            before.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            grid.addWidget(before, i, 1)
            arrow = IconLabel("arrow_forward", 16)
            arrow.set_icon("arrow_forward", t.fg_subtle)
            grid.addWidget(arrow, i, 2)
            after = _label(change["after"], role or "strong")
            after.setSizePolicy(
                QSizePolicy.Policy.Maximum if role else QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Fixed,
            )
            holder = QHBoxLayout()
            holder.setContentsMargins(0, 0, 8, 0)
            holder.addWidget(after)
            if role:
                holder.addStretch(1)
            grid.addLayout(holder, i, 3)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self._wiz_body.addLayout(grid)

    def _fill_confirm(self, plan: dict) -> None:
        t = self._tokens
        self._wiz_body.addWidget(_label("What happens when you switch", "strong"))
        for item in plan["consequences"]:
            row = QHBoxLayout()
            row.setSpacing(10)
            icon = IconLabel(item["icon"], 20)
            icon.set_icon(item["icon"], tone_color(t, item["tone"]))
            row.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
            text = QVBoxLayout()
            text.setSpacing(1)
            text.addWidget(_label(item["title"], "strong", wrap=True))
            text.addWidget(_label(item["text"], "muted", wrap=True))
            row.addLayout(text, 1)
            self._wiz_body.addLayout(row)
        box = QFrame()
        box.setObjectName("loginBox")
        box.setStyleSheet(
            f"QFrame#loginBox {{ background: {t.soft(t.warning, 0.14).name()};"
            f" border: 1px solid {t.soft(t.warning, 0.5).name()}; border-radius: 8px; }}"
        )
        box_layout = QHBoxLayout(box)
        box_layout.setContentsMargins(12, 10, 12, 10)
        icon = IconLabel("login", 22, box)
        icon.set_icon("login", t.warning)
        box_layout.addWidget(icon)
        box_layout.addWidget(
            _label("Afterwards the group must log in to this computer as", "strong", box)
        )
        box_layout.addWidget(_label(plan["linuxAccount"], "chip", box))
        box_layout.addStretch(1)
        self._wiz_body.addWidget(box)

    def _fill_login(self, plan: dict, state: dict) -> None:
        t = self._tokens
        banner = Banner()
        banner.set_message(
            "ok",
            f"{state['wizard']['targetInfo'].get('pgroup', '')} is now the active experiment",
            "New scans are saved for the new experiment. One step is left on this computer:",
            t,
        )
        self._wiz_body.addWidget(banner)
        account_row = QHBoxLayout()
        account_row.addWidget(_label("Log in as", "h2"))
        account_row.addWidget(_label(plan["linuxAccount"], "bigChip"))
        account_row.addStretch(1)
        self._wiz_body.addLayout(account_row)
        for i, step in enumerate(plan["loginSteps"], start=1):
            row = QHBoxLayout()
            row.setSpacing(10)
            number = QLabel(str(i))
            number.setFixedSize(22, 22)
            number.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number.setStyleSheet(
                f"background: {t.soft(t.primary, 0.2).name()}; color: {t.fg.name()};"
                " border-radius: 11px; font-weight: 700; font-size: 12px;"
            )
            row.addWidget(number, 0, Qt.AlignmentFlag.AlignTop)
            text = QVBoxLayout()
            text.setSpacing(1)
            text.addWidget(_label(step["title"], "strong", wrap=True))
            text.addWidget(_label(step["text"], "muted", wrap=True))
            row.addLayout(text, 1)
            self._wiz_body.addLayout(row)

    def cleanup(self):
        """Stop the session pills and the Atlas connection."""
        for pill in self.findChildren(StatusPill):
            pill.cleanup()
        super().cleanup()
