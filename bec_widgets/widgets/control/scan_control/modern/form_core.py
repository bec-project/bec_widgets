"""View-independent state for the modernized scan control.

Both the QML and the QWidget versions of the modern scan control render the same
``ScanFormState`` and ``MetadataFormState``. Keeping the form state in plain Python makes the
two views directly comparable: they only differ in how they draw the form, not in what the
form does.
"""

from __future__ import annotations

import inspect
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal
from types import NoneType, UnionType
from typing import Any, Callable, Literal, Union, get_args, get_origin

from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from bec_lib.scan_history import ScanHistory
from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticUndefined
from qtpy.QtCore import QObject, Signal

from bec_widgets.utils.scan_arg_metadata import format_display_name

logger = bec_logger.logger

FieldKind = Literal["device", "float", "int", "bool", "str", "choice"]

INT_LIMIT = 2147483647
DEFAULT_DECIMALS = 4
RECENT_SCAN_HISTORY_COUNT = 50
MAX_HISTORY_LOOKBACK = 500


def scan_summary(docstring: str | None) -> str:
    """Return the first paragraph of a scan docstring as one line."""
    if not docstring:
        return ""
    text = inspect.cleandoc(docstring)
    first = re.split(r"\n\s*\n", text, maxsplit=1)[0]
    return " ".join(line.strip() for line in first.splitlines())


@dataclass
class FieldSpec:
    """One input of the scan form."""

    name: str
    label: str
    kind: FieldKind
    default: Any = None
    tooltip: str = ""
    units: str | None = None
    reference_units: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    decimals: int = DEFAULT_DECIMALS
    choices: list[str] = field(default_factory=list)
    expert: bool = False

    @classmethod
    def from_input(cls, item: dict) -> FieldSpec | None:
        """Build a field from a ``ScanInfoAdapter`` input config, or None if unsupported."""
        item_type = item.get("type")
        choices: list[str] = []
        if isinstance(item_type, dict) and "Literal" in item_type:
            kind = "choice"
            # Keep the declared order (the classic widget used a set and shuffled it).
            literals = list(dict.fromkeys(item_type["Literal"]))
            choices = ["" if value is None else str(value) for value in literals]
        elif item_type in ("device", "DeviceBase"):
            kind = "device"
        elif item_type in ("float", "int", "bool", "str"):
            kind = item_type
        else:
            logger.error(f"Unsupported annotation '{item_type}' for parameter '{item.get('name')}'")
            return None

        default = item.get("default")
        if default == "_empty":
            default = None
        precision = item.get("precision")
        try:
            decimals = max(0, int(precision)) if precision is not None else DEFAULT_DECIMALS
        except (TypeError, ValueError):
            decimals = DEFAULT_DECIMALS

        spec = cls(
            name=item["name"],
            label=item.get("display_name") or format_display_name(item["name"]),
            kind=kind,
            default=default,
            tooltip=item.get("tooltip") or "",
            units=item.get("units"),
            reference_units=item.get("reference_units"),
            decimals=decimals if kind == "float" else 0,
            choices=choices,
            expert=bool(item.get("expert", False)),
        )
        spec._apply_limits(item)
        return spec

    def _apply_limits(self, item: dict) -> None:
        if self.kind not in ("int", "float"):
            return
        step = 1 if self.kind == "int" else 10 ** (-self.decimals)
        if item.get("ge") is not None:
            self.minimum = float(item["ge"])
        if item.get("gt") is not None:
            self.minimum = float(item["gt"]) + step
        if item.get("le") is not None:
            self.maximum = float(item["le"])
        if item.get("lt") is not None:
            self.maximum = float(item["lt"]) - step

    def initial_value(self) -> Any:
        """Value shown before the user edits the field."""
        if self.default is not None:
            return self.coerce(self.default)
        if self.kind in ("int", "float"):
            value = 0.0
            if self.minimum is not None and value < self.minimum:
                value = self.minimum
            if self.maximum is not None and value > self.maximum:
                value = self.maximum
            return int(value) if self.kind == "int" else value
        if self.kind == "bool":
            return False
        if self.kind == "choice":
            # An optional literal (None among the choices) starts unset, like the classic widget.
            return "" if "" in self.choices or not self.choices else self.choices[0]
        return ""

    def coerce(self, value: Any) -> Any:
        """Convert a value coming from a view or from BEC to this field's type."""
        try:
            if self.kind == "int":
                return int(value)
            if self.kind == "float":
                return float(value)
        except (TypeError, ValueError):
            return 0 if self.kind == "int" else 0.0
        if self.kind == "bool":
            if isinstance(value, str):
                return value.strip().lower() in ("1", "true", "yes", "on")
            return bool(value)
        if self.kind == "device":
            return getattr(value, "name", None) or ("" if value is None else str(value))
        return "" if value is None else str(value)

    def to_dict(self) -> dict:
        """Plain dict for QML."""
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "tooltip": self.tooltip,
            "minimum": -INT_LIMIT if self.minimum is None else self.minimum,
            "maximum": INT_LIMIT if self.maximum is None else self.maximum,
            "decimals": self.decimals,
            "choices": self.choices,
            "expert": self.expert,
        }


