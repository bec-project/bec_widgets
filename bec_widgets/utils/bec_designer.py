import ast
import importlib.metadata
import importlib.util
import inspect
import itertools
import json
import os
import site
import sys
import sysconfig
from pathlib import Path

from bec_lib.logger import bec_logger
from bec_qthemes import material_icon
from qtpy import PYSIDE6
from qtpy.QtGui import QIcon
from zmq import PLAIN

from bec_widgets.utils.bec_plugin_helper import user_widget_plugin
from bec_widgets.utils.bec_widget import BECWidget

if PYSIDE6:
    from PySide6.scripts.pyside_tool import (
        _extend_path_var,
        init_virtual_env,
        qt_tool_wrapper,
        is_pyenv_python,
        is_virtual_env,
        ui_tool_binary,
    )

import bec_widgets

logger = bec_logger.logger


def designer_material_icon(icon_name: str) -> QIcon:
    """
    Create a QIcon for the BECDesigner with the given material icon name.

    Args:
        icon_name (str): The name of the material icon.

    Returns:
        QIcon: The QIcon for the material icon.
    """
    return QIcon(material_icon(icon_name, filled=True, convert_to_pixmap=True))


def list_editable_packages() -> set[str]:
    """
    List all editable packages in the environment.

    Returns:
        set: A set of paths to editable packages.
    """

    editable_packages = set()

    # Get site-packages directories
    site_packages = site.getsitepackages()
    if hasattr(site, "getusersitepackages"):
        site_packages.append(site.getusersitepackages())

    for dist in importlib.metadata.distributions():
        location = dist.locate_file("").resolve()
        is_editable = all(not str(location).startswith(site_pkg) for site_pkg in site_packages)

        if is_editable:
            editable_packages.add(str(location))

    for packages in site_packages:
        # all dist-info directories in site-packages that contain a direct_url.json file
        dist_info_dirs = Path(packages).rglob("*.dist-info")
        for dist_info_dir in dist_info_dirs:
            direct_url = dist_info_dir / "direct_url.json"
            if not direct_url.exists():
                continue
            # load the json file and get the path to the package
            with open(direct_url, "r", encoding="utf-8") as f:
                data = json.load(f)
                path = data.get("url", "")
                if path.startswith("file://"):
                    path = path[7:]
                    editable_packages.add(path)

    return editable_packages


def patch_designer():  # pragma: no cover
    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Cannot patch designer.")
        return

    init_virtual_env()

    major_version = sys.version_info[0]
    minor_version = sys.version_info[1]
    os.environ["PY_MAJOR_VERSION"] = str(major_version)
    os.environ["PY_MINOR_VERSION"] = str(minor_version)

    if sys.platform == "win32":
        if is_virtual_env():
            _extend_path_var("PATH", os.fspath(Path(sys._base_executable).parent), True)
    else:
        if sys.platform == "linux":
            env_var = "LD_PRELOAD"
            current_pid = os.getpid()
            with open(f"/proc/{current_pid}/maps", "rt") as f:
                for line in f:
                    if "libpython" in line:
                        lib_path = line.split()[-1]
                        os.environ[env_var] = lib_path
                        break

        elif sys.platform == "darwin":
            suffix = ".dylib"
            env_var = "DYLD_INSERT_LIBRARIES"
            version = f"{major_version}.{minor_version}"
            library_name = f"libpython{version}{suffix}"
            lib_path = str(Path(sysconfig.get_config_var("LIBDIR")) / library_name)
            os.environ[env_var] = lib_path
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")

        if is_pyenv_python() or is_virtual_env():
            # append all editable packages to the PYTHONPATH
            editable_packages = list_editable_packages()
            for pckg in editable_packages:
                _extend_path_var("PYTHONPATH", pckg, True)
    qt_tool_wrapper(ui_tool_binary("designer"), sys.argv[1:])


def _plugin_classes_for_python_file(file: Path):
    logger.debug(f"getting plugin classes for {file}")
    if not str(file).endswith(".py"):
        raise ValueError("Please pass a python file")
    spec = importlib.util.spec_from_file_location("_temp", file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_temp"] = mod
    spec.loader.exec_module(mod)

    plugin_widgets = list(
        mem[0]
        for mem in inspect.getmembers(mod, inspect.isclass)
        if issubclass(mem[1], BECWidget) and hasattr(mem[1], "PLUGIN") and mem[1].PLUGIN is True
    )
    logger.debug(f"Found: {plugin_widgets}")
    return plugin_widgets


def _plugin_classes_for_pyproject(path: Path):
    if not str(path).endswith(".pyproject"):
        raise ValueError("Please pass the path of the designer pyproject file")
    with open(path) as pyproject:
        plugin_filenames = ast.literal_eval(pyproject.read())["files"]
    plugin_files = (path.parent / file for file in plugin_filenames)
    return itertools.chain(*(_plugin_classes_for_python_file(f) for f in plugin_files))


def find_plugin_paths(base_path: Path) -> dict[str, list[str]]:
    """
    Recursively find all directories containing a .pyproject file. Returns a dictionary with keys of
    such paths, and values of the names of the classes contained in them if those classes are
    desginer plugins.
    """
    return {
        str(path.parent): list(_plugin_classes_for_pyproject(path))
        for path in base_path.rglob("*.pyproject")
    }


def set_plugin_environment_variable(plugin_paths):
    """
    Set the PYSIDE_DESIGNER_PLUGINS environment variable with the given plugin paths.
    """
    current_paths = os.environ.get("PYSIDE_DESIGNER_PLUGINS", "")
    if current_paths:
        current_paths = current_paths.split(os.pathsep)
    else:
        current_paths = []

    current_paths.extend(plugin_paths)
    os.environ["PYSIDE_DESIGNER_PLUGINS"] = os.pathsep.join(current_paths)


def _extend_plugin_paths(plugin_paths: dict[str, list[str]], plugin_repo_dir: Path):
    plugin_plugin_paths = find_plugin_paths(plugin_repo_dir)
    builtin_plugin_names = list(itertools.chain(*plugin_paths.values()))
    for plugin_file, plugin_classes in plugin_plugin_paths.items():
        logger.info(f"{plugin_classes} {builtin_plugin_names}")
        if any(name in builtin_plugin_names for name in plugin_classes):
            logger.warning(
                f"Ignoring plugin {plugin_file} because it contains widgets {plugin_classes} which include duplicates of built-in widgets!"
            )
        else:
            plugin_paths[plugin_file] = plugin_classes


# Patch the designer function
def main():  # pragma: no cover
    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Exiting...")
        return
    base_dir = Path(os.path.dirname(bec_widgets.__file__)).resolve()

    plugin_paths = find_plugin_paths(base_dir)

    if (plugin_repo := user_widget_plugin()) and isinstance(plugin_repo.__file__, str):
        plugin_repo_dir = Path(os.path.dirname(plugin_repo.__file__)).resolve()
        _extend_plugin_paths(plugin_paths, plugin_repo_dir)

    set_plugin_environment_variable(plugin_paths.keys())

    patch_designer()


if __name__ == "__main__":  # pragma: no cover
    main()
