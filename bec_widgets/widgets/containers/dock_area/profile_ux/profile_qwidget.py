"""Profile library, name dialog and revert dialog built from QWidgets.

Same UX as :mod:`profile_qml`; state and rules come from :mod:`.common`.
"""

from __future__ import annotations

from bec_qthemes import material_icon
from qtpy.QtCore import QRectF, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QPixmap, QShortcut
from qtpy.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.utils.ux_kit import (
    IconButton,
    StatusPill,
    TextButton,
    ToggleSwitch,
    field_qss,
    rgba,
    set_invalid,
)
from bec_widgets.widgets.containers.dock_area.profile_utils import is_profile_read_only
from bec_widgets.widgets.containers.dock_area.profile_ux.common import (
    NameCheck,
    NameMode,
    ProfileActions,
    ProfileLibraryController,
    absolute_time,
    relative_time,
)

TITLES = {"save": "Save profile", "rename": "Rename profile", "duplicate": "Duplicate profile"}


def tone_color(tokens: ThemeTokens, tone: str) -> QColor:
    """Colour of a hint or banner tone."""
    return {
        "error": tokens.danger,
        "warning": tokens.warning,
        "success": tokens.success,
        "info": tokens.primary,
    }.get(tone, tokens.fg_muted)


TONE_ICONS = {
    "error": "error",
    "warning": "warning",
    "success": "check_circle",
    "info": "info",
    "neutral": "",
}


class PreviewFrame(QWidget):
    """Rounded screenshot preview that keeps the aspect ratio, with a placeholder text."""

    def __init__(self, parent: QWidget | None = None, placeholder: str = "No preview yet"):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._placeholder = placeholder
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(160, 100)

    def set_pixmap(self, pixmap: QPixmap | None, placeholder: str | None = None) -> None:
        """Show *pixmap*, or the placeholder when it is None."""
        self._pixmap = pixmap if pixmap is not None and not pixmap.isNull() else None
        if placeholder is not None:
            self._placeholder = placeholder
        self.update()

    def has_pixmap(self) -> bool:
        """Whether a screenshot is shown."""
        return self._pixmap is not None

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Preferred preview size."""
        return QSize(320, 200)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        """Paint the screenshot or the placeholder."""
        tokens = ThemeTokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._pixmap is not None:
            scaled = self._pixmap.size().scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio)
            target = QRectF(
                (self.width() - scaled.width()) / 2,
                (self.height() - scaled.height()) / 2,
                scaled.width(),
                scaled.height(),
            )
            path = QPainterPath()
            path.addRoundedRect(target, 8, 8)
            painter.setClipPath(path)
            painter.drawPixmap(target.toRect(), self._pixmap)
            painter.setClipping(False)
            painter.setPen(tokens.border)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(target.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        else:
            painter.setPen(tokens.border)
            painter.setBrush(tokens.soft(tokens.fg, 0.04))
            painter.drawRoundedRect(rect, 8, 8)
            icon = material_icon("dashboard", size=(64, 64), color=tokens.fg_subtle)
            icon_rect = QRectF(rect.center().x() - 16, rect.center().y() - 28, 32, 32)
            painter.drawPixmap(icon_rect.toRect(), icon)
            painter.setPen(tokens.fg_subtle)
            font = self.font()
            font.setPixelSize(12)
            painter.setFont(font)
            painter.drawText(
                rect.adjusted(8, 40, -8, 0),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                self._placeholder,
            )
        painter.end()


class HintLine(QWidget):
    """Icon and text in the colour of a tone, used under fields and in banners."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.icon = QLabel(self)
        self.icon.setFixedSize(16, 16)
        self.text = QLabel(self)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.text, 1)
        self._tone = "neutral"

    def set_hint(self, tone: str, text: str) -> None:
        """Show *text* in the colour of *tone*."""
        self._tone = tone
        tokens = ThemeTokens()
        color = tone_color(tokens, tone)
        icon = TONE_ICONS.get(tone, "")
        self.icon.setVisible(bool(icon))
        if icon:
            self.icon.setPixmap(material_icon(icon, size=(32, 32), color=color).scaled(16, 16))
        text_color = tokens.fg_muted if tone == "neutral" else color
        if tone == "warning" and not tokens.dark:
            text_color = tokens.warning.darker(160)
        self.text.setStyleSheet(f"color: {text_color.name()}; font-size: 12px;")
        self.text.setText(text)