@dataclass
class FieldGroup:
    """A titled group of keyword fields."""

    name: str
    fields: list[FieldSpec]


@dataclass
class ScanFormSpec:
    """Everything a view needs to render the form of one scan."""

    scan_name: str = ""
    summary: str = ""
    arg_title: str = ""
    arg_fields: list[FieldSpec] = field(default_factory=list)
    arg_min: int = 0
    arg_max: int | None = None
    groups: list[FieldGroup] = field(default_factory=list)

    @classmethod
    def from_ui_config(cls, scan_name: str, docstring: str | None, ui_config: dict):
        """Build the spec from ``ScanInfoAdapter.build_scan_ui_config`` output."""
        spec = cls(scan_name=scan_name, summary=scan_summary(docstring))
        arg_group = ui_config.get("arg_group") or {}
        if arg_group.get("arg_inputs"):
            spec.arg_title = arg_group.get("name") or "Scan Arguments"
            spec.arg_fields = [
                f for f in map(FieldSpec.from_input, arg_group.get("inputs", [])) if f is not None
            ]
            spec.arg_min = arg_group.get("min") or 1
            spec.arg_max = arg_group.get("max")
        for group in ui_config.get("kwarg_groups", []):
            fields = [f for f in map(FieldSpec.from_input, group.get("inputs", [])) if f]
            if fields:
                spec.groups.append(FieldGroup(group.get("name", ""), fields))
        return spec

    @property
    def kwarg_fields(self) -> list[FieldSpec]:
        """All keyword fields across groups."""
        return [f for group in self.groups for f in group.fields]


