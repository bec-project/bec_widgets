from __future__ import annotations

import importlib.metadata
import inspect
import pkgutil
import traceback
from importlib import util as importlib_util
from importlib.machinery import FileFinder, ModuleSpec, SourceFileLoader
from types import ModuleType
from typing import Generator

from bec_lib.logger import bec_logger

from bec_widgets.utils.plugin_utils import BECClassContainer, BECClassInfo

logger = bec_logger.logger


def _submodule_specs(module: ModuleType) -> tuple[ModuleSpec | None, ...]:
    """Return specs for all submodules of the given module."""
    return tuple(
        module_info.module_finder.find_spec(module_info.name)
        for module_info in pkgutil.iter_modules(module.__path__)
        if isinstance(module_info.module_finder, FileFinder)
    )


def _loaded_submodules_from_specs(
    submodule_specs: tuple[ModuleSpec | None, ...],
) -> Generator[ModuleType, None, None]:
    """Load all submodules from the given specs."""
    for submodule in (
        importlib_util.module_from_spec(spec) for spec in submodule_specs if spec is not None
    ):
        assert isinstance(
            submodule.__loader__, SourceFileLoader
        ), "Module found from FileFinder should have SourceFileLoader!"
        try:
            submodule.__loader__.exec_module(submodule)
        except Exception as e:
            logger.error(
                f"Error loading plugin {submodule}: \n{''.join(traceback.format_exception(e))}"
            )
        yield submodule


def _submodule_by_name(module: ModuleType, name: str):
    for submod in _loaded_submodules_from_specs(_submodule_specs(module)):
        if submod.__name__ == name:
            return submod
    return None


def _get_widgets_from_module(module: ModuleType) -> BECClassContainer:
    """Find any BECWidget subclasses in the given module and return them with their info."""
    from bec_widgets.utils.bec_widget import BECWidget  # avoid circular import

    classes = inspect.getmembers(
        module,
        predicate=lambda item: inspect.isclass(item)
        and issubclass(item, BECWidget)
        and item is not BECWidget,
    )
    return BECClassContainer(
        BECClassInfo(name=k, module=module.__name__, file=module.__loader__.get_filename(), obj=v)
        for k, v in classes
    )


def _all_widgets_from_all_submods(module) -> BECClassContainer:
    """Recursively load submodules, find any BECWidgets, and return them all as a flat dict."""
    widgets = _get_widgets_from_module(module)
    if not hasattr(module, "__path__"):
        return widgets
    for submod in _loaded_submodules_from_specs(_submodule_specs(module)):
        widgets += _all_widgets_from_all_submods(submod)
    return widgets


def user_widget_plugin() -> ModuleType | None:
    plugins = importlib.metadata.entry_points(group="bec.widgets.user_widgets")  # type: ignore
    return None if len(plugins) == 0 else tuple(plugins)[0].load()


def get_plugin_client_module() -> ModuleType | None:
    """If there is a plugin repository installed, return the client module."""
    return _submodule_by_name(plugin, "client") if (plugin := user_widget_plugin()) else None


def get_all_plugin_widgets() -> BECClassContainer:
    """If there is a plugin repository installed, load all widgets from it."""
    if plugin := user_widget_plugin():
        return _all_widgets_from_all_submods(plugin)
    else:
        return BECClassContainer()


if __name__ == "__main__":  # pragma: no cover

    client = get_plugin_client_module()
    print(get_all_plugin_widgets())
    ...
