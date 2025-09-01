from random import randint
from typing import Any, Iterable

from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_manager.components.available_device_resources._util import (
    yield_only_passing,
)
from bec_widgets.widgets.control.device_manager.components.available_device_resources.available_device_resources_ui import (
    Ui_availableDeviceResources,
)
from bec_widgets.widgets.control.device_manager.components.available_device_resources.device_resource_backend import (
    HashableDevice,
    get_backend,
)


class AvailableDeviceResources(BECWidget, QWidget, Ui_availableDeviceResources):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setupUi(self)
        self._backend = get_backend()
        self.refresh_full_list()
        self.search_box.textChanged.connect(self.tag_groups_list.update_filter)

    def refresh_full_list(self):
        self.tag_groups_list.clear()
        for tag_group, devices in self._backend.tag_groups.items():
            self._add_tag_group(tag_group, devices)
        self._add_tag_group("Untagged devices", self._backend.untagged_devices)

    def _add_tag_group(self, tag_group: str, devices: set[HashableDevice]):
        self.tag_groups_list.add_item(
            tag_group, self.tag_groups_list, tag_group, devices, expanded=False
        )

    def _reset_devices_state(self):
        for tag_group in self.tag_groups_list.widgets():
            tag_group.reset_devices_state()

    def set_devices_state(self, devices: Iterable[HashableDevice], included: bool):
        for device in devices:
            for tag_group in self.tag_groups_list.widgets():
                tag_group.set_item_state(hash(device), included)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for list_item, tag_group_widget in self.tag_groups_list.item_widget_pairs():
            list_item.setSizeHint(tag_group_widget.sizeHint())

    @SafeSlot(list)
    def update_devices_state(self, config_list: list[dict[str, Any]]):
        self.set_devices_state(yield_only_passing(HashableDevice.model_validate, config_list), True)


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
