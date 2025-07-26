import datetime
import importlib
import os

from qtpy.QtWidgets import QInputDialog, QMessageBox, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty
from bec_widgets.widgets.containers.explorer.collapsible_tree_section import CollapsibleSection
from bec_widgets.widgets.containers.explorer.explorer import Explorer
from bec_widgets.widgets.containers.explorer.script_tree_widget import ScriptTreeWidget


class IDEExplorer(BECWidget, QWidget):
    """Integrated Development Environment Explorer"""

    PLUGIN = True
    RPC = False

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self._sections = set()
        self.main_explorer = Explorer(parent=self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.main_explorer)
        self.setLayout(layout)
        self.sections = ["scripts"]

    @SafeProperty(list)
    def sections(self):
        return list(self._sections)

    @sections.setter
    def sections(self, value):
        existing_sections = set(self._sections)
        self._sections = set(value)
        self._update_section_visibility(self._sections - existing_sections)

    def _update_section_visibility(self, sections):
        for section in sections:
            self._add_section(section)

    def _add_section(self, section_name):
        match section_name.lower():
            case "scripts":
                self.add_script_section()
            case _:
                pass

    def add_script_section(self):
        section = CollapsibleSection(parent=self, title="SCRIPTS", indentation=0)
        section.expanded = False

        script_explorer = Explorer(parent=self)
        script_widget = ScriptTreeWidget(parent=self)
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
        shared_script_section = CollapsibleSection(title="Shared", parent=self)
        shared_script_widget = ScriptTreeWidget(parent=self)
        shared_script_section.set_widget(shared_script_widget)
        shared_script_widget.set_directory(plugin_scripts_dir)
        script_explorer.add_section(shared_script_section)
        # macros_section = CollapsibleSection("MACROS", indentation=0)
        # macros_section.set_widget(QLabel("Macros will be implemented later"))
        # self.main_explorer.add_section(macros_section)

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


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    app = QApplication([])
    script_explorer = IDEExplorer()
    script_explorer.show()
    app.exec_()
