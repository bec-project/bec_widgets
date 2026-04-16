from __future__ import annotations

import ast
import importlib
import inspect
import os
from dataclasses import dataclass
from functools import lru_cache
from importlib import util as importlib_util
from typing import TYPE_CHECKING, Callable, Iterable

if TYPE_CHECKING:  # pragma: no cover
    from bec_widgets.utils.bec_connector import BECConnector
    from bec_widgets.utils.bec_widget import BECWidget
    from bec_widgets.widgets.containers.auto_update.auto_updates import AutoUpdates

_DISCOVERY_BASE_NAMES = frozenset({"BECConnector", "BECWidget", "ViewBase"})


def get_plugin_widgets() -> dict[str, "BECConnector"]:
    """
    Get all available widgets from the plugin directory. Widgets are classes that inherit from BECConnector.
    The plugins are provided through python plugins and specified in the respective pyproject.toml file using
    the following key:

        [project.entry-points."bec.widgets.user_widgets"]
        plugin_widgets = "path.to.plugin.module"

    e.g.
        [project.entry-points."bec.widgets.user_widgets"]
        plugin_widgets = "pxiii_bec.bec_widgets.widgets"

        assuming that the widgets module for the package pxiii_bec is located at pxiii_bec/bec_widgets/widgets and
        contains the widgets to be loaded within the pxiii_bec/bec_widgets/widgets/__init__.py file.

    Returns:
        dict[str, BECConnector]: A dictionary of widget names and their respective classes.
    """
    from bec_lib.plugin_helper import _get_available_plugins

    modules = _get_available_plugins("bec.widgets.user_widgets")
    loaded_plugins = {}
    for module in modules:
        mods = inspect.getmembers(module, predicate=_filter_plugins)
        for name, mod_cls in mods:
            if name in loaded_plugins:
                print(f"Duplicated widgets plugin {name}.")
            loaded_plugins[name] = mod_cls
    return loaded_plugins


def _filter_plugins(obj):
    from bec_widgets.utils.bec_connector import BECConnector

    return inspect.isclass(obj) and issubclass(obj, BECConnector)


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
    obj: type["BECWidget"]
    is_connector: bool = False
    is_widget: bool = False
    is_plugin: bool = False


@dataclass(frozen=True)
class BECClassReference:
    name: str
    module: str


class BECClassContainer:
    def __init__(self, initial: Iterable[BECClassInfo] = ()):
        self._collection: list[BECClassInfo] = list(initial)

    def __repr__(self):
        return str(list(cl.name for cl in self.collection))

    def __iter__(self):
        return self._collection.__iter__()

    def __add__(self, other: BECClassContainer):
        return BECClassContainer((*self, *(c for c in other if c.name not in self.names)))

    def as_dict(self, ignores: list[str] | None = None) -> dict[str, type["BECWidget"]]:
        """get a dict of {name: Type} for all the entries in the collection.

        Args:
            ignores(list[str]): a list of class names to exclude from the dictionary."""
        ignore_set = set(ignores or ())
        return {c.name: c.obj for c in self if c.name not in ignore_set}

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


def _ast_node_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _class_has_rpc_markers(node: ast.ClassDef) -> bool:
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            target_names = {target.id for target in stmt.targets if isinstance(target, ast.Name)}
            if (
                "PLUGIN" in target_names
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value
            ):
                return True
            if {"RPC_CONTENT_CLASS", "USER_ACCESS"} & target_names:
                return True
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if (
                stmt.target.id == "PLUGIN"
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value
            ):
                return True
            if stmt.target.id in {"RPC_CONTENT_CLASS", "USER_ACCESS"}:
                return True
    return False


def _class_is_candidate(node: ast.ClassDef) -> bool:
    base_names = {_ast_node_name(base) for base in node.bases}
    return bool(_DISCOVERY_BASE_NAMES & base_names) or _class_has_rpc_markers(node)


def _candidate_top_level_class_names(path: str) -> list[str]:
    with open(path, encoding="utf-8") as file_handle:
        module = ast.parse(file_handle.read(), filename=path)
    return [
        node.name
        for node in module.body
        if isinstance(node, ast.ClassDef) and _class_is_candidate(node)
    ]