class ScanFormState(QObject):
    """Values of the scan form plus their validation.

    Signals:
        rebuilt: the spec or the number of argument rows changed; views rebuild their layout.
        values_changed: one or more values changed; views refresh their editors.
    """

    rebuilt = Signal()
    values_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.spec = ScanFormSpec()
        self.arg_rows: list[dict[str, Any]] = []
        self.kwargs: dict[str, Any] = {}
        self.device_names: list[str] = []
        self.units_resolver: Callable[[str], str | None] = lambda _name: None

    # ------------------------------------------------------------------ structure

    def load(self, spec: ScanFormSpec) -> None:
        """Show a new scan with its default values."""
        self.spec = spec
        self.arg_rows = [self._new_row() for _ in range(spec.arg_min if spec.arg_fields else 0)]
        self.kwargs = {f.name: f.initial_value() for f in spec.kwarg_fields}
        self.rebuilt.emit()
        self.values_changed.emit()

    def _new_row(self) -> dict[str, Any]:
        return {f.name: f.initial_value() for f in self.spec.arg_fields}

    def can_add_row(self) -> bool:
        """Whether one more argument row is allowed."""
        if not self.spec.arg_fields:
            return False
        return self.spec.arg_max is None or len(self.arg_rows) < self.spec.arg_max

    def can_remove_row(self) -> bool:
        """Whether an argument row can be removed."""
        return len(self.arg_rows) > max(self.spec.arg_min, 0)

    def add_row(self) -> None:
        """Append an argument row, copying nothing but defaults."""
        if not self.can_add_row():
            return
        self.arg_rows.append(self._new_row())
        self.rebuilt.emit()
        self.values_changed.emit()

    def remove_row(self, index: int) -> None:
        """Remove the argument row at ``index``."""
        if not self.can_remove_row() or not 0 <= index < len(self.arg_rows):
            return
        del self.arg_rows[index]
        self.rebuilt.emit()
        self.values_changed.emit()

    # ------------------------------------------------------------------ values

    def _arg_field(self, name: str) -> FieldSpec | None:
        return next((f for f in self.spec.arg_fields if f.name == name), None)

    def _kwarg_field(self, name: str) -> FieldSpec | None:
        return next((f for f in self.spec.kwarg_fields if f.name == name), None)

    def set_arg_value(self, row: int, name: str, value: Any) -> None:
        """Set one value of an argument row."""
        spec = self._arg_field(name)
        if spec is None or not 0 <= row < len(self.arg_rows):
            return
        value = spec.coerce(value)
        if self.arg_rows[row].get(name) == value:
            return
        self.arg_rows[row][name] = value
        self.values_changed.emit()

    def set_kwarg_value(self, name: str, value: Any) -> None:
        """Set one keyword value."""
        spec = self._kwarg_field(name)
        if spec is None:
            return
        value = spec.coerce(value)
        if self.kwargs.get(name) == value:
            return
        self.kwargs[name] = value
        self.values_changed.emit()

    def set_args(self, args: list) -> None:
        """Replace all argument rows from a flat argument list."""
        n_fields = len(self.spec.arg_fields)
        if not args or n_fields == 0:
            return
        n_rows = max(math.ceil(len(args) / n_fields), self.spec.arg_min)
        row_count_changed = n_rows != len(self.arg_rows)
        self.arg_rows = [self._new_row() for _ in range(n_rows)]
        for index, value in enumerate(args):
            row, column = divmod(index, n_fields)
            spec = self.spec.arg_fields[column]
            self.arg_rows[row][spec.name] = spec.coerce(value)
        if row_count_changed:
            self.rebuilt.emit()
        self.values_changed.emit()

    def set_kwargs(self, kwargs: dict) -> None:
        """Update keyword values that belong to this scan; unknown keys are ignored."""
        for spec in self.spec.kwarg_fields:
            if spec.name in kwargs:
                self.kwargs[spec.name] = spec.coerce(kwargs[spec.name])
        self.values_changed.emit()

    def args_list(self, dev=None) -> list:
        """Flat positional arguments; device names become device objects when ``dev`` is set."""
        args = []
        for row in self.arg_rows:
            for spec in self.spec.arg_fields:
                value = row.get(spec.name)
                if spec.kind == "device" and dev is not None:
                    value = getattr(dev, value, None) or dev[value]
                args.append(value)
        return args

    def kwargs_dict(self) -> dict:
        """Keyword arguments as BEC expects them."""
        result = {}
        for spec in self.spec.kwarg_fields:
            value = self.kwargs.get(spec.name)
            if spec.kind == "choice" and value == "":
                value = None
            result[spec.name] = value
        return result

    def selected_devices(self) -> list[str]:
        """Device names chosen in the argument rows, in row order."""
        return [
            row.get(spec.name, "")
            for row in self.arg_rows
            for spec in self.spec.arg_fields
            if spec.kind == "device"
        ]

    # ------------------------------------------------------------------ derived

    def units_for(self, spec: FieldSpec, row: int | None = None) -> str:
        """Units of a field, resolving ``reference_units`` through the referenced device."""
        if spec.units:
            return spec.units
        ref = spec.reference_units
        if not ref:
            return ""
        device = None
        if self._arg_field(ref) is not None and self.arg_rows:
            device = self.arg_rows[row if row is not None else 0].get(ref)
        elif ref in self.kwargs:
            device = self.kwargs.get(ref)
        if device and device in self.device_names:
            return self.units_resolver(device) or ""
        return ""

    def field_error(self, spec: FieldSpec, value: Any) -> str:
        """Message for an invalid value, or an empty string."""
        if spec.kind != "device":
            return ""
        if not value:
            return f"Choose a {spec.label.lower()}"
        if value not in self.device_names:
            return f"Unknown device '{value}'"
        return ""

    def problems(self) -> list[str]:
        """Human-readable reasons why the scan cannot start yet."""
        problems = []
        multi_row = len(self.arg_rows) > 1
        for index, row in enumerate(self.arg_rows):
            for spec in self.spec.arg_fields:
                error = self.field_error(spec, row.get(spec.name))
                if error:
                    problems.append(f"Row {index + 1}: {error}" if multi_row else error)
        for spec in self.spec.kwarg_fields:
            error = self.field_error(spec, self.kwargs.get(spec.name))
            if error:
                problems.append(f"{spec.label}: {error}")
        return problems


@dataclass
class MetadataField:
    """One field of the metadata schema."""

    name: str
    label: str
    kind: Literal["str", "int", "float", "bool"]
    required: bool
    default: Any
    description: str

    def placeholder(self, scan_name: str) -> str:
        """Hint shown in the empty field."""
        return scan_name if self.name == "scan_name" else self.description

    def to_dict(self, scan_name: str = "") -> dict:
        """Plain dict for QML."""
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "required": self.required,
            "description": self.description,
            "placeholder": self.placeholder(scan_name),
        }


