import sys
import uuid

import pyqtgraph as pg
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QFileDialog, QFrame, QSplitter, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
from bec_widgets.widgets.editors.web_console.web_console import WebConsole

logger = bec_logger.logger


class ScriptInterface(BECWidget, QWidget):
    """
    A simple script interface widget that allows interaction with Monaco editor and Web Console.
    """

    PLUGIN = True
    ICON_NAME = "terminal"

    def __init__(self, parent=None, config=None, client=None, gui_id=None, **kwargs):
        super().__init__(
            parent=parent, client=client, gui_id=gui_id, config=config, theme_update=True, **kwargs
        )
        self.current_script_id = ""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.toolbar = ModularToolBar(parent=self, orientation="horizontal")

        self.splitter = QSplitter(self)
        self.splitter.setObjectName("splitter")
        self.splitter.setFrameShape(QFrame.Shape.NoFrame)
        self.splitter.setOrientation(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(True)

        self.monaco_editor = MonacoWidget(self)
        self.splitter.addWidget(self.monaco_editor)
        self.web_console = WebConsole(self)
        self.splitter.addWidget(self.web_console)
        layout.addWidget(self.toolbar)

        layout.addWidget(self.splitter)

        self.setLayout(layout)

        self.toolbar.components.add_safe(
            "new_script", MaterialIconAction("add", "New Script", parent=self)
        )
        self.toolbar.components.add_safe(
            "open", MaterialIconAction("folder_open", "Open Script", parent=self)
        )
        self.toolbar.components.add_safe(
            "save", MaterialIconAction("save", "Save Script", parent=self)
        )
        self.toolbar.components.add_safe(
            "run", MaterialIconAction("play_arrow", "Run Script", parent=self)
        )
        self.toolbar.components.add_safe(
            "stop", MaterialIconAction("stop", "Stop Script", parent=self)
        )

        bundle = ToolbarBundle("file_io", self.toolbar.components)
        bundle.add_action("new_script")
        bundle.add_action("open")
        bundle.add_action("save")
        self.toolbar.add_bundle(bundle)

        bundle = ToolbarBundle("script_execution", self.toolbar.components)
        bundle.add_action("run")
        bundle.add_action("stop")
        self.toolbar.add_bundle(bundle)

        self.toolbar.components.get_action("open").action.triggered.connect(self.open_file_dialog)
        self.toolbar.components.get_action("run").action.triggered.connect(self.run_script)
        self.toolbar.components.get_action("stop").action.triggered.connect(
            self.web_console.send_ctrl_c
        )

        self.set_save_button_enabled(False)

        self.toolbar.show_bundles(["file_io", "script_execution"])
        self.web_console.set_readonly(True)
        self._init_file_content = ""

        self._text_changed_proxy = pg.SignalProxy(
            self.monaco_editor.text_changed, rateLimit=1, slot=self._on_text_changed
        )

    @SafeSlot(str)
    def _on_text_changed(self, text: str):
        """
        Handle text changes in the Monaco editor.
        """
        text = text[0]
        if text != self._init_file_content:
            self.set_save_button_enabled(True)
        else:
            self.set_save_button_enabled(False)

    @property
    def current_script_id(self):
        return self._current_script_id

    @current_script_id.setter
    def current_script_id(self, value):
        if not isinstance(value, str):
            raise ValueError("Script ID must be a string.")
        self._current_script_id = value
        self._update_subscription()

    def _update_subscription(self):
        if self.current_script_id:
            self.bec_dispatcher.connect_slot(
                self.on_script_execution_info,
                MessageEndpoints.script_execution_info(self.current_script_id),
            )
        else:
            self.bec_dispatcher.disconnect_slot(
                self.on_script_execution_info,
                MessageEndpoints.script_execution_info(self.current_script_id),
            )

    @SafeSlot(dict, dict)
    def on_script_execution_info(self, content: dict, metadata: dict):
        print(f"Script execution info: {content}")
        current_lines = content.get("current_lines")
        if not current_lines:
            self.monaco_editor.clear_highlighted_lines()
            return
        line_number = current_lines[0]
        self.monaco_editor.clear_highlighted_lines()
        self.monaco_editor.set_highlighted_lines(line_number, line_number)

    def open_file_dialog(self):
        """
        Open a file dialog to select a script file.
        """
        start_dir = "./"
        dialog = QFileDialog(self)
        dialog.setDirectory(start_dir)
        dialog.setNameFilter("Python Files (*.py);;All Files (*)")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)

        if dialog.exec():
            selected_files = dialog.selectedFiles()
            if not selected_files:
                return
            file_path = selected_files[0]
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                self.monaco_editor.set_text(content)
                self._init_file_content = content

            logger.info(f"Selected files: {selected_files}")

    def set_save_button_enabled(self, enabled: bool):
        """
        Set the save button enabled state.
        """
        action = self.toolbar.components.get_action("save")
        if action:
            action.action.setEnabled(enabled)

    def run_script(self):
        print("Running script...")
        script_id = str(uuid.uuid4())
        self.current_script_id = script_id
        script_text = self.monaco_editor.get_text()

        script_text = f'bec._run_script("{script_id}", """{script_text}""")'
        script_text = script_text.replace("\n", "\\n").replace("'", "\\'").strip()
        if not script_text.endswith("\n"):
            script_text += "\\n"
        self.web_console.write(script_text)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    script_interface = ScriptInterface()
    script_interface.resize(800, 600)
    script_interface.show()
    sys.exit(app.exec_())
