from __future__ import annotations

import re

import markdown
from bec_lib.endpoints import MessageEndpoints
from bec_lib.script_executor import upload_script
from bec_qthemes import material_icon
from qtpy.QtGui import QKeySequence, QShortcut
from qtpy.QtWidgets import QTextEdit

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.toolbars.actions import MaterialIconAction
from bec_widgets.utils.toolbars.bundles import ToolbarBundle
from bec_widgets.utils.toolbars.toolbar import ModularToolBar
from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import AdvancedDockArea
from bec_widgets.widgets.containers.advanced_dock_area.basic_dock_area import DockAreaWidget
from bec_widgets.widgets.containers.qt_ads import CDockWidget
from bec_widgets.widgets.editors.monaco.monaco_dock import MonacoDock
from bec_widgets.widgets.editors.monaco.monaco_widget import MonacoWidget
from bec_widgets.widgets.editors.web_console.web_console import BECShell, WebConsole
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


class DeveloperWidget(DockAreaWidget):

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, variant="compact", **kwargs)

        # Promote toolbar above the dock manager provided by the base class
        self.toolbar = ModularToolBar(self)
        self.init_developer_toolbar()
        self._root_layout.insertWidget(0, self.toolbar)

        # Initialize the widgets
        self.explorer = IDEExplorer(self)
        self.explorer.setObjectName("Explorer")

        self.console = BECShell(self)
        self.console.setObjectName("BEC Shell")
        self.terminal = WebConsole(self)
        self.terminal.setObjectName("Terminal")
        self.monaco = MonacoDock(self)
        self.monaco.setObjectName("MonacoEditor")
        self.monaco.save_enabled.connect(self._on_save_enabled_update)
        self.plotting_ads = AdvancedDockArea(
            self,
            mode="plot",
            default_add_direction="bottom",
            profile_namespace="developer_plotting",
            auto_profile_namespace=False,
            enable_profile_management=False,
            variant="compact",
        )
        self.plotting_ads.setObjectName("PlottingArea")
        self.signature_help = QTextEdit(self)
        self.signature_help.setObjectName("Signature Help")
        self.signature_help.setAcceptRichText(True)
        self.signature_help.setReadOnly(True)
        self.signature_help.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        opt = self.signature_help.document().defaultTextOption()
        opt.setWrapMode(opt.WrapMode.WrapAnywhere)
        self.signature_help.document().setDefaultTextOption(opt)
        self.monaco.signature_help.connect(
            lambda text: self.signature_help.setHtml(markdown_to_html(text))
        )
        self._current_script_id: str | None = None
        self.script_editor_tab = None

        self._initialize_layout()

        # Connect editor signals
        self.explorer.file_open_requested.connect(self._open_new_file)
        self.monaco.macro_file_updated.connect(self.explorer.refresh_macro_file)
        self.monaco.focused_editor.connect(self._on_focused_editor_changed)

        self.toolbar.show_bundles(["save", "execution", "settings"])

    def _initialize_layout(self) -> None:
        """Create the default dock arrangement for the developer workspace."""

        # Monaco editor as the central dock
        self.monaco_dock = self.new(
            self.monaco,
            closable=False,
            floatable=False,
            movable=False,
            return_dock=True,
            show_title_bar=False,
            show_settings_action=False,
            title_buttons={"float": False, "close": False, "menu": False},
            # promote_central=True,
        )

        # Explorer on the left without a title bar
        self.explorer_dock = self.new(
            self.explorer,
            where="left",
            closable=False,
            floatable=False,
            movable=False,
            return_dock=True,
            show_title_bar=False,
        )

        # Console and terminal tabbed along the bottom
        self.console_dock = self.new(
            self.console,
            relative_to=self.monaco_dock,
            where="bottom",
            closable=False,
            floatable=False,
            movable=False,
            return_dock=True,
            title_buttons={"float": True, "close": False},
        )
        self.terminal_dock = self.new(
            self.terminal,
            closable=False,
            floatable=False,
            movable=False,
            tab_with=self.console_dock,
            return_dock=True,
            title_buttons={"float": False, "close": False},
        )

        # Plotting area on the right with signature help tabbed alongside
        self.plotting_ads_dock = self.new(
            self.plotting_ads,
            where="right",
            closable=False,
            floatable=False,
            movable=False,
            return_dock=True,
            title_buttons={"float": True},
        )
        self.signature_dock = self.new(
            self.signature_help,
            closable=False,
            floatable=False,
            movable=False,
            tab_with=self.plotting_ads_dock,
            return_dock=True,
            title_buttons={"float": False, "close": False},
        )

        self.set_layout_ratios(horizontal=[2, 5, 3], vertical=[7, 3])

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
        save_as_button.action.triggered.connect(self.on_save_as)

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
        self.monaco.open_file(file_name, scope)

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
        """Save the currently focused file in the Monaco editor."""
        self.monaco.save_file()

    @SafeSlot()
    def on_save_as(self):
        """Save the currently focused file in the Monaco editor with a 'Save As' dialog."""
        self.monaco.save_file(force_save_as=True)

    @SafeSlot()
    def on_vim_triggered(self):
        """Toggle Vim mode in the Monaco editor."""
        self.monaco.set_vim_mode(self.toolbar.components.get_action("vim").action.isChecked())

    @SafeSlot(bool)
    def _on_save_enabled_update(self, enabled: bool):
        self.toolbar.components.get_action("save").action.setEnabled(enabled)
        self.toolbar.components.get_action("save_as").action.setEnabled(enabled)

    @SafeSlot()
    def on_execute(self):
        """Upload and run the currently focused script in the Monaco editor."""
        self.script_editor_tab = self.monaco.last_focused_editor
        if not self.script_editor_tab:
            return
        widget = self.script_editor_tab.widget()
        if not isinstance(widget, MonacoWidget):
            return
        if widget.modified:
            # Save the file before execution if there are unsaved changes
            self.monaco.save_file()
            if widget.modified:
                # If still modified, user likely cancelled save dialog
                return
        self.current_script_id = upload_script(self.client.connector, widget.get_text())
        self.console.write(f'bec._run_script("{self.current_script_id}")')
        print(f"Uploaded script with ID: {self.current_script_id}")

    @SafeSlot()
    def on_stop(self):
        """Stop the execution of the currently running script"""
        if not self.current_script_id:
            return
        self.console.send_ctrl_c()

    @property
    def current_script_id(self):
        """Get the ID of the currently running script."""
        return self._current_script_id

    @current_script_id.setter
    def current_script_id(self, value: str | None):
        """
        Set the ID of the currently running script.

        Args:
            value (str | None): The script ID to set.
        Raises:
            ValueError: If the provided value is not a string or None.
        """
        if value is not None and not isinstance(value, str):
            raise ValueError("Script ID must be a string.")
        old_script_id = self._current_script_id
        self._current_script_id = value
        self._update_subscription(value, old_script_id)

    def _update_subscription(self, new_script_id: str | None, old_script_id: str | None):
        if old_script_id is not None:
            self.bec_dispatcher.disconnect_slot(
                self.on_script_execution_info, MessageEndpoints.script_execution_info(old_script_id)
            )
        if new_script_id is not None:
            self.bec_dispatcher.connect_slot(
                self.on_script_execution_info, MessageEndpoints.script_execution_info(new_script_id)
            )

    @SafeSlot(CDockWidget)
    def _on_focused_editor_changed(self, tab_widget: CDockWidget):
        """
        Disable the run / stop buttons if the focused editor is a macro file.
        Args:
            tab_widget: The currently focused tab widget in the Monaco editor.
        """
        if not isinstance(tab_widget, CDockWidget):
            return
        widget = tab_widget.widget()
        if not isinstance(widget, MonacoWidget):
            return
        file_scope = widget.metadata.get("scope", "")
        run_action = self.toolbar.components.get_action("run")
        stop_action = self.toolbar.components.get_action("stop")
        if "macro" in file_scope:
            run_action.action.setEnabled(False)
            stop_action.action.setEnabled(False)
        else:
            run_action.action.setEnabled(True)
            stop_action.action.setEnabled(True)

    @SafeSlot(dict, dict)
    def on_script_execution_info(self, content: dict, metadata: dict):
        """
        Handle script execution info messages to update the editor highlights.
        Args:
            content (dict): The content of the message containing execution info.
            metadata (dict): Additional metadata for the message.
        """
        print(f"Script execution info: {content}")
        current_lines = content.get("current_lines")
        if self.script_editor_tab is None:
            return
        widget = self.script_editor_tab.widget()
        if not isinstance(widget, MonacoWidget):
            return
        if not current_lines:
            widget.clear_highlighted_lines()
            return
        line_number = current_lines[0]
        widget.clear_highlighted_lines()
        widget.set_highlighted_lines(line_number, line_number)

    def cleanup(self):
        """Clean up resources used by the developer widget."""
        self.delete_all()
        return super().cleanup()


if __name__ == "__main__":
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    from bec_widgets.applications.main_app import BECMainApp

    app = QApplication(sys.argv)
    apply_theme("dark")

    _app = BECMainApp()
    _app.show()
    # developer_view.show()
    # developer_view.setWindowTitle("Developer View")
    # developer_view.resize(1920, 1080)
    # developer_view.set_stretch(horizontal=[1, 3, 2], vertical=[5, 5]) #can be set during runtime
    sys.exit(app.exec_())
