import glob
import importlib
import inspect
import os
import pathlib
from collections import defaultdict
from pathlib import Path
from typing import Literal

import bec_lib
from bec_qthemes import material_icon
from pydantic import BaseModel
from pygments.token import Token
from qtpy.QtCore import QSize, Qt, Signal, Slot
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.qt_utils.error_popups import SafeSlot
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_accent_colors, set_theme
from bec_widgets.widgets.editors.console.console import BECConsole
from bec_widgets.widgets.editors.vscode.vscode import VSCodeEditor

logger = bec_lib.bec_logger.logger


class EnchancedQTreeWidget(QTreeWidget):
    """Thin wrapper around QTreeWidget to add some functionality for user scripting"""

    play_button_clicked = Signal(str)
    edit_button_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderHidden(True)
        self.setObjectName(__class__.__name__)
        self._update_style_sheet()
        self._icon_size = QSize(24, 24)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setWordWrap(True)
        self.setAnimated(True)
        self.setIndentation(24)
        self._adjust_size_policy()

    def _adjust_size_policy(self):
        """Adjust the size policy"""
        header = self.header()
        header.setMinimumSectionSize(42)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)

    def _update_style_sheet(self) -> None:
        """Update the style sheet"""
        name = __class__.__name__
        colors = get_accent_colors()
        # pylint: ignore=protected-access
        color = colors._palette.midlight().color().name()
        self.setStyleSheet(
            f"""
            {name}::item {{
                    border: none;
                    background: transparent;
                }}
                QTreeView::branch:hover {{
                    background: transparent;
                    color: {color};
                }}
                {name}::item:hover {{
                    background: {color};
                }}
                {name}::item:selected:hover {{
                    background: {color};
                }}
                """
        )

    def add_top_item(self, label: str) -> QTreeWidgetItem:
        """Add a top item to the tree widget

        Args:
            label (str): The label for the top item

        Returns:
            QTreeWidgetItem: The top item
        """
        top_item = QTreeWidgetItem(self, [label])
        top_item.setExpanded(True)
        top_item.setSelected(False)
        self.resizeColumnToContents(0)
        return top_item

    def add_module_item(self, top_item: QTreeWidgetItem, mod_name: str) -> QTreeWidgetItem:
        """Add a top item to the tree widget together with an edit button in column 0 and label in 1

        Args:
            top_item (QTreeWidgetItem): The top item to add the child item to
            mod_name (str): The label for the child item

        Returns:
            QTreeWidgetItem: The top item
        """
        child_item = QTreeWidgetItem(top_item)
        # Add label
        label = QLabel(mod_name, parent=top_item.treeWidget())
        # Add edit button with label as parent
        edit_button = self._create_button(parent=label, button_type="edit")
        edit_button.clicked.connect(self._handle_edit_button_clicked)
        self.setItemWidget(child_item, 0, edit_button)
        self.setItemWidget(child_item, 1, label)
        self.resizeColumnToContents(0)
        return child_item

    def add_child_item(self, top_item: QTreeWidgetItem, label: str) -> None:
        """Add a child item to the top item together with a play button in column 1

        Args:
            top_item (QTreeWidgetItem): The top item to add the child item to
            label (str): The label for the child item

        Returns:
            QTreeWidgetItem: The child item
        """
        widget = QWidget(top_item.treeWidget())
        label = QLabel(label)
        spacer = QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QHBoxLayout(widget)
        layout.addWidget(label)
        layout.addItem(spacer)
        layout.setSpacing(4)
        layout.setContentsMargins(0, 0, 0, 0)
        button = self._create_button(parent=top_item.treeWidget(), button_type="play")
        button.clicked.connect(self._handle_play_button_clicked)
        layout.addWidget(button)
        child_item = QTreeWidgetItem(top_item)
        self.setItemWidget(child_item, 1, widget)
        return child_item

    @Slot()
    def _handle_edit_button_clicked(self):
        """Handle the click of the edit button"""
        button = self.sender()
        tree_widget_item = self.itemAt(button.pos())
        text = self.itemWidget(tree_widget_item, 1).text()
        self.edit_button_clicked.emit(text)

    @Slot()
    def _handle_play_button_clicked(self):
        """Handle the click of the play button"""
        button = self.sender()
        widget = button.parent()
        text = widget.findChild(QLabel).text()
        self.play_button_clicked.emit(text)

    def _create_button(self, parent: QWidget, button_type: Literal["edit", "play"]) -> QToolButton:
        """Create a button for 'edit' or 'play'

        Args:
            button_type (Literal["edit", "play"]): The type of button to create
        """
        colors = get_accent_colors()
        if button_type == "edit":
            color = colors.highlight
            name = "edit_document"
        elif button_type == "play":
            color = colors.success
            name = "play_arrow"
        else:
            raise ValueError("Invalid button type")
        button = QToolButton(
            parent=parent,
            icon=material_icon(
                name, filled=False, color=color, size=self._icon_size, convert_to_pixmap=False
            ),
        )
        button.setContentsMargins(0, 0, 0, 0)
        button.setStyleSheet("QToolButton { border: none; }")
        return button

    def _hide_buttons(self, exclude_item: QWidget = None):
        for button in self.viewport().findChildren(QToolButton):
            if exclude_item is not None:
                if button.parent() == exclude_item:
                    continue
            button.setVisible(False)


