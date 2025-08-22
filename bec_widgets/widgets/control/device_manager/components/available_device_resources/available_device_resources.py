from random import randint
from typing import Any, Callable, Generator, Iterable, TypeVar

from qtpy.QtCore import QSize
from qtpy.QtWidgets import QListWidgetItem, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_manager.components.available_device_resources.available_device_resources_ui import (
    Ui_availableDeviceResources,
)
from bec_widgets.widgets.control.device_manager.components.available_device_resources.device_resource_backend import (
    HashableDevice,
    get_backend,
)
from bec_widgets.widgets.control.device_manager.components.available_device_resources.device_tag_group import (
    DeviceTagGroup,
)

_T = TypeVar("_T")
_RT = TypeVar("_RT")


def _yield_only_passing(fn: Callable[[_T], _RT], vals: Iterable[_T]) -> Generator[_RT, Any, None]:
    for v in vals:
        try:
            yield fn(v)
        except BaseException:
            pass


class AvailableDeviceResources(BECWidget, QWidget, Ui_availableDeviceResources):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setupUi(self)
        self._backend = get_backend()
        self._items: dict[str, tuple[QListWidgetItem, DeviceTagGroup]] = {}
        self.refresh_full_list()

    def refresh_full_list(self):
        self.tag_groups_list.clear()
        self._items = {}
        for tag_group, devices in self._backend.tag_groups.items():
            item = QListWidgetItem(self.tag_groups_list)
            tag_group_widget = DeviceTagGroup(self.tag_groups_list, tag_group, devices)
            self.tag_groups_list.setItemWidget(item, tag_group_widget)
            self.tag_groups_list.addItem(item)
            self._items[tag_group] = (item, tag_group_widget)
            item.setSizeHint(QSize(tag_group_widget.width(), tag_group_widget.height()))

    def set_devices_state(self, devices: Iterable[HashableDevice], included: bool):
        for _, tag_group in self._items.values():
            for device in devices:
                tag_group.set_item_state(hash(device), included)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for list_item, tag_group_widget in self._items.values():
            list_item.setSizeHint(tag_group_widget.sizeHint())

    @SafeSlot(list)
    def update_devices_state(self, config_list: list[dict[str, Any]]):
        self.set_devices_state(
            _yield_only_passing(HashableDevice.model_validate, config_list), True
        )


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = AvailableDeviceResources()
    widget.set_devices_state(
        list(filter(lambda _: randint(0, 1) == 1, widget._backend.all_devices)), True
    )
    widget.show()
    sys.exit(app.exec())