def _label(text: str, role: str = "body", parent: QWidget | None = None) -> QLabel:
    tokens = ThemeTokens()
    label = QLabel(text, parent)
    styles = {
        "title": f"color: {tokens.fg.name()}; font-size: 16px; font-weight: 600;",
        "heading": f"color: {tokens.fg.name()}; font-size: 13px; font-weight: 600;",
        "body": f"color: {tokens.fg.name()}; font-size: 13px;",
        "muted": f"color: {tokens.fg_muted.name()}; font-size: 12px;",
        "caption": (
            f"color: {tokens.fg_subtle.name()}; font-size: 11px; font-weight: 600;"
            " letter-spacing: 0.5px;"
        ),
    }
    label.setStyleSheet(styles[role])
    return label


################################################################################
# Name dialog
################################################################################


class ProfileNameDialog(QDialog):
    """
    One dialog for saving, renaming and duplicating profiles. The name is checked while
    typing; conflicts are explained under the field instead of in follow-up message boxes.

    Args:
        actions(ProfileActions): Profile operations and checks.
        mode(NameMode): ``save``, ``rename`` or ``duplicate``.
        original(str): Profile being renamed or duplicated.
        initial(str): Initial text of the name field.
        preview(QPixmap | None): Screenshot shown next to the form.
        parent(QWidget | None): Parent widget.
    """

    def __init__(
        self,
        actions: ProfileActions,
        mode: NameMode,
        original: str = "",
        initial: str = "",
        preview: QPixmap | None = None,
        parent: QWidget | None = None,
        notes: str = "",
        pinned: bool = True,
    ):
        super().__init__(parent)
        self.actions = actions
        self.mode = mode
        self.original = original
        self._check: NameCheck | None = None
        tokens = ThemeTokens()
        self.setWindowTitle(TITLES[mode])
        self.setModal(True)
        self.setObjectName("ProfileNameDialog")
        self.setStyleSheet(
            f"QDialog#ProfileNameDialog {{ background: {tokens.card.name()}; }}" + field_qss(tokens)
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)
        heading = TITLES[mode] if mode == "save" else f"{TITLES[mode]} '{original}'"
        root.addWidget(_label(heading, "title", self))

        body = QHBoxLayout()
        body.setSpacing(16)
        self.preview = PreviewFrame(self, "Nothing to preview")
        self.preview.setFixedSize(220, 140)
        self.preview.set_pixmap(preview)
        body.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignTop)

        form = QVBoxLayout()
        form.setSpacing(6)
        form.addWidget(_label("Name", "heading", self))
        self.name_edit = QLineEdit(initial, self)
        self.name_edit.setPlaceholderText("e.g. alignment, overview, tomo_scan")
        self.name_edit.setMinimumWidth(300)
        self.name_edit.selectAll()
        form.addWidget(self.name_edit)
        self.hint = HintLine(self)
        form.addWidget(self.hint)
        self.suggestion_button = TextButton("", "ghost", "auto_fix_high", self)
        self.suggestion_button.setMinimumHeight(26)
        self.suggestion_button.clicked.connect(self._use_suggestion)
        form.addWidget(self.suggestion_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.notes_edit = QLineEdit(notes, self)
        self.pin_switch = ToggleSwitch(self)
        self.pin_switch.setChecked(pinned)
        if mode == "save":
            form.addSpacing(6)
            form.addWidget(_label("Description", "heading", self))
            self.notes_edit.setPlaceholderText("Optional, shown in the profile library")
            form.addWidget(self.notes_edit)
            form.addSpacing(6)
            pin_row = QHBoxLayout()
            pin_text = QVBoxLayout()
            pin_text.setSpacing(0)
            pin_text.addWidget(_label("Show in toolbar list", "heading", self))
            pin_text.addWidget(_label("Quick access from the profile drop-down.", "muted", self))
            pin_row.addLayout(pin_text, 1)
            pin_row.addWidget(self.pin_switch)
            form.addLayout(pin_row)
        else:
            self.notes_edit.hide()
            self.pin_switch.hide()
        form.addStretch(1)
        body.addLayout(form, 1)
        root.addLayout(body)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_button = TextButton("Cancel", "neutral", parent=self)
        self.confirm_button = TextButton(TITLES[mode].split()[0], "primary", parent=self)
        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button.clicked.connect(self._confirm)
        self.confirm_button.setDefault(True)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.confirm_button)
        root.addLayout(buttons)

        self.name_edit.textChanged.connect(self._validate)
        self.name_edit.returnPressed.connect(self._confirm)
        self._validate()

    @property
    def check(self) -> NameCheck:
        """The latest validation result."""
        return self._check

    def profile_name(self) -> str:
        """The entered name."""
        return self.name_edit.text().strip()

    def notes(self) -> str:
        """The entered description."""
        return self.notes_edit.text().strip()

    def pinned(self) -> bool:
        """Whether the profile shows in the toolbar list."""
        return self.pin_switch.isChecked()

    def _validate(self, *_args) -> None:
        check = self.actions.check(self.name_edit.text(), self.mode, self.original or None)
        self._check = check
        self.hint.set_hint(check.tone, check.message)
        self.hint.setVisible(bool(check.message))
        set_invalid(self.name_edit, check.tone == "error")
        self.suggestion_button.setVisible(bool(check.suggestion))
        if check.suggestion:
            self.suggestion_button.setText(f"Use '{check.suggestion}'")
        self.confirm_button.setText(check.action)
        self.confirm_button.set_variant("danger" if check.replaces else "primary")
        self.confirm_button.setEnabled(check.ok)

    def _use_suggestion(self) -> None:
        if self._check and self._check.suggestion:
            self.name_edit.setText(self._check.suggestion)
            self.name_edit.setFocus()

    def _confirm(self) -> None:
        if self._check is not None and self._check.ok:
            self.accept()


