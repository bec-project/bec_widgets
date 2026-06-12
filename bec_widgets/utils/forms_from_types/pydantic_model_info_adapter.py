from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from bec_lib.scan_args import ScanArgument
from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from bec_widgets.utils.scan_arg_metadata import ui_config_from_metadata

NUMERIC_BOUND_KEYS = {"gt", "ge", "lt", "le"}


def pydantic_model_input_configs(model: type[BaseModel]) -> list[dict[str, Any]]:
    """Return scan-control-style field items for a Pydantic model."""
    configs = []
    for name, info in model.model_fields.items():
        metadata: dict[str, Any] = {}
        for entry in info.metadata:
            if isinstance(entry, ScanArgument):
                metadata.update(entry.model_dump(exclude_none=True))
                continue
            for key in NUMERIC_BOUND_KEYS:
                value = getattr(entry, key, None)
                if value is not None:
                    metadata.setdefault(key, value)

        if isinstance(info.json_schema_extra, Mapping):
            metadata.update(dict(info.json_schema_extra))

        if info.description and metadata.get("description") is None:
            metadata["description"] = info.description

        default: Any
        if info.default is not PydanticUndefined:
            default = info.default
        elif info.default_factory is not None:
            default = info.get_default(call_default_factory=True)
        else:
            default = None

        display_name = metadata.get("display_name") or info.title
        if display_name is None:
            display_name = name.replace("_", " ").capitalize()

        item = ui_config_from_metadata(
            name=name, metadata=metadata, default=default, display_name=display_name
        )
        item.update({key: value for key, value in metadata.items() if key not in item})
        configs.append(item)

    return configs
