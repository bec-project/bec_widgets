"""The *Devices* and *Config* views rendered with Qt Quick (QML).

QML twin of :mod:`devices_qwidget`: the scenes in ``qml/`` render the controllers of
:mod:`devices_core` through small backend objects.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, QUrl, Signal, Slot
from qtpy.QtWidgets import QFileDialog, QStackedWidget, QVBoxLayout, QWidget

from bec_widgets.applications.views.devices_views.devices_core import (
    DEVICE_CLASSES,
    KINDS,
    NEW_NAME_RULE,
    ON_FAILURE_LABELS,
    READOUT_HINT,
    READOUT_LABELS,
    ConfigEditor,
    DeviceBrowser,
    class_docstring,
)
from bec_widgets.applications.views.devices_views.staff_access import StaffAccess
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.quick import DictListModel, create_quick_widget, release_quick_widget
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_qml import (
    QML_FILE as POSITIONER_QML,
)
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_qml import (
    PositionerBackend,
    PositionerBoxQML,
)

QML_DIR = Path(__file__).parent / "qml"
CONFIG_ROLES = [
    "name",
    "deviceClass",
    "readout",
    "readoutWas",
    "on",
    "tags",
    "change",
    "changeLabel",
    "statusText",
    "statusTone",
    "statusIcon",
    "selected",
]
DEVICE_ROLES = ["name", "what", "kind", "valueText", "selected"]
SIGNAL_ROLES = ["key", "section", "settable", "doc", "valueText", "statusText", "statusTone"]


# ----------------------------------------------------------------------------------- Devices view
class _SceneMotor(PositionerBoxQML):
    """Positioner box whose card is drawn inside another QML scene instead of its own view."""

    def _init_view(self) -> None:
        self.backend = PositionerBackend(self)
        self.view = None

    def apply_theme(self, theme: str):  # pylint: disable=unused-argument
        return

    def cleanup(self):
        super(PositionerBoxQML, self).cleanup()  # pylint: disable=bad-super-call


class DevicesBackend(QObject):
    """Bridge between :class:`DeviceBrowser` and ``DevicesView.qml``."""

    changed = Signal()
    values_changed = Signal()
    spark_changed = Signal()
    motor_changed = Signal()

    def __init__(self, browser: DeviceBrowser, parent: QObject):
        super().__init__(parent)
        self.browser = browser
        self._rows = DictListModel(DEVICE_ROLES, self)
        self._detail: dict = {}
        self._settings = DictListModel(SIGNAL_ROLES, self)
        self._readings = DictListModel(SIGNAL_ROLES, self)
        self._signal_device: str | None = None
        self._motor = None
        browser.changed.connect(self.refresh)
        browser.values_changed.connect(self._refresh_values)
        browser.spark_changed.connect(self.spark_changed)

    def refresh(self) -> None:
        """Re-read rows and the detail panel."""
        rows = self.browser.rows()
        if self.browser.selected is None and rows:
            self.browser.selected = rows[0]["name"]
            rows = self.browser.rows()
        self._rows.set_items(rows)
        self._detail = self.browser.detail()
        self._refresh_signals()
        self.changed.emit()
        self.values_changed.emit()

    def _refresh_values(self) -> None:
        self._rows.set_items(self.browser.rows())
        self._detail = self.browser.detail()
        self._refresh_signals()
        self.values_changed.emit()

    def _refresh_signals(self) -> None:
        rows = self.browser.signal_rows()
        if self._signal_device != self.browser.selected:
            # New device: drop the old delegates so typed text does not carry over.
            self._signal_device = self.browser.selected
            self._settings.set_items([])
            self._readings.set_items([])
        self._settings.set_items([r for r in rows if r["section"] == "setting"])
        self._readings.set_items([r for r in rows if r["section"] == "reading"])

    def set_motor(self, motor) -> None:
        """Positioner box shown for motors."""
        self._motor = motor
        self.motor_changed.emit()

    # pylint: disable=invalid-name, missing-function-docstring
    @Slot(str)
    def select(self, name: str) -> None:
        self.browser.select(name)

    @Slot(str)
    def setKind(self, kind: str) -> None:
        self.browser.set_kind(kind)

    @Slot(str)
    def setQuery(self, text: str) -> None:
        self.browser.set_query(text)

    @Slot()
    def openInWorkspace(self) -> None:
        self.browser.request_open()

    @Slot(str, str)
    def setSignal(self, key: str, text: str) -> None:
        self.browser.set_signal(key, text)

    rows = Property(QObject, lambda self: self._rows, constant=True)
    detail = Property("QVariantMap", lambda self: self._detail, notify=values_changed)
    settings = Property(QObject, lambda self: self._settings, constant=True)
    readings = Property(QObject, lambda self: self._readings, constant=True)
    detailName = Property(str, lambda self: self._detail.get("name", ""), notify=changed)
    kind = Property(str, lambda self: self.browser.kind, notify=changed)
    kinds = Property(
        "QVariantList",
        lambda self: [
            {"key": k, "label": f"{l}  {self.browser.kind_counts().get(k, 0)}"} for k, l in KINDS
        ],
        notify=changed,
    )
    shownText = Property(str, lambda self: self.browser.shown_text(), notify=changed)
    selectedIndex = Property(
        int,
        lambda self: next((i for i, r in enumerate(self._rows.items) if r["selected"]), -1),
        notify=changed,
    )
    spark = Property("QVariantList", lambda self: self.browser.spark_points(), notify=spark_changed)
    motor = Property(
        QObject, lambda self: self._motor.backend if self._motor else None, notify=motor_changed
    )
    motorSource = Property(
        QUrl, lambda self: QUrl.fromLocalFile(str(POSITIONER_QML)), constant=True
    )


class DevicesViewQML(BECWidget, QWidget):
    """Devices for everyone: find a device, see its live value and move it (QML version)."""

    RPC = False
    PLUGIN = False

    def __init__(self, parent=None, client=None, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self.get_bec_shortcuts()
        self.browser = DeviceBrowser(self.client, self.bec_dispatcher, self)
        self.open_in_workspace = self.browser.open_in_workspace
        self.backend = DevicesBackend(self.browser, self)
        self._motor = None
        self.browser.changed.connect(self._sync_motor)
        self.backend.refresh()
        self._sync_motor()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(
            self, QML_DIR / "DevicesView.qml", {"backend": self.backend}
        )
        lay.addWidget(self.view)

    def _sync_motor(self) -> None:
        detail = self.browser.detail()
        if detail.get("kind") != "positioner":
            return
        name = detail["name"]
        if self._motor is None:
            self._motor = _SceneMotor(parent=self, device=name, client=self.client)
            self._motor.hide_device_selection = True
            self._motor.hide()
            self.backend.set_motor(self._motor)
        elif self._motor.device != name:
            self._motor.set_positioner(name)

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        if getattr(self, "view", None) is not None:
            self.view.setClearColor(self.palette().window().color())

    def cleanup(self):
        release_quick_widget(self.view)
        self.browser.cleanup()
        if self._motor is not None:
            self._motor.close()
            self._motor.deleteLater()
        super().cleanup()


# ------------------------------------------------------------------------------------ Config view
class ConfigBackend(QObject):
    """Bridge between :class:`ConfigEditor` and ``DeviceConfigView.qml``."""

    changed = Signal()
    detail_changed = Signal()
    facets_changed = Signal()
    toast = Signal(str, str, bool)
    tab_changed = Signal()

    def __init__(self, editor: ConfigEditor, owner: QWidget):
        super().__init__(owner)
        self.editor = editor
        self._owner = owner
        self._rows = DictListModel(CONFIG_ROLES, self)
        self._detail: dict = {}
        self._facets: list = []
        self._tab = "form"
        editor.changed.connect(self.refresh)
        editor.toast.connect(self.toast)
        self._staff = ""

    def refresh(self) -> None:
        """Re-read everything the scene shows."""
        self._rows.set_items(self.editor.rows())
        detail = self.editor.detail()
        if detail != self._detail:
            self._detail = detail
            self.detail_changed.emit()
        facets = self.editor.facet_sections()
        if facets != self._facets:
            self._facets = facets
            self.facets_changed.emit()
        self.changed.emit()

    # pylint: disable=invalid-name, missing-function-docstring
    @Slot(str)
    def select(self, name: str) -> None:
        self.editor.select(name)

    @Slot(int)
    def selectRelative(self, step: int) -> None:
        names = [r["name"] for r in self._rows.items]
        if not names:
            return
        index = names.index(self.editor.selected) if self.editor.selected in names else -1
        self.editor.select(names[max(0, min(len(names) - 1, index + step))])

    @Slot(str)
    def setQuery(self, text: str) -> None:
        self.editor.set_query(text)

    @Slot(str, str, bool)
    def toggleFacet(self, key: str, value: str, checked: bool) -> None:
        self.editor.toggle_facet(key, value, checked)

    @Slot()
    def clearFilters(self) -> None:
        self.editor.clear_filters()

    @Slot(str, str, "QVariant")
    def setField(self, name: str, key: str, value) -> None:
        self.editor.set_field(name, key, value)

    @Slot(str, str, str)
    def setConfigValue(self, name: str, key: str, text: str) -> None:
        self.editor.set_config_value(name, key, text)

    @Slot(str, str)
    def addTag(self, name: str, tag: str) -> None:
        self.editor.add_tag(name, tag)

    @Slot(str, str)
    def removeTag(self, name: str, tag: str) -> None:
        self.editor.remove_tag(name, tag)

    @Slot(str, result=str)
    def validateNewName(self, name: str) -> str:
        return self.editor.validate_new_name(name)

    @Slot(str, str, str, result=str)
    def addDevice(self, name: str, device_class: str, prefix: str) -> str:
        return self.editor.add_device(name, device_class, prefix)

    @Slot()
    def remove(self) -> None:
        self.editor.remove()

    @Slot()
    def revert(self) -> None:
        self.editor.revert()

    @Slot()
    def undo(self) -> None:
        self.editor.undo()

    @Slot()
    def test(self) -> None:
        self.editor.test()

    @Slot()
    def testAll(self) -> None:
        self.editor.test_all()

    @Slot()
    def loadSession(self) -> None:
        self.editor.load_session()

    @Slot()
    def openFile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._owner, "Open device config", "", "YAML (*.yaml *.yml)"
        )
        if path:
            self.editor.open_file(path)

    @Slot()
    def saveFile(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self._owner, "Save device config", "", "YAML (*.yaml)"
        )
        if path:
            self.editor.save_file(path)

    @Slot(result=bool)
    def apply(self) -> bool:
        return self.editor.apply()

    @Slot(str, result=str)
    def clearSession(self, text: str) -> str:
        return self.editor.clear_session(text)

    @Slot(str)
    def setTab(self, tab: str) -> None:
        if tab != self._tab:
            self._tab = tab
            self.tab_changed.emit()

    @Slot(str, result=str)
    def docs(self, device_class: str) -> str:
        return class_docstring(device_class)

    rows = Property(QObject, lambda self: self._rows, constant=True)
    bar = Property("QVariantMap", lambda self: self.editor.bar_state(), notify=changed)
    staff_changed = Signal()
    sign_out_requested = Signal()
    staffUser = Property(str, lambda self: self._staff, notify=staff_changed)

    def set_staff(self, user: str) -> None:
        """Who is signed in through BEC Atlas ("" when locked)."""
        self._staff = user
        self.staff_changed.emit()

    @Slot()
    def signOut(self) -> None:  # pylint: disable=invalid-name
        self.sign_out_requested.emit()

    detail = Property("QVariantMap", lambda self: self._detail, notify=detail_changed)
    facets = Property("QVariantList", lambda self: self._facets, notify=facets_changed)
    problems = Property("QVariantList", lambda self: self.editor.problems(), notify=changed)
    problemCount = Property(int, lambda self: self.editor.problem_counts()[0], notify=changed)
    uncheckedCount = Property(int, lambda self: self.editor.problem_counts()[1], notify=changed)
    selectedIndex = Property(
        int,
        lambda self: next((i for i, r in enumerate(self._rows.items) if r["selected"]), -1),
        notify=changed,
    )
    showingText = Property(
        str,
        lambda self: f"Showing {self._rows.rowCount()} of {len(self.editor.work)} devices",
        notify=changed,
    )
    filtersActive = Property(bool, lambda self: self.editor.filters_active(), notify=changed)
    review = Property("QVariantMap", lambda self: self.editor.review(), notify=changed)
    applying = Property(bool, lambda self: self.editor.applying, notify=changed)
    applyRows = Property("QVariantList", lambda self: self.editor.apply_rows, notify=changed)
    applySummary = Property(str, lambda self: self.editor.apply_summary, notify=changed)
    canApply = Property(bool, lambda self: self.editor.can_apply(), notify=changed)
    sessionCount = Property(int, lambda self: len(self.editor.session), notify=changed)
    workCount = Property(int, lambda self: len(self.editor.work), notify=changed)
    tab = Property(str, lambda self: self._tab, notify=tab_changed)
    readoutKeys = Property("QStringList", lambda self: list(READOUT_LABELS), constant=True)
    readoutLabels = Property(
        "QStringList", lambda self: list(READOUT_LABELS.values()), constant=True
    )
    readoutHint = Property(str, lambda self: READOUT_HINT, constant=True)
    failureKeys = Property("QStringList", lambda self: list(ON_FAILURE_LABELS), constant=True)
    failureLabels = Property(
        "QStringList",
        lambda self: [f"{v} ({k})" for k, v in ON_FAILURE_LABELS.items()],
        constant=True,
    )
    deviceClasses = Property("QStringList", lambda self: DEVICE_CLASSES, constant=True)
    nameRule = Property(str, lambda self: NEW_NAME_RULE, constant=True)


class DeviceConfigViewQML(BECWidget, QWidget):
    """Config for staff: edit a copy of the session config, review, then apply (QML version)."""

    RPC = False
    PLUGIN = False
    sign_out_requested = Signal()

    def __init__(self, parent=None, client=None, load_session: bool = True, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self.get_bec_shortcuts()
        self.editor = ConfigEditor(self.client, self.bec_dispatcher, self)
        self.backend = ConfigBackend(self.editor, self)
        if load_session:
            self.editor.load_session()
        self.backend.refresh()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(
            self, QML_DIR / "DeviceConfigView.qml", {"backend": self.backend}
        )
        lay.addWidget(self.view)
        self.backend.sign_out_requested.connect(self.sign_out_requested)

    def set_staff(self, user: str) -> None:
        """Show who is signed in (BEC Atlas) next to Review changes."""
        self.backend.set_staff(user)

    def open_review(self):
        """Open the review sheet (also reachable from the session bar)."""
        self.view.rootObject().openReview()
        return self.view.rootObject()

    def open_add_device(self):
        """Open the add-device sheet."""
        self.view.rootObject().openAdd()
        return self.view.rootObject()

    def open_clear_session(self):
        """Open the danger-zone sheet."""
        self.view.rootObject().openClear()
        return self.view.rootObject()

    def close_sheet(self) -> None:
        """Close whichever sheet is open."""
        self.view.rootObject().closeSheets()

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        if getattr(self, "view", None) is not None:
            self.view.setClearColor(self.palette().window().color())

    def cleanup(self):
        release_quick_widget(self.view)
        self.editor.cleanup()
        super().cleanup()


# ------------------------------------------------------------------------------------ staff gate
class StaffBackend(QObject):
    """Bridge between :class:`StaffAccess` and ``LockScreen.qml``."""

    changed = Signal()

    def __init__(self, access: StaffAccess, parent: QObject):
        super().__init__(parent)
        self.access = access
        access.changed.connect(self.changed)

    # pylint: disable=invalid-name, missing-function-docstring
    @Slot(str, str)
    def signIn(self, user: str, password: str) -> None:
        self.access.sign_in(user, password)

    busy = Property(bool, lambda self: self.access.busy, notify=changed)
    error = Property(str, lambda self: self.access.error, notify=changed)
    deployment = Property(str, lambda self: self.access.deployment, notify=changed)


class DeviceConfigGateQML(BECWidget, QWidget):
    """Device Config behind the BEC Atlas staff sign-in (QML version).

    The Config view is built on the first sign-in and locks again when the view is left.
    """

    RPC = False
    PLUGIN = False

    def __init__(self, parent=None, client=None, **kwargs):
        super().__init__(parent=parent, client=client, **kwargs)
        self.get_bec_shortcuts()
        self.access = StaffAccess(self.bec_dispatcher, self)
        self.staff_backend = StaffBackend(self.access, self)
        self.config: DeviceConfigViewQML | None = None
        self.stack = QStackedWidget(self)
        self.lock_view = create_quick_widget(
            self, QML_DIR / "LockScreen.qml", {"backend": self.staff_backend}
        )
        self.stack.addWidget(self.lock_view)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self.access.changed.connect(self._sync)

    def _sync(self) -> None:
        if self.access.unlocked and self.config is None:
            self.config = DeviceConfigViewQML(parent=self, client=self.client)
            self.config.sign_out_requested.connect(self.access.sign_out)
            self.stack.addWidget(self.config)
        if self.config is not None:
            self.config.set_staff(self.access.user)
        self.stack.setCurrentWidget(
            self.config if self.access.unlocked and self.config else self.lock_view
        )

    def hideEvent(self, event):  # pylint: disable=invalid-name
        super().hideEvent(event)
        if not event.spontaneous():
            self.access.sign_out()

    def cleanup(self):
        release_quick_widget(self.lock_view)
        self.access.cleanup()
        if self.config is not None:
            self.config.close()
            self.config.deleteLater()
        super().cleanup()
