"""
Launcher for BEC GUI Applications

Application must be located in bec_widgets/applications ;
in order for the launcher to find the application, it has to be put in
a subdirectory with the same name as the main Python module:

/bec_widgets/applications
    ├── alignment
    │   └── alignment_1d
    │       └── alignment_1d.py
    ├── other_app
        └── other_app.py

The tree above would contain 2 applications, alignment_1d and other_app.

The Python module for the application must have `if __name__ == "__main__":`
in order for the launcher to execute it (it is run with `python -m`).
"""

import argparse
import os
import sys

MODULE_PATH = os.path.dirname(__file__)


def find_apps(base_dir: str) -> list[str]:
    matching_modules = []

    for root, dirs, files in os.walk(base_dir):
        parent_dir = os.path.basename(root)

        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                file_name_without_ext = os.path.splitext(file)[0]

                if file_name_without_ext == parent_dir:
                    rel_path = os.path.relpath(root, base_dir)
                    module_path = rel_path.replace(os.sep, ".")

                    module_name = f"{module_path}.{file_name_without_ext}"
                    matching_modules.append((file_name_without_ext, module_name))

    return matching_modules


def main():
    parser = argparse.ArgumentParser(description="BEC application launcher")

    parser.add_argument("-m", "--module", type=str, help="The module to run (string argument).")

    # Add a positional argument for the module, which acts as a fallback if -m is not provided
    parser.add_argument(
        "positional_module",
        nargs="?",  # This makes the positional argument optional
        help="Positional argument that is treated as module if -m is not specified.",
    )

    args = parser.parse_args()
    # If the -m/--module is not provided, fallback to the positional argument
    module = args.module if args.module else args.positional_module

    if module:
        for app_name, app_module in find_apps(MODULE_PATH):
            if module in (app_name, app_module):
                print("Starting:", app_name)
                python_executable = sys.executable

                # Replace the current process with the new Python module
                os.execvp(
                    python_executable,
                    [python_executable, "-m", f"bec_widgets.applications.{app_module}"],
                )
        print(f"Error: cannot find application {module}")

    # display list of apps
    print("Available applications:")
    for app, _ in find_apps(MODULE_PATH):
        print(f"  - {app}")


if __name__ == "__main__":  # pragma: no cover
    main()
