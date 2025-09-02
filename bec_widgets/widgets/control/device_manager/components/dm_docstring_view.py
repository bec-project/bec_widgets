"""Module to visualize the docstring of a device class."""

from __future__ import annotations

import inspect
import re
import traceback

from bec_lib.logger import bec_logger
from bec_lib.plugin_helper import get_plugin_class, plugin_package_name
from bec_lib.utils.rpc_utils import rgetattr
from qtpy import QtCore, QtWidgets

from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger

try:
    import ophyd
    import ophyd_devices

    READY_TO_VIEW = True
except ImportError:
    logger.warning(f"Optional dependencies not available: {ImportError}")
    ophyd_devices = None
    ophyd = None


class DocstringView(QtWidgets.QTextEdit):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        if not READY_TO_VIEW:
            self._set_text("Ophyd or ophyd_devices not installed, cannot show docstrings.")
            self.setEnabled(False)
            return

    def _format_docstring(self, doc: str | None) -> str:
        if not doc:
            return "<i>No docstring available.</i>"

        # Escape HTML
        doc = doc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Remove leading/trailing blank lines from the entire docstring
        lines = [line.rstrip() for line in doc.splitlines()]
        while lines and lines[0].strip() == "":
            lines.pop(0)
        while lines and lines[-1].strip() == "":
            lines.pop()
        doc = "\n".join(lines)

        # Improved regex: match section header + all following indented lines
        section_regex = re.compile(
            r"(?m)^(Parameters|Args|Returns|Examples|Attributes|Raises)\b(?:\n([ \t]+.*))*",
            re.MULTILINE,
        )

        def strip_section(match: re.Match) -> str:
            # Capture all lines in the match
            block = match.group(0)
            lines = block.splitlines()
            # Remove leading/trailing empty lines within the section
            lines = [line for line in lines if line.strip() != ""]
            return "\n".join(lines)

        doc = section_regex.sub(strip_section, doc)

        # Highlight section titles
        doc = re.sub(
            r"(?m)^(Parameters|Args|Returns|Examples|Attributes|Raises)\b", r"<b>\1</b>", doc
        )

        # Convert indented blocks to <pre> and strip leading/trailing newlines
        def pre_block(match: re.Match) -> str:
            text = match.group(0).strip("\n")
            return f"<pre>{text}</pre>"

        doc = re.sub(r"(?m)(?:\n[ \t]+.*)+", pre_block, doc)

        # Replace remaining newlines with <br> and collapse multiple <br>
        doc = doc.replace("\n", "<br>")
        doc = re.sub(r"(<br>)+", r"<br>", doc)
        doc = doc.strip("<br>")

        return f"<div style='font-family: sans-serif; font-size: 12pt;'>{doc}</div>"

    def _set_text(self, text: str):
        self.setReadOnly(False)
        self.setMarkdown(text)
        # self.setHtml(self._format_docstring(text))
        self.setReadOnly(True)

    @SafeSlot(list)
    def on_select_config(self, device: list[dict]):
        if len(device) != 1:
            self._set_text("")
            return
        device_class = device[0].get("deviceClass", "")
        self.set_device_class(device_class)

    @SafeSlot(str)
    def set_device_class(self, device_class_str: str) -> None:
        docstring = ""
        if not READY_TO_VIEW:
            return
        try:
            module_cls = get_plugin_class(device_class_str, [ophyd_devices, ophyd])
            docstring = inspect.getdoc(module_cls)
            self._set_text(docstring or "No docstring available.")
        except Exception:
            content = traceback.format_exc()
            logger.error(f"Error retrieving docstring for {device_class_str}: {content}")
            self._set_text(f"Error retrieving docstring for {device_class_str}")


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    config_view = DocstringView()
    config_view.set_device_class("ophyd_devices.sim.sim_camera.SimCamera")
    config_view.show()
    sys.exit(app.exec_())
