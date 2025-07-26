from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QSizePolicy, QSpacerItem, QSplitter, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.colors import get_theme_palette
from bec_widgets.widgets.containers.explorer.collapsible_tree_section import CollapsibleSection


class Explorer(BECWidget, QWidget):
    """
    A widget that combines multiple collapsible sections for an explorer-like interface.
    Each section can be expanded or collapsed, and sections can be reordered. The explorer
    can contain also sub-explorers for nested structures.
    """

    RPC = False
    PLUGIN = False

    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Splitter for sections
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_layout.addWidget(self.splitter)

        # Spacer for when all sections are collapsed
        self.expander = QSpacerItem(0, 0)
        self.main_layout.addItem(self.expander)

        # Registry of sections
        self.sections: list[CollapsibleSection] = []

        # Setup splitter styling
        self._setup_splitter_styling()

    def add_section(self, section: CollapsibleSection) -> None:
        """
        Add a collapsible section to the explorer

        Args:
            section (CollapsibleSection): The section to add
        """
        if not isinstance(section, CollapsibleSection):
            raise TypeError("section must be an instance of CollapsibleSection")

        if section in self.sections:
            return

        self.sections.append(section)
        self.splitter.addWidget(section)

        # Connect the section's toggle to update spacer
        section.header_button.clicked.connect(self._update_spacer)

        # Connect section reordering if supported
        if hasattr(section, "section_reorder_requested"):
            section.section_reorder_requested.connect(self._handle_section_reorder)

        self._update_spacer()

    def remove_section(self, section: CollapsibleSection) -> None:
        """
        Remove a collapsible section from the explorer

        Args:
            section (CollapsibleSection): The section to remove
        """
        if section not in self.sections:
            return
        self.sections.remove(section)
        section.deleteLater()
        section.close()

        # Disconnect signals
        try:
            section.header_button.clicked.disconnect(self._update_spacer)
            if hasattr(section, "section_reorder_requested"):
                section.section_reorder_requested.disconnect(self._handle_section_reorder)
        except RuntimeError:
            # Signals already disconnected
            pass

        self._update_spacer()

    def get_section(self, title: str) -> CollapsibleSection | None:
        """Get a section by its title"""
        for section in self.sections:
            if section.title == title:
                return section
        return None

    def _setup_splitter_styling(self) -> None:
        """Setup the splitter styling with theme colors"""
        palette = get_theme_palette()
        separator_color = palette.mid().color()

        self.splitter.setStyleSheet(
            f"""
            QSplitter::handle {{
                height: 0.1px;
                background-color: rgba({separator_color.red()}, {separator_color.green()}, {separator_color.blue()}, 60);
            }}
        """
        )

    def _update_spacer(self) -> None:
        """Update the spacer size based on section states"""
        any_expanded = any(section.expanded for section in self.sections)

        if any_expanded:
            self.expander.changeSize(0, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        else:
            self.expander.changeSize(
                0, 10, QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Expanding
            )

    def _handle_section_reorder(self, source_title: str, target_title: str) -> None:
        """Handle reordering of sections"""
        if source_title == target_title:
            return

        source_section = self.get_section(source_title)
        target_section = self.get_section(target_title)

        if not source_section or not target_section:
            return

        # Get current indices
        source_index = self.splitter.indexOf(source_section)
        target_index = self.splitter.indexOf(target_section)

        if source_index == -1 or target_index == -1:
            return

        # Insert at target position
        self.splitter.insertWidget(target_index, source_section)

        # Update sections
        self.sections.remove(source_section)
        self.sections.insert(target_index, source_section)


if __name__ == "__main__":
    import os

    from qtpy.QtWidgets import QApplication, QLabel

    from bec_widgets.widgets.containers.explorer.script_tree_widget import ScriptTreeWidget

    app = QApplication([])
    explorer = Explorer()
    section = CollapsibleSection(title="SCRIPTS", indentation=0)

    script_explorer = Explorer()
    script_widget = ScriptTreeWidget()
    local_scripts_section = CollapsibleSection(title="Local")
    local_scripts_section.set_widget(script_widget)
    script_widget.set_directory(os.path.abspath("./"))
    script_explorer.add_section(local_scripts_section)

    section.set_widget(script_explorer)
    explorer.add_section(section)
    shared_script_section = CollapsibleSection(title="Shared")
    shared_script_widget = ScriptTreeWidget()
    shared_script_widget.set_directory(os.path.abspath("./"))
    shared_script_section.set_widget(shared_script_widget)
    script_explorer.add_section(shared_script_section)
    macros_section = CollapsibleSection(title="MACROS", indentation=0)
    macros_section.set_widget(QLabel("Macros will be implemented later"))
    explorer.add_section(macros_section)
    explorer.show()
    app.exec()
