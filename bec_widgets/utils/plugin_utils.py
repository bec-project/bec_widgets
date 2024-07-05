import importlib
import inspect
import os
from typing import Literal

from bec_lib.plugin_helper import _get_available_plugins
from qtpy.QtWidgets import QGraphicsWidget, QWidget

from bec_widgets.utils import BECConnector
from bec_widgets.utils.bec_widget import BECWidget


def get_plugin_widgets() -> dict[str, BECConnector]:
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
    modules = _get_available_plugins("bec.widgets.user_widgets")
    loaded_plugins = {}
    print(modules)
    for module in modules:
        mods = inspect.getmembers(module, predicate=_filter_plugins)
        for name, mod_cls in mods:
            if name in loaded_plugins:
                print(f"Duplicated widgets plugin {name}.")
            loaded_plugins[name] = mod_cls
    return loaded_plugins


def _filter_plugins(obj):
    return inspect.isclass(obj) and issubclass(obj, BECConnector)


def get_rpc_classes(
    repo_name: str,
) -> dict[Literal["connector_classes", "top_level_classes"], list[type]]:
    """
    Get all RPC-enabled classes in the specified repository.

    Args:
        repo_name(str): The name of the repository.

    Returns:
        dict: A dictionary with keys "connector_classes" and "top_level_classes" and values as lists of classes.
    """
    connector_classes = []
    top_level_classes = []
    anchor_module = importlib.import_module(f"{repo_name}.widgets")
    directory = os.path.dirname(anchor_module.__file__)
    for root, _, files in sorted(os.walk(directory)):
        for file in files:
            if not file.endswith(".py") or file.startswith("__"):
                continue

            path = os.path.join(root, file)
            subs = os.path.dirname(os.path.relpath(path, directory)).split("/")
            if len(subs) == 1 and not subs[0]:
                module_name = file.split(".")[0]
            else:
                module_name = ".".join(subs + [file.split(".")[0]])

            module = importlib.import_module(f"{repo_name}.widgets.{module_name}")

            for name in dir(module):
                obj = getattr(module, name)
                if not hasattr(obj, "__module__") or obj.__module__ != module.__name__:
                    continue
                if isinstance(obj, type) and issubclass(obj, BECWidget):
                    connector_classes.append(obj)
                    if len(subs) == 1 and (
                        issubclass(obj, QWidget) or issubclass(obj, QGraphicsWidget)
                    ):
                        top_level_classes.append(obj)

    return {"connector_classes": connector_classes, "top_level_classes": top_level_classes}
