import re

import markdown
import PySide6QtAds as QtAds
from bec_lib.endpoints import MessageEndpoints
from bec_lib.script_executor import upload_script
from bec_qthemes import material_icon
from PySide6QtAds import CDockManager, CDockWidget
from qtpy.QtGui import QKeySequence, QShortcut
from qtpy.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from bec_widgets import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import AdvancedDockArea
from bec_widgets.widgets.editors.monaco.monaco_tab import MonacoDock
from bec_widgets.widgets.editors.web_console.web_console import WebConsole
from bec_widgets.widgets.utility.ide_explorer.ide_explorer import IDEExplorer


def markdown_to_html(md_text: str) -> str:
    """Convert Markdown with syntax highlighting to HTML (Qt-compatible)."""

    # Preprocess: convert consecutive >>> lines to Python code blocks
    def replace_python_examples(match):
        indent = match.group(1)
        examples = match.group(2)
        # Remove >>> prefix and clean up the code
        lines = []
        for line in examples.strip().split("\n"):
            line = line.strip()
            if line.startswith(">>> "):
                lines.append(line[4:])  # Remove '>>> '
            elif line.startswith(">>>"):
                lines.append(line[3:])  # Remove '>>>'
        code = "\n".join(lines)

        return f"{indent}```python\n{indent}{code}\n{indent}```"

    # Match one or more consecutive >>> lines (with same indentation)
    pattern = r"^(\s*)((?:>>> .+(?:\n|$))+)"
    md_text = re.sub(pattern, replace_python_examples, md_text, flags=re.MULTILINE)

    extensions = ["fenced_code", "codehilite", "tables", "sane_lists"]
    html = markdown.markdown(
        md_text,
        extensions=extensions,
        extension_configs={
            "codehilite": {"linenums": False, "guess_lang": False, "noclasses": True}
        },
        output_format="html",
    )

    # Remove hardcoded background colors that conflict with themes
    html = re.sub(r'style="background: #[^"]*"', 'style="background: transparent"', html)
    html = re.sub(r"background: #[^;]*;", "", html)

    # Add CSS to force code blocks to wrap
    css = """
    <style>
    pre, code {
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
    .codehilite pre {
        white-space: pre-wrap !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }
    </style>
    """

    return css + html


