from __future__ import annotations

import ast
import importlib
import inspect
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtWidgets import QWidget

    from bec_widgets.utils.bec_connector import BECConnector
    from bec_widgets.utils.bec_widget import BECWidget
    from bec_widgets.widgets.containers.auto_update.auto_updates import AutoUpdates


def get_plugin_auto_updates() -> dict[str, type[AutoUpdates]]:
    """
    Get all available auto update classes from the plugin directory. AutoUpdates must inherit from AutoUpdate and be
    placed in the plugin repository's bec_widgets/auto_updates directory. The entry point for the auto updates is
    specified in the respective pyproject.toml file using the following key:
        [project.entry-points."bec.widgets.auto_updates"]
        plugin_widgets_update = "<beamline_name>.bec_widgets.auto_updates"

    e.g.
        [project.entry-points."bec.widgets.auto_updates"]
        plugin_widgets_update = "pxiii_bec.bec_widgets.auto_updates"

    Returns:
        dict[str, AutoUpdates]: A dictionary of widget names and their respective classes.
    """
    from bec_lib.plugin_helper import _get_available_plugins

    modules = _get_available_plugins("bec.widgets.auto_updates")
    loaded_plugins = {}
    for module in modules:
        mods = inspect.getmembers(module, predicate=_filter_auto_updates)
        for name, mod_cls in mods:
            if name in loaded_plugins:
                print(f"Duplicated auto update {name}.")
            loaded_plugins[name] = mod_cls
    return loaded_plugins


def _filter_auto_updates(obj):
    from bec_widgets.widgets.containers.auto_update.auto_updates import AutoUpdates

    return (
        inspect.isclass(obj) and issubclass(obj, AutoUpdates) and not obj.__name__ == "AutoUpdates"
    )


@dataclass
class BECClassInfo:
    name: str
    module: str
    file: str
    obj: type[BECWidget]
    is_connector: bool = False
    is_widget: bool = False
    is_plugin: bool = False


class BECClassContainer:
    def __init__(self, initial: Iterable[BECClassInfo] = []):
        self._collection: list[BECClassInfo] = list(initial)

    def __repr__(self):
        return str(list(cl.name for cl in self.collection))

    def __iter__(self):
        return self._collection.__iter__()

    def __add__(self, other: BECClassContainer):
        return BECClassContainer((*self, *(c for c in other if c.name not in self.names)))

    def as_dict(self, ignores: list[str] = []) -> dict[str, type[BECWidget]]:
        """get a dict of {name: Type} for all the entries in the collection.

        Args:
            ignores(list[str]): a list of class names to exclude from the dictionary."""
        return {c.name: c.obj for c in self if c.name not in ignores}

    def add_class(self, class_info: BECClassInfo):
        """
        Add a class to the collection.

        Args:
            class_info(BECClassInfo): The class information
        """
        self.collection.append(class_info)

    @property
    def names(self):
        """Return a list of class names"""
        return [c.name for c in self]

    @property
    def collection(self):
        """Get the collection of classes."""
        return self._collection

    @property
    def connector_classes(self):
        """Get all connector classes."""
        return [info.obj for info in self.collection if info.is_connector]

    @property
    def top_level_classes(self):
        """Get all top-level classes."""
        return [info.obj for info in self.collection if info.is_plugin]

    @property
    def plugins(self):
        """Get all plugins. These are all classes that are on the top level and are widgets."""
        return [info.obj for info in self.collection if info.is_widget and info.is_plugin]

    @property
    def widgets(self):
        """Get all widgets. These are all classes inheriting from BECWidget."""
        return [info.obj for info in self.collection if info.is_widget]

    @property
    def rpc_top_level_classes(self):
        """Get all top-level classes that are RPC-enabled. These are all classes that users can choose from."""
        return [info.obj for info in self.collection if info.is_plugin and info.is_connector]

    @property
    def classes(self):
        """Get all classes."""
        return [info.obj for info in self.collection]