@lru_cache(maxsize=64)
def _find_package_roots(module_name: str) -> tuple[str, ...]:
    spec = importlib_util.find_spec(module_name)
    if spec is None:
        raise ModuleNotFoundError(module_name)

    package_roots = tuple(spec.submodule_search_locations or ())
    if package_roots:
        return package_roots
    if spec.origin:
        return (os.path.dirname(spec.origin),)
    raise ModuleNotFoundError(module_name)


def _discover_class_references_from_roots(
    module_prefix: str,
    package_roots: Iterable[str],
    *,
    file_name_filter: Callable[[str], bool],
    candidate_filter: Callable[[ast.ClassDef], bool],
) -> tuple[BECClassReference, ...]:
    references: list[BECClassReference] = []
    seen_names: set[str] = set()

    for package_root in package_roots:
        for root, _, files in sorted(os.walk(package_root)):
            for file_name in sorted(files):
                if not file_name_filter(file_name):
                    continue
                path = os.path.join(root, file_name)
                with open(path, encoding="utf-8") as file_handle:
                    module = ast.parse(file_handle.read(), filename=path)
                rel_path = os.path.relpath(path, package_root).removesuffix(".py")
                module_name = ".".join([module_prefix, *rel_path.split(os.sep)])
                for node in module.body:
                    if not isinstance(node, ast.ClassDef) or not candidate_filter(node):
                        continue
                    if node.name in seen_names:
                        continue
                    references.append(BECClassReference(name=node.name, module=module_name))
                    seen_names.add(node.name)

    return tuple(references)


def _iter_candidate_modules(repo_name: str, package: str) -> Iterable[tuple[str, str, list[str]]]:
    try:
        package_roots = _find_package_roots(f"{repo_name}.{package}")
    except ModuleNotFoundError:
        return ()

    modules: list[tuple[str, str, list[str]]] = []
    for directory in package_roots:
        for root, _, files in sorted(os.walk(directory)):
            for file_name in sorted(files):
                if (
                    not file_name.endswith(".py")
                    or file_name.startswith("__")
                    or file_name.startswith("register_")
                    or file_name.endswith("_plugin.py")
                ):
                    continue
                path = os.path.join(root, file_name)
                rel_dir = os.path.dirname(os.path.relpath(path, directory))
                module_name = (
                    file_name.removesuffix(".py")
                    if rel_dir in ("", ".")
                    else ".".join(rel_dir.split(os.sep) + [file_name.removesuffix(".py")])
                )
                class_names = _candidate_top_level_class_names(path)
                if class_names:
                    modules.append((f"{repo_name}.{package}.{module_name}", path, class_names))
    return tuple(modules)


def _collect_classes_from_package(repo_name: str, package: str) -> BECClassContainer:
    """Collect classes from a package subtree (for example ``widgets`` or ``applications``)."""
    collection = BECClassContainer()
    for module_name, path, _ in _iter_candidate_modules(repo_name, package):
        from qtpy.QtWidgets import QWidget

        from bec_widgets.utils.bec_connector import BECConnector
        from bec_widgets.utils.bec_widget import BECWidget

        module = importlib.import_module(module_name)
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module.__name__:
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


