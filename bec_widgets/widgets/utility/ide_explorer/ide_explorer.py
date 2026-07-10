import datetime
import importlib
import importlib.metadata
import os
import re
import shutil
from typing import Literal

from bec_qthemes import material_icon
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QInputDialog, QMessageBox, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty
from bec_widgets.widgets.containers.explorer.collapsible_tree_section import CollapsibleSection
from bec_widgets.widgets.containers.explorer.explorer import Explorer
from bec_widgets.widgets.containers.explorer.file_browser_tree_widget import FileBrowserTreeWidget


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

    def _remove_section(self, section_name):
        section = self.main_explorer.get_section(section_name.upper())
        if section:
            self.main_explorer.remove_section(section)
            self._sections.remove(section_name)

    def clear(self):
        """Clear all sections from the explorer."""
        for section in reversed(self._sections):
            self._remove_section(section)

    def add_script_section(self):
        section = CollapsibleSection(
            parent=self,
            title="SCRIPTS",
            indentation=0,
            tooltip="Scripts are executable Python files for scan workflows, "
            "automation, and quick experiments.\n"
            "In contrast to macros, scripts can contain executable code outside of function definitions.\n"
            "Scripts can be run directly from the IDE by clicking the 'Run' button in the toolbar.",
        )

        script_explorer = Explorer(parent=self)
        local_script_dir = os.path.expanduser(
            self.client._service_config.model.user_scripts.base_path
        )
        os.makedirs(local_script_dir, exist_ok=True)
        script_widget = FileBrowserTreeWidget(
            parent=self, directory=local_script_dir, read_only=False
        )
        script_widget.file_open_requested.connect(self._emit_file_open_scripts_local)
        script_widget.file_selected.connect(self._emit_file_preview_scripts_local)
        script_widget.file_delete_requested.connect(self._delete_local_script)
        script_widget.file_renamed.connect(self._rename_local_script_path)
        local_scripts_section = CollapsibleSection(title="Local", show_add_button=True, parent=self)
        local_scripts_section.header_add_button.clicked.connect(self._add_local_script)
        local_scripts_section.set_widget(script_widget)
        script_explorer.add_section(local_scripts_section)

        section.set_widget(script_explorer)
        self.main_explorer.add_section(section)

        plugin_scripts_dir = self._get_plugin_dir("scripts")

        if not plugin_scripts_dir or not os.path.exists(plugin_scripts_dir):
            return
        shared_script_section = CollapsibleSection(title="Shared (Read-only)", parent=self)
        shared_script_section.setToolTip("Shared scripts (read-only)")
        shared_script_widget = FileBrowserTreeWidget(
            parent=self, directory=plugin_scripts_dir, read_only=True
        )
        shared_script_section.set_widget(shared_script_widget)
        script_explorer.add_section(shared_script_section)
        shared_script_widget.file_open_requested.connect(self._emit_file_open_scripts_shared)
        shared_script_widget.file_selected.connect(self._emit_file_preview_scripts_shared)

    def add_macro_section(self):
        section = CollapsibleSection(
            parent=self,
            title="MACROS",
            indentation=0,
            show_add_button=True,
            tooltip="Macros are reusable Python functions that can be called from scripts or the console.\n"
            "All macros are automatically loaded and available for use. As a result,\n"
            "macros must not have executable code outside of function definitions to\n"
            "avoid unintended execution when imported.",
        )
        section.header_add_button.setIcon(
            material_icon("refresh", size=(20, 20), convert_to_pixmap=False)
        )
        section.header_add_button.setToolTip("Reload all macros")
        section.header_add_button.clicked.connect(self._reload_macros)

        macro_explorer = Explorer(parent=self)
        local_macro_dir = os.path.expanduser(
            self.client._service_config.model.user_macros.base_path
        )
        os.makedirs(local_macro_dir, exist_ok=True)
        macro_widget = FileBrowserTreeWidget(
            parent=self, directory=local_macro_dir, read_only=False
        )
        macro_widget.file_open_requested.connect(self._emit_file_open_macros_local)
        macro_widget.file_selected.connect(self._emit_file_preview_macros_local)
        macro_widget.file_delete_requested.connect(self._delete_local_macro)
        macro_widget.file_renamed.connect(self._rename_local_macro_path)
        local_macros_section = CollapsibleSection(title="Local", show_add_button=True, parent=self)
        local_macros_section.header_add_button.clicked.connect(self._add_local_macro)
        local_macros_section.set_widget(macro_widget)
        macro_explorer.add_section(local_macros_section)

        section.set_widget(macro_explorer)
        self.main_explorer.add_section(section)

        plugin_macros_dir = self._get_plugin_dir("macros")

        if not plugin_macros_dir or not os.path.exists(plugin_macros_dir):
            return
        shared_macro_section = CollapsibleSection(title="Shared (Read-only)", parent=self)
        shared_macro_section.setToolTip("Shared macros (read-only)")
        shared_macro_widget = FileBrowserTreeWidget(
            parent=self, directory=plugin_macros_dir, read_only=True
        )
        shared_macro_section.set_widget(shared_macro_widget)
        macro_explorer.add_section(shared_macro_section)
        shared_macro_widget.file_open_requested.connect(self._emit_file_open_macros_shared)
        shared_macro_widget.file_selected.connect(self._emit_file_preview_macros_shared)

    def _get_plugin_dir(self, dir_name: Literal["scripts", "macros"]) -> str | None:
        """Get the path to the specified directory within the BEC plugin.

        Returns:
            The path to the specified directory, or None if not found.
        """
        plugins = importlib.metadata.entry_points(group="bec")
        for plugin in plugins:
            if plugin.name == "plugin_bec":
                plugin = plugin.load()
                return os.path.join(plugin.__path__[0], dir_name)
        return None

    def _emit_file_open_scripts_local(self, file_name: str):
        self.file_open_requested.emit(file_name, "scripts/local")

    def _emit_file_preview_scripts_local(self, file_name: str):
        self.file_preview_requested.emit(file_name, "scripts/local")

    def _emit_file_open_scripts_shared(self, file_name: str):
        self.file_open_requested.emit(file_name, "scripts/shared")

    def _emit_file_preview_scripts_shared(self, file_name: str):
        self.file_preview_requested.emit(file_name, "scripts/shared")

    def _emit_file_open_macros_local(self, *args):
        file_path = args[-1]
        self.file_open_requested.emit(file_path, "macros/local")

    def _emit_file_preview_macros_local(self, *args):
        file_path = args[-1]
        self.file_preview_requested.emit(file_path, "macros/local")

    def _emit_file_open_macros_shared(self, *args):
        file_path = args[-1]
        self.file_open_requested.emit(file_path, "macros/shared")

    def _emit_file_preview_macros_shared(self, *args):
        file_path = args[-1]
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
                f.write(f"""
\"\"\"
{filename} - Created at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
\"\"\"
""")

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
                f.write(f'''"""
{function_name} macro - Created at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""


def {function_name}():
    """
    Description of what this macro does.
    
    Add your macro implementation here.
    """
    print("Executing macro: {function_name}")
    # TODO: Add your macro code here
''')

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

                # Refresh the macro tree widgets to show updated files
                target_section = self.main_explorer.get_section("MACROS")
                if target_section and hasattr(target_section, "content_widget"):
                    local_section = target_section.content_widget.get_section("Local")
                    if local_section and hasattr(local_section, "content_widget"):
                        local_section.content_widget.refresh()

                    shared_section = target_section.content_widget.get_section("Shared (Read-only)")
                    if shared_section and hasattr(shared_section, "content_widget"):
                        shared_section.content_widget.refresh()

                QMessageBox.information(
                    self, "Reload Macros", "Macros have been reloaded successfully."
                )
            else:
                QMessageBox.warning(self, "Reload Macros", "Macros functionality is not available.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reload macros: {str(e)}")

    def _delete_local_script(self, file_path: str):
        """Delete a local script file or directory from disk."""
        target_section = self.main_explorer.get_section("SCRIPTS")
        script_dir_section = target_section.content_widget.get_section("Local")
        local_script_dir = script_dir_section.content_widget.directory

        if not self._is_local_path(file_path, local_script_dir):
            return

        item_name = os.path.basename(file_path)
        is_directory = os.path.isdir(file_path)
        title = "Delete Folder" if is_directory else "Delete Script"
        message = (
            f"Delete folder '{item_name}'?\nThis will permanently remove the folder and its contents."
            if is_directory
            else f"Delete script '{item_name}'?\nThis will permanently remove the file from disk."
        )
        response = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        try:
            self._close_open_editors_for_path(file_path)
            self._remove_path(file_path)
            script_dir_section.content_widget.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete script: {str(e)}")

    def _delete_local_macro(self, file_path: str):
        """Delete a local macro file or directory from disk and unload its macros."""
        target_section = self.main_explorer.get_section("MACROS")
        macro_dir_section = target_section.content_widget.get_section("Local")
        local_macro_dir = macro_dir_section.content_widget.directory

        if not self._is_local_path(file_path, local_macro_dir):
            return

        item_name = os.path.basename(file_path)
        is_directory = os.path.isdir(file_path)
        title = "Delete Folder" if is_directory else "Delete Macro"
        message = (
            f"Delete folder '{item_name}'?\nThis removes all macro files inside that folder."
            if is_directory
            else (
                f"Delete macro file '{item_name}'?\n"
                "This removes all macros defined in that file."
            )
        )
        response = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        try:
            self._close_open_editors_for_path(file_path)
            for macro_file in self._iter_python_files(file_path):
                self._broadcast_removed_macros(macro_file)
            self._remove_path(file_path)
            macro_dir_section.content_widget.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to delete macro: {str(e)}")

    def _rename_local_script_path(self, old_path: str, new_path: str) -> None:
        """Update open editor state after a local script path rename."""
        target_section = self.main_explorer.get_section("SCRIPTS")
        script_dir_section = target_section.content_widget.get_section("Local")
        local_script_dir = script_dir_section.content_widget.directory

        if not self._is_local_path(new_path, local_script_dir):
            return

        self._rename_open_editor_path(old_path, new_path)
        script_dir_section.content_widget.refresh()

    def _rename_local_macro_path(self, old_path: str, new_path: str) -> None:
        """Update macro/editor state after a local macro path rename."""
        target_section = self.main_explorer.get_section("MACROS")
        macro_dir_section = target_section.content_widget.get_section("Local")
        local_macro_dir = macro_dir_section.content_widget.directory

        if not self._is_local_path(new_path, local_macro_dir):
            return

        if old_path.endswith(".py"):
            self._broadcast_removed_macros(old_path)

        self._rename_open_editor_path(old_path, new_path)
        if hasattr(self.client, "macros"):
            self.client.macros.load_all_user_macros()
        macro_dir_section.content_widget.refresh()

    @staticmethod
    def _is_local_path(file_path: str, base_dir: str | None) -> bool:
        """Return True when file_path is a file inside base_dir."""
        if not file_path or not base_dir:
            return False

        try:
            file_path = os.path.abspath(file_path)
            base_dir = os.path.abspath(base_dir)
            return os.path.commonpath([file_path, base_dir]) == base_dir
        except ValueError:
            return False

    def _close_open_editors_for_path(self, file_path: str) -> None:
        """Close editor tabs for a file or for every file under a directory."""
        parent = self.parent()
        while parent is not None and not hasattr(parent, "monaco"):
            parent = parent.parent()

        monaco = getattr(parent, "monaco", None)
        if monaco is None or not hasattr(monaco, "close_file"):
            return

        if os.path.isdir(file_path) and hasattr(monaco, "_get_open_files"):
            for open_file in list(monaco._get_open_files()):
                if self._is_local_path(open_file, file_path):
                    monaco.close_file(open_file, force=True)
            return

        monaco.close_file(file_path, force=True)

    def _rename_open_editor_path(self, old_path: str, new_path: str) -> None:
        """Update Monaco editor paths after a file or directory rename."""
        parent = self.parent()
        while parent is not None and not hasattr(parent, "monaco"):
            parent = parent.parent()

        monaco = getattr(parent, "monaco", None)
        if monaco is not None and hasattr(monaco, "rename_open_path"):
            monaco.rename_open_path(old_path, new_path)

    def _broadcast_removed_macros(self, file_path: str) -> None:
        """Broadcast removal of macros currently loaded from a deleted file."""
        if not hasattr(self.client, "macros") or not hasattr(self.client.macros, "_update_handler"):
            return

        handler = self.client.macros._update_handler
        existing_macros = handler.get_existing_macros(file_path)
        for macro_name in existing_macros:
            handler.broadcast(action="remove", name=macro_name)

    @staticmethod
    def _iter_python_files(file_path: str):
        """Yield Python files under a file or directory path."""
        if os.path.isfile(file_path):
            if file_path.endswith(".py"):
                yield file_path
            return

        if not os.path.isdir(file_path):
            return

        for root, _dirs, files in os.walk(file_path):
            for name in files:
                if name.endswith(".py"):
                    yield os.path.join(root, name)

    @staticmethod
    def _remove_path(file_path: str) -> None:
        """Delete a file or directory from disk."""
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
            return
        os.remove(file_path)

    def refresh_macro_file(self, file_path: str):
        """Refresh the macro file browser when a macro file changes.

        Args:
            file_path: Path to the macro file that was updated
        """
        target_section = self.main_explorer.get_section("MACROS")
        if not target_section or not hasattr(target_section, "content_widget"):
            return

        # Determine if this is a local or shared macro based on the file path
        local_section = target_section.content_widget.get_section("Local")
        shared_section = target_section.content_widget.get_section("Shared (Read-only)")

        # Check if file belongs to local macros directory
        if (
            local_section
            and hasattr(local_section, "content_widget")
            and hasattr(local_section.content_widget, "directory")
        ):
            local_macro_dir = local_section.content_widget.directory
            if local_macro_dir and file_path.startswith(local_macro_dir):
                local_section.content_widget.refresh()
                return

        # Check if file belongs to shared macros directory
        if (
            shared_section
            and hasattr(shared_section, "content_widget")
            and hasattr(shared_section.content_widget, "directory")
        ):
            shared_macro_dir = shared_section.content_widget.directory
            if shared_macro_dir and file_path.startswith(shared_macro_dir):
                shared_section.content_widget.refresh()
                return


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    script_explorer = IDEExplorer()
    script_explorer.show()
    app.exec_()