def _collect_classes_from_package(repo_name: str, package: str) -> BECClassContainer:
    """Collect classes from a package subtree (for example ``widgets`` or ``applications``)."""
    from qtpy.QtWidgets import QWidget

    from bec_widgets.utils.bec_connector import BECConnector
    from bec_widgets.utils.bec_widget import BECWidget

    collection = BECClassContainer()
    try:
        anchor_module = importlib.import_module(f"{repo_name}.{package}")
    except ModuleNotFoundError as exc:
        # Some plugin repositories expose only one subtree. Skip gracefully if it does not exist.
        if exc.name == f"{repo_name}.{package}":
            return collection
        raise

    directory = os.path.dirname(anchor_module.__file__)
    for root, _, files in sorted(os.walk(directory)):
        for file in files:
            if not file.endswith(".py") or file.startswith("__"):
                continue

            path = os.path.join(root, file)
            rel_dir = os.path.dirname(os.path.relpath(path, directory))
            if rel_dir in ("", "."):
                module_name = file.split(".")[0]
            else:
                module_name = ".".join(rel_dir.split(os.sep) + [file.split(".")[0]])

            module = importlib.import_module(f"{repo_name}.{package}.{module_name}")

            for name in dir(module):
                obj = getattr(module, name)
                if not isinstance(obj, type):
                    continue
                if not hasattr(obj, "__module__") or obj.__module__ != module.__name__:
                    continue
                class_info = BECClassInfo(name=name, module=module.__name__, file=path, obj=obj)
                if issubclass(obj, BECConnector):
                    class_info.is_connector = True
                if issubclass(obj, QWidget) or issubclass(obj, BECWidget):
                    class_info.is_widget = True
                if hasattr(obj, "PLUGIN") and obj.PLUGIN:
                    class_info.is_plugin = True
                collection.add_class(class_info)
    return collection


def get_custom_classes(
    repo_name: str, packages: tuple[str, ...] | None = None
) -> BECClassContainer:
    """
    Get all relevant classes for RPC/CLI in the specified repository.

    By default, discovery is limited to ``<repo>.widgets`` for backward compatibility.
    Additional package subtrees (for example ``applications``) can be included explicitly.

    Args:
        repo_name(str): The name of the repository.
        packages(tuple[str, ...] | None): Optional tuple of package names to scan. Defaults to ("widgets",) for backward compatibility.

    Returns:
        BECClassContainer: Container with collected class information.
    """
    selected_packages = packages or ("widgets",)
    collection = BECClassContainer()
    for package in selected_packages:
        collection += _collect_classes_from_package(repo_name, package)
    return collection


def _get_designer_registry() -> dict[str, tuple[str, str]]:
    from bec_widgets.cli.designer_plugins import designer_plugins

    return designer_plugins


def _resolve_widget_from_registry(import_path: str, widget_name: str) -> type[QWidget]:
    widget = importlib.import_module(import_path)
    return getattr(widget, widget_name)


def designer_plugin_exists(name: str) -> bool:
    from bec_widgets.utils.bec_plugin_helper import get_plugin_designer_registry

    internal_registry = _get_designer_registry()
    external_registry = get_plugin_designer_registry()
    return name in internal_registry or name in external_registry


def get_designer_plugin(name: str, raise_on_missing: bool = True) -> type[QWidget] | None:
    from bec_widgets.utils.bec_plugin_helper import get_plugin_designer_registry

    internal_registry = _get_designer_registry()
    external_registry = get_plugin_designer_registry()
    if name in external_registry:
        import_path, widget_name = external_registry[name]
        return _resolve_widget_from_registry(import_path, widget_name)
    if name in internal_registry:
        import_path, widget_name = internal_registry[name]
        return _resolve_widget_from_registry(import_path, widget_name)

    if raise_on_missing:
        raise ValueError(
            f"Designer plugin {name} not found in either internal or external registry."
        )
    return None


def rpc_widget_registry_from_source(path: str | Path) -> dict[str, tuple[str, str]]:
    """Parse a generated RPC client module and return its widget registry."""
    source_path = Path(path)
    module_node = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    registry = {}
    for node in module_node.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "_IMPORT_MODULE"
                for target in item.targets
            ):
                continue
            if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                registry[node.name] = (item.value.value, node.name)
            break
    return registry


@lru_cache
def get_rpc_widget_registry() -> dict[str, tuple[str, str]]:
    client_path = Path(__file__).resolve().parents[1] / "cli" / "client.py"
    return rpc_widget_registry_from_source(client_path)


@lru_cache
def rpc_widget_registry() -> dict[str, tuple[str, str]]:
    from bec_widgets.utils.bec_plugin_helper import get_plugin_rpc_widget_registry

    internal_registry = get_rpc_widget_registry()
    external_registry = get_plugin_rpc_widget_registry()
    return {**external_registry, **internal_registry}


def get_rpc_widget(name: str, raise_on_missing: bool = True) -> type[QWidget] | None:
    registry = rpc_widget_registry()
    if name in registry:
        import_path, widget_name = registry[name]
        return _resolve_widget_from_registry(import_path, widget_name)

    if raise_on_missing:
        raise ValueError(f"RPC widget {name} not found in registry.")
    return None