class VSCodeDialog(QDialog):
    """Dialog for the VSCode editor"""

    def __init__(self, parent=None, client=None, editor: VSCodeEditor = None):
        super().__init__(parent=parent)
        self.setWindowTitle("VSCode Editor")
        self.setMinimumWidth(800)
        self.setMinimumHeight(600)
        self.layout = QVBoxLayout(self)
        self.editor = editor
        self.layout.addWidget(self.editor)


class InputDialog(QDialog):
    """Dialog for input

    Args:
        header (str): The header of the dialog
        info (str): The information of the dialog
        fields (dict): The fields of the dialog
        parent (QWidget): The parent widget
    """

    def __init__(self, header: str, info: str, fields: dict, parent=None):
        super().__init__(parent=parent)
        self.header = header
        self.info = info
        self.fields = fields
        self._layout = QVBoxLayout(self)
        self.button_ok = QPushButton(parent=self, text="OK")
        self.button_cancel = QPushButton(parent=self, text="Cancel")
        self._init_ui()
        self.button_ok.clicked.connect(self.accept)
        self.button_cancel.clicked.connect(self.reject)

    def _init_ui(self):
        """Initialize the UI"""
        self.setWindowTitle(f"{self.header}")
        self.setMinimumWidth(200)
        box = QGroupBox(self)
        box.setTitle(self.info)
        layout = QGridLayout(box)
        layout.setSpacing(4)
        layout.setContentsMargins(4, 30, 4, 30)
        row = 0
        for name, default in self.fields.items():
            label = QLabel(parent=self, text=name)
            line_input = QLineEdit(parent=self)
            line_input.setObjectName(name)
            if default is not None:
                line_input.setText(f"{default}")
            layout.addWidget(label, row, 0)
            layout.addWidget(line_input, row, 1)
            row += 1
        self._layout.addWidget(box)
        widget = QWidget(self)
        sub_layout = QHBoxLayout(widget)
        sub_layout.addWidget(self.button_ok)
        sub_layout.addWidget(self.button_cancel)
        self._layout.addWidget(widget)
        self.setLayout(self._layout)
        self.resize(self._layout.sizeHint() * 1.05)

    def get_inputs(self):
        """Get the input from the dialog"""
        out = {}
        for name, _ in self.fields.items():
            line_input = self.findChild(QLineEdit, name)
            if line_input is not None:
                out[name] = line_input.text()
        return out


class ScriptBlock(BaseModel):
    """Model block for a script"""

    location: Literal["BEC", "USER", "BL"]
    fname: str
    module_name: str
    user_script_name: str | None = None


