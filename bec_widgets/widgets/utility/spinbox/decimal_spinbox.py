import sys

from bec_qthemes import material_icon
from qtpy.QtGui import Qt
from qtpy.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QInputDialog,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from bec_widgets.utils import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget


class BECSpinBox(BECWidget, QDoubleSpinBox):
    PLUGIN = True
    RPC = False
    ICON_NAME = "123"

    def __init__(
        self,
        parent: QWidget | None = None,
        config: ConnectionConfig | None = None,
        client=None,
        gui_id: str | None = None,
        **kwargs,
    ) -> None:
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(client=client, gui_id=gui_id, config=config, **kwargs)
        QDoubleSpinBox.__init__(self, parent=parent)

        self.setObjectName("BECSpinBox")
        # Make the widget as compact as possible horizontally.
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.setAlignment(Qt.AlignHCenter)

        # Configure default QDoubleSpinBox settings.
        self.setRange(-2147483647, 2147483647)
        self.setDecimals(2)

        # Create an embedded settings button.
        self.setting_button = QToolButton(self)
        self.setting_button.setIcon(material_icon("settings"))
        self.setting_button.setToolTip("Set number of decimals")
        self.setting_button.setCursor(Qt.PointingHandCursor)
        self.setting_button.setFocusPolicy(Qt.NoFocus)
        self.setting_button.setStyleSheet("QToolButton { border: none; padding: 0px; }")

        self.setting_button.clicked.connect(self.change_decimals)

        self._button_size = 12
        self._arrow_width = 20

    def resizeEvent(self, event):
        super().resizeEvent(event)
        arrow_width = self._arrow_width

        # Position the settings button inside the spin box, to the left of the arrow buttons.
        x = self.width() - arrow_width - self._button_size - 2  # 2px margin
        y = (self.height() - self._button_size) // 2
        self.setting_button.setFixedSize(self._button_size, self._button_size)
        self.setting_button.move(x, y)

    def change_decimals(self):
        """
        Change the number of decimals in the spin box.
        """
        current = self.decimals()
        new_decimals, ok = QInputDialog.getInt(
            self, "Set Decimals", "Number of decimals:", current, 0, 10, 1
        )
        if ok:
            self.setDecimals(new_decimals)


if __name__ == "__main__":  # pragma: no cover
    app = QApplication(sys.argv)
    window = BECSpinBox()
    window.show()
    sys.exit(app.exec())
