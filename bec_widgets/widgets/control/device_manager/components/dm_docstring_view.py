"""Module to visualize the docstring of a device class."""

from __future__ import annotations

import inspect
import re
import textwrap
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


def docstring_to_markdown(obj) -> str:
    """
    Convert a Python docstring to Markdown suitable for QTextEdit.setMarkdown.
    """
    raw = inspect.getdoc(obj) or "*No docstring available.*"

    # Dedent and normalize newlines
    text = textwrap.dedent(raw).strip()

    md = ""
    if hasattr(obj, "__name__"):
        md += f"# {obj.__name__}\n\n"

    # Highlight section headers for Markdown
    headers = ["Parameters", "Args", "Returns", "Raises", "Attributes", "Examples", "Notes"]
    for h in headers:
        text = re.sub(rf"(?m)^({h})\s*:?\s*$", rf"### \1", text)

    # Preserve code blocks (4+ space indented lines)
    def fence_code(match: re.Match) -> str:
        block = re.sub(r"^ {4}", "", match.group(0), flags=re.M)
        return f"```\n{block}\n```"

    doc = re.sub(r"(?m)(^ {4,}.*(\n {4,}.*)*)", fence_code, text)

    # Preserve normal line breaks for Markdown
    lines = doc.splitlines()
    processed_lines = []
    for line in lines:
        if line.strip() == "":
            processed_lines.append("")
        else:
            processed_lines.append(line + "  ")
    doc = "\n".join(processed_lines)

    md += doc
    return md


class DocstringView(QtWidgets.QTextEdit):
    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        if not READY_TO_VIEW:
            self._set_text("Ophyd or ophyd_devices not installed, cannot show docstrings.")
            self.setEnabled(False)
            return

    def _set_text(self, text: str):
        self.setReadOnly(False)
        self.setMarkdown(text)
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
        if not READY_TO_VIEW:
            return
        try:
            module_cls = get_plugin_class(device_class_str, [ophyd_devices, ophyd])
            markdown = docstring_to_markdown(module_cls)
            self._set_text(markdown)
        except Exception:
            logger.exception("Error retrieving docstring")
            self._set_text(f"*Error retrieving docstring for `{device_class_str}`*")


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(widget)
    widget.setLayout(layout)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    config_view = DocstringView()
    config_view.set_device_class("ophyd_devices.sim.sim_camera.SimCamera")
    layout.addWidget(config_view)
    combo = QtWidgets.QComboBox()
    combo.addItems(
        [
            "",
            "ophyd_devices.sim.sim_camera.SimCamera",
            "ophyd.EpicsSignalWithRBV",
            "ophyd.EpicsMotor",
            "csaxs_bec.devices.epics.mcs_card.mcs_card_csaxs.MCSCardCSAXS",
        ]
    )
    combo.currentTextChanged.connect(config_view.set_device_class)
    layout.addWidget(combo)
    widget.show()
    sys.exit(app.exec_())
