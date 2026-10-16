from __future__ import annotations

from typing import TYPE_CHECKING

import yaml
from bec_lib.atlas_models import Device as DeviceConfigModel
from bec_lib.config_helper import ConfigHelper
from bec_lib.devicemanager import DeviceContainer
from bec_lib.logger import bec_logger
from bec_lib.messages import ConfigAction
from bec_qthemes import material_icon
from qtpy.QtCore import QMimeData, QSize, Qt, QThreadPool, Signal
from qtpy.QtGui import QDrag, QFontDatabase
from qtpy.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.applications.views.device_manager_view.device_manager_dialogs import (
    DeviceFormDialog,
)
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.expandable_frame import ExpandableGroupFrame
from bec_widgets.widgets.services.device_browser.device_item.config_communicator import (
    CommunicateConfigAction,
)
from bec_widgets.widgets.services.device_browser.device_item.device_signal_display import (
    SignalDisplay,
)

if TYPE_CHECKING:  # pragma: no cover
    from qtpy.QtGui import QMouseEvent


logger = bec_logger.logger

# Changing any of these means the device server has to remove and recreate the device
_RECREATE_KEYS = {"name", "deviceClass", "deviceConfig"}


def config_to_yaml(config: DeviceConfigModel) -> str:
    """Format a device config as YAML for display, with the name and class first.

    Args:
        config (DeviceConfigModel): the device config to format.

    Returns:
        str: the YAML text.
    """
    data = config.model_dump(mode="json", exclude_none=True)
    ordered = {key: data.pop(key) for key in ("name", "deviceClass") if key in data}
    return yaml.safe_dump({**ordered, **data}, sort_keys=False, default_flow_style=False)


def config_change(current: dict, edited: dict) -> dict:
    """Work out what to send to BEC for an edit of a device config.

    Args:
        current (dict): the config of the device as it is in BEC.
        edited (dict): the config from the edit dialog. Keys it leaves out keep their current value.

    Returns:
        dict: an empty dict if nothing changed, the whole config if the device must be recreated,
            otherwise only the changed entries.
    """
    current_dump = DeviceConfigModel.model_validate(current).model_dump()
    new_dump = DeviceConfigModel.model_validate({**current, **edited}).model_dump()
    diff = {k: v for k, v in new_dump.items() if current_dump.get(k) != v}
    if _RECREATE_KEYS & diff.keys():
        return new_dump
    return diff


