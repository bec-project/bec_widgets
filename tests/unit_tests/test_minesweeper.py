# pylint: disable=missing-function-docstring, missing-module-docstring, unused-import

import pytest
from qtpy.QtCore import Qt

from bec_widgets.widgets.games import Minesweeper
from bec_widgets.widgets.games.minesweeper import LEVELS, GameStatus, Pos


@pytest.fixture
def minesweeper(qtbot):
    widget = Minesweeper()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_minesweeper_init(minesweeper: Minesweeper):
    assert minesweeper.status == GameStatus.READY


def test_changing_level_updates_size_and_removes_old_grid_items(minesweeper: Minesweeper):
    assert minesweeper.b_size == LEVELS["1"][0]
    grid_items = [minesweeper.grid.itemAt(i).widget() for i in range(minesweeper.grid.count())]
    for w in grid_items:
        assert w.parent() is not None
    minesweeper.change_level("2")
    assert minesweeper.b_size == LEVELS["2"][0]
    for w in grid_items:
        assert w.parent() is None


def test_game_state_changes_to_failed_on_loss(qtbot, minesweeper: Minesweeper):
    assert minesweeper.status == GameStatus.READY
    grid_items: list[Pos] = [
        minesweeper.grid.itemAt(i).widget() for i in range(minesweeper.grid.count())
    ]
    mine = [p for p in grid_items if p.is_mine][0]

    with qtbot.waitSignal(mine.ohno, timeout=1000):
        qtbot.mouseRelease(mine, Qt.MouseButton.LeftButton)
    assert minesweeper.status == GameStatus.FAILED


def test_game_resets_on_reset_click(minesweeper: Minesweeper):
    assert minesweeper.status == GameStatus.READY
    minesweeper.grid.itemAt(1).widget().ohno.emit()
    assert minesweeper.status == GameStatus.FAILED
    minesweeper.reset_button_pressed()
    assert minesweeper.status == GameStatus.PLAYING
