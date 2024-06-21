import os
import sys
import sysconfig
from pathlib import Path

import bec_widgets

from PySide6.scripts.pyside_tool import (
    qt_tool_wrapper,
    ui_tool_binary,
    init_virtual_env,
    is_pyenv_python,
    is_virtual_env,
    _extend_path_var,
)


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


# Patch the designer function
def main():  # pragma: no cover
    os.environ["PYSIDE_DESIGNER_PLUGINS"] = os.path.join(
        os.path.dirname(bec_widgets.__file__), "widgets/device_inputs/device_combobox"
    )
    # os.environ["PYSIDE_DESIGNER_PLUGINS"] = os.path.join(
    #     os.path.dirname(bec_widgets.__file__), "widgets/motor_control/selection"
    # )
    patch_designer()


if __name__ == "__main__":  # pragma: no cover
    main()
