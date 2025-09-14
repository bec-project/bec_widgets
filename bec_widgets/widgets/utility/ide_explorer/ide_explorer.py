import datetime
import importlib
import importlib.metadata
import os
import re

from bec_qthemes import material_icon
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QInputDialog, QMessageBox, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty
from bec_widgets.widgets.containers.explorer.collapsible_tree_section import CollapsibleSection
from bec_widgets.widgets.containers.explorer.explorer import Explorer
from bec_widgets.widgets.containers.explorer.macro_tree_widget import MacroTreeWidget
from bec_widgets.widgets.containers.explorer.script_tree_widget import ScriptTreeWidget


class IDEExplorer(BECWidget, QWidget):
    """Integrated Development Environment Explorer"""

    PLUGIN = True
    RPC = False

    file_open_requested = Signal(str, str)
    file_preview_requested = Signal(str, str)

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self._sections = []  # Use list to maintain order instead of set
        self.main_explorer = Explorer(parent=self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.main_explorer)
        self.setLayout(layout)
        self.sections = ["scripts", "macros"]

    @SafeProperty(list)
    def sections(self):
        return list(self._sections)

    @sections.setter
    def sections(self, value):
        existing_sections = set(self._sections)
        new_sections = set(value)
        # Find sections to add, maintaining the order from the input value list
        sections_to_add = [
            section for section in value if section in (new_sections - existing_sections)
        ]
        self._sections = list(value)  # Store as ordered list
        self._update_section_visibility(sections_to_add)

    def _update_section_visibility(self, sections):
        # sections is now an ordered list, not a set
        for section in sections:
            self._add_section(section)

    def _add_section(self, section_name):
        match section_name.lower():
            case "scripts":
                self.add_script_section()
            case "macros":
                self.add_macro_section()
            case _:
                pass

    def add_script_section(self):
        section = CollapsibleSection(parent=self, title="SCRIPTS", indentation=0)

        script_explorer = Explorer(parent=self)
        script_widget = ScriptTreeWidget(parent=self)
        script_widget.file_open_requested.connect(self._emit_file_open_scripts_local)
        script_widget.file_selected.connect(self._emit_file_preview_scripts_local)
        local_scripts_section = CollapsibleSection(title="Local", show_add_button=True, parent=self)
        local_scripts_section.header_add_button.clicked.connect(self._add_local_script)
        local_scripts_section.set_widget(script_widget)
        local_script_dir = self.client._service_config.model.user_scripts.base_path
        if not os.path.exists(local_script_dir):
            os.makedirs(local_script_dir)
        script_widget.set_directory(local_script_dir)
        script_explorer.add_section(local_scripts_section)

        section.set_widget(script_explorer)
        self.main_explorer.add_section(section)

        plugin_scripts_dir = None
        plugins = importlib.metadata.entry_points(group="bec")
        for plugin in plugins:
            if plugin.name == "plugin_bec":
                plugin = plugin.load()
                plugin_scripts_dir = os.path.join(plugin.__path__[0], "scripts")
                break

        if not plugin_scripts_dir or not os.path.exists(plugin_scripts_dir):
            return
        shared_script_section = CollapsibleSection(title="Shared (Read-only)", parent=self)
        shared_script_section.setToolTip("Shared scripts (read-only)")
        shared_script_widget = ScriptTreeWidget(parent=self)
        shared_script_section.set_widget(shared_script_widget)
        shared_script_widget.set_directory(plugin_scripts_dir)
        script_explorer.add_section(shared_script_section)
        shared_script_widget.file_open_requested.connect(self._emit_file_open_scripts_shared)
        shared_script_widget.file_selected.connect(self._emit_file_preview_scripts_shared)
        # macros_section = CollapsibleSection("MACROS", indentation=0)
        # macros_section.set_widget(QLabel("Macros will be implemented later"))
        # self.main_explorer.add_section(macros_section)

    def add_macro_section(self):
        section = CollapsibleSection(
            parent=self, title="MACROS", indentation=0, show_add_button=True
        )
        section.header_add_button.setIcon(material_icon("refresh", size=(20, 20)))
        section.header_add_button.setToolTip("Reload all macros")
        section.header_add_button.clicked.connect(self._reload_macros)

        macro_explorer = Explorer(parent=self)
        macro_widget = MacroTreeWidget(parent=self)
        macro_widget.macro_open_requested.connect(self._emit_file_open_macros_local)
        macro_widget.macro_selected.connect(self._emit_file_preview_macros_local)
        local_macros_section = CollapsibleSection(title="Local", show_add_button=True, parent=self)
        local_macros_section.header_add_button.clicked.connect(self._add_local_macro)
        local_macros_section.set_widget(macro_widget)
        local_macro_dir = self.client._service_config.model.user_macros.base_path
        if not os.path.exists(local_macro_dir):
            os.makedirs(local_macro_dir)
        macro_widget.set_directory(local_macro_dir)
        macro_explorer.add_section(local_macros_section)

        section.set_widget(macro_explorer)
        self.main_explorer.add_section(section)

        plugin_macros_dir = None
        plugins = importlib.metadata.entry_points(group="bec")
        for plugin in plugins:
            if plugin.name == "plugin_bec":
                plugin = plugin.load()
                plugin_macros_dir = os.path.join(plugin.__path__[0], "macros")
                break

        if not plugin_macros_dir or not os.path.exists(plugin_macros_dir):
            return
        shared_macro_section = CollapsibleSection(title="Shared (Read-only)", parent=self)
        shared_macro_section.setToolTip("Shared macros (read-only)")
        shared_macro_widget = MacroTreeWidget(parent=self)
        shared_macro_section.set_widget(shared_macro_widget)
        shared_macro_widget.set_directory(plugin_macros_dir)
        macro_explorer.add_section(shared_macro_section)
        shared_macro_widget.macro_open_requested.connect(self._emit_file_open_macros_shared)
        shared_macro_widget.macro_selected.connect(self._emit_file_preview_macros_shared)

    def _emit_file_open_scripts_local(self, file_name: str):
        self.file_open_requested.emit(file_name, "scripts/local")

    def _emit_file_preview_scripts_local(self, file_name: str):
        self.file_preview_requested.emit(file_name, "scripts/local")

    def _emit_file_open_scripts_shared(self, file_name: str):
        self.file_open_requested.emit(file_name, "scripts/shared")

    def _emit_file_preview_scripts_shared(self, file_name: str):
        self.file_preview_requested.emit(file_name, "scripts/shared")

    def _emit_file_open_macros_local(self, function_name: str, file_path: str):
        self.file_open_requested.emit(file_path, "macros/local")

    def _emit_file_preview_macros_local(self, function_name: str, file_path: str):
        self.file_preview_requested.emit(file_path, "macros/local")

    def _emit_file_open_macros_shared(self, function_name: str, file_path: str):
        self.file_open_requested.emit(file_path, "macros/shared")

    def _emit_file_preview_macros_shared(self, function_name: str, file_path: str):
        self.file_preview_requested.emit(file_path, "macros/shared")

    def _add_local_script(self):
        """Show a dialog to enter the name of a new script and create it."""

        target_section = self.main_explorer.get_section("SCRIPTS")
        script_dir_section = target_section.content_widget.get_section("Local")

        local_script_dir = script_dir_section.content_widget.directory

        # Prompt user for filename
        filename, ok = QInputDialog.getText(
            self, "New Script", f"Enter script name ({local_script_dir}/<filename>):"
        )

        if not ok or not filename:
            return  # User cancelled or didn't enter a name

        # Add .py extension if not already present
        if not filename.endswith(".py"):
            filename = f"{filename}.py"

        file_path = os.path.join(local_script_dir, filename)

        # Check if file already exists
        if os.path.exists(file_path):
            response = QMessageBox.question(
                self,
                "File exists",
                f"The file '{filename}' already exists. Do you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if response != QMessageBox.StandardButton.Yes:
                return  # User chose not to overwrite

        try:
            # Create the file with a basic template
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(
                    f"""
\"\"\"
{filename} - Created at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
\"\"\"
"""
                )

        except Exception as e:
            # Show error if file creation failed
            QMessageBox.critical(self, "Error", f"Failed to create script: {str(e)}")

    def _add_local_macro(self):
        """Show a dialog to enter the name of a new macro function and create it."""

        target_section = self.main_explorer.get_section("MACROS")
        macro_dir_section = target_section.content_widget.get_section("Local")

        local_macro_dir = macro_dir_section.content_widget.directory

        # Prompt user for function name
        function_name, ok = QInputDialog.getText(self, "New Macro", f"Enter macro function name:")

        if not ok or not function_name:
            return  # User cancelled or didn't enter a name

        # Sanitize function name
        function_name = re.sub(r"[^a-zA-Z0-9_]", "_", function_name)
        if not function_name or function_name[0].isdigit():
            QMessageBox.warning(
                self, "Invalid Name", "Function name must be a valid Python identifier."
            )
            return

        # Create filename based on function name
        filename = f"{function_name}.py"
        file_path = os.path.join(local_macro_dir, filename)

        # Check if file already exists
        if os.path.exists(file_path):
            response = QMessageBox.question(
                self,
                "File exists",
                f"The file '{filename}' already exists. Do you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )

            if response != QMessageBox.StandardButton.Yes:
                return  # User chose not to overwrite

        try:
            # Create the file with a macro function template
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(
                    f'''"""
{function_name} macro - Created at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""


def {function_name}():
    """
    Description of what this macro does.
    
    Add your macro implementation here.
    """
    print(f"Executing macro: {function_name}")
    # TODO: Add your macro code here
    pass
'''
                )

            # Refresh the macro tree to show the new function
            macro_dir_section.content_widget.refresh()

        except Exception as e:
            # Show error if file creation failed
            QMessageBox.critical(self, "Error", f"Failed to create macro: {str(e)}")

    def _reload_macros(self):
        """Reload all macros using the BEC client."""
        try:
            if hasattr(self.client, "macros"):
                self.client.macros.load_all_user_macros()

                # Refresh the macro tree widgets to show updated functions
                target_section = self.main_explorer.get_section("MACROS")
                if target_section and hasattr(target_section, "content_widget"):
                    local_section = target_section.content_widget.get_section("Local")
                    if local_section and hasattr(local_section, "content_widget"):
                        local_section.content_widget.refresh()

                    shared_section = target_section.content_widget.get_section("Shared")
                    if shared_section and hasattr(shared_section, "content_widget"):
                        shared_section.content_widget.refresh()

                QMessageBox.information(
                    self, "Reload Macros", "Macros have been reloaded successfully."
                )
            else:
                QMessageBox.warning(self, "Reload Macros", "Macros functionality is not available.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reload macros: {str(e)}")


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    script_explorer = IDEExplorer()
    script_explorer.show()
    app.exec_()