class DeveloperWidget(BECWidget, QWidget):

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)

        # Top-level layout hosting a toolbar and the dock manager
        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)
        self.toolbar = ModularToolBar(self)
        self.init_developer_toolbar()
        self._root_layout.addWidget(self.toolbar)

        self.dock_manager = CDockManager(self)
        self.dock_manager.setStyleSheet("")
        self._root_layout.addWidget(self.dock_manager)

        # Initialize the widgets
        self.explorer = IDEExplorer(self)
        self.console = WebConsole(self)
        self.terminal = WebConsole(self, startup_cmd="")
        self.monaco = MonacoDock(self)
        self.monaco.save_enabled.connect(self._on_save_enabled_update)
        self.plotting_ads = AdvancedDockArea(self, mode="plot", default_add_direction="bottom")
        self.signature_help = QTextEdit(self)
        self.signature_help.setAcceptRichText(True)
        self.signature_help.setReadOnly(True)
        self.signature_help.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        opt = self.signature_help.document().defaultTextOption()
        opt.setWrapMode(opt.WrapMode.WrapAnywhere)
        self.signature_help.document().setDefaultTextOption(opt)
        self.monaco.signature_help.connect(
            lambda text: self.signature_help.setHtml(markdown_to_html(text))
        )

        # Create the dock widgets
        self.explorer_dock = QtAds.CDockWidget("Explorer", self)
        self.explorer_dock.setWidget(self.explorer)

        self.console_dock = QtAds.CDockWidget("Console", self)
        self.console_dock.setWidget(self.console)

        self.monaco_dock = QtAds.CDockWidget("Monaco Editor", self)
        self.monaco_dock.setWidget(self.monaco)

        self.terminal_dock = QtAds.CDockWidget("Terminal", self)
        self.terminal_dock.setWidget(self.terminal)

        # Monaco will be central widget
        self.dock_manager.setCentralWidget(self.monaco_dock)

        # Add the dock widgets to the dock manager
        area_bottom = self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.BottomDockWidgetArea, self.console_dock
        )
        self.dock_manager.addDockWidgetTabToArea(self.terminal_dock, area_bottom)

        area_left = self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock
        )
        area_left.titleBar().setVisible(False)

        for dock in self.dock_manager.dockWidgets():
            # dock.setFeature(CDockWidget.DockWidgetDeleteOnClose, True)#TODO implement according to MonacoDock or AdvancedDockArea
            # dock.setFeature(CDockWidget.CustomCloseHandling, True) #TODO same
            dock.setFeature(CDockWidget.DockWidgetClosable, False)
            dock.setFeature(CDockWidget.DockWidgetFloatable, False)
            dock.setFeature(CDockWidget.DockWidgetMovable, False)

        self.plotting_ads_dock = QtAds.CDockWidget("Plotting Area", self)
        self.plotting_ads_dock.setWidget(self.plotting_ads)

        self.signature_dock = QtAds.CDockWidget("Signature Help", self)
        self.signature_dock.setWidget(self.signature_help)

        area_right = self.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.RightDockWidgetArea, self.plotting_ads_dock
        )
        self.dock_manager.addDockWidgetTabToArea(self.signature_dock, area_right)

        # Connect editor signals
        self.explorer.file_open_requested.connect(self._open_new_file)

        self.toolbar.show_bundles(["save", "execution", "settings"])

    def init_developer_toolbar(self):
        """Initialize the developer toolbar with necessary actions and widgets."""
        save_button = MaterialIconAction(
            icon_name="save", tooltip="Save", label_text="Save", filled=True, parent=self
        )
        save_button.action.triggered.connect(self.on_save)
        self.toolbar.components.add_safe("save", save_button)

        save_as_button = MaterialIconAction(
            icon_name="save_as", tooltip="Save As", label_text="Save As", parent=self
        )
        self.toolbar.components.add_safe("save_as", save_as_button)

        save_bundle = ToolbarBundle("save", self.toolbar.components)
        save_bundle.add_action("save")
        save_bundle.add_action("save_as")
        self.toolbar.add_bundle(save_bundle)

        run_action = MaterialIconAction(
            icon_name="play_arrow",
            tooltip="Run current file",
            label_text="Run",
            filled=True,
            parent=self,
        )
        run_action.action.triggered.connect(self.on_execute)
        self.toolbar.components.add_safe("run", run_action)

        stop_action = MaterialIconAction(
            icon_name="stop",
            tooltip="Stop current execution",
            label_text="Stop",
            filled=True,
            parent=self,
        )
        stop_action.action.triggered.connect(self.on_stop)
        self.toolbar.components.add_safe("stop", stop_action)

        execution_bundle = ToolbarBundle("execution", self.toolbar.components)
        execution_bundle.add_action("run")
        execution_bundle.add_action("stop")
        self.toolbar.add_bundle(execution_bundle)

        vim_action = MaterialIconAction(
            icon_name="vim",
            tooltip="Toggle Vim Mode",
            label_text="Vim",
            filled=True,
            parent=self,
            checkable=True,
        )
        self.toolbar.components.add_safe("vim", vim_action)
        vim_action.action.triggered.connect(self.on_vim_triggered)

        settings_bundle = ToolbarBundle("settings", self.toolbar.components)
        settings_bundle.add_action("vim")
        self.toolbar.add_bundle(settings_bundle)

        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self.on_save)
        save_as_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        save_as_shortcut.activated.connect(self.on_save_as)

    def _open_new_file(self, file_name: str, scope: str):
        self.monaco.open_file(file_name)

        # Set read-only mode for shared files
        if "shared" in scope:
            self.monaco.set_file_readonly(file_name, True)

        # Add appropriate icon based on file type
        if "script" in scope:
            # Use script icon for script files
            icon = material_icon("script", size=(24, 24))
            self.monaco.set_file_icon(file_name, icon)
        elif "macro" in scope:
            # Use function icon for macro files
            icon = material_icon("function", size=(24, 24))
            self.monaco.set_file_icon(file_name, icon)

    @SafeSlot()
    def on_save(self):
        self.monaco.save_file()

    @SafeSlot()
    def on_save_as(self):
        self.monaco.save_file(force_save_as=True)

    @SafeSlot()
    def on_vim_triggered(self):
        self.monaco.set_vim_mode(self.toolbar.components.get_action("vim").action.isChecked())

    @SafeSlot(bool)
    def _on_save_enabled_update(self, enabled: bool):
        self.toolbar.components.get_action("save").action.setEnabled(enabled)
        self.toolbar.components.get_action("save_as").action.setEnabled(enabled)

    @SafeSlot()
    def on_execute(self):
        self.script_editor_tab = self.monaco.last_focused_editor
        if not self.script_editor_tab:
            return
        self.current_script_id = upload_script(
            self.client.connector, self.script_editor_tab.widget().get_text()
        )
        self.console.write(f'bec._run_script("{self.current_script_id}")')
        print(f"Uploaded script with ID: {self.current_script_id}")

    @SafeSlot()
    def on_stop(self):
        print("Stopping execution...")

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
            self.script_editor_tab.widget().clear_highlighted_lines()
            return
        line_number = current_lines[0]
        self.script_editor_tab.widget().clear_highlighted_lines()
        self.script_editor_tab.widget().set_highlighted_lines(line_number, line_number)


if __name__ == "__main__":
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    from bec_widgets.applications.main_app import BECMainApp

    app = QApplication(sys.argv)
    apply_theme("dark")

    _app = BECMainApp()
    screen = app.primaryScreen()
    screen_geometry = screen.availableGeometry()
    screen_width = screen_geometry.width()
    screen_height = screen_geometry.height()
    # 70% of screen height, keep 16:9 ratio
    height = int(screen_height * 0.9)
    width = int(height * (16 / 9))

    # If width exceeds screen width, scale down
    if width > screen_width * 0.9:
        width = int(screen_width * 0.9)
        height = int(width / (16 / 9))

    _app.resize(width, height)
    developer_view = DeveloperView()
    _app.add_view(
        icon="code_blocks", title="IDE", widget=developer_view, id="developer_view", exclusive=True
    )
    _app.show()
    # developer_view.show()
    # developer_view.setWindowTitle("Developer View")
    # developer_view.resize(1920, 1080)
    # developer_view.set_stretch(horizontal=[1, 3, 2], vertical=[5, 5]) #can be set during runtime
    sys.exit(app.exec_())
