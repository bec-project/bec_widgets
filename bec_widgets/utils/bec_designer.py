import os
import sys
import sysconfig
from pathlib import Path

from PySide6.scripts.pyside_tool import (
    _extend_path_var,
    init_virtual_env,
    is_pyenv_python,
    is_virtual_env,
    qt_tool_wrapper,
    ui_tool_binary,
)

import bec_widgets


def patch_designer():  # pragma: no cover
    # init_virtual_env()

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

    base_dir = Path(os.path.dirname(bec_widgets.__file__)).resolve()
    plugin_paths = find_plugin_paths(base_dir)
    set_plugin_environment_variable(plugin_paths)

    patch_designer()


if __name__ == "__main__":  # pragma: no cover
    main()
