import pytest
from qtpy.QtWidgets import QTreeView, QWidget

from bec_widgets.utils.colors import apply_theme


class DummyTree(QWidget):
    def __init__(self):
        super().__init__()
        tree = QTreeView(self)


@pytest.fixture
def tree_widget(qtbot):
    tree = DummyTree()
    qtbot.addWidget(tree)
    qtbot.waitExposed(tree)
    yield tree


def test_tree_widget_init(tree_widget):
    assert isinstance(tree_widget, QWidget)
