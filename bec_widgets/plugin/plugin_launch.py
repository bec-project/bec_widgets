import os
import subprocess
import sys

from PySide6.scripts.pyside_tool import designer

import bec_widgets


def main():
    os.environ["PYSIDE_DESIGNER_PLUGINS"] = os.path.join(
        "/Users/janwyzula/PSI/bec_widgets/bec_widgets/plugin"
    )
    # os.environ["PYSIDE_DESIGNER_PLUGINS"] = os.path.join(
    #     os.path.dirname(bec_widgets.__file__), "widgets/motor_control/selection"
    # )
    # os.environ["PYTHONFRAMEWORKPREFIX"] = os.path.join(
    #     os.path.dirname(bec_widgets.__file__), "widgets/motor_control/selection"
    # )
    designer()


if __name__ == "__main__":
    main()
