import sys
import uuid

from bec_lib.endpoints import MessageEndpoints
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
from bec_widgets.widgets.editors.web_console.web_console import WebConsole


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

        self.monaco_editor = MonacoWidget(self)
        self.web_console = WebConsole(self)
        layout.addWidget(self.toolbar)

        layout.addWidget(self.monaco_editor)
        layout.addWidget(self.web_console)

        self.setLayout(layout)

        self.toolbar.add_action("run", MaterialIconAction("play_arrow", "Run Script", parent=self))
        self.toolbar.add_action("stop", MaterialIconAction("stop", "Stop Script", parent=self))

        self.toolbar.components.get_action("run").action.triggered.connect(self.run_script)
        self.toolbar.components.get_action("stop").action.triggered.connect(
            self.web_console.send_ctrl_c
        )

        self.toolbar.show_bundles(["run", "stop"])

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
