"""QML version of the redesigned curve settings dialog.

Shows :class:`CurveDialogModel` through ``qml/CurveDialog.qml``. Device and signal fields are
drawn in QML; clicking one opens the QML popup of a hidden :class:`DevicePickerQML` or
:class:`SignalPickerQML`, anchored to the field, so search, grouping and live values are the same
as everywhere else the pickers are used.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Property, QObject, QSize, Signal, Slot
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QColorDialog, QVBoxLayout, QWidget

from bec_widgets.utils.colors import Colors
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.quick import create_quick_widget, release_quick_widget
from bec_widgets.utils.settings_dialog import SettingWidget
from bec_widgets.widgets.control.device_input.picker.picker_qml import (
    DevicePickerQML,
    SignalPickerQML,
)
from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_common import (
    open_picker_at,
    select_device,
    select_signal,
    signal_obj_name,
)
from bec_widgets.widgets.plots.waveform.settings.curve_dialog.curve_dialog_model import (
    PEN_STYLE_LABELS,
    PEN_STYLES,
    SYMBOL_LABELS,
    SYMBOLS,
    X_MODE_HELP,
    X_MODE_LABELS,
    X_MODES,
    CurveDialogModel,
    _pretty_model,
    color_hex,
)

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.plots.waveform.waveform import Waveform

QML_FILE = Path(__file__).parent / "qml" / "CurveDialog.qml"


class CurveDialogBackend(QObject):
    """Exposes :class:`CurveDialogModel` to QML as plain lists and maps."""

    rowsChanged = Signal()
    selectedChanged = Signal()
    xAxisChanged = Signal()
    paletteChanged = Signal()
    pickerRequested = Signal(str, float, float, float, float)

    def __init__(self, model: CurveDialogModel, parent: QObject | None = None):
        super().__init__(parent)
        self.model = model
        self._rows: list = []
        self._selected: dict = {}
        model.rows_changed.connect(self._on_rows)
        model.selection_changed.connect(self._on_selected)
        model.draft_changed.connect(self._on_draft)
        model.x_axis_changed.connect(self.xAxisChanged)
        model.x_axis_changed.connect(self._on_rows)
        model.palette_changed.connect(self.paletteChanged)
        self._on_rows()
        self._on_selected()

    # ---- change tracking ---------------------------------------------------------------------

    def _on_rows(self) -> None:
        self._rows = self.model.rows()
        self.rowsChanged.emit()
        # errors and titles shown in the inspector depend on the rows too
        self._on_selected()

    def _on_draft(self, uid: int) -> None:
        if uid == self.model.selected_uid:
            self._on_selected()

    def _on_selected(self) -> None:
        self._selected = self._inspector_data()
        self.selectedChanged.emit()

    def _inspector_data(self) -> dict:
        model = self.model
        draft = model.selected
        if draft is None:
            return {"uid": -1}
        errors = model.validate()
        row = model.row(draft, errors)
        error = errors.get(draft.uid, "")
        data = dict(row)
        data.update(
            {
                "device": draft.device,
                "signal": draft.signal,
                "swatches": model.swatches(row["color"]),
                "deviceError": error if "evice" in error else "",
                "signalError": error if "ignal" in error else "",
                "scanError": error if "scan" in error else "",
                "modelError": error if draft.kind == "dap" else "",
                "fits": [model.row(fit, errors) for fit in model.children(draft.uid)],
            }
        )
        scans = model.scans()
        scan_ids = [scan_id for _, scan_id in scans]
        scan_labels = [label for label, _ in scans]
        if draft.config.scan_id and draft.config.scan_id not in scan_ids:
            scan_ids.append(draft.config.scan_id)
            scan_labels.append(f"Scan #{draft.config.scan_number} (missing)")
        data["scanLabels"] = scan_labels
        data["scanIndex"] = scan_ids.index(draft.config.scan_id or None)
        self._scan_ids = scan_ids
        if draft.kind == "dap":
            available = model.available_models() or list(draft.models)
            if draft.models[0] not in available:
                available = [draft.models[0]] + available
            data["models"] = available
            data["modelIndex"] = available.index(draft.models[0])
            data["extras"] = [
                {"name": m, "label": _pretty_model(m), "checked": m in draft.models[1:]}
                for m in available
                if m != draft.models[0]
            ]
            data["composite"] = (
                f"Composite fit: the sum of {' + '.join(draft.models)}."
                if len(draft.models) > 1
                else "Select more models to fit their sum (a composite fit)."
            )
            parent = model.draft(draft.parent_uid)
            data["parentUid"] = parent.uid if parent else -1
            data["parentTitle"] = model.row(parent, errors)["title"] if parent else ""
        return data

    # ---- properties --------------------------------------------------------------------------

    @Property("QVariantList", notify=rowsChanged)
    def rows(self) -> list:
        """Rows of the curve list."""
        return self._rows

    @Property(int, notify=rowsChanged)
    def curveCount(self) -> int:  # pylint: disable=invalid-name
        """Number of curves without their fits."""
        return sum(1 for r in self._rows if r["depth"] == 0)

    @Property("QVariantList", notify=rowsChanged)
    def problems(self) -> list:
        """Problems that block applying."""
        return self.model.problems()

    @Property("QVariantMap", notify=selectedChanged)
    def selected(self) -> dict:
        """Everything the inspector shows for the selected curve (``uid`` -1 if none)."""
        return self._selected

    @Property("QVariantList", constant=True)
    def xModes(self) -> list:  # pylint: disable=invalid-name
        """Labels of the X axis modes."""
        return [X_MODE_LABELS[m] for m in X_MODES]

    @Property(int, notify=xAxisChanged)
    def xModeIndex(self) -> int:  # pylint: disable=invalid-name
        """Selected X axis mode."""
        return X_MODES.index(self.model.x_mode)

    @Property(str, notify=xAxisChanged)
    def xHelp(self) -> str:  # pylint: disable=invalid-name
        """Explanation of the X axis mode, or the X axis problem."""
        return self.model.x_axis_error() or X_MODE_HELP[self.model.x_mode]

    @Property(bool, notify=xAxisChanged)
    def xInvalid(self) -> bool:  # pylint: disable=invalid-name
        """Whether the X axis selection is incomplete."""
        return bool(self.model.x_axis_error())

    @Property(str, notify=xAxisChanged)
    def xDevice(self) -> str:  # pylint: disable=invalid-name
        """X axis device."""
        return self.model.x_device

    @Property(str, notify=xAxisChanged)
    def xSignal(self) -> str:  # pylint: disable=invalid-name
        """X axis signal."""
        return self.model.x_signal

    @Property(str, notify=paletteChanged)
    def palette(self) -> str:
        """Current palette."""
        return self.model.palette

    @Property("QVariantList", notify=paletteChanged)
    def palettes(self) -> list:
        """Palettes with gradient stops for the selector."""
        return [
            {
                "name": name,
                "stops": [
                    QColor(c).name()
                    for c in Colors.evenly_spaced_colors(colormap=name, num=6, format="HEX")
                ],
            }
            for name in self.model.palettes()
        ]

    @Property("QVariantList", constant=True)
    def penStyles(self) -> list:  # pylint: disable=invalid-name
        """Line styles with labels."""
        return [{"value": s, "label": PEN_STYLE_LABELS[s]} for s in PEN_STYLES]

    @Property("QVariantList", constant=True)
    def symbols(self) -> list:
        """Symbols with labels."""
        return [{"value": s, "label": SYMBOL_LABELS[s]} for s in SYMBOLS]

    # ---- slots -------------------------------------------------------------------------------

    @Slot(int)
    def select(self, uid: int) -> None:
        """Select a curve."""
        self.model.select(uid)

    @Slot(int)
    def move(self, step: int) -> None:
        """Select the next (+1) or previous (-1) row."""
        uids = [r["uid"] for r in self._rows]
        if not uids:
            return
        current = uids.index(self.model.selected_uid) if self.model.selected_uid in uids else 0
        self.model.select(uids[max(0, min(len(uids) - 1, current + step))])

    @Slot(int)
    def remove(self, uid: int) -> None:
        """Remove a curve with its fits, or a fit."""
        self.model.remove(uid)

    @Slot(int)
    def addFit(self, uid: int) -> None:  # pylint: disable=invalid-name
        """Add a fit to a curve."""
        self.model.add_fit(uid)

    @Slot(int, str, "QVariant")
    def setStyle(self, uid: int, key: str, value) -> None:  # pylint: disable=invalid-name
        """Change a style field (``color``, ``pen_style``, ``pen_width``, ``symbol``,
        ``symbol_size``)."""
        self.model.set_style(uid, key, value)

    @Slot(int, int)
    def setScan(self, uid: int, index: int) -> None:  # pylint: disable=invalid-name
        """Choose the data source by index into ``selected.scanLabels``."""
        ids = getattr(self, "_scan_ids", [None])
        if 0 <= index < len(ids):
            self.model.set_scan(uid, ids[index])

    @Slot(int, str)
    def setPrimaryModel(self, uid: int, model: str) -> None:  # pylint: disable=invalid-name
        """Change the primary fit model."""
        self.model.set_primary_model(uid, model)

    @Slot(int, str)
    def toggleExtraModel(self, uid: int, model: str) -> None:  # pylint: disable=invalid-name
        """Add or remove a model of a composite fit."""
        self.model.toggle_extra_model(uid, model)

    @Slot(int)
    def setXMode(self, index: int) -> None:  # pylint: disable=invalid-name
        """Choose the X axis mode by index."""
        self.model.set_x_mode(X_MODES[index])

    @Slot(str)
    def setPalette(self, name: str) -> None:  # pylint: disable=invalid-name
        """Choose the palette (recolours all curves)."""
        self.model.set_palette(name)

    @Slot()
    def recolorAll(self) -> None:  # pylint: disable=invalid-name
        """Recolour all curves from the palette."""
        self.model.recolor_all()

    @Slot(int)
    def pickCustomColor(self, uid: int) -> None:  # pylint: disable=invalid-name
        """Open the colour dialog for a curve."""
        draft = self.model.draft(uid)
        if draft is None:
            return
        color = QColorDialog.getColor(QColor(color_hex(draft.config.color)), None, "Curve colour")
        if color.isValid():
            self.model.set_style(uid, "color", color.name())

    @Slot(str, float, float, float, float)
    def openPicker(
        self, purpose: str, x: float, y: float, w: float, h: float
    ) -> None:  # pylint: disable=invalid-name
        """Open a device or signal picker under the given rectangle of the QML scene.

        Args:
            purpose(str): ``add``, ``device``, ``signal``, ``xdevice`` or ``xsignal``.
        """
        self.pickerRequested.emit(purpose, x, y, w, h)


class CurveSettingsQml(SettingWidget):
    """Curve settings of a :class:`Waveform`, drawn in QML.

    Args:
        parent(QWidget | None): Parent widget.
        target_widget(Waveform): The waveform to edit.
    """

    def __init__(self, parent=None, target_widget: Waveform | None = None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setProperty("skip_settings", True)
        self.target_widget = target_widget
        self.model = CurveDialogModel(target_widget, parent=self)
        self.backend = CurveDialogBackend(self.model, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.view = create_quick_widget(
            self, QML_FILE, properties={"backend": self.backend}, raise_on_error=True
        )
        layout.addWidget(self.view)
        # an invisible widget moved over the QML field that opened a picker; the popup is
        # positioned under it
        self._anchor = QWidget(self.view)
        self._anchor.hide()
        self._purpose = ""
        self.device_picker = DevicePickerQML(parent=self, client=self.model.client)
        self.device_picker.setEditable(True)
        self.device_picker.hide()
        self.device_picker.picker_controller.picked.connect(self._on_device_picked)
        self.signal_picker = SignalPickerQML(parent=self, client=self.model.client)
        self.signal_picker.include_config_signals = False
        self.signal_picker.setEditable(True)
        self.signal_picker.hide()
        self.signal_picker.picker_controller.picked.connect(self._on_signal_picked)
        self.backend.pickerRequested.connect(self._open_picker)
        self._cleaned = False

    def sizeHint(self) -> QSize:  # pylint: disable=invalid-name
        """Default size of the dialog content."""
        return QSize(940, 600)

    @SafeSlot(str, float, float, float, float)
    def _open_picker(self, purpose: str, x: float, y: float, w: float, h: float) -> None:
        self._purpose = purpose
        self._anchor.setGeometry(int(x), int(y), max(1, int(w)), max(1, int(h)))
        model = self.model
        draft = model.selected
        if purpose in ("add", "device", "xdevice"):
            current = ""
            if purpose == "device" and draft is not None:
                current = draft.device
            elif purpose == "xdevice":
                current = model.x_device
            select_device(self.device_picker, current)
            open_picker_at(self.device_picker, self._anchor)
        else:
            if purpose == "signal" and draft is not None:
                select_signal(self.signal_picker, draft.device, draft.signal)
            else:
                select_signal(self.signal_picker, model.x_device, model.x_signal)
            open_picker_at(self.signal_picker, self._anchor)

    @SafeSlot(str)
    def _on_device_picked(self, device: str) -> None:
        if self._purpose == "add":
            self.model.add_curve(device)
        elif self._purpose == "device" and self.model.selected is not None:
            self.model.set_device(self.model.selected_uid, device)
        elif self._purpose == "xdevice":
            self.model.set_x_device(device)

    @SafeSlot(str)
    def _on_signal_picked(self, text: str) -> None:
        signal = signal_obj_name(self.signal_picker, text)
        if self._purpose == "signal" and self.model.selected is not None:
            self.model.set_signal(self.model.selected_uid, signal)
        elif self._purpose == "xsignal":
            self.model.set_x_signal(signal)

    @SafeSlot(popup_error=True)
    def accept_changes(self):
        """Apply the staged curves, X axis and palette to the waveform."""
        self.model.apply()

    @SafeSlot()
    def refresh(self):
        """Reload from the waveform, e.g. after it was changed over RPC."""
        self.model.load_from_waveform()

    def cleanup(self):
        """Unload the QML scene and close the pickers."""
        if self._cleaned:
            return
        self._cleaned = True
        release_quick_widget(self.view)
        for picker in (self.device_picker, self.signal_picker):
            picker.close()
            picker.deleteLater()