################################################################################
# Revert dialog
################################################################################


class RevertProfileDialog(QDialog):
    """
    Confirm reverting a profile to its saved layout, showing the current and the saved
    layout side by side. Cancel is the default button.

    Args:
        name(str): Profile name.
        saved_at(str): ISO timestamp of the saved copy.
        current(QPixmap | None): Screenshot of the current layout.
        saved(QPixmap | None): Screenshot of the saved layout.
        read_only(bool): Whether the profile is a read-only one (reverts to its original).
        parent(QWidget | None): Parent widget.
    """

    def __init__(
        self,
        name: str,
        saved_at: str,
        current: QPixmap | None,
        saved: QPixmap | None,
        read_only: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        tokens = ThemeTokens()
        self.setWindowTitle("Revert to saved layout")
        self.setModal(True)
        self.setObjectName("RevertProfileDialog")
        self.setStyleSheet(f"QDialog#RevertProfileDialog {{ background: {tokens.card.name()}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)
        root.addWidget(_label(f"Revert '{name}' to its saved layout?", "title", self))
        when = relative_time(saved_at)
        what = "its original layout" if read_only else "the layout saved"
        text = f"Changes made since then are discarded. You go back to {what}"
        text += f" {when}." if when and not read_only else "."
        body = _label(text, "muted", self)
        body.setWordWrap(True)
        root.addWidget(body)

        row = QHBoxLayout()
        row.setSpacing(12)
        for caption, pixmap, sub in (
            ("NOW", current, "Current layout"),
            ("AFTER REVERT", saved, absolute_time(saved_at) or "Saved layout"),
        ):
            column = QVBoxLayout()
            column.setSpacing(6)
            column.addWidget(_label(caption, "caption", self))
            frame = PreviewFrame(self, "No screenshot")
            frame.setFixedSize(300, 190)
            frame.set_pixmap(pixmap)
            column.addWidget(frame)
            column.addWidget(_label(sub, "muted", self))
            row.addLayout(column)
            if caption == "NOW":
                arrow = QLabel(self)
                arrow.setPixmap(
                    material_icon("arrow_forward", size=(40, 40), color=tokens.fg_subtle).scaled(
                        20, 20
                    )
                )
                row.addWidget(arrow, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_button = TextButton("Keep current layout", "neutral", parent=self)
        self.revert_button = TextButton("Revert", "danger", "history", self)
        self.cancel_button.setDefault(True)
        self.cancel_button.clicked.connect(self.reject)
        self.revert_button.clicked.connect(self.accept)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.revert_button)
        root.addLayout(buttons)


################################################################################
# Library
################################################################################


class _Row(QFrame):
    """One profile row of the library list."""

    pin_clicked = Signal(str)
    restore_clicked = Signal(str)

    def __init__(self, row: dict, parent: QWidget | None = None):
        super().__init__(parent)
        tokens = ThemeTokens()
        self.key = row["key"]
        self.setObjectName("libRow")
        self._selected = None
        self.set_selected(row["selected"])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 6, 6)
        layout.setSpacing(8)
        icon_name = {"trash": "delete", "bundled": "lock"}.get(row["kind"], "dashboard")
        icon = QLabel(self)
        icon_color = tokens.primary if row["isCurrent"] else tokens.fg_subtle
        icon.setPixmap(material_icon(icon_name, size=(36, 36), color=icon_color).scaled(18, 18))
        icon.setStyleSheet("background: none; border: none;")
        layout.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(1)
        name = QLabel(row["name"], self)
        weight = 600 if row["isCurrent"] else 500
        fg = tokens.fg_muted if row["kind"] == "trash" else tokens.fg
        name.setStyleSheet(
            f"color: {fg.name()}; font-size: 13px; font-weight: {weight}; background: none;"
            " border: none;"
        )
        subtitle = QLabel(row["subtitle"], self)
        subtitle.setStyleSheet(
            f"color: {tokens.fg_subtle.name()}; font-size: 11px; background: none; border: none;"
        )
        text.addWidget(name)
        text.addWidget(subtitle)
        layout.addLayout(text, 1)
        if row["isCurrent"] or row["isOpen"]:
            pill = StatusPill(self)
            pill.set_status(
                "This tab" if row["isCurrent"] else "Open",
                tokens.primary if row["isCurrent"] else tokens.success,
            )
            layout.addWidget(pill)
        if row["kind"] == "trash":
            restore = TextButton("Restore", "ghost", "restore_from_trash", self)
            restore.setMinimumHeight(28)
            restore.clicked.connect(lambda: self.restore_clicked.emit(row["token"]))
            layout.addWidget(restore)
        else:
            pin = IconButton("star", "Show in toolbar list", self, size=16)
            pin.setIcon(
                material_icon(
                    "star",
                    size=(32, 32),
                    filled=row["pinned"],
                    color=tokens.warning if row["pinned"] else tokens.fg_subtle,
                    convert_to_pixmap=False,
                )
            )
            pin.setToolTip(
                "Shown in the toolbar list. Click to hide."
                if row["pinned"]
                else "Not in the toolbar list. Click to show."
            )
            pin.clicked.connect(lambda: self.pin_clicked.emit(self.key))
            layout.addWidget(pin)

    def set_selected(self, selected: bool) -> None:
        """Show the row as selected or not."""
        if selected == self._selected:
            return
        self._selected = selected
        tokens = ThemeTokens()
        bg = rgba(tokens.soft(tokens.primary, 0.14), 1.0) if selected else "transparent"
        hover = bg if selected else tokens.hover.name()
        border = tokens.primary.name() if selected else "transparent"
        self.setStyleSheet(
            f"QFrame#libRow {{ background: {bg}; border-radius: 8px; border: 1px solid {border}; }}"
            f"QFrame#libRow:hover {{ background: {hover}; }}"
        )


class ProfileLibraryWidget(QWidget):
    """
    The profile library: searchable list with sections on the left, the selected profile's
    preview, description, facts and actions on the right.

    Args:
        controller(ProfileLibraryController): State and actions.
        parent(QWidget | None): Parent widget.
    """

    def __init__(self, controller: ProfileLibraryController, parent: QWidget | None = None):
        super().__init__(parent)
        self.controller = controller
        self.setObjectName("ProfileLibrary")
        tokens = ThemeTokens()
        self.setStyleSheet(
            f"QWidget#ProfileLibrary {{ background: {tokens.bg.name()}; }}" + field_qss(tokens)
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # header
        header = QHBoxLayout()
        header.setSpacing(10)
        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        self.title = _label("Profiles", "title", self)
        self.count_label = _label("", "muted", self)
        title_col.addWidget(self.title)
        title_col.addWidget(self.count_label)
        header.addLayout(title_col)
        header.addStretch(1)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search profiles  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(260)
        self.search.addAction(
            material_icon("search", size=(32, 32), color=tokens.fg_subtle, convert_to_pixmap=False),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        header.addWidget(self.search)
        self.save_button = TextButton("Save current layout…", "primary", "save", self)
        header.addWidget(self.save_button)
        root.addLayout(header)

        # banner
        self.banner = QFrame(self)
        self.banner.setObjectName("libBanner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(12, 6, 6, 6)
        self.banner_hint = HintLine(self.banner)
        banner_layout.addWidget(self.banner_hint, 1)
        self.banner_action = TextButton("", "ghost", parent=self.banner)
        self.banner_action.setMinimumHeight(28)
        banner_layout.addWidget(self.banner_action)
        self.banner_close = IconButton("close", "Dismiss", self.banner, size=16)
        banner_layout.addWidget(self.banner_close)
        root.addWidget(self.banner)

        # body
        body = QHBoxLayout()
        body.setSpacing(14)
        self.list = QListWidget(self)
        self.list.setFixedWidth(330)
        self.list.setSpacing(1)
        self.list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setStyleSheet(
            f"QListWidget {{ background: {tokens.card.name()}; border: 1px solid"
            f" {tokens.border.name()}; border-radius: 10px; padding: 6px; outline: none; }}"
            "QListWidget::item, QListWidget::item:selected, QListWidget::item:hover"
            " { background: transparent; border: none; }"
        )
        body.addWidget(self.list)

        self.details = QFrame(self)
        self.details.setObjectName("libDetails")
        self.details.setStyleSheet(
            f"QFrame#libDetails {{ background: {tokens.card.name()}; border: 1px solid"
            f" {tokens.border.name()}; border-radius: 10px; }}"
        )
        details = QVBoxLayout(self.details)
        details.setContentsMargins(16, 16, 16, 14)
        details.setSpacing(10)
        self.preview = PreviewFrame(self.details)
        self.preview.setMinimumHeight(220)
        details.addWidget(self.preview, 1)
        name_row = QHBoxLayout()
        self.name_label = _label("", "title", self.details)
        self.status_pill = StatusPill(self.details)
        name_row.addWidget(self.name_label)
        name_row.addWidget(self.status_pill)
        name_row.addStretch(1)
        self.delete_button = TextButton("Delete…", "ghost", "delete", self.details)
        name_row.addWidget(self.delete_button)
        details.addLayout(name_row)
        self.notes_edit = QLineEdit(self.details)
        self.notes_edit.setPlaceholderText("Add a description…")
        details.addWidget(self.notes_edit)
        self.read_only_hint = HintLine(self.details)
        details.addWidget(self.read_only_hint)
        self.facts = QGridLayout()
        self.facts.setHorizontalSpacing(18)
        self.facts.setVerticalSpacing(4)
        details.addLayout(self.facts)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.open_button = TextButton("Open in new tab", "primary", "tab", self.details)
        self.open_here_button = TextButton("Open here", "neutral", "open_in_browser", self.details)
        self.duplicate_button = TextButton("Duplicate…", "neutral", "content_copy", self.details)
        self.rename_button = TextButton("Rename…", "neutral", "edit", self.details)
        self.revert_button = TextButton("Revert…", "neutral", "history", self.details)
        self.restore_button = TextButton("Restore", "primary", "restore_from_trash", self.details)
        for button in (
            self.open_button,
            self.open_here_button,
            self.restore_button,
            self.duplicate_button,
            self.rename_button,
            self.revert_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        details.addLayout(actions)

        self.confirm = QFrame(self.details)
        self.confirm.setObjectName("libConfirm")
        confirm_layout = QHBoxLayout(self.confirm)
        confirm_layout.setContentsMargins(12, 8, 8, 8)
        self.confirm_text = HintLine(self.confirm)
        confirm_layout.addWidget(self.confirm_text, 1)
        self.confirm_cancel = TextButton("Cancel", "neutral", parent=self.confirm)
        self.confirm_delete = TextButton(
            "Move to Recently deleted", "danger", "delete", self.confirm
        )
        confirm_layout.addWidget(self.confirm_cancel)
        confirm_layout.addWidget(self.confirm_delete)
        details.addWidget(self.confirm)
        body.addWidget(self.details, 1)

        self.empty = _label("", "muted", self)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addLayout(body, 1)

        # wiring
        self.search.textChanged.connect(controller.set_query)
        self.search.installEventFilter(self)
        self.list.currentItemChanged.connect(self._on_current_item)
        self.list.itemDoubleClicked.connect(lambda *_: controller.open_selected(True))
        self.save_button.clicked.connect(lambda: controller.request_name("save"))
        self.open_button.clicked.connect(lambda: controller.open_selected(True))
        self.open_here_button.clicked.connect(lambda: controller.open_selected(False))
        self.duplicate_button.clicked.connect(lambda: controller.request_name("duplicate"))
        self.rename_button.clicked.connect(lambda: controller.request_name("rename"))
        self.revert_button.clicked.connect(controller.request_revert)
        self.restore_button.clicked.connect(lambda: controller.restore(None))
        self.delete_button.clicked.connect(controller.request_delete)
        self.confirm_cancel.clicked.connect(controller.cancel_delete)
        self.confirm_delete.clicked.connect(controller.confirm_delete)
        self.banner_action.clicked.connect(controller.banner_action)
        self.banner_close.clicked.connect(controller.dismiss_banner)
        self.notes_edit.editingFinished.connect(
            lambda: controller.save_notes(self.notes_edit.text())
        )
        controller.changed.connect(self.render)
        controller.preview_changed.connect(self._render_preview)
        for keys, slot in (
            ("Ctrl+F", self.search.setFocus),
            ("F2", lambda: controller.request_name("rename")),
            ("Ctrl+D", lambda: controller.request_name("duplicate")),
            ("Ctrl+S", lambda: controller.request_name("save")),
            ("Delete", controller.request_delete),
        ):
            shortcut = QShortcut(QKeySequence(keys), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(slot)
        self._rendering = False
        self._list_signature = None
        self.render()
        self._render_preview()

    def eventFilter(self, obj, event):  # pylint: disable=invalid-name
        """Let Up/Down/Enter in the search field drive the list."""
        if obj is self.search and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self.controller.move_selection(1 if event.key() == Qt.Key.Key_Down else -1)
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.controller.open_selected(True)
                return True
        return super().eventFilter(obj, event)

    def _on_current_item(self, item: QListWidgetItem | None, _previous=None) -> None:
        if self._rendering or item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if key:
            QTimer.singleShot(0, lambda: self.controller.select(key))

    def _render_preview(self) -> None:
        selected = self.controller.state.selected
        if selected and selected["kind"] == "trash":
            self.preview.set_pixmap(None, "Deleted profile. Restore it to open it.")
        else:
            self.preview.set_pixmap(self.controller.preview_for_selected(), "No preview yet")

    def render(self) -> None:
        """Rebuild the list and the details from the controller state."""
        state = self.controller.state
        tokens = ThemeTokens()
        self._render_list(state)
        self._render_header(state, tokens)
        self._render_details(state, tokens)

    def _render_list(self, state) -> None:
        signature = [tuple(v for k, v in row.items() if k != "selected") for row in state.rows]
        signature.append(state.empty_text)
        if signature == self._list_signature:
            # only the selection moved: restyle the rows instead of rebuilding them
            self._rendering = True
            for index in range(self.list.count()):
                item = self.list.item(index)
                widget = self.list.itemWidget(item)
                if isinstance(widget, _Row):
                    selected = widget.key == (state.selected or {}).get("key")
                    widget.set_selected(selected)
                    if selected:
                        self.list.setCurrentItem(item)
                        self.list.scrollToItem(item)
            self._rendering = False
            return
        self._list_signature = signature
        self._rendering = True
        self.list.clear()
        section = None
        current_item = None
        for row in state.rows:
            if row["section"] != section:
                section = row["section"]
                header = QListWidgetItem(self.list)
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                label = _label(section.upper(), "caption")
                label.setContentsMargins(8, 10 if self.list.count() > 1 else 2, 0, 2)
                header.setSizeHint(label.sizeHint())
                self.list.setItemWidget(header, label)
            item = QListWidgetItem(self.list)
            item.setData(Qt.ItemDataRole.UserRole, row["key"])
            widget = _Row(row)
            widget.pin_clicked.connect(self.controller.toggle_pin)
            widget.restore_clicked.connect(self.controller.restore)
            item.setSizeHint(QSize(0, 48))
            self.list.setItemWidget(item, widget)
            if row["selected"]:
                current_item = item
        if not state.rows:
            item = QListWidgetItem(self.list)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            label = _label(state.empty_text, "muted")
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setContentsMargins(12, 30, 12, 30)
            item.setSizeHint(QSize(0, 100))
            self.list.setItemWidget(item, label)
        if current_item is not None:
            self.list.setCurrentItem(current_item)
            self.list.scrollToItem(current_item)
        self._rendering = False

    def _render_header(self, state, tokens) -> None:
        if self.search.text() != state.query and not self.search.hasFocus():
            blocked = self.search.blockSignals(True)
            self.search.setText(state.query)
            self.search.blockSignals(blocked)
        count = state.total
        self.count_label.setText(f"{count} profile" + ("" if count == 1 else "s"))
        self.save_button.setVisible(True)

        banner = state.banner
        self.banner.setVisible(banner is not None)
        if banner is not None:
            color = tone_color(tokens, banner.tone)
            self.banner.setStyleSheet(
                f"QFrame#libBanner {{ background: {tokens.soft(color, 0.14).name()};"
                f" border: 1px solid {tokens.soft(color, 0.45).name()}; border-radius: 8px; }}"
            )
            self.banner_hint.set_hint(banner.tone, banner.text)
            self.banner_action.setVisible(bool(banner.action))
            self.banner_action.setText(banner.action)

    def _render_details(self, state, tokens) -> None:
        selected = state.selected
        self.details.setVisible(selected is not None)
        if selected is None:
            return
        is_trash = selected["kind"] == "trash"
        self.name_label.setText(selected["name"])
        status = selected["status"]
        self.status_pill.setVisible(bool(status) and not is_trash)
        if status:
            self.status_pill.set_status(
                status, tokens.primary if selected["isCurrent"] else tokens.success
            )
        if not self.notes_edit.hasFocus():
            self.notes_edit.setText(selected["notes"] or "")
        self.notes_edit.setVisible(not is_trash and not selected["readOnly"])
        if is_trash:
            self.read_only_hint.set_hint("neutral", status)
        elif selected["readOnly"]:
            self.read_only_hint.set_hint(
                "info",
                f"Read-only profile from {selected['source']}. Your changes are kept as you"
                " work; Revert brings back the original. Duplicate it to keep your own version.",
            )
        self.read_only_hint.setVisible(is_trash or selected["readOnly"])

        while self.facts.count():
            item = self.facts.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, (key, value) in enumerate(selected["facts"]):
            self.facts.addWidget(_label(key, "muted", self.details), index // 2, (index % 2) * 2)
            self.facts.addWidget(
                _label(value, "body", self.details), index // 2, (index % 2) * 2 + 1
            )
        self.facts.setColumnStretch(1, 1)
        self.facts.setColumnStretch(3, 1)

        has_tabs = state.has_tabs
        self.open_button.setVisible(not is_trash and not selected["isCurrent"])
        self.open_button.setText(
            ("Go to tab" if selected["isOpen"] else "Open in new tab") if has_tabs else "Open"
        )
        self.open_here_button.setVisible(not is_trash and has_tabs and not selected["isOpen"])
        self.restore_button.setVisible(is_trash)
        self.duplicate_button.setVisible(not is_trash)
        self.rename_button.setVisible(not is_trash and not selected["readOnly"])
        self.revert_button.setVisible(not is_trash)
        self.revert_button.setEnabled(selected["canRevert"])
        self.revert_button.setToolTip(
            "Go back to the saved layout"
            if selected["canRevert"]
            else "Nothing saved to go back to"
        )
        self.delete_button.setVisible(not is_trash)
        self.delete_button.setEnabled(selected["canDelete"])
        self.delete_button.setToolTip(selected["deleteReason"] or "Move to Recently deleted")

        pending = bool(state.pending_delete)
        self.confirm.setVisible(pending)
        if pending:
            self.confirm.setStyleSheet(
                f"QFrame#libConfirm {{ background: {tokens.soft(tokens.danger, 0.12).name()};"
                f" border: 1px solid {tokens.soft(tokens.danger, 0.5).name()};"
                " border-radius: 8px; }"
            )
            self.confirm_text.set_hint(
                "warning",
                f"Move '{state.pending_delete}' to Recently deleted? You can restore it any time.",
            )


################################################################################
# Windows and flows
################################################################################


class ProfileLibraryDialog(QDialog):
    """Non-modal window hosting :class:`ProfileLibraryWidget`."""

    def __init__(self, actions: ProfileActions, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Profile library")
        self.setModal(False)
        self.resize(1040, 640)
        self.setMinimumSize(820, 520)
        self.controller = ProfileLibraryController(actions, self)
        self.library = ProfileLibraryWidget(self.controller, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.library)
        self.controller.name_requested.connect(self._ask_name)
        self.controller.revert_requested.connect(self._ask_revert)

    def _ask_name(self, mode: str, original: str) -> None:
        actions = self.controller.actions
        form = actions.name_form(mode, original)
        preview = actions.live_preview() if mode == "save" else actions.preview(original)
        dialog = ProfileNameDialog(
            actions, mode, original, form["initial"], preview, self, form["notes"], form["pinned"]
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.controller.apply_name(
            mode, original, dialog.profile_name(), notes=dialog.notes(), pinned=dialog.pinned()
        )

    def _ask_revert(self, name: str) -> None:
        if run_revert_flow(self.controller.actions, name, self):
            self.controller.apply_revert(name)


def run_name_flow(
    actions: ProfileActions, mode: NameMode, original: str = "", parent: QWidget | None = None
) -> str | None:
    """
    Show the name dialog and run the save, rename or duplicate.

    Returns:
        str | None: The new name, or None when cancelled.
    """
    form = actions.name_form(mode, original)
    preview = actions.preview(original) if mode == "duplicate" else actions.live_preview()
    dialog = ProfileNameDialog(
        actions, mode, original, form["initial"], preview, parent, form["notes"], form["pinned"]
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    actions.apply_name(mode, original, dialog.profile_name(), dialog.notes(), dialog.pinned())
    return dialog.profile_name()


def run_revert_flow(actions: ProfileActions, name: str, parent: QWidget | None = None) -> bool:
    """Ask whether to revert *name*; returns True when confirmed (the caller reverts)."""
    current = actions.live_preview(name) or actions.preview(name)
    dialog = RevertProfileDialog(
        name,
        actions.saved_at(name),
        current,
        actions.saved_preview(name),
        is_profile_read_only(name, actions.namespace),
        parent,
    )
    return dialog.exec() == QDialog.DialogCode.Accepted
