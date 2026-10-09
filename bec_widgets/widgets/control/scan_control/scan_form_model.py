"""Toolkit-independent model of the scan parameter form.

The QML and QWidget ports of :class:`ScanControl` both render this model. It turns the scan UI
configuration produced by :class:`ScanInfoAdapter` into groups of typed fields, keeps the entered
text of every field, validates it and converts it into scan ``args`` and ``kwargs``.

Field values are stored as the text the user typed (booleans as ``bool``), so a half-typed
number never loses keystrokes and validation can explain what is wrong.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from qtpy.QtCore import QObject, Signal

from bec_widgets.utils.scan_arg_metadata import device_units

FIELD_TYPES = {"device": "device", "DeviceBase": "device", "float": "float", "int": "int"}
FIELD_TYPES.update({"bool": "bool", "str": "str"})


def field_type(item_type: Any) -> str:
    """Map a scan input type to a form field type."""
    if isinstance(item_type, dict) and "Literal" in item_type:
        return "literal"
    return FIELD_TYPES.get(item_type, "str") if isinstance(item_type, str) else "str"


def literal_options(item_type: Any) -> list[str]:
    """Options of a ``Literal`` input as strings; ``None`` becomes an empty first option."""
    values = list(dict.fromkeys(item_type.get("Literal", [])))
    options = [""] if None in values else []
    options += [str(value) for value in values if value is not None]
    return options


def _format_number(value: Any) -> str:
    if value is None or value == "_empty":
        return ""
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return str(value)


class ScanFormModel(QObject):
    """Fields, values and validation of the scan parameter form.

    Args:
        device_names(Callable[[], list[str]]): Returns the names of selectable devices.
        device_lookup(Callable[[str], Any]): Returns the device object for a name.
        parent: Parent QObject.
    """

    structure_changed = Signal()
    values_changed = Signal()
    device_selected = Signal(str)

    def __init__(
        self,
        device_names: Callable[[], list[str]],
        device_lookup: Callable[[str], Any],
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._device_names = device_names
        self._device_lookup = device_lookup
        self._arg_group: dict | None = None
        self._kwarg_groups: list[dict] = []
        self._bundles = 0
        self._values: dict[str, Any] = {}
        self._last_devices = ""

    # ---- structure -----------------------------------------------------------------------

    def load(self, gui_config: dict | None) -> None:
        """Build the fields of a scan from its UI configuration (empty config clears the form)."""
        gui_config = gui_config or {}
        arg_group = gui_config.get("arg_group")
        self._arg_group = arg_group if arg_group and arg_group.get("inputs") else None
        self._kwarg_groups = [
            group for group in gui_config.get("kwarg_groups", []) if group.get("inputs")
        ]
        self._values = {}
        self._bundles = 0
        if self._arg_group is not None:
            for _ in range(max(1, int(self._arg_group.get("min") or 1))):
                self._append_bundle()
        for group in self._kwarg_groups:
            for item in group["inputs"]:
                self._values[self.kwarg_key(item["name"])] = self._initial_value(item)
        self.structure_changed.emit()
        self._values_updated()

    @staticmethod
    def arg_key(bundle: int, name: str) -> str:
        """Key of an argument field in bundle ``bundle``."""
        return f"args:{bundle}:{name}"

    @staticmethod
    def kwarg_key(name: str) -> str:
        """Key of a keyword argument field."""
        return f"kwargs:{name}"

    @staticmethod
    def _initial_value(item: dict) -> Any:
        kind = field_type(item.get("type"))
        default = item.get("default")
        if default == "_empty":
            default = None
        if kind == "bool":
            return bool(default)
        if kind == "literal":
            options = literal_options(item["type"])
            text = "" if default is None else str(default)
            if text in options:
                return text
            return options[0] if options else ""
        return (
            _format_number(default)
            if kind in ("float", "int")
            else ("" if default is None else str(default))
        )

    def _append_bundle(self) -> None:
        for item in self._arg_group["inputs"]:
            self._values[self.arg_key(self._bundles, item["name"])] = self._initial_value(item)
        self._bundles += 1

    @property
    def has_args(self) -> bool:
        """Whether the scan has a positional argument group."""
        return self._arg_group is not None

    @property
    def bundle_count(self) -> int:
        """Number of rows in the argument group."""
        return self._bundles

    def can_add_bundle(self) -> bool:
        """Whether another argument row may be added."""
        if self._arg_group is None:
            return False
        maximum = self._arg_group.get("max")
        return maximum is None or self._bundles < maximum

    def can_remove_bundle(self) -> bool:
        """Whether an argument row may be removed."""
        if self._arg_group is None:
            return False
        return self._bundles > max(1, int(self._arg_group.get("min") or 1))

    def add_bundle(self) -> bool:
        """Append an argument row. Returns False when the maximum is reached."""
        if not self.can_add_bundle():
            return False
        self._append_bundle()
        self.structure_changed.emit()
        self._values_updated()
        return True

    def remove_bundle(self, index: int | None = None) -> bool:
        """Remove an argument row (the last one by default)."""
        if not self.can_remove_bundle():
            return False
        index = self._bundles - 1 if index is None else index
        if not 0 <= index < self._bundles:
            return False
        names = [item["name"] for item in self._arg_group["inputs"]]
        for bundle in range(index, self._bundles - 1):
            for name in names:
                self._values[self.arg_key(bundle, name)] = self._values[
                    self.arg_key(bundle + 1, name)
                ]
        for name in names:
            self._values.pop(self.arg_key(self._bundles - 1, name), None)
        self._bundles -= 1
        self.structure_changed.emit()
        self._values_updated()
        return True

    def _items(self) -> dict[str, dict]:
        items = {}
        if self._arg_group is not None:
            for bundle in range(self._bundles):
                for item in self._arg_group["inputs"]:
                    items[self.arg_key(bundle, item["name"])] = item
        for group in self._kwarg_groups:
            for item in group["inputs"]:
                items[self.kwarg_key(item["name"])] = item
        return items

    # ---- values --------------------------------------------------------------------------

    def value(self, key: str) -> Any:
        """Raw value of a field (text, or bool for switches)."""
        return self._values.get(key)

    def set_value(self, key: str, value: Any) -> None:
        """Set the raw value of a field."""
        if key not in self._values:
            return
        if isinstance(value, float) and math.isnan(value):
            value = ""
        if self._values[key] == value:
            return
        self._values[key] = value
        self._values_updated()

    def _values_updated(self) -> None:
        self.values_changed.emit()
        devices = " ".join(self.selected_devices())
        if devices != self._last_devices:
            self._last_devices = devices
            self.device_selected.emit(devices)

    def selected_devices(self) -> list[str]:
        """Valid devices chosen in the argument rows, in order."""
        if self._arg_group is None:
            return []
        known = set(self._device_names())
        devices = []
        for bundle in range(self._bundles):
            for item in self._arg_group["inputs"]:
                if field_type(item["type"]) != "device":
                    continue
                name = str(self._values.get(self.arg_key(bundle, item["name"]), "")).strip()
                if name in known:
                    devices.append(name)
        return devices

    # ---- validation and conversion --------------------------------------------------------

    def _parse(self, key: str, item: dict) -> tuple[Any, str]:
        """Return ``(value, error)`` for a field."""
        kind = field_type(item.get("type"))
        raw = self._values.get(key)
        is_arg = key.startswith("args:")
        if kind == "bool":
            return bool(raw), ""
        text = "" if raw is None else str(raw).strip()
        if kind == "device":
            if not text:
                return None, "Select a device" if is_arg else ""
            if text not in self._device_names():
                return None, f"Unknown device '{text}'"
            return text, ""
        if kind == "literal":
            return (text or None), ""
        if kind == "str":
            return text, ""
        if not text:
            default = item.get("default")
            if not is_arg and default not in (None, "_empty"):
                return default, ""
            return None, "Required"
        try:
            number = int(text) if kind == "int" else float(text)
        except ValueError:
            return None, "Enter a whole number" if kind == "int" else "Enter a number"
        for bound, check, message in (
            ("ge", lambda v, b: v >= b, "≥"),
            ("gt", lambda v, b: v > b, ">"),
            ("le", lambda v, b: v <= b, "≤"),
            ("lt", lambda v, b: v < b, "<"),
        ):
            limit = item.get(bound)
            if limit is not None and not check(number, limit):
                return None, f"Must be {message} {_format_number(limit)}"
        return number, ""

    def errors(self) -> dict[str, str]:
        """Error message per field key, only for fields with a problem."""
        errors = {}
        for key, item in self._items().items():
            _value, error = self._parse(key, item)
            if error:
                errors[key] = error
        return errors

    def is_valid(self) -> bool:
        """Whether every field holds a usable value."""
        return not self.errors()

    def args(self, bec_object: bool = True) -> list:
        """Positional arguments, flattened over the rows.

        Args:
            bec_object(bool): Return device objects instead of device names.
        """
        if self._arg_group is None:
            return []
        args = []
        for bundle in range(self._bundles):
            for item in self._arg_group["inputs"]:
                key = self.arg_key(bundle, item["name"])
                value, error = self._parse(key, item)
                if field_type(item["type"]) == "device":
                    if error:
                        value = str(self._values.get(key, ""))
                    elif bec_object and value:
                        value = self._device_lookup(value)
                args.append(value)
        return args

    def kwargs(self) -> dict:
        """Keyword arguments; device fields are passed by name."""
        kwargs = {}
        for group in self._kwarg_groups:
            for item in group["inputs"]:
                key = self.kwarg_key(item["name"])
                value, _error = self._parse(key, item)
                kwargs[item["name"]] = value
        return kwargs

    def set_args(self, args: list) -> None:
        """Fill the argument rows from a flat list, adding rows as needed."""
        if self._arg_group is None or not args:
            return
        names = [item["name"] for item in self._arg_group["inputs"]]
        if not names:
            return
        bundles = max(-(-len(args) // len(names)), int(self._arg_group.get("min") or 1))
        maximum = self._arg_group.get("max")
        if maximum is not None:
            bundles = min(bundles, maximum)
        for key in [key for key in self._values if key.startswith("args:")]:
            del self._values[key]
        self._bundles = 0
        for _ in range(bundles):
            self._append_bundle()
        for index, value in enumerate(args[: bundles * len(names)]):
            bundle, position = divmod(index, len(names))
            item = self._arg_group["inputs"][position]
            self._values[self.arg_key(bundle, item["name"])] = self._to_raw(item, value)
        self.structure_changed.emit()
        self._values_updated()

    def set_kwargs(self, kwargs: dict) -> None:
        """Fill keyword fields from a dict; unknown keys are ignored."""
        changed = False
        for group in self._kwarg_groups:
            for item in group["inputs"]:
                if item["name"] not in kwargs:
                    continue
                key = self.kwarg_key(item["name"])
                raw = self._to_raw(item, kwargs[item["name"]])
                if self._values.get(key) != raw:
                    self._values[key] = raw
                    changed = True
        if changed:
            self.structure_changed.emit()
            self._values_updated()

    @staticmethod
    def _to_raw(item: dict, value: Any) -> Any:
        kind = field_type(item.get("type"))
        if kind == "bool":
            return bool(value)
        if kind == "device":
            return getattr(value, "name", "" if value is None else str(value))
        if value is None:
            return ""
        return _format_number(value) if kind in ("float", "int") else str(value)

    # ---- presentation ---------------------------------------------------------------------

    def _field(self, key: str, item: dict, units_for: Callable[[dict], str]) -> dict:
        kind = field_type(item.get("type"))
        units = units_for(item)
        default = item.get("default")
        placeholder = ""
        if kind in ("float", "int") and default not in (None, "_empty"):
            placeholder = f"default {_format_number(default)}"
        return {
            "key": key,
            "name": item["name"],
            "label": item.get("display_name") or item["name"],
            "kind": kind,
            "value": self._values.get(key),
            "options": literal_options(item["type"]) if kind == "literal" else [],
            "tooltip": item.get("tooltip") or "",
            "units": units,
            "placeholder": placeholder,
        }

    def _units_resolver(self, bundle: int | None) -> Callable[[dict], str]:
        def units_for(item: dict) -> str:
            if item.get("units"):
                return str(item["units"])
            reference = item.get("reference_units")
            if not reference:
                return ""
            candidates = []
            if bundle is not None:
                candidates.append(self.arg_key(bundle, reference))
            candidates.append(self.kwarg_key(reference))
            candidates.append(self.arg_key(0, reference))
            for key in candidates:
                name = self._values.get(key)
                if name and name in self._device_names():
                    return device_units(self._device_lookup(name)) or ""
            return ""

        return units_for

    def groups(self) -> list[dict]:
        """Description of all groups and fields for the renderers."""
        groups = []
        if self._arg_group is not None:
            rows = []
            for bundle in range(self._bundles):
                units_for = self._units_resolver(bundle)
                rows.append(
                    [
                        self._field(self.arg_key(bundle, item["name"]), item, units_for)
                        for item in self._arg_group["inputs"]
                    ]
                )
            groups.append(
                {
                    "id": "args",
                    "title": self._arg_group.get("name") or "Scan arguments",
                    "kind": "args",
                    "rows": rows,
                    "fields": [],
                    "canAdd": self.can_add_bundle(),
                    "canRemove": self.can_remove_bundle(),
                }
            )
        units_for = self._units_resolver(None)
        for index, group in enumerate(self._kwarg_groups):
            groups.append(
                {
                    "id": f"kwargs{index}",
                    "title": group.get("name") or "Parameters",
                    "kind": "kwargs",
                    "rows": [],
                    "fields": [
                        self._field(self.kwarg_key(item["name"]), item, units_for)
                        for item in group["inputs"]
                    ],
                    "canAdd": False,
                    "canRemove": False,
                }
            )
        return groups