class UserScriptWidget(BECWidget, QWidget):
    """Dialog for displaying the fit summary and params for LMFit DAP processes"""

    PLUGIN = True

    USER_ACCESS = []
    ICON_NAME = "manage_accounts"

    def __init__(self, parent=None, client=None, config=None, gui_id: str | None = None):
        """"""
        super().__init__(client=client, config=config, gui_id=gui_id, theme_update=True)
        QWidget.__init__(self, parent=parent)
        self.button_new_script = QPushButton(parent=self, text="New Script")
        self.button_new_script.setObjectName("button_new_script")
        self._vscode_editor = VSCodeEditor(parent=self, client=self.client, gui_id=self.gui_id)
        self._console = BECConsole(parent=self)
        self.tree_widget = EnchancedQTreeWidget(parent=self)
        self.layout = QVBoxLayout(self)
        self.user_scripts = defaultdict(lambda: ScriptBlock)
        self._base_path = os.path.join(str(Path.home()), "bec", "scripts")
        self._icon_size = QSize(16, 16)
        self._script_button_register = {}
        self._code_dialog = None
        self._script_dialog = None
        self._new_script_dialog = None

        self.init_ui()
        self.button_new_script.clicked.connect(self.new_script)
        self.tree_widget.edit_button_clicked.connect(self.handle_edit_button_clicked)
        self.tree_widget.play_button_clicked.connect(self.handle_play_button_clicked)

    def apply_theme(self, theme: str):
        """Apply the theme"""
        self._update_button_ui()
        self.update_user_scripts()
        self.tree_widget._update_style_sheet()
        super().apply_theme(theme)

    def _setup_console(self):
        """Setup the console. Toents are needed to allow for the console to check for the prompt during shutdown."""
        self._console.set_prompt_tokens(
            (Token.OutPromptNum, "•"),
            (Token.Prompt, ""),  # will match arbitrary string,
            (Token.Prompt, " ["),
            (Token.PromptNum, "3"),
            (Token.Prompt, "/"),
            (Token.PromptNum, "1"),
            (Token.Prompt, "] "),
            (Token.Prompt, "❯❯"),
        )
        self._console.start()
        self._console.hide()

    def init_ui(self):
        """Initialize the UI"""
        # Add buttons
        widget = QWidget(self)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.button_new_script)
        self.layout.addWidget(widget)
        self.layout.addWidget(self.tree_widget)
        # self.layout.addWidget(self._console)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._vscode_editor.hide()
        self._update_button_ui()
        self._setup_console()
        self.update_user_scripts()
        self._vscode_editor.file_saved.connect(self._handle_file_saved)

    @Slot(str)
    def _handle_file_saved(self, fname: str):
        """Handle the file saved signal"""
        self.update_user_scripts()

    def _update_button_ui(self):
        """Update the button UI"""
        colors = get_accent_colors()
        name = self.button_new_script.objectName()
        self.button_new_script.setStyleSheet(
            f"QWidget#{name} {{ color: {colors._palette.windowText().color().name()}; }}"
        )

    def save_script(self):
        """Save the script"""
        self._vscode_editor.save_file()
        self._vscode_editor.hide()
        if self._code_dialog is not None:
            self._code_dialog.hide()
        self.update_user_scripts()

    def open_script(self, fname: str):
        """Open a script

        Args:
            fname (str): The file name of the script
        """
        if self._code_dialog is None:
            self._code_dialog = VSCodeDialog(parent=self, editor=self._vscode_editor)
            self._code_dialog.show()
            self._vscode_editor.show()
            # Only works after show was called for the first time
            self._vscode_editor.zen_mode()
        else:
            self._code_dialog.show()
            self._vscode_editor.show()
        self._vscode_editor.open_file(fname)

    @SafeSlot(popup_error=True)
    def new_script(self, *args, **kwargs):
        """Create a new script"""
        self._new_script_dialog = InputDialog(
            header="New Script", info="Enter filename for new script", fields={"Filename": ""}
        )
        if self._new_script_dialog.exec_():
            name = self._new_script_dialog.get_inputs()["Filename"]
            check_name = name.replace("_", "").replace("-", "")
            if not check_name.isalnum() or not check_name.isascii():
                raise NameError(f"Invalid name {name}, must be alphanumeric and ascii")
            if not name.endswith(".py"):
                name = name + ".py"
            fname = os.path.join(self._base_path, name)
            # Check if file exists on disk

            if os.path.exists(fname):
                logger.error(f"File {fname} already exists")
                raise FileExistsError(f"File {fname} already exists")
            try:
                os.makedirs(os.path.dirname(fname), exist_ok=True, mode=0o775)
                with open(fname, "w", encoding="utf-8") as f:
                    f.write("# New BEC Script\n")
            except Exception as e:
                logger.error(f"Error creating new script: {e}")
                raise e
            self.open_script(fname)

    def get_script_files(self) -> dict:
        """Get all script files in the base path"""
        files = {"BEC": [], "USER": [], "BL": []}
        # bec
        bec_lib_path = pathlib.Path(bec_lib.__file__).parent.parent.resolve()
        bec_scripts_dir = os.path.join(str(bec_lib_path), "scripts")
        files["BEC"].extend(glob.glob(os.path.abspath(os.path.join(bec_scripts_dir, "*.py"))))

        # user
        user_scripts_dir = os.path.join(os.path.expanduser("~"), "bec", "scripts")
        if os.path.exists(user_scripts_dir):
            files["USER"].extend(glob.glob(os.path.abspath(os.path.join(user_scripts_dir, "*.py"))))

        # load scripts from the beamline plugin
        plugins = importlib.metadata.entry_points(group="bec")
        for plugin in plugins:
            if plugin.name == "plugin_bec":
                plugin = plugin.load()
                plugin_scripts_dir = os.path.join(plugin.__path__[0], "scripts")
                if os.path.exists(plugin_scripts_dir):
                    files["BL"].extend(
                        glob.glob(os.path.abspath(os.path.join(plugin_scripts_dir, "*.py")))
                    )
        return files

    @SafeSlot(popup_error=True)
    def reload_user_scripts(self, *args, **kwargs):
        """Reload the user scripts"""
        self.client.load_all_user_scripts()

    @Slot()
    def update_user_scripts(self) -> None:
        """Update the user scripts"""
        self.user_scripts.clear()
        self.tree_widget.clear()
        script_files = self.get_script_files()
        for key, files in script_files.items():
            if len(files) == 0:
                continue
            top_item = self.tree_widget.add_top_item(key)
            for fname in files:
                mod_name = fname.split("/")[-1].strip(".py")
                self.user_scripts[mod_name] = ScriptBlock(
                    fname=fname, module_name=mod_name, location=key
                )
                child_item = self.tree_widget.add_module_item(top_item, mod_name)
                # pylint: disable=protected-access
                self.reload_user_scripts(popup_error=True)
                for user_script_name, info in self.client._scripts.items():
                    if info["fname"] == fname:
                        self.user_scripts[mod_name].user_script_name = user_script_name
                        _ = self.tree_widget.add_child_item(child_item, user_script_name)
        self.tree_widget.expandAll()

    @Slot(str)
    def handle_edit_button_clicked(self, text: str):
        """Handle the click of the edit button"""
        self.open_script(self.user_scripts[text].fname)

    @Slot(str)
    def handle_play_button_clicked(self, text: str):
        """Handle the click of the play button"""
        self._console.execute_command("bec.load_all_user_scripts()")
        info = self.client._scripts[text]
        caller_args = inspect.getfullargspec(info["cls"])
        args = caller_args.args + caller_args.kwonlyargs
        if args:
            self._handle_call_with_args(text, caller_args)
        else:
            self._console.execute_command(f"{text}()")

    def _handle_call_with_args(self, text: str, caller_args: inspect.FullArgSpec) -> None:
        """Handle the call with arguments"""
        defaults = []
        args = caller_args.args + caller_args.kwonlyargs
        for value in args:
            if caller_args.kwonlydefaults is not None:
                defaults.append(caller_args.kwonlydefaults.get(value, None))
        fields = dict((arg, default) for arg, default in zip(args, defaults))
        info = ", ".join([f"{k}={v}" for k, v in fields.items()]).replace("None", "")
        info = f"Example: {text}({info})"
        self._script_dialog = InputDialog(
            parent=self, header="Script Arguments", info=info, fields=fields
        )
        if self._script_dialog.exec_():
            args = self._script_dialog.get_inputs()
            args = ", ".join([f"{k}={v}" for k, v in args.items()])
            self._console.execute_command(f"{text}({args})")
            self._script_dialog = None

    def cleanup(self):
        """Cleanup the widget"""
        self._vscode_editor.cleanup()
        self._vscode_editor.deleteLater()
        if self._code_dialog is not None:
            self._code_dialog.deleteLater()
        if self._script_dialog is not None:
            self._script_dialog.deleteLater()
        if self._new_script_dialog is not None:
            self._new_script_dialog.deleteLater()
        self.tree_widget.clear()
        self._console.cleanup()


if __name__ == "__main__":

    from qtpy.QtWidgets import QApplication

    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QApplication([])
    set_theme("dark")
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.addWidget(DarkModeButton())
    layout.addWidget(UserScriptWidget())
    w.show()
    app.exec_()
