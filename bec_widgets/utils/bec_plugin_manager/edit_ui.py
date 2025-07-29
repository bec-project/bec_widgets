import re
import subprocess
from pathlib import Path

from bec_lib.logger import bec_logger
from bec_lib.plugin_helper import plugin_package_name, plugin_repo_path
from watchdog.events import (
    DirCreatedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from bec_widgets.utils.bec_designer import open_designer
from bec_widgets.utils.bec_plugin_helper import get_all_plugin_widgets
from bec_widgets.utils.plugin_utils import get_custom_classes

logger = bec_logger.logger


class RecompileHandler(FileSystemEventHandler):
    def __init__(self, in_file: Path, out_file: Path) -> None:
        super().__init__()
        self.in_file = str(in_file)
        self.out_file = str(out_file)
        self._pyside_import_re = re.compile(r"from PySide6\.(.*) import ")
        self._widget_import_re = re.compile(
            r"^from ([a-zA-Z_]*) import ([a-zA-Z_]*)$", re.MULTILINE
        )
        self._widget_modules = {
            c.name: c.module for c in (get_custom_classes("bec_widgets") + get_all_plugin_widgets())
        }

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent) -> None:
        self.recompile(event)

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent) -> None:
        self.recompile(event)

    def on_moved(self, event: DirMovedEvent | FileMovedEvent) -> None:
        self.recompile(event)

    def recompile(self, event: FileSystemEvent) -> None:
        if event.src_path == self.in_file or event.dest_path == self.in_file:
            self._recompile()

    def _recompile(self):
        logger.success(".ui file modified, recompiling...")
        code = subprocess.call(
            ["pyside6-uic", "--absolute-imports", self.in_file, "-o", self.out_file]
        )
        logger.success(f"compilation exited with code {code}")
        if code != 0:
            return
        self._add_comment_to_file()
        logger.success("updating imports...")
        self._update_imports()
        logger.success("formatting...")
        code = subprocess.call(
            ["black", "--line-length=100", "--skip-magic-trailing-comma", self.out_file]
        )
        if code != 0:
            logger.error(f"Error while running black on {self.out_file}, code: {code}")
            return
        code = subprocess.call(
            [
                "isort",
                "--line-length=100",
                "--profile=black",
                "--multi-line=3",
                "--trailing-comma",
                self.out_file,
            ]
        )
        if code != 0:
            logger.error(f"Error while running isort on {self.out_file}, code: {code}")
            return
        logger.success("done!")

    def _add_comment_to_file(self):
        with open(self.out_file, "r+") as f:
            initial = f.read()
            f.seek(0)
            f.write(f"# Generated from {self.in_file} by bec-plugin-manager - do not edit! \n")
            f.write(
                "# Use 'bec-plugin-manager edit-ui [widget_name]' to make changes, and this file will be updated accordingly. \n\n"
            )
            f.write(initial)

    def _update_imports(self):
        with open(self.out_file, "r+") as f:
            initial = f.read()
            f.seek(0)
            qtpy_imports = re.sub(
                self._pyside_import_re, lambda ob: f"from qtpy.{ob.group(1)} import ", initial
            )
            print(self._widget_modules)
            print(re.findall(self._widget_import_re, qtpy_imports))
            widget_imports = re.sub(
                self._widget_import_re,
                lambda ob: (
                    f"from {module} import {ob.group(2)}"
                    if (module := self._widget_modules.get(ob.group(2))) is not None
                    else ob.group(1)
                ),
                qtpy_imports,
            )
            f.write(widget_imports)
            f.truncate()


def open_and_watch_ui_editor(widget_name: str):
    logger.info(f"Opening the editor for {widget_name}, and watching")
    repo = Path(plugin_repo_path())
    widget_dir = repo / plugin_package_name() / "bec_widgets" / "widgets" / widget_name
    ui_file = widget_dir / f"{widget_name}.ui"
    ui_outfile = widget_dir / f"{widget_name}_ui.py"

    logger.info(
        f"Opening the editor for {widget_name}, and watching {ui_file} for changes. Whenever you save the file, it will be recompiled to {ui_outfile}"
    )
    recompile_handler = RecompileHandler(ui_file, ui_outfile)
    observer = Observer()
    observer.schedule(recompile_handler, str(ui_file.parent))
    observer.start()
    try:
        open_designer([str(ui_file)])
    finally:
        observer.stop()
        observer.join()
    logger.info("Editing session ended, exiting...")
