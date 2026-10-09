"""Toolkit-independent state of the redesigned curve settings dialog.

The dialog edits a staged copy of the waveform's curves ("drafts") and only writes them back
on :meth:`CurveDialogModel.apply`. The QWidget and the QML views are thin layers over this
model, so both behave identically and the JSON they produce matches the legacy curve tree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from bec_lib.logger import bec_logger
from qtpy.QtCore import QObject, Signal
from qtpy.QtGui import QColor

from bec_widgets.utils.colors import Colors
from bec_widgets.widgets.plots.waveform.curve import CurveConfig, DeviceSignal

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.widgets.plots.waveform.waveform import Waveform

logger = bec_logger.logger

X_MODES = ("auto", "index", "timestamp", "device")
X_MODE_LABELS = {"auto": "Auto", "index": "Index", "timestamp": "Time", "device": "Device"}
X_MODE_HELP = {
    "auto": "Uses the scan motor, or the point index when the scan has no motor.",
    "index": "Plots every curve against its point number.",
    "timestamp": "Plots every curve against the time each point was read.",
    "device": "Plots every curve against a signal you choose.",
}
PEN_STYLES = ("solid", "dash", "dot", "dashdot")
PEN_STYLE_LABELS = {"solid": "Solid", "dash": "Dash", "dot": "Dot", "dashdot": "Dash-dot"}
# pyqtgraph symbol codes; "" means no symbol
SYMBOLS = ("", "o", "s", "t", "d", "star", "+", "x")
SYMBOL_LABELS = {
    "": "None",
    "o": "Circle",
    "s": "Square",
    "t": "Triangle",
    "d": "Diamond",
    "star": "Star",
    "+": "Plus",
    "x": "Cross",
}
PALETTES = ("plasma", "viridis", "magma", "inferno", "cividis", "turbo")
SWATCH_COUNT = 10


def _pretty_model(model: str) -> str:
    """``GaussianModel`` -> ``Gaussian``."""
    return model[:-5] if model.endswith("Model") and len(model) > 5 else model


def color_hex(color: str | tuple | None) -> str:
    """Return a curve colour as ``#rrggbb`` (grey if unset)."""
    if color is None:
        return "#888888"
    if isinstance(color, str):
        return QColor(color).name()
    return QColor(*[int(c) for c in color[:4]]).name()


