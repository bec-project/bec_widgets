"""Profile library, name dialog and revert dialog rendered with Qt Quick (QML).

Same UX as :mod:`profile_qwidget`; state and rules come from :mod:`.common`.
"""

# QML properties below read the backend's private state through lambdas.
# pylint: disable=protected-access

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, QSize, Qt, Signal, Slot
from qtpy.QtGui import QPixmap
from qtpy.QtQuick import QQuickImageProvider
from qtpy.QtWidgets import QDialog, QVBoxLayout, QWidget

from bec_widgets.utils.quick import (
    DictListModel,
    create_quick_widget,
    quick_engine,
    release_quick_widget,
)
from bec_widgets.widgets.containers.dock_area.profile_utils import is_profile_read_only
from bec_widgets.widgets.containers.dock_area.profile_ux.common import (
    ROW_KEYS,
    NameMode,
    ProfileActions,
    ProfileLibraryController,
    absolute_time,
    relative_time,
)

QML_DIR = Path(__file__).parent / "qml"
PROVIDER_ID = "bwprofile"
TITLES = {"save": "Save profile", "rename": "Rename profile", "duplicate": "Duplicate profile"}


class PreviewProvider(QQuickImageProvider):
    """Serve profile screenshots to QML as ``image://bwprofile/<key>?<revision>``."""

    def __init__(self):
        super().__init__(QQuickImageProvider.ImageType.Pixmap)
        self._pixmaps: dict[str, QPixmap] = {}
        self._revision = 0

    def publish(self, key: str, pixmap: QPixmap | None) -> str:
        """Store *pixmap* under *key* and return its URL, or "" when there is none."""
        if pixmap is None or pixmap.isNull():
            self._pixmaps.pop(key, None)
            return ""
        self._revision += 1
        self._pixmaps[key] = pixmap
        return f"image://{PROVIDER_ID}/{key}?{self._revision}"

    def requestPixmap(
        self, image_id: str, size: QSize, requested: QSize
    ) -> QPixmap:  # pylint: disable=invalid-name
        pixmap = self._pixmaps.get(image_id.partition("?")[0], QPixmap())
        if requested.isValid() and not pixmap.isNull() and requested.width() > 0:
            pixmap = pixmap.scaled(
                requested,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        if size is not None:
            size.setWidth(pixmap.width())
            size.setHeight(pixmap.height())
        return pixmap


_PROVIDER: PreviewProvider | None = None


def preview_provider() -> PreviewProvider:
    """Return the preview image provider, registering it with the shared QML engine."""
    global _PROVIDER  # pylint: disable=global-statement
    engine = quick_engine()
    if _PROVIDER is None or engine.imageProvider(PROVIDER_ID) is None:
        _PROVIDER = PreviewProvider()
        engine.addImageProvider(PROVIDER_ID, _PROVIDER)
    return _PROVIDER


class _QuickDialog(QDialog):
    """QDialog showing one QML file with a backend object."""

    def __init__(self, qml_file: str, backend: QObject, parent: QWidget | None, title: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.backend = backend
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(self, QML_DIR / qml_file, {"backend": backend})
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.view)
        self.view.setFocus()

    def done(self, result: int) -> None:  # pylint: disable=invalid-name
        """Unload the scene before the backend goes away."""
        release_quick_widget(self.view)
        super().done(result)


################################################################################
# Name dialog
################################################################################


class NameBackend(QObject):
    """Backend of ``ProfileNameDialog.qml``."""

    changed = Signal()
    accepted = Signal()
    rejected = Signal()

    def __init__(
        self,
        actions: ProfileActions,
        mode: NameMode,
        original: str,
        form: dict,
        preview: QPixmap | None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.actions = actions
        self._mode = mode
        self._original = original
        self._name = form["initial"]
        self._notes = form["notes"]
        self._pinned = form["pinned"]
        self._preview = preview_provider().publish(f"name-{id(self)}", preview)
        self._check = actions.check(self._name, mode, original or None).as_dict()

    # pylint: disable=invalid-name,missing-function-docstring
    @Slot(str)
    def setName(self, text: str) -> None:
        self._name = text
        self._check = self.actions.check(text, self._mode, self._original or None).as_dict()
        self.changed.emit()

    @Slot(str)
    def setNotes(self, text: str) -> None:
        self._notes = text

    @Slot(bool)
    def setPinned(self, value: bool) -> None:
        self._pinned = value

    @Slot()
    def confirm(self) -> None:
        if self._check["ok"]:
            self.accepted.emit()

    @Slot()
    def cancel(self) -> None:
        self.rejected.emit()

    def name(self) -> str:
        return self._name.strip()

    def notes(self) -> str:
        return self._notes.strip()

    def pinned(self) -> bool:
        return bool(self._pinned)

    mode = Property(str, lambda self: self._mode, constant=True)
    heading = Property(
        str,
        lambda self: (
            TITLES[self._mode]
            if self._mode == "save"
            else f"{TITLES[self._mode]} '{self._original}'"
        ),
        constant=True,
    )
    initialName = Property(str, lambda self: self._name, constant=True)
    initialNotes = Property(str, lambda self: self._notes, constant=True)
    initialPinned = Property(bool, lambda self: bool(self._pinned), constant=True)
    previewUrl = Property(str, lambda self: self._preview, constant=True)
    check = Property("QVariantMap", lambda self: self._check, notify=changed)


class ProfileNameDialog(_QuickDialog):
    """QML version of the save, rename and duplicate dialog."""

    def __init__(
        self,
        actions: ProfileActions,
        mode: NameMode,
        original: str = "",
        form: dict | None = None,
        preview: QPixmap | None = None,
        parent: QWidget | None = None,
    ):
        form = form or actions.name_form(mode, original)
        backend = NameBackend(actions, mode, original, form, preview)
        super().__init__("ProfileNameDialog.qml", backend, parent, TITLES[mode])
        backend.setParent(self)
        self.setModal(True)
        self.resize(620, 380 if mode == "save" else 270)
        backend.accepted.connect(self.accept)
        backend.rejected.connect(self.reject)

    def profile_name(self) -> str:
        """The entered name."""
        return self.backend.name()

    def notes(self) -> str:
        """The entered description."""
        return self.backend.notes()

    def pinned(self) -> bool:
        """Whether the profile shows in the toolbar list."""
        return self.backend.pinned()


################################################################################
# Revert dialog
################################################################################


class RevertBackend(QObject):
    """Backend of ``RevertProfileDialog.qml``."""

    accepted = Signal()
    rejected = Signal()

    def __init__(self, name: str, saved_at: str, current, saved, read_only: bool, parent=None):
        super().__init__(parent)
        provider = preview_provider()
        self._name = name
        when = relative_time(saved_at)
        what = "its original layout" if read_only else "the layout saved"
        text = f"Changes made since then are discarded. You go back to {what}"
        self._text = text + (f" {when}." if when and not read_only else ".")
        self._saved_caption = absolute_time(saved_at) or "Saved layout"
        self._now = provider.publish(f"revert-now-{id(self)}", current)
        self._saved = provider.publish(f"revert-saved-{id(self)}", saved)

    # pylint: disable=invalid-name,missing-function-docstring
    @Slot()
    def confirm(self) -> None:
        self.accepted.emit()

    @Slot()
    def cancel(self) -> None:
        self.rejected.emit()

    name = Property(str, lambda self: self._name, constant=True)
    text = Property(str, lambda self: self._text, constant=True)
    savedCaption = Property(str, lambda self: self._saved_caption, constant=True)
    nowUrl = Property(str, lambda self: self._now, constant=True)
    savedUrl = Property(str, lambda self: self._saved, constant=True)


class RevertProfileDialog(_QuickDialog):
    """QML version of the revert confirmation."""

    def __init__(self, name, saved_at, current, saved, read_only=False, parent=None):
        backend = RevertBackend(name, saved_at, current, saved, read_only)
        super().__init__("RevertProfileDialog.qml", backend, parent, "Revert to saved layout")
        backend.setParent(self)
        self.setModal(True)
        self.resize(720, 400)
        backend.accepted.connect(self.accept)
        backend.rejected.connect(self.reject)


################################################################################
# Library
################################################################################


class LibraryBackend(QObject):
    """Bridge between :class:`ProfileLibraryController` and ``ProfileLibrary.qml``."""

    changed = Signal()
    previewChanged = Signal()

    def __init__(self, controller: ProfileLibraryController, parent: QObject | None = None):
        super().__init__(parent)
        self.controller = controller
        self._rows = DictListModel(ROW_KEYS, self)
        self._state: dict = {}
        self._preview = ""
        controller.changed.connect(self._sync)
        controller.preview_changed.connect(self._sync_preview)
        self._sync()
        self._sync_preview()

    def _sync(self) -> None:
        state = self.controller.state
        self._rows.set_items(state.rows)
        selected = dict(state.selected or {})
        if selected:
            selected["facts"] = [{"label": k, "value": v} for k, v in selected["facts"]]
        self._state = {
            "selected": selected,
            "query": state.query,
            "banner": state.banner.as_dict() if state.banner else {},
            "pendingDelete": state.pending_delete,
            "emptyText": state.empty_text,
            "hasTabs": state.has_tabs,
            "total": state.total,
        }
        self.changed.emit()

    def _sync_preview(self) -> None:
        self._preview = preview_provider().publish(
            f"library-{id(self)}", self.controller.preview_for_selected()
        )
        self.previewChanged.emit()

    # pylint: disable=invalid-name,missing-function-docstring
    @Slot(str)
    def select(self, key: str) -> None:
        self.controller.select(key)

    @Slot(int)
    def moveSelection(self, step: int) -> None:
        self.controller.move_selection(step)

    @Slot(str)
    def setQuery(self, text: str) -> None:
        self.controller.set_query(text)

    @Slot(bool)
    def openSelected(self, new_tab: bool) -> None:
        self.controller.open_selected(new_tab)

    @Slot(str)
    def togglePin(self, key: str) -> None:
        self.controller.toggle_pin(key)

    @Slot(str)
    def saveNotes(self, text: str) -> None:
        self.controller.save_notes(text)

    @Slot(str)
    def requestName(self, mode: str) -> None:
        self.controller.request_name(mode)

    @Slot()
    def requestRevert(self) -> None:
        self.controller.request_revert()

    @Slot()
    def requestDelete(self) -> None:
        self.controller.request_delete()

    @Slot()
    def cancelDelete(self) -> None:
        self.controller.cancel_delete()

    @Slot()
    def confirmDelete(self) -> None:
        self.controller.confirm_delete()

    @Slot(str)
    def restore(self, token: str) -> None:
        self.controller.restore(token or None)

    @Slot()
    def bannerAction(self) -> None:
        self.controller.banner_action()

    @Slot()
    def dismissBanner(self) -> None:
        self.controller.dismiss_banner()

    rows = Property(QObject, lambda self: self._rows, constant=True)
    state = Property("QVariantMap", lambda self: self._state, notify=changed)
    previewUrl = Property(str, lambda self: self._preview, notify=previewChanged)


class ProfileLibraryDialog(QDialog):
    """Non-modal window hosting ``ProfileLibrary.qml``."""

    def __init__(self, actions: ProfileActions, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Profile library")
        self.setModal(False)
        self.resize(1040, 640)
        self.setMinimumSize(820, 520)
        self.controller = ProfileLibraryController(actions, self)
        self.backend = LibraryBackend(self.controller, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(
            self, QML_DIR / "ProfileLibrary.qml", {"backend": self.backend}
        )
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout.addWidget(self.view)
        self.view.setFocus()
        self.controller.name_requested.connect(self._ask_name)
        self.controller.revert_requested.connect(self._ask_revert)

    def done(self, result: int) -> None:  # pylint: disable=invalid-name
        """Unload the scene before the backend goes away."""
        release_quick_widget(self.view)
        super().done(result)

    def _ask_name(self, mode: str, original: str) -> None:
        actions = self.controller.actions
        preview = actions.live_preview() if mode == "save" else actions.preview(original)
        dialog = ProfileNameDialog(actions, mode, original, None, preview, self)
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
    Show the QML name dialog and run the save, rename or duplicate.

    Returns:
        str | None: The new name, or None when cancelled.
    """
    preview = actions.preview(original) if mode == "duplicate" else actions.live_preview()
    dialog = ProfileNameDialog(actions, mode, original, None, preview, parent)
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