def _metadata_kind(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        args = [arg for arg in get_args(annotation) if arg is not NoneType]
        annotation = args[0] if args else str
    if annotation is bool:
        return "bool"
    if annotation is int:
        return "int"
    if annotation in (float, Decimal):
        return "float"
    return "str"


class MetadataFormState(QObject):
    """Values and validation of the scan metadata form, driven by the scan's pydantic schema."""

    rebuilt = Signal()
    values_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.schema: type[BaseModel] | None = None
        self.fields: list[MetadataField] = []
        self.values: dict[str, Any] = {}
        self.extras: list[list[str]] = []
        self.scan_name = ""
        self.errors: dict[str, str] = {}
        self.data: dict | None = None

    def load(self, schema: type[BaseModel], scan_name: str) -> None:
        """Switch to a new schema, keeping values of fields that still exist."""
        old_values = self.values
        self.schema = schema
        self.scan_name = scan_name
        self.fields = []
        for name, info in schema.model_fields.items():
            default = None if info.default is PydanticUndefined else info.default
            self.fields.append(
                MetadataField(
                    name=name,
                    label=info.title or format_display_name(name),
                    kind=_metadata_kind(info.annotation),
                    required=info.is_required(),
                    default=default,
                    description=info.description or "",
                )
            )
        self.values = {f.name: old_values.get(f.name, f.default) for f in self.fields}
        self.rebuilt.emit()
        self.validate()

    def set_value(self, name: str, value: Any) -> None:
        """Set a schema field; empty text clears it."""
        spec = next((f for f in self.fields if f.name == name), None)
        if spec is None:
            return
        if isinstance(value, str) and value.strip() == "" and spec.kind != "str":
            value = None
        self.values[name] = value
        self.validate()

    def set_extras(self, extras: list[list[str]]) -> None:
        """Set the free key/value metadata."""
        self.extras = [[str(k), str(v)] for k, v in extras]
        self.validate()

    def validate(self) -> None:
        """Validate and publish the result in ``data`` and ``errors``."""
        self.errors = {}
        self.data = None
        if self.schema is None:
            self.values_changed.emit()
            return
        data = {k: v for k, v in self.extras if k}
        data.update({k: v for k, v in self.values.items() if v is not None})
        if "scan_name" in self.values and not data.get("scan_name"):
            data["scan_name"] = self.scan_name
        try:
            self.data = self.schema.model_validate(data).model_dump()
        except ValidationError as exc:
            for error in exc.errors():
                name = str(error["loc"][0]) if error["loc"] else ""
                self.errors.setdefault(name, error["msg"])
        self.values_changed.emit()

    def problems(self) -> list[str]:
        """Human-readable validation problems."""
        labels = {f.name: f.label for f in self.fields}
        return [f"Metadata {labels.get(k, k)}: {msg}" for k, msg in self.errors.items()]

    def summary(self) -> str:
        """Short one-line description of the filled metadata."""
        parts = [
            f"{f.label}: {self.values[f.name]}"
            for f in self.fields
            if f.name != "scan_name" and self.values.get(f.name) not in (None, "")
        ]
        parts += [f"{k}: {v}" for k, v in self.extras if k]
        return ", ".join(parts)


def device_names_for_scans(dev) -> list[str]:
    """Devices and writable signals the scan form offers, like the classic DeviceComboBox."""
    from bec_lib.device import Device  # pylint: disable=import-outside-toplevel

    try:
        enabled = list(dev.enabled_devices)
    except Exception:  # pylint: disable=broad-except
        return []
    names = [d.name for d in enabled if isinstance(d, Device)]
    seen = set(names)
    for d in enabled:
        info = getattr(d, "_info", None) or {}
        if info.get("write_access") and d.name not in seen:
            names.append(d.name)
            seen.add(d.name)
    return sorted(names)


def lookup_last_scan_parameters(client, scan_name: str) -> tuple[list, dict] | None:
    """Find the newest parameters for ``scan_name`` in the history cache or a bounded window.

    Runs off the GUI thread. Mirrors the bounded search of the classic ``ScanControl``.
    """
    # pylint: disable=import-outside-toplevel,protected-access
    from bec_widgets.widgets.control.scan_control.scan_control import ScanControl

    endpoint = MessageEndpoints.scan_history()

    def window(count: int) -> list[dict]:
        entries = client.connector.get_last(endpoint, count=count)
        if isinstance(entries, dict):
            entries = [entries]
        return entries or []

    tip = window(1)
    tip_id = getattr(tip[0].get("data"), "scan_id", None) if tip else None
    history = getattr(client, "history", None)
    if isinstance(history, ScanHistory) and len(history):
        newest = getattr(history[len(history) - 1], "_msg", None)
        if newest is not None and newest.scan_id == tip_id:
            for index in range(len(history) - 1, -1, -1):
                msg = getattr(history[index], "_msg", None)
                if msg is not None and msg.scan_name == scan_name:
                    return ScanControl._parameters_from_request_inputs(msg.request_inputs)

    entries = window(RECENT_SCAN_HISTORY_COUNT)
    found = ScanControl._find_last_scan_parameters(scan_name, entries)
    if found is not None or len(entries) < RECENT_SCAN_HISTORY_COUNT:
        return found
    return ScanControl._find_last_scan_parameters(scan_name, window(MAX_HISTORY_LOOKBACK))