def normalize_dap(dap_value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    """Return the fit models of a serialized DAP value as a list, primary model first."""
    if isinstance(dap_value, (list, tuple)):
        models: list[str] = []
        for model in dap_value:
            if model and model not in models:
                models.append(model)
        return models or ["GaussianModel"]
    if isinstance(dap_value, str) and dap_value:
        return [dap_value]
    return ["GaussianModel"]


@dataclass
class CurveDraft:
    """One curve as edited in the dialog.

    Attributes:
        uid(int): Stable id within the dialog session.
        kind(str): ``"device"`` (live or history data), ``"dap"`` (a fit) or ``"custom"``.
        config(CurveConfig): Working copy of the curve config.
        parent_uid(int | None): The curve a fit belongs to.
        original_label(str | None): Label of the waveform curve this draft was loaded from.
        original_dap(Any): DAP value the draft was loaded with; fit parameters only carry over
            while it is unchanged.
    """

    uid: int
    kind: str
    config: CurveConfig
    parent_uid: int | None = None
    original_label: str | None = None
    original_dap: Any = None
    models: list[str] = field(default_factory=list)

    @property
    def device(self) -> str:
        """Device of the curve ('' if none)."""
        return self.config.signal.device if self.config.signal else ""

    @property
    def signal(self) -> str:
        """Signal object name of the curve ('' if none)."""
        return self.config.signal.signal if self.config.signal else ""


class CurveDialogModel(QObject):
    """Staged curves, X axis and palette of one waveform.

    Signals:
        rows_changed: The list of curves or anything shown in it changed.
        selection_changed: Another curve was selected (views rebuild their inspector).
        draft_changed(int): A field of the given curve changed through the model.
        x_axis_changed: Mode, device or signal of the X axis changed.
        palette_changed: The palette changed.
    """

    rows_changed = Signal()
    selection_changed = Signal()
    draft_changed = Signal(int)
    x_axis_changed = Signal()
    palette_changed = Signal()

    def __init__(
        self, waveform: Waveform | None = None, client=None, parent: QObject | None = None
    ):
        super().__init__(parent)
        self.waveform = waveform
        self.client = client if client is not None else getattr(waveform, "client", None)
        self._drafts: list[CurveDraft] = []
        self._next_uid = 1
        self._selected: int | None = None
        self.x_mode = "auto"
        self.x_device = ""
        self.x_signal = ""
        self.palette = "plasma"
        self.load_from_waveform()

    # ---- loading -----------------------------------------------------------------------------

    def load_from_waveform(self) -> None:
        """(Re)load curves, X axis and palette from the waveform, discarding staged edits."""
        self._drafts = []
        self._next_uid = 1
        selected_label = None
        if self._selected is not None and self.draft(self._selected) is not None:
            selected_label = self.draft(self._selected).original_label
        self._selected = None
        waveform = self.waveform
        if waveform is None:
            self.rows_changed.emit()
            self.selection_changed.emit()
            return
        self.palette = getattr(waveform, "color_palette", None) or "plasma"
        mode = waveform.x_axis_mode.get("name", "auto")
        if mode in ("auto", "index", "timestamp"):
            self.x_mode, self.x_device, self.x_signal = mode, "", ""
        else:
            self.x_mode = "device"
            self.x_device = mode or ""
            self.x_signal = waveform.x_axis_mode.get("entry") or ""

        curves = list(waveform.curves)
        tops = [c for c in curves if c.config.source in ("device", "history", "custom")]
        fits = [c for c in curves if c.config.source == "dap"]
        for curve in tops:
            kind = "custom" if curve.config.source == "custom" else "device"
            top = self._new_draft(kind, curve.config.model_copy(deep=True), curve.name())
            for fit in fits:
                if fit.config.parent_label == curve.config.label:
                    config = fit.config.model_copy(deep=True)
                    draft = self._new_draft("dap", config, fit.name(), parent_uid=top.uid)
                    draft.original_dap = config.signal.dap if config.signal else None
                    draft.models = normalize_dap(draft.original_dap)
        for draft in self._drafts:
            if draft.original_label == selected_label:
                self._selected = draft.uid
        if self._selected is None and self._drafts:
            self._selected = self._drafts[0].uid
        self.x_axis_changed.emit()
        self.palette_changed.emit()
        self.rows_changed.emit()
        self.selection_changed.emit()

    def _new_draft(
        self,
        kind: str,
        config: CurveConfig,
        original_label: str | None = None,
        parent_uid: int | None = None,
    ) -> CurveDraft:
        draft = CurveDraft(
            uid=self._next_uid,
            kind=kind,
            config=config,
            parent_uid=parent_uid,
            original_label=original_label,
        )
        self._next_uid += 1
        if parent_uid is None:
            self._drafts.append(draft)
        else:
            # keep fits right after their parent and its other fits
            index = max(
                i for i, d in enumerate(self._drafts) if parent_uid in (d.uid, d.parent_uid)
            )
            self._drafts.insert(index + 1, draft)
        return draft

    # ---- queries -----------------------------------------------------------------------------

    @property
    def drafts(self) -> list[CurveDraft]:
        """All drafts in display order (each curve followed by its fits)."""
        return list(self._drafts)

    def draft(self, uid: int | None) -> CurveDraft | None:
        """The draft with ``uid``, or None."""
        return next((d for d in self._drafts if d.uid == uid), None)

    def children(self, uid: int) -> list[CurveDraft]:
        """Fits of the curve ``uid``."""
        return [d for d in self._drafts if d.parent_uid == uid]

    @property
    def selected_uid(self) -> int | None:
        """Uid of the selected curve."""
        return self._selected

    @property
    def selected(self) -> CurveDraft | None:
        """The selected draft."""
        return self.draft(self._selected)

    def device_names(self) -> list[str]:
        """Names of the devices known to the device manager."""
        dm = getattr(self.client, "device_manager", None)
        devices = getattr(dm, "devices", None) or {}
        return list(devices.keys())

    def _device(self, name: str):
        dm = getattr(self.client, "device_manager", None)
        devices = getattr(dm, "devices", None) or {}
        return devices.get(name) if name else None

    def device_signals(self, device: str) -> list[str]:
        """Object names of the plottable (hinted and normal) signals of ``device``."""
        dev = self._device(device)
        if dev is None:
            return []
        info = (getattr(dev, "_info", None) or {}).get("signals", {}) or {}
        names = []
        for name, signal in info.items():
            kind = str(signal.get("kind_str", ""))
            if kind in ("hinted", "normal") or "hinted" in kind or "normal" in kind:
                names.append(signal.get("obj_name") or name)
        return names or [device]

    def default_signal(self, device: str) -> str:
        """The signal a new curve of ``device`` starts with: its first hint, else the device."""
        dev = self._device(device)
        if dev is None:
            return ""
        hints = []
        try:
            hints = list(getattr(dev, "_hints", None) or [])
        except Exception:  # pylint: disable=broad-except
            hints = []
        if hints:
            return hints[0]
        signals = self.device_signals(device)
        return signals[0] if signals else device

    def available_models(self) -> list[str]:
        """Fit models offered by the DAP service."""
        # pylint: disable=protected-access
        plugins = getattr(getattr(self.client, "dap", None), "_available_dap_plugins", {}) or {}
        return list(plugins.keys())

    def scans(self) -> list[tuple[str, str | None]]:
        """Selectable data sources: ``("Live scan", None)`` then ``("Scan #N", scan_id)``."""
        out: list[tuple[str, str | None]] = [("Live scan", None)]
        history = getattr(self.client, "history", None)
        if history is None:
            return out
        # pylint: disable=protected-access
        numbers = list(getattr(history, "_scan_numbers", []) or [])
        ids = list(getattr(history, "_scan_ids", []) or [])
        for number, scan_id in sorted(zip(numbers, ids), key=lambda pair: pair[0], reverse=True):
            out.append((f"Scan #{number}", scan_id))
        return out

    def swatches(self, current: str | None = None) -> list[str]:
        """Suggested colours: evenly spaced over the palette, led by ``current`` if it is not
        one of them."""
        colors = [
            QColor(c).name()
            for c in Colors.evenly_spaced_colors(
                colormap=self.palette, num=SWATCH_COUNT, format="HEX"
            )
        ]
        if current and current.lower() not in colors:
            colors = [current.lower()] + colors[:-1]
        return colors

    def palettes(self) -> list[str]:
        """Palettes offered in the palette selector."""
        names = list(PALETTES)
        if self.palette not in names:
            names.insert(0, self.palette)
        return names

    # ---- rows shown in the curve list --------------------------------------------------------

    def label_of(self, draft: CurveDraft) -> str:
        """The label the curve will get on apply (the legacy naming scheme)."""
        if draft.kind == "custom":
            return draft.original_label or draft.config.label or ""
        if draft.kind == "device":
            label = f"{draft.device}-{draft.signal}"
            if draft.config.scan_id:
                label += f"-scan-{draft.config.scan_number}"
            return label
        parent = self.draft(draft.parent_uid)
        parent_label = self.label_of(parent) if parent else draft.config.parent_label or ""
        return f"{parent_label}-{'+'.join(draft.models)}"

    def display_name(self, draft: CurveDraft) -> str:
        """Short name of a curve for texts: ``device``, or ``device · signal`` when they differ."""
        if draft.kind == "custom":
            return draft.original_label or draft.config.label or "custom"
        if draft.kind == "dap":
            return " + ".join(_pretty_model(m) for m in draft.models) + " fit"
        name = draft.device or "new curve"
        if draft.signal and draft.signal != draft.device:
            name += f" · {draft.signal}"
        if draft.config.scan_id:
            name += f" (scan #{draft.config.scan_number})"
        return name

    def row(self, draft: CurveDraft, errors: dict[int, str] | None = None) -> dict:
        """Display data of one draft for the curve list."""
        errors = self.validate() if errors is None else errors
        config = draft.config
        if draft.kind == "device":
            title = draft.device or "New curve"
            source = f"scan #{config.scan_number}" if config.scan_id else "live"
            subtitle = f"{draft.signal or 'no signal'} · {source}"
            tag = "history" if config.scan_id else ""
        elif draft.kind == "dap":
            title = " + ".join(_pretty_model(m) for m in draft.models) + " fit"
            parent = self.draft(draft.parent_uid)
            subtitle = f"fit of {self.display_name(parent)}" if parent else ""
            tag = "fit"
        else:
            title = draft.original_label or config.label or "custom"
            subtitle = "data sent from the command line"
            tag = "custom"
        color = color_hex(config.color)
        return {
            "uid": draft.uid,
            "kind": draft.kind,
            "depth": 1 if draft.parent_uid is not None else 0,
            "title": title,
            "subtitle": subtitle,
            "tag": tag,
            "color": color,
            "penStyle": config.pen_style or "solid",
            "penWidth": int(config.pen_width or 1),
            "symbol": config.symbol or "",
            "symbolSize": int(config.symbol_size or 1),
            "error": errors.get(draft.uid, ""),
            "selected": draft.uid == self._selected,
        }

    def rows(self) -> list[dict]:
        """Display data of all drafts in order."""
        errors = self.validate()
        return [self.row(d, errors) for d in self._drafts]

    # ---- validation --------------------------------------------------------------------------

    def validate(self) -> dict[int, str]:
        """Problems that block applying, keyed by draft uid."""
        errors: dict[int, str] = {}
        devices = set(self.device_names())
        models = set(self.available_models())
        scan_ids = {scan_id for _, scan_id in self.scans() if scan_id}
        labels: dict[str, int] = {}
        for draft in self._drafts:
            if draft.kind == "device":
                if not draft.device:
                    errors[draft.uid] = "Choose a device."
                elif devices and draft.device not in devices:
                    errors[draft.uid] = f"Device '{draft.device}' is not loaded."
                elif not draft.signal:
                    errors[draft.uid] = "Choose a signal."
                elif draft.config.scan_id and draft.config.scan_id not in scan_ids:
                    errors[draft.uid] = "This scan is no longer in the history."
            elif draft.kind == "dap":
                missing = [m for m in draft.models if models and m not in models]
                if missing:
                    errors[draft.uid] = f"Fit model {missing[0]} is not available."
            label = self.label_of(draft)
            if draft.uid not in errors and label in labels:
                errors[draft.uid] = "The same curve is already listed."
            labels.setdefault(label, draft.uid)
        return errors

    def x_axis_error(self) -> str:
        """Problem with the X axis selection, '' if none."""
        if self.x_mode != "device":
            return ""
        if not self.x_device:
            return "Choose the device for the X axis."
        if self.device_names() and self.x_device not in self.device_names():
            return f"Device '{self.x_device}' is not loaded."
        return ""

    def problems(self) -> list[str]:
        """Human-readable problems that block applying."""
        out = []
        x_error = self.x_axis_error()
        if x_error:
            out.append(f"X axis: {x_error}")
        errors = self.validate()
        for draft in self._drafts:
            if draft.uid in errors:
                out.append(f"{self.row(draft, errors)['title']}: {errors[draft.uid]}")
        return out

    # ---- editing -----------------------------------------------------------------------------

    def select(self, uid: int | None) -> None:
        """Select the curve ``uid`` (None clears the selection)."""
        if uid == self._selected or (uid is not None and self.draft(uid) is None):
            return
        self._selected = uid
        self.rows_changed.emit()
        self.selection_changed.emit()

    def _next_color(self) -> str:
        used = {str(d.config.color).lower() for d in self._drafts}
        buffer = Colors.golden_angle_color(
            colormap=self.palette, num=max(10, len(self._drafts) + 1), format="HEX"
        )
        for color in buffer:
            if color.lower() not in used:
                return color
        return buffer[len(self._drafts) % len(buffer)]

    def add_curve(self, device: str = "", signal: str = "") -> int:
        """Add a live curve of ``device`` and select it.

        Args:
            device(str): Device name; may be empty and chosen later.
            signal(str): Signal object name; defaults to the device's first hint.

        Returns:
            int: Uid of the new curve.
        """
        if device and not signal:
            signal = self.default_signal(device)
        existing = next(
            (
                d
                for d in self._drafts
                if d.kind == "device"
                and d.device == device
                and d.signal == signal
                and not d.config.scan_id
                and device
            ),
            None,
        )
        if existing is not None:
            # the curve is already plotted: show it instead of adding a duplicate
            self.select(existing.uid)
            return existing.uid
        color = self._next_color()
        config = CurveConfig(
            widget_class="Curve",
            parent_id=getattr(self.waveform, "gui_id", None),
            source="device",
            signal=DeviceSignal(device=device, signal=signal),
            color=color,
            symbol_color=color,
        )
        draft = self._new_draft("device", config)
        self._selected = draft.uid
        self.rows_changed.emit()
        self.selection_changed.emit()
        return draft.uid

    def add_fit(self, parent_uid: int, model: str | None = None) -> int | None:
        """Add a fit to the curve ``parent_uid`` and select it.

        Returns:
            int | None: Uid of the new fit, None if the parent cannot have fits.
        """
        parent = self.draft(parent_uid)
        if parent is None or parent.kind == "dap":
            return None
        models = self.available_models()
        model = model or ("GaussianModel" if not models or "GaussianModel" in models else models[0])
        color = self._next_color()
        config = CurveConfig(
            widget_class="Curve",
            parent_id=getattr(self.waveform, "gui_id", None),
            source="dap",
            parent_label=self.label_of(parent),
            # fits of command-line curves address their parent by label (as Waveform does)
            signal=(
                DeviceSignal(device=self.label_of(parent), signal="custom", dap=model)
                if parent.kind == "custom"
                else DeviceSignal(device=parent.device, signal=parent.signal, dap=model)
            ),
            color=color,
            symbol_color=color,
        )
        draft = self._new_draft("dap", config, parent_uid=parent.uid)
        draft.models = [model]
        self._selected = draft.uid
        self.rows_changed.emit()
        self.selection_changed.emit()
        return draft.uid

    def remove(self, uid: int) -> None:
        """Remove a device curve with its fits, or a single fit. Custom curves stay."""
        draft = self.draft(uid)
        if draft is None or draft.kind == "custom":
            return
        removed = {uid} | {d.uid for d in self.children(uid)}
        index = self._drafts.index(draft)
        self._drafts = [d for d in self._drafts if d.uid not in removed]
        if self._selected in removed:
            if draft.parent_uid is not None:
                self._selected = draft.parent_uid
            elif self._drafts:
                self._selected = self._drafts[min(index, len(self._drafts) - 1)].uid
                if self.draft(self._selected).parent_uid is not None:
                    self._selected = self.draft(self._selected).parent_uid
            else:
                self._selected = None
            self.selection_changed.emit()
        self.rows_changed.emit()

    def _changed(self, uid: int) -> None:
        self.draft_changed.emit(uid)
        self.rows_changed.emit()

    def set_device(self, uid: int, device: str) -> None:
        """Change the device of a curve; the signal resets to the device's first hint."""
        draft = self.draft(uid)
        if draft is None or draft.kind != "device" or device == draft.device:
            return
        draft.config.signal = DeviceSignal(device=device, signal=self.default_signal(device))
        self._changed(uid)

    def set_signal(self, uid: int, signal: str) -> None:
        """Change the signal (object name) of a curve."""
        draft = self.draft(uid)
        if draft is None or draft.kind != "device" or signal == draft.signal:
            return
        draft.config.signal = DeviceSignal(device=draft.device, signal=signal)
        self._changed(uid)

    def set_scan(self, uid: int, scan_id: str | None) -> None:
        """Plot the curve from the live scan (None) or from a scan of the history."""
        draft = self.draft(uid)
        if draft is None or draft.kind != "device":
            return
        number = None
        if scan_id:
            history = getattr(self.client, "history", None)
            # pylint: disable=protected-access
            pairs = dict(
                zip(getattr(history, "_scan_ids", []), getattr(history, "_scan_numbers", []))
            )
            number = pairs.get(scan_id)
        draft.config.scan_id = scan_id or None
        draft.config.scan_number = number
        self._changed(uid)

    def set_models(self, uid: int, models: list[str]) -> None:
        """Set the fit models of a fit, primary first; more than one makes a composite fit."""
        draft = self.draft(uid)
        if draft is None or draft.kind != "dap":
            return
        models = normalize_dap(models)
        if models == draft.models:
            return
        draft.models = models
        self._changed(uid)

    def set_primary_model(self, uid: int, model: str) -> None:
        """Replace the primary fit model, keeping the other models of a composite fit."""
        draft = self.draft(uid)
        if draft is None or draft.kind != "dap":
            return
        self.set_models(uid, [model] + [m for m in draft.models[1:] if m != model])

    def toggle_extra_model(self, uid: int, model: str) -> None:
        """Add ``model`` to a composite fit, or remove it."""
        draft = self.draft(uid)
        if draft is None or draft.kind != "dap" or model == draft.models[0]:
            return
        extras = list(draft.models[1:])
        if model in extras:
            extras.remove(model)
        else:
            extras.append(model)
        self.set_models(uid, [draft.models[0]] + extras)

    def set_style(self, uid: int, key: str, value: Any) -> None:
        """Change a style field of a curve.

        Args:
            uid(int): Curve.
            key(str): ``color``, ``pen_style``, ``pen_width``, ``symbol`` or ``symbol_size``.
            value: New value.
        """
        draft = self.draft(uid)
        if draft is None or key not in ("color", "pen_style", "pen_width", "symbol", "symbol_size"):
            return
        if key == "symbol":
            value = value or None
        if key in ("pen_width", "symbol_size"):
            value = max(1, min(20, int(value)))
        if getattr(draft.config, key) == value:
            return
        setattr(draft.config, key, value)
        if key == "color":
            draft.config.symbol_color = value
        self._changed(uid)

    def set_palette(self, palette: str, recolor: bool = True) -> None:
        """Choose the palette new curves take their colours from; recolours all curves."""
        if palette == self.palette and not recolor:
            return
        self.palette = palette
        if recolor:
            self.recolor_all(emit=False)
        self.palette_changed.emit()
        self.rows_changed.emit()
        if self._selected is not None:
            self.draft_changed.emit(self._selected)

    def recolor_all(self, emit: bool = True) -> None:
        """Give every curve the next colour of the palette, in list order."""
        colors = Colors.golden_angle_color(
            colormap=self.palette, num=max(10, len(self._drafts) + 1), format="HEX"
        )
        for index, draft in enumerate(self._drafts):
            draft.config.color = colors[index]
            draft.config.symbol_color = colors[index]
        if emit:
            self.rows_changed.emit()
            if self._selected is not None:
                self.draft_changed.emit(self._selected)

    def set_x_mode(self, mode: str) -> None:
        """Choose how the X axis is built (see :data:`X_MODES`)."""
        if mode not in X_MODES or mode == self.x_mode:
            return
        self.x_mode = mode
        self.x_axis_changed.emit()

    def set_x_device(self, device: str) -> None:
        """Choose the X axis device; the signal resets to its first hint."""
        if device == self.x_device:
            return
        self.x_device = device
        self.x_signal = self.default_signal(device) if device else ""
        self.x_axis_changed.emit()

    def set_x_signal(self, signal: str) -> None:
        """Choose the X axis signal (object name)."""
        if signal == self.x_signal:
            return
        self.x_signal = signal
        self.x_axis_changed.emit()

    # ---- export and apply --------------------------------------------------------------------

    def _export_draft(self, draft: CurveDraft) -> dict:
        config = draft.config.model_copy(deep=True)
        if draft.kind == "device":
            config.source = "history" if config.scan_id else "device"
            if not config.scan_id:
                config.scan_number = None
            config.label = self.label_of(draft)
        elif draft.kind == "dap":
            parent = self.draft(draft.parent_uid)
            device, signal = (parent.device, parent.signal) if parent else ("", "")
            if parent is not None and parent.kind == "custom":
                device, signal = draft.device, draft.signal
            dap: str | list[str] = draft.models if len(draft.models) > 1 else draft.models[0]
            old = draft.config.signal
            config.signal = DeviceSignal(
                device=device,
                signal=signal,
                dap=dap,
                dap_oversample=old.dap_oversample if old is not None else 1,
                dap_parameters=(
                    old.dap_parameters
                    if old is not None
                    and draft.original_dap is not None
                    and draft.original_dap == dap
                    else None
                ),
            )
            config.source = "dap"
            config.parent_label = self.label_of(parent) if parent else config.parent_label
            config.label = self.label_of(draft)
        return config.model_dump()

    def export_curves(self) -> list[dict]:
        """Configs of all non-custom curves, in the format of ``Waveform.curve_json``."""
        return [self._export_draft(d) for d in self._drafts if d.kind != "custom"]

    def apply(self) -> None:
        """Write palette, X axis and curves to the waveform.

        Raises:
            ValueError: If a curve or the X axis is incomplete.
        """
        problems = self.problems()
        if problems:
            raise ValueError("Cannot apply the curve settings:\n" + "\n".join(problems))
        waveform = self.waveform
        if waveform is None:
            return
        if waveform.color_palette != self.palette:
            waveform.color_palette = self.palette
        if self.x_mode == "device":
            waveform.x_mode = self.x_device
            if self.x_signal:
                waveform.signal_x = self.x_signal
        else:
            waveform.x_mode = self.x_mode
        waveform.curve_json = json.dumps(self.export_curves(), indent=2)
        self._apply_custom_styles()
        # reload so that labels and fit parameters match what the waveform now holds
        self.load_from_waveform()

    def _apply_custom_styles(self) -> None:
        by_name = {curve.name(): curve for curve in self.waveform.curves}
        for draft in self._drafts:
            if draft.kind != "custom":
                continue
            curve = by_name.get(draft.original_label)
            if curve is None:
                continue
            for key in ("color", "symbol_color", "pen_style", "pen_width", "symbol", "symbol_size"):
                setattr(curve.config, key, getattr(draft.config, key))
            curve.apply_config()
