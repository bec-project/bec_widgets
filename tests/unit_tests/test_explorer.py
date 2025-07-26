import pytest

from bec_widgets.widgets.containers.explorer.collapsible_tree_section import CollapsibleSection
from bec_widgets.widgets.containers.explorer.explorer import Explorer


@pytest.fixture
def explorer(qtbot):
    widget = Explorer()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_explorer_initialization(explorer):
    assert explorer is not None
    assert len(explorer.sections) == 0


def test_add_remove_section(explorer, qtbot):
    section = CollapsibleSection(title="Test Section", parent=explorer)
    explorer.add_section(section)
    assert len(explorer.sections) == 1
    assert explorer.sections[0].title == "Test Section"

    section2 = CollapsibleSection(title="Another Section", parent=explorer)
    explorer.add_section(section2)
    assert len(explorer.sections) == 2
    assert explorer.sections[1].title == "Another Section"

    explorer.remove_section(section)
    assert len(explorer.sections) == 1
    assert explorer.sections[0].title == "Another Section"
    qtbot.wait(100)  # Allow time for the section to be removed
    assert explorer.splitter.count() == 1


def test_section_reorder(explorer):
    section = CollapsibleSection(title="Section 1", parent=explorer)
    explorer.add_section(section)

    section2 = CollapsibleSection(title="Section 2", parent=explorer)
    explorer.add_section(section2)

    assert explorer.sections[0].title == "Section 1"
    assert explorer.sections[1].title == "Section 2"
    assert len(explorer.sections) == 2
    assert explorer.splitter.count() == 2

    explorer._handle_section_reorder("Section 1", "Section 2")

    assert explorer.sections[0].title == "Section 2"
    assert explorer.sections[1].title == "Section 1"
    assert len(explorer.sections) == 2
    assert explorer.splitter.count() == 2
