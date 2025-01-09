import enum
import random
import time

from bec_qthemes import material_icon
from qtpy.QtCore import QSize, Qt, QTimer, Signal, Slot
from qtpy.QtGui import QBrush, QColor, QPainter, QPen
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.bec_widget import BECWidget

NUM_COLORS = {
    1: QColor("#f44336"),
    2: QColor("#9C27B0"),
    3: QColor("#3F51B5"),
    4: QColor("#03A9F4"),
    5: QColor("#00BCD4"),
    6: QColor("#4CAF50"),
    7: QColor("#E91E63"),
    8: QColor("#FF9800"),
}

LEVELS: dict[str, tuple[int, int]] = {"1": (8, 10), "2": (16, 40), "3": (24, 99)}


class GameStatus(enum.Enum):
    READY = 0
    PLAYING = 1
    FAILED = 2
    SUCCESS = 3


class Pos(QWidget):
    expandable = Signal(int, int)
    clicked = Signal()
    ohno = Signal()

    def __init__(self, x, y, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setFixedSize(QSize(20, 20))

        self.x = x
        self.y = y
        self.is_start = False
        self.is_mine = False
        self.adjacent_n = 0
        self.is_revealed = False
        self.is_flagged = False

    def reset(self):
        """Restore the tile to its original state before mine status is assigned"""
        self.is_start = False
        self.is_mine = False
        self.adjacent_n = 0

        self.is_revealed = False
        self.is_flagged = False

        self.update()

    def paintEvent(self, event):
        p = QPainter(self)

        r = event.rect()

        if self.is_revealed:
            color = self.palette().base().color()
            outer, inner = color, color
        else:
            outer, inner = (self.palette().highlightedText().color(), self.palette().text().color())

        p.fillRect(r, QBrush(inner))
        pen = QPen(outer)
        pen.setWidth(1)
        p.setPen(pen)
        p.drawRect(r)

        if self.is_revealed:
            if self.is_mine:
                p.drawPixmap(r, material_icon("experiment", convert_to_pixmap=True, filled=True))

            elif self.adjacent_n > 0:
                pen = QPen(NUM_COLORS[self.adjacent_n])
                p.setPen(pen)
                f = p.font()
                f.setBold(True)
                p.setFont(f)
                p.drawText(r, Qt.AlignHCenter | Qt.AlignVCenter, str(self.adjacent_n))

        elif self.is_flagged:
            p.drawPixmap(
                r,
                material_icon(
                    "flag",
                    size=(50, 50),
                    convert_to_pixmap=True,
                    filled=True,
                    color=self.palette().base().color(),
                ),
            )
        p.end()

    def flag(self):
        self.is_flagged = not self.is_flagged
        self.update()

        self.clicked.emit()

    def reveal(self):
        self.is_revealed = True
        self.update()

    def click(self):
        if not self.is_revealed:
            self.reveal()
            if self.adjacent_n == 0:
                self.expandable.emit(self.x, self.y)

        self.clicked.emit()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton and not self.is_revealed:
            self.flag()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            self.click()
            if self.is_mine:
                self.ohno.emit()


class Minesweeper(BECWidget, QWidget):

    PLUGIN = True
    ICON_NAME = "videogame_asset"
    USER_ACCESS = []

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        QWidget.__init__(self, parent=parent)

        self._ui_initialised = False
        self._timer_start_num_seconds = 0
        self._set_level_params(LEVELS["1"])

        self._init_ui()
        self._init_map()

        self.update_status(GameStatus.READY)
        self.reset_map()
        self.update_status(GameStatus.READY)

    def _init_ui(self):
        if self._ui_initialised:
            return
        self._ui_initialised = True

        status_hb = QHBoxLayout()
        self.mines = QLabel()
        self.mines.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        f = self.mines.font()
        f.setPointSize(24)
        self.mines.setFont(f)

        self.reset_button = QPushButton()
        self.reset_button.setFixedSize(QSize(32, 32))
        self.reset_button.setIconSize(QSize(32, 32))
        self.reset_button.setFlat(True)
        self.reset_button.pressed.connect(self.reset_button_pressed)

        self.clock = QLabel()
        self.clock.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.clock.setFont(f)
        self._timer = QTimer()
        self._timer.timeout.connect(self.update_timer)
        self._timer.start(1000)  # 1 second timer
        self.mines.setText(f"{self.num_mines:03d}")
        self.clock.setText("000")

        status_hb.addWidget(self.mines)
        status_hb.addWidget(self.reset_button)
        status_hb.addWidget(self.clock)

        level_hb = QHBoxLayout()
        self.level_selector = QComboBox()
        self.level_selector.addItems(list(LEVELS.keys()))
        level_hb.addWidget(QLabel("Level: "))
        level_hb.addWidget(self.level_selector)
        self.level_selector.currentTextChanged.connect(self.change_level)

        vb = QVBoxLayout()
        vb.addLayout(level_hb)
        vb.addLayout(status_hb)

        self.grid = QGridLayout()
        self.grid.setSpacing(5)

        vb.addLayout(self.grid)
        self.setLayout(vb)

    def _init_map(self):
        """Redraw the grid of mines"""

        # Remove any previous grid items and reset the grid
        for i in reversed(range(self.grid.count())):
            w: Pos = self.grid.itemAt(i).widget()
            w.clicked.disconnect(self.on_click)
            w.expandable.disconnect(self.expand_reveal)
            w.ohno.disconnect(self.game_over)
            w.setParent(None)
            w.deleteLater()

        # Add positions to the map
        for x in range(0, self.b_size):
            for y in range(0, self.b_size):
                w = Pos(x, y)
                self.grid.addWidget(w, y, x)
                # Connect signal to handle expansion.
                w.clicked.connect(self.on_click)
                w.expandable.connect(self.expand_reveal)
                w.ohno.connect(self.game_over)

    def reset_map(self):
        """
        Reset the map and add new mines.
        """
        # Clear all mine positions
        for x in range(0, self.b_size):
            for y in range(0, self.b_size):
                w = self.grid.itemAtPosition(y, x).widget()
                w.reset()

        # Add mines to the positions
        positions = []
        while len(positions) < self.num_mines:
            x, y = (random.randint(0, self.b_size - 1), random.randint(0, self.b_size - 1))
            if (x, y) not in positions:
                w = self.grid.itemAtPosition(y, x).widget()
                w.is_mine = True
                positions.append((x, y))

        def get_adjacency_n(x, y):
            positions = self.get_surrounding(x, y)
            num_mines = sum(1 if w.is_mine else 0 for w in positions)

            return num_mines

        # Add adjacencies to the positions
        for x in range(0, self.b_size):
            for y in range(0, self.b_size):
                w = self.grid.itemAtPosition(y, x).widget()
                w.adjacent_n = get_adjacency_n(x, y)

        # Place starting marker
        while True:
            x, y = (random.randint(0, self.b_size - 1), random.randint(0, self.b_size - 1))
            w = self.grid.itemAtPosition(y, x).widget()
            # We don't want to start on a mine.
            if (x, y) not in positions:
                w = self.grid.itemAtPosition(y, x).widget()
                w.is_start = True

                # Reveal all positions around this, if they are not mines either.
                for w in self.get_surrounding(x, y):
                    if not w.is_mine:
                        w.click()
                break

    def get_surrounding(self, x, y):
        positions = []
        for xi in range(max(0, x - 1), min(x + 2, self.b_size)):
            for yi in range(max(0, y - 1), min(y + 2, self.b_size)):
                positions.append(self.grid.itemAtPosition(yi, xi).widget())
        return positions

    def get_num_hidden(self) -> int:
        """
        Get the number of hidden positions.
        """
        return sum(
            1
            for x in range(0, self.b_size)
            for y in range(0, self.b_size)
            if not self.grid.itemAtPosition(y, x).widget().is_revealed
        )

    def get_num_remaining_flags(self) -> int:
        """
        Get the number of remaining flags.
        """
        return self.num_mines - sum(
            1
            for x in range(0, self.b_size)
            for y in range(0, self.b_size)
            if self.grid.itemAtPosition(y, x).widget().is_flagged
        )

    def reset_button_pressed(self):
        match self.status:
            case GameStatus.PLAYING:
                self.game_over()
            case GameStatus.FAILED | GameStatus.SUCCESS:
                self.reset_map()

    def reveal_map(self):
        for x in range(0, self.b_size):
            for y in range(0, self.b_size):
                w = self.grid.itemAtPosition(y, x).widget()
                w.reveal()

    @Slot(str)
    def change_level(self, level: str):
        self._set_level_params(LEVELS[level])
        self._init_map()
        self.reset_map()

    @Slot(int, int)
    def expand_reveal(self, x, y):
        """
        Expand the reveal to the surrounding

        Args:
            x (int): The x position.
            y (int): The y position.
        """
        for xi in range(max(0, x - 1), min(x + 2, self.b_size)):
            for yi in range(max(0, y - 1), min(y + 2, self.b_size)):
                w = self.grid.itemAtPosition(yi, xi).widget()
                if not w.is_mine:
                    w.click()

    @Slot()
    def on_click(self):
        """
        Handle the click event. If the game is not started, start the game.
        """
        self.update_available_flags()
        if self.status != GameStatus.PLAYING:
            # First click.
            self.update_status(GameStatus.PLAYING)
            # Start timer.
            self._timer_start_num_seconds = int(time.time())
            return
        self.check_win()

    def update_available_flags(self):
        """
        Update the number of available flags.
        """
        self.mines.setText(f"{self.get_num_remaining_flags():03d}")

    def check_win(self):
        """
        Check if the game is won.
        """
        if self.get_num_hidden() == self.num_mines:
            self.update_status(GameStatus.SUCCESS)

    def update_status(self, status: GameStatus):
        """
        Update the status of the game.

        Args:
            status (GameStatus): The status of the game.
        """
        self.status = status
        match status:
            case GameStatus.READY:
                icon = material_icon(icon_name="add", convert_to_pixmap=False)
            case GameStatus.PLAYING:
                icon = material_icon(icon_name="smart_toy", convert_to_pixmap=False)
            case GameStatus.FAILED:
                icon = material_icon(icon_name="error", convert_to_pixmap=False)
            case GameStatus.SUCCESS:
                icon = material_icon(icon_name="celebration", convert_to_pixmap=False)
        self.reset_button.setIcon(icon)

    def update_timer(self):
        """
        Update the timer.
        """
        if self.status == GameStatus.PLAYING:
            num_seconds = int(time.time()) - self._timer_start_num_seconds
            self.clock.setText(f"{num_seconds:03d}")

    def game_over(self):
        """Cause the game to end early"""
        self.reveal_map()
        self.update_status(GameStatus.FAILED)

    def _set_level_params(self, level: tuple[int, int]):
        self.b_size, self.num_mines = level


if __name__ == "__main__":
    from bec_widgets.utils.colors import set_theme

    app = QApplication([])
    set_theme("light")
    widget = Minesweeper()
    widget.show()

    app.exec_()
