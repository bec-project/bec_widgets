"""Helpers for translating BEC scan metadata into ScanControl UI configuration."""

from __future__ import annotations

import re
from typing import Any

AnnotationValue = str | dict[str, Any] | list[Any] | None
ScanArgumentMetadata = dict[str, Any]
SignatureEntry = dict[str, Any]
ScanInputConfig = dict[str, Any]
ScanInfo = dict[str, Any]
ScanUIConfig = dict[str, Any]

SUPPORTED_SCAN_INPUT_TYPES = {"device", "DeviceBase", "float", "int", "bool", "str"}


class ScanInfoAdapter:
    """Normalize available-scan payloads into the structure consumed by ``ScanControl``."""

    @staticmethod
    def has_scan_ui_config(scan_info: ScanInfo) -> bool:
        """Check whether a scan exposes enough metadata to build a UI.

        Args:
            scan_info (ScanInfo): Available-scan payload for one scan.

        Returns:
            bool: ``True`` when a supported GUI metadata field is present.
        """
        if not (
            scan_info.get("gui_visibility")
            or scan_info.get("gui_config")
            or scan_info.get("gui_visualization")
            or scan_info.get("signature")
        ):
            return False

        gui_config = ScanInfoAdapter().build_scan_ui_config(scan_info)
        return not ScanInfoAdapter.unsupported_inputs(gui_config)

    @staticmethod
    def is_supported_input_type(input_type: AnnotationValue) -> bool:
        """Return whether ``ScanGroupBox`` has a widget for this serialized type."""
        return (
            isinstance(input_type, str)
            and input_type in SUPPORTED_SCAN_INPUT_TYPES
            or isinstance(input_type, dict)
            and "Literal" in input_type
        )

    @staticmethod
    def unsupported_inputs(gui_config: ScanUIConfig) -> list[ScanInputConfig]:
        """Return input configs that cannot be rendered by ``ScanGroupBox``."""
        inputs = []
        arg_group = gui_config.get("arg_group")
        if arg_group:
            inputs.extend(arg_group.get("inputs", []))
        for group in gui_config.get("kwarg_groups", []):
            inputs.extend(group.get("inputs", []))
        return [
            input_config
            for input_config in inputs
            if not ScanInfoAdapter.is_supported_input_type(input_config.get("type"))
        ]

    @staticmethod
    def format_display_name(name: str) -> str:
        """Convert a parameter name into a user-facing label.

        Args:
            name (str): Raw parameter name.

        Returns:
            str: Formatted display label such as ``Exp Time``.
        """
        parts = re.split(r"(_|\d+)", name)
        return " ".join(part.capitalize() for part in parts if part.isalnum()).strip()

    @staticmethod
    def resolve_tooltip(scan_argument: ScanArgumentMetadata) -> str | None:
        """Resolve the tooltip text from parsed ``ScanArgument`` metadata.

        Args:
            scan_argument (ScanArgumentMetadata): Parsed ``ScanArgument`` metadata.

        Returns:
            str | None: Explicit tooltip text if provided, otherwise the description fallback.
        """
        return scan_argument.get("tooltip") or scan_argument.get("description")

    @staticmethod
    def parse_annotation(
        annotation: AnnotationValue,
    ) -> tuple[AnnotationValue, ScanArgumentMetadata]:
        """Extract the serialized base annotation and ``ScanArgument`` metadata.

        Args:
            annotation (AnnotationValue): Serialized annotation payload from BEC.

        Returns:
            tuple[AnnotationValue, ScanArgumentMetadata]: The unwrapped annotation and parsed
            ``ScanArgument`` metadata.
        """
        scan_argument: ScanArgumentMetadata = {}
        if isinstance(annotation, list):
            annotation = next(
                (entry for entry in annotation if entry != "NoneType"),
                annotation[0] if annotation else "_empty",
            )
        if isinstance(annotation, dict) and "Annotated" in annotation:
            annotated = annotation["Annotated"]
            annotation = annotated.get("type", "_empty")
            scan_argument = annotated.get("metadata", {}).get("ScanArgument", {}) or {}
        return annotation, scan_argument

    @staticmethod
    def scan_arg_type_from_annotation(annotation: AnnotationValue) -> AnnotationValue:
        """Normalize an annotation value to the widget type expected by ``ScanControl``.

        Args:
            annotation (AnnotationValue): Serialized or parsed annotation value.

        Returns:
            AnnotationValue: The normalized type identifier used by the widget layer.
        """
        if isinstance(annotation, dict):
            return annotation
        if annotation in ("_empty", None):
            return "str"
        return annotation

    def scan_input_from_signature(
        self, param: SignatureEntry, arg: bool = False
    ) -> ScanInputConfig:
        """Build one ScanControl input description from a signature entry.

        Args:
            param (SignatureEntry): Serialized signature entry.
            arg (bool): Whether the parameter belongs to the positional arg bundle.

        Returns:
            ScanInputConfig: Normalized input configuration for ``ScanControl``.
        """
        annotation, scan_argument = self.parse_annotation(param.get("annotation"))
        return self._build_scan_input(
            name=param["name"],
            annotation=annotation,
            scan_argument=scan_argument,
            arg=arg,
            default=None if arg else param.get("default", None),
        )

    def scan_input_from_arg_input(
        self, name: str, item_type: AnnotationValue, signature_by_name: dict[str, SignatureEntry]
    ) -> ScanInputConfig:
        """Build one arg-bundle input description from ``arg_input`` metadata.

        Args:
            name (str): Argument name from ``arg_input``.
            item_type (AnnotationValue): Serialized argument type from ``arg_input``.
            signature_by_name (dict[str, SignatureEntry]): Signature entries indexed by
                parameter name.

        Returns:
            ScanInputConfig: Normalized input configuration for one arg-bundle field.
        """
        if name in signature_by_name:
            scan_input = self.scan_input_from_signature(signature_by_name[name], arg=True)
            scan_input["type"] = self.scan_arg_type_from_annotation(
                self.parse_annotation(signature_by_name[name].get("annotation"))[0]
            )
        else:
            annotation, scan_argument = self.parse_annotation(item_type)
            scan_input = self._build_scan_input(
                name=name,
                annotation=annotation,
                scan_argument=scan_argument,
                arg=True,
                default=None,
            )
        if scan_input["type"] in ("_empty", None):
            scan_input["type"] = item_type
        return scan_input

    def _build_scan_input(
        self,
        name: str,
        annotation: AnnotationValue,
        scan_argument: ScanArgumentMetadata,
        *,
        arg: bool,
        default: Any,
    ) -> ScanInputConfig:
        """Build one normalized ScanControl input configuration.

        Args:
            name (str): Parameter name.
            annotation (AnnotationValue): Parsed annotation value.
            scan_argument (ScanArgumentMetadata): Parsed ``ScanArgument`` metadata.
            arg (bool): Whether the parameter belongs to the positional arg bundle.
            default (Any): Default value for the parameter.

        Returns:
            ScanInputConfig: Normalized input configuration.
        """
        return {
            "arg": arg,
            "name": name,
            "type": self.scan_arg_type_from_annotation(annotation),
            "display_name": scan_argument.get("display_name") or self.format_display_name(name),
            "tooltip": self.resolve_tooltip(scan_argument),
            "default": default,
            "expert": scan_argument.get("expert", False),
            "hidden": scan_argument.get("hidden", False),
            "precision": scan_argument.get("precision"),
            "units": scan_argument.get("units"),
            "reference_units": scan_argument.get("reference_units"),
            "gt": scan_argument.get("gt"),
            "ge": scan_argument.get("ge"),
            "lt": scan_argument.get("lt"),
            "le": scan_argument.get("le"),
            "alternative_group": scan_argument.get("alternative_group"),
        }

    def build_scan_ui_config(self, scan_info: ScanInfo) -> ScanUIConfig:
        """Normalize one available-scan entry into the widget UI configuration.

        Args:
            scan_info (ScanInfo): Available-scan payload for one scan.

        Returns:
            ScanUIConfig: Legacy group structure consumed by ``ScanControl`` and
            ``ScanGroupBox``.
        """
        gui_visualization = (
            scan_info.get("gui_visualization") or scan_info.get("gui_visibility") or {}
        )
        if not gui_visualization and scan_info.get("gui_config"):
            return scan_info["gui_config"]

        signature = scan_info.get("signature", [])
        signature_by_name = {entry["name"]: entry for entry in signature}

        arg_group = None
        arg_input = scan_info.get("arg_input", {})
        if isinstance(arg_input, dict) and arg_input:
            bundle_size = scan_info.get("arg_bundle_size", {})
            inputs = [
                self.scan_input_from_arg_input(name, item_type, signature_by_name)
                for name, item_type in arg_input.items()
            ]
            arg_group = {
                "name": "Scan Arguments",
                "bundle": bundle_size.get("bundle"),
                "arg_inputs": arg_input,
                "inputs": inputs,
                "min": bundle_size.get("min"),
                "max": bundle_size.get("max"),
            }

        kwarg_groups = []
        arg_names = set(arg_input) if isinstance(arg_input, dict) else set()
        visible_kwarg_names = set()
        for group_name, input_names in gui_visualization.items():
            inputs = []
            for input_name in input_names:
                if input_name in arg_names or input_name not in signature_by_name:
                    continue
                if input_name in visible_kwarg_names:
                    continue
                param = signature_by_name[input_name]
                if param.get("kind") in ("VAR_POSITIONAL", "VAR_KEYWORD"):
                    continue
                scan_input = self.scan_input_from_signature(param)
                if scan_input.get("hidden"):
                    continue
                inputs.append(scan_input)
                visible_kwarg_names.add(input_name)
            if inputs:
                kwarg_groups.append({"name": group_name, "inputs": inputs})

        return {
            "scan_class_name": scan_info.get("class"),
            "arg_group": arg_group,
            "kwarg_groups": kwarg_groups,
        }
