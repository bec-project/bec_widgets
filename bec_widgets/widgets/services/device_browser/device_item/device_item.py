from __future__ import annotations

from typing import TYPE_CHECKING

from bec_lib.atlas_models import Device as DeviceConfigModel
from bec_lib.logger import bec_logger
from qtpy.QtCore import QMimeData, QSize, Qt, Signal
from qtpy.QtGui import QDrag
from qtpy.QtWidgets import QApplication, QHBoxLayout, QWidget

from bec_widgets.utils.colors import get_theme_name
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.expandable_frame import ExpandableGroupFrame
from bec_widgets.utils.forms_from_types import styles
from bec_widgets.utils.forms_from_types.forms import PydanticModelForm
from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtGui import QMouseEvent

logger = bec_logger.logger


class DeviceItemForm(PydanticModelForm):
    RPC = False
    PLUGIN = False

    def __init__(self, parent=None, client=None, pretty_display=False, **kwargs):
        super().__init__(
            parent=parent,
            data_model=DeviceConfigModel,
            pretty_display=pretty_display,
            client=client,
            **kwargs,
        )
        self._validity.setVisible(False)
        self._connect_to_theme_change()

    def set_pretty_display_theme(self, theme: str | None = None):
        if theme is None:
            theme = get_theme_name()
        self.setStyleSheet(styles.pretty_display_theme(theme))

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self.set_pretty_display_theme)  # type: ignore


class DeviceItem(ExpandableGroupFrame):
    broadcast_size_hint = Signal(QSize)

    RPC = False

    def __init__(self, parent, device: str, icon: str = "") -> None:
        super().__init__(parent, title=device, expanded=False, icon=icon)

        self._drag_pos = None
        self._expanded_first_time = False
        self._data = None
        self.device = device
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.set_layout(layout)

        self.adjustSize()
        self._title.clicked.connect(self.switch_expanded_state)
        self._title_icon.clicked.connect(self.switch_expanded_state)

    @SafeSlot()
    def switch_expanded_state(self):
        if not self.expanded and not self._expanded_first_time:
            self._expanded_first_time = True
            self.form = DeviceItemForm(parent=self, pretty_display=True)
            self._contents.layout().addWidget(self.form)
            if self._data:
                self.form.set_data(self._data)
            self.broadcast_size_hint.emit(self.sizeHint())
        super().switch_expanded_state()
        if self._expanded_first_time:
            self.form.adjustSize()
            self.updateGeometry()
            if self._expanded:
                self.form.set_pretty_display_theme()
        self.adjustSize()
        self.broadcast_size_hint.emit(self.sizeHint())

    def set_display_config(self, config_dict: dict):
        """Set the displayed information from a device config dict, which must conform to the
        bec_lib.atlas_models.Device config model."""
        self._data = DeviceConfigModel.model_validate(config_dict)
        if self._expanded_first_time:
            self.form.set_data(self._data)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not (event.buttons() and Qt.LeftButton):
            return
        if (event.pos() - self._drag_pos).manhattanLength() < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setText(self.device)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.MoveAction)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        logger.debug("Double Clicked")
        # TODO: Implement double click action for opening the device properties dialog
        return super().mouseDoubleClickEvent(event)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = QWidget()
    layout = QHBoxLayout()
    widget.setLayout(layout)
    item = DeviceItem("Device")
    layout.addWidget(DarkModeButton())
    layout.addWidget(item)
    item.set_display_config(
        {
            "name": "Test Device",
            "enabled": True,
            "deviceClass": "FakeDeviceClass",
            "deviceConfig": {"kwarg1": "value1"},
            "readoutPriority": "baseline",
            "description": "A device for testing out a widget",
            "readOnly": True,
            "softwareTrigger": False,
            "deviceTags": ["tag1", "tag2", "tag3"],
            "userParameter": {"some_setting": "some_ value"},
        }
    )
    widget.show()
    sys.exit(app.exec_())
