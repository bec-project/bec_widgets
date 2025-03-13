from __future__ import annotations

import importlib.metadata
import inspect
import pkgutil
from importlib import util as importlib_util
from importlib.machinery import FileFinder, ModuleSpec, SourceFileLoader
from types import ModuleType
from typing import Generator

from bec_widgets.utils.bec_widget import BECWidget


def _submodule_specs(module: ModuleType) -> tuple[ModuleSpec | None, ...]:
    """Return specs for all submodules of the given module."""
    return tuple(
        module_info.module_finder.find_spec(module_info.name)
        for module_info in pkgutil.iter_modules(module.__path__)
        if isinstance(module_info.module_finder, FileFinder)
    )


def _loaded_submodules_from_specs(
    submodule_specs: tuple[ModuleSpec | None, ...]
) -> Generator[ModuleType, None, None]:
    """Load all submodules from the given specs."""
    for submodule in (
        importlib_util.module_from_spec(spec) for spec in submodule_specs if spec is not None
    ):
        assert isinstance(
            submodule.__loader__, SourceFileLoader
        ), "Module found from FileFinder should have SourceFileLoader!"
        submodule.__loader__.exec_module(submodule)
        yield submodule


def _submodule_by_name(module: ModuleType, name: str):
    for submod in _loaded_submodules_from_specs(_submodule_specs(module)):
        if submod.__name__ == name:
            return submod
    return None


def _get_widgets_from_module(module: ModuleType) -> dict[str, "type[BECWidget]"]:
    """Find any BECWidget subclasses in the given module and return them with their names."""
    from bec_widgets.utils.bec_widget import BECWidget  # avoid circular import

    return dict(
        inspect.getmembers(
            module,
            predicate=lambda item: inspect.isclass(item)
            and issubclass(item, BECWidget)
            and item is not BECWidget,
        )
    )


def _all_widgets_from_all_submods(module):
    """Recursively load submodules, find any BECWidgets, and return them all as a flat dict."""
    widgets = _get_widgets_from_module(module)
    if not hasattr(module, "__path__"):
        return widgets
    for submod in _loaded_submodules_from_specs(_submodule_specs(module)):
        widgets.update(_all_widgets_from_all_submods(submod))
    return widgets


def user_widget_plugin() -> ModuleType | None:
    plugins = importlib.metadata.entry_points(group="bec.widgets.user_widgets")  # type: ignore
    return None if len(plugins) == 0 else tuple(plugins)[0].load()


def get_plugin_client_module() -> ModuleType | None:
    """If there is a plugin repository installed, return the client module."""
    return _submodule_by_name(plugin, "client") if (plugin := user_widget_plugin()) else None


def get_all_plugin_widgets() -> dict[str, "type[BECWidget]"]:
    """If there is a plugin repository installed, load all widgets from it."""
    if plugin := user_widget_plugin():
        return _all_widgets_from_all_submods(plugin)
    else:
        return {}


if __name__ == "__main__":  # pragma: no cover
    #  print(get_all_plugin_widgets())
    client = get_plugin_client_module()
    ...