class DeviceItem(ExpandableGroupFrame):
    RPC = False

    def __init__(
        self,
        *,
        parent,
        device: str,
        devices: DeviceContainer,
        icon: str = "",
        config_helper: ConfigHelper,
        q_threadpool: QThreadPool | None = None,
    ) -> None:
        super().__init__(parent, title=device, expanded=False, icon=icon)
        self.dev = devices
        self._drag_pos = None
        self._expanded_first_time = False
        self._data = None
        self.device = device

        self._layout = QHBoxLayout()
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._tab_widget = QTabWidget(tabShape=QTabWidget.TabShape.Rounded)
        self._tab_widget.setDocumentMode(True)
        self._layout.addWidget(self._tab_widget)

        self._form_page = QWidget(parent=self)
        self._form_page_layout = QVBoxLayout()
        self._form_page.setLayout(self._form_page_layout)

        self._signal_page = QWidget(parent=self)
        self._signal_page_layout = QVBoxLayout()
        self._signal_page.setLayout(self._signal_page_layout)

        self._tab_widget.addTab(self._form_page, "Configuration")
        self._tab_widget.addTab(self._signal_page, "Signals")
        self._config_helper = config_helper
        self._q_threadpool = q_threadpool or QThreadPool()

        self.set_layout(self._layout)
        self.adjustSize()

    def _create_title_layout(self, title: str, icon: str):
        super()._create_title_layout(title, icon)

        self.edit_button = QToolButton()
        self.edit_button.setIcon(material_icon(icon_name="edit", size=(15, 15)))
        self._title_layout.insertWidget(self._title_layout.count() - 1, self.edit_button)
        self.edit_button.clicked.connect(self._create_edit_dialog)

        self.delete_button = QToolButton()
        self.delete_button.setIcon(material_icon(icon_name="delete", size=(15, 15)))
        self._title_layout.insertWidget(self._title_layout.count() - 1, self.delete_button)
        self.delete_button.clicked.connect(self._delete_device)

    @SafeSlot()
    def _create_edit_dialog(self):
        dialog = DeviceFormDialog(parent=self, add_btn_text="Apply Changes")
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.setWindowTitle(f"Edit config for: {self.device}")
        dialog.set_device_config(self._current_config())
        dialog.accepted_data.connect(self._apply_edited_config)
        dialog.open()

    @SafeSlot(dict, int, int, str, str, popup_error=True)
    def _apply_edited_config(self, config: dict, *_):
        change = config_change(self._current_config(), config)
        if not change:
            logger.info(f"No changes made to the config of {self.device}")
            return
        new_name = change.get("name", self.device)
        if new_name != self.device and new_name in self.dev:
            raise ValueError(f"Can't rename {self.device}: a device named {new_name} exists!")
        logger.info(f"Sending request to update device config of {self.device}: {change}")
        updater = CommunicateConfigAction(self._config_helper, self.device, change, "update")
        updater.signals.error.connect(self._update_error)
        updater.signals.done.connect(
            self._deletion_done if new_name != self.device else self._reload_config
        )
        self._q_threadpool.start(updater)

    @SafeSlot(Exception, popup_error=True)
    def _update_error(self, e: Exception):
        self._reload_config()
        raise e

    @SafeSlot()
    def _delete_device(self):
        self.expanded = False
        deleter = CommunicateConfigAction(self._config_helper, self.device, None, "remove")
        deleter.signals.error.connect(self._deletion_error)
        deleter.signals.done.connect(self._deletion_done)
        self._q_threadpool.start(deleter)

    @SafeSlot(Exception, popup_error=True)
    def _deletion_error(self, e: Exception):
        raise e

    @SafeSlot()
    def _deletion_done(self):
        self.imminent_deletion.emit()
        self.deleteLater()

    @SafeSlot()
    def switch_expanded_state(self):
        if not self.expanded and not self._expanded_first_time:
            self._expanded_first_time = True
            self.config_view = QLabel(parent=self)
            self.config_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            self.config_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.config_view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            # long values are clipped instead of widening the whole device list
            self.config_view.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            self._form_page_layout.addWidget(self.config_view)
            self.signals = SignalDisplay(parent=self, device=self.device)
            self._signal_page_layout.addWidget(self.signals)
            self._reload_config()
            self.broadcast_size_hint.emit(self.sizeHint())
        super().switch_expanded_state()
        if self._expanded_first_time:
            self.config_view.adjustSize()
            self.updateGeometry()
        self.adjustSize()
        self.broadcast_size_hint.emit(self.sizeHint())

    @SafeSlot(bool)
    def set_editable(self, enabled: bool):
        self.edit_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled)

    @SafeSlot(str, dict)
    def config_update(self, action: ConfigAction, content: dict) -> None:
        if self.device in content:
            self._reload_config()

    @SafeSlot(popup_error=True)
    def _reload_config(self, *_):
        self.set_display_config(self._current_config())

    def _current_config(self) -> dict:
        return self.dev[self.device]._config  # pylint: disable=protected-access

    def set_display_config(self, config_dict: dict):
        """Set the displayed information from a device config dict, which must conform to the
        bec_lib.atlas_models.Device config model."""
        self._data = DeviceConfigModel.model_validate(config_dict)
        if self._expanded_first_time:
            self.config_view.setText(config_to_yaml(self._data))

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
    from unittest.mock import MagicMock

    from qtpy.QtWidgets import QApplication

    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QApplication(sys.argv)
    widget = QWidget()
    layout = QHBoxLayout()
    widget.setLayout(layout)
    mock_config = {
        "name": "Test Device",
        "enabled": True,
        "deviceClass": "FakeDeviceClass",
        "deviceConfig": {"kwarg1": "value1"},
        "readoutPriority": "baseline",
        "description": "A device for testing out a widget",
        "readOnly": True,
        "softwareTrigger": False,
        "deviceTags": {"tag1", "tag2", "tag3"},
        "userParameter": {"some_setting": "some_ value"},
    }
    item = DeviceItem(
        parent=widget,
        device="Device",
        devices={"Device": MagicMock(enabled=True, _config=mock_config)},  # type: ignore
        config_helper=ConfigHelper(MagicMock()),
    )
    layout.addWidget(DarkModeButton())
    layout.addWidget(item)
    widget.show()
    sys.exit(app.exec_())
