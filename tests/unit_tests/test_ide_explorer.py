import os
from unittest import mock

import pytest

from bec_widgets.widgets.utility.ide_explorer.ide_explorer import IDEExplorer


@pytest.fixture
def ide_explorer(qtbot, tmpdir):
    """Create an IDEExplorer widget for testing"""
    widget = IDEExplorer()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_ide_explorer_initialization(ide_explorer):
    """Test the initialization of the IDEExplorer widget"""
    assert ide_explorer is not None
    assert "scripts" in ide_explorer.sections
    assert ide_explorer.main_explorer.sections[0].title == "SCRIPTS"


def test_ide_explorer_add_local_script(ide_explorer, qtbot, tmpdir):
    local_script_section = ide_explorer.main_explorer.get_section(
        "SCRIPTS"
    ).content_widget.get_section("Local")
    local_script_section.content_widget.set_directory(str(tmpdir))

    with mock.patch(
        "bec_widgets.widgets.utility.ide_explorer.ide_explorer.QInputDialog.getText",
        return_value=("test_file.py", True),
    ):
        ide_explorer._add_local_script()
        assert os.path.exists(os.path.join(tmpdir, "test_file.py"))
