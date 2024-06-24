import importlib.metadata
import json
import os
import site
import sys
import sysconfig
from pathlib import Path

from qtpy import PYSIDE6

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


def list_editable_packages() -> list[tuple[str, str]]:
    """
    List all editable packages in the environment.

    Returns:
        list[tuple[str, str]]: A list of tuples containing the package name and the path to the package.
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

    if sys.platform == "linux":
        version = f"{major_version}.{minor_version}"
        library_name = f"libpython{version}{sys.abiflags}.so"
        if is_pyenv_python():
            library_name = str(Path(sysconfig.get_config_var("LIBDIR")) / library_name)
        os.environ["LD_PRELOAD"] = library_name
    elif sys.platform == "darwin":
        library_name = f"libpython{major_version}.{minor_version}.dylib"
        lib_path = str(Path(sysconfig.get_config_var("LIBDIR")) / library_name)
        os.environ["DYLD_INSERT_LIBRARIES"] = lib_path

        if is_pyenv_python() or is_virtual_env():
            # append all editable packages to the PYTHONPATH
            editable_packages = list_editable_packages()
            for pckg in editable_packages:
                _extend_path_var("PYTHONPATH", pckg, True)
    elif sys.platform == "win32":
        if is_virtual_env():
            _extend_path_var("PATH", os.fspath(Path(sys._base_executable).parent), True)

    qt_tool_wrapper(ui_tool_binary("designer"), sys.argv[1:])


def find_plugin_paths(base_path: Path):
    """
    Recursively find all directories containing a .pyproject file.
    """
    plugin_paths = []
    for path in base_path.rglob("*.pyproject"):
        plugin_paths.append(str(path.parent))
    return plugin_paths


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


# Patch the designer function
def main():  # pragma: no cover
    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Exiting...")
        return
    base_dir = Path(os.path.dirname(bec_widgets.__file__)).resolve()
    plugin_paths = find_plugin_paths(base_dir)
    set_plugin_environment_variable(plugin_paths)

    patch_designer()


if __name__ == "__main__":  # pragma: no cover
    main()