def _build_ast_inheritance_map(
    repo_name: str, packages: tuple[str, ...]
) -> dict[str, tuple[str, set[str]]]:
    """
    Walk all candidate modules in the given packages and return a map of:
        class_name -> (module_name, {direct_base_names})

    This is used for the transitive-closure widget discovery so that subclasses
    of discovered widget bases are themselves discoverable without needing to
    repeat ``PLUGIN = True`` on every intermediate or leaf class.
    """
    mapping: dict[str, tuple[str, set[str]]] = {}
    for package in packages:
        try:
            package_roots = _find_package_roots(f"{repo_name}.{package}")
        except ModuleNotFoundError:
            continue
        for directory in package_roots:
            for root, _, files in sorted(os.walk(directory)):
                for file_name in sorted(files):
                    if (
                        not file_name.endswith(".py")
                        or file_name.startswith("__")
                        or file_name.startswith("register_")
                        or file_name.endswith("_plugin.py")
                    ):
                        continue
                    path = os.path.join(root, file_name)
                    rel_dir = os.path.dirname(os.path.relpath(path, directory))
                    module_name = (
                        file_name.removesuffix(".py")
                        if rel_dir in ("", ".")
                        else ".".join(rel_dir.split(os.sep) + [file_name.removesuffix(".py")])
                    )
                    full_module = f"{repo_name}.{package}.{module_name}"
                    with open(path, encoding="utf-8") as fh:
                        tree = ast.parse(fh.read(), filename=path)
                    for node in tree.body:
                        if not isinstance(node, ast.ClassDef):
                            continue
                        base_names = {_ast_node_name(b) for b in node.bases} - {None}
                        mapping[node.name] = (full_module, base_names)  # type: ignore[arg-type]
    return mapping


@lru_cache(maxsize=32)
def _cached_custom_class_references(
    repo_name: str, packages: tuple[str, ...]
) -> tuple[BECClassReference, ...]:
    """Discover widget/connector class references using a transitive-closure AST scan.

    The first pass identifies classes that directly inherit from
    ``_DISCOVERY_BASE_NAMES`` or carry explicit RPC markers (``PLUGIN``,
    ``USER_ACCESS``, ``RPC_CONTENT_CLASS``).  Subsequent passes treat every
    newly found class name as an additional base name, so subclasses of
    subclasses are discovered automatically — without requiring each
    intermediate class to repeat ``PLUGIN = True``.
    """
    inheritance_map = _build_ast_inheritance_map(repo_name, packages)

    # Seed with _class_has_rpc_markers — we need the AST nodes for that check.
    # Re-parse only to identify initial RPC-marker classes; inheritance_map
    # already has everything else we need.
    rpc_marker_names: set[str] = set()
    for package in packages:
        try:
            package_roots = _find_package_roots(f"{repo_name}.{package}")
        except ModuleNotFoundError:
            continue
        for directory in package_roots:
            for root, _, files in sorted(os.walk(directory)):
                for file_name in sorted(files):
                    if (
                        not file_name.endswith(".py")
                        or file_name.startswith("__")
                        or file_name.startswith("register_")
                        or file_name.endswith("_plugin.py")
                    ):
                        continue
                    path = os.path.join(root, file_name)
                    with open(path, encoding="utf-8") as fh:
                        tree = ast.parse(fh.read(), filename=path)
                    for node in tree.body:
                        if isinstance(node, ast.ClassDef) and _class_has_rpc_markers(node):
                            rpc_marker_names.add(node.name)

    # Transitive closure: start with known base names + RPC-marker classes,
    # then repeatedly add classes whose direct bases are already known.
    known: set[str] = set(_DISCOVERY_BASE_NAMES) | rpc_marker_names
    changed = True
    while changed:
        changed = False
        for class_name, (_, bases) in inheritance_map.items():
            if class_name not in known and bases & known:
                known.add(class_name)
                changed = True

    # Build the final list of references, preserving first-seen order and
    # keeping only classes that are in the inheritance map (i.e. have a module).
    references: list[BECClassReference] = []
    seen_names: set[str] = set()
    for class_name, (module_name, bases) in inheritance_map.items():
        if class_name not in known:
            continue
        if class_name in seen_names:
            continue
        # Only emit if the class is actually a candidate (not just a raw base)
        if class_name in _DISCOVERY_BASE_NAMES:
            continue
        references.append(BECClassReference(name=class_name, module=module_name))
        seen_names.add(class_name)
    return tuple(references)


def get_custom_class_references(
    repo_name: str, packages: tuple[str, ...] | None = None, *, use_cache: bool = True
) -> list[BECClassReference]:
    selected_packages = packages or ("widgets",)
    if use_cache:
        return list(_cached_custom_class_references(repo_name, tuple(selected_packages)))
    _cached_custom_class_references.cache_clear()
    return list(_cached_custom_class_references(repo_name, tuple(selected_packages)))


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
