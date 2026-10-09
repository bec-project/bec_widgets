"""Scan control rendered in QML, hosted in a ``QQuickWidget``."""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Property, QObject, QUrl, Signal, Slot
from qtpy.QtWidgets import QApplication, QVBoxLayout

from bec_widgets.widgets.control.scan_control.modern.base import ModernScanControlBase
from bec_widgets.widgets.control.scan_control.modern.qml_support import (
    QmlTheme,
    create_quick_widget,
)

QML_DIR = Path(__file__).parent / "qml"


class ScanControlBridge(QObject):  # pylint: disable=too-many-public-methods
    """Exposes the scan control state to QML as plain lists and maps.

    The accessors below are QML properties and slots named after their QML use.
    """

    # pylint: disable=missing-function-docstring

    structureChanged = Signal()
    valuesChanged = Signal()
    statusChanged = Signal()
    metadataStructureChanged = Signal()
    metadataChanged = Signal()
    notice = Signal(str)

    def __init__(self, control: ModernScanControlBase):
        super().__init__(control)
        self._c = control
        control.form.rebuilt.connect(self.structureChanged)
        control.form.values_changed.connect(self.valuesChanged)
        control.status_changed.connect(self.statusChanged)
        control.metadata.rebuilt.connect(self.metadataStructureChanged)
        control.metadata.values_changed.connect(self.metadataChanged)
        control.notice.connect(self.notice)

    # ------------------------------------------------------------------ scan list

    @Property("QStringList", notify=statusChanged)
    def scans(self):
        return self._c.visible_scans

    @Property(str, notify=structureChanged)
    def currentScan(self):  # pylint: disable=invalid-name
        return self._c.current_scan

    @Property(str, notify=structureChanged)
    def summary(self):
        return self._c.form.spec.summary

    @Slot(str)
    def selectScan(self, name: str):  # pylint: disable=invalid-name
        self._c.set_current_scan(name)

    @Slot(str, result=bool)
    def isValidScan(self, name: str) -> bool:  # pylint: disable=invalid-name
        return self._c.is_valid_scan(name)

    @Slot()
    def showInfo(self):  # pylint: disable=invalid-name
        self._c.show_selected_scan_info()

    @Slot()
    def showFilter(self):  # pylint: disable=invalid-name
        self._c.show_scan_selector_settings()

    # ------------------------------------------------------------------ arguments

    @Property(str, notify=structureChanged)
    def argTitle(self):  # pylint: disable=invalid-name
        return self._c.form.spec.arg_title

    @Property("QVariantList", notify=structureChanged)
    def argFields(self):  # pylint: disable=invalid-name
        return [f.to_dict() for f in self._c.form.spec.arg_fields]

    @Property(int, notify=structureChanged)
    def rowCount(self):  # pylint: disable=invalid-name
        return len(self._c.form.arg_rows)

    @Property("QVariantList", notify=valuesChanged)
    def argRows(self):  # pylint: disable=invalid-name
        form = self._c.form
        rows = []
        for index, row in enumerate(form.arg_rows):
            rows.append(
                {
                    "values": dict(row),
                    "units": {f.name: form.units_for(f, index) for f in form.spec.arg_fields},
                    "errors": {
                        f.name: form.field_error(f, row.get(f.name)) for f in form.spec.arg_fields
                    },
                }
            )
        return rows

    @Property(bool, notify=valuesChanged)
    def canAddRow(self):  # pylint: disable=invalid-name
        return self._c.form.can_add_row()

    @Property(bool, notify=valuesChanged)
    def canRemoveRow(self):  # pylint: disable=invalid-name
        return self._c.form.can_remove_row()

    @Slot(int, str, "QVariant")
    def setArg(self, row: int, name: str, value):  # pylint: disable=invalid-name
        self._c.form.set_arg_value(row, name, value)

    @Slot()
    def addRow(self):  # pylint: disable=invalid-name
        self._c.form.add_row()

    @Slot(int)
    def removeRow(self, row: int):  # pylint: disable=invalid-name
        self._c.form.remove_row(row)

    # ------------------------------------------------------------------ keyword groups

    @Property("QVariantList", notify=structureChanged)
    def groups(self):
        return [
            {"name": g.name, "fields": [f.to_dict() for f in g.fields]}
            for g in self._c.form.spec.groups
        ]

    @Property("QVariantMap", notify=valuesChanged)
    def kwargs(self):
        form = self._c.form
        return {
            "values": dict(form.kwargs),
            "units": {f.name: form.units_for(f) for f in form.spec.kwarg_fields},
            "errors": {
                f.name: form.field_error(f, form.kwargs.get(f.name)) for f in form.spec.kwarg_fields
            },
        }

    @Slot(str, "QVariant")
    def setKwarg(self, name: str, value):  # pylint: disable=invalid-name
        self._c.form.set_kwarg_value(name, value)

    @Property("QStringList", notify=statusChanged)
    def devices(self):
        return self._c.form.device_names

    @Slot()
    def refreshDevices(self):  # pylint: disable=invalid-name
        self._c.refresh_devices()
        self.statusChanged.emit()

    # ------------------------------------------------------------------ metadata

    @Property("QVariantList", notify=metadataStructureChanged)
    def metaFields(self):  # pylint: disable=invalid-name
        return [f.to_dict(self._c.metadata.scan_name) for f in self._c.metadata.fields]

    @Property("QVariantMap", notify=metadataChanged)
    def metaValues(self):  # pylint: disable=invalid-name
        return {k: ("" if v is None else v) for k, v in self._c.metadata.values.items()}

    @Property("QVariantMap", notify=metadataChanged)
    def metaErrors(self):  # pylint: disable=invalid-name
        return dict(self._c.metadata.errors)

    @Property("QVariantList", notify=metadataChanged)
    def metaExtras(self):  # pylint: disable=invalid-name
        return [list(pair) for pair in self._c.metadata.extras]

    @Property(str, notify=metadataChanged)
    def metaSummary(self):  # pylint: disable=invalid-name
        return self._c.metadata.summary()

    @Slot(str, "QVariant")
    def setMeta(self, name: str, value):  # pylint: disable=invalid-name
        self._c.metadata.set_value(name, value)

    @Slot("QVariantList")
    def setExtras(self, extras):  # pylint: disable=invalid-name
        self._c.metadata.set_extras([list(pair) for pair in extras])

    # ------------------------------------------------------------------ status and actions

    @Property("QStringList", notify=statusChanged)
    def problems(self):
        return self._c.problems()

    @Property(bool, notify=statusChanged)
    def restoring(self):
        return self._c.is_restoring

    @Property(bool, notify=statusChanged)
    def stopArmed(self):  # pylint: disable=invalid-name
        return self._c.stop_armed

    @Property("QVariantMap", notify=statusChanged)
    def options(self):
        return dict(self._c._options)  # pylint: disable=protected-access

    @Slot()
    def start(self):
        self._c.run_scan()

    @Slot()
    def stop(self):
        self._c.stop_scan()

    @Slot()
    def restoreLast(self):  # pylint: disable=invalid-name
        self._c.request_last_executed_scan_parameters()


class ScanControlQml(ModernScanControlBase):
    """Widget to submit new scans to the queue, drawn in QML."""

    ICON_NAME = "tune"

    def _build_view(self) -> None:
        self.bridge = ScanControlBridge(self)
        self.qml_theme = QmlTheme(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(
            self, QML_DIR / "ScanControl.qml", {"sc": self.bridge, "theme": self.qml_theme}
        )
        layout.addWidget(self.view)
        self.setMinimumSize(360, 420)

    def cleanup(self):
        """Unload the QML scene before the objects it binds to are deleted."""
        self.view.setSource(QUrl())
        super().cleanup()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    widget = ScanControlQml()
    widget.resize(520, 760)
    widget.show()
    sys.exit(app.exec())
