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
from bec_widgets.widgets.control.device_manager.components.constants import CONFIG_DATA_ROLE


class AvailableDeviceResources(BECWidget, QWidget, Ui_availableDeviceResources):
    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setupUi(self)
        self._backend = get_backend()
        self.grouping_selector.addItem("deviceTags")
        self.grouping_selector.addItems(self._backend.allowed_sort_keys)
        self._grouping_selection_changed("deviceTags")
        self.grouping_selector.currentTextChanged.connect(self._grouping_selection_changed)
        self.search_box.textChanged.connect(self.device_groups_list.update_filter)

    def refresh_full_list(self, device_groups: dict[str, set[HashableDevice]]):
        self.device_groups_list.clear()
        for device_group, devices in device_groups.items():
            self._add_device_group(device_group, devices)
        if self.grouping_selector.currentText == "deviceTags":
            self._add_device_group("Untagged devices", self._backend.untagged_devices)
        self.device_groups_list.sortItems()

    def _add_device_group(self, device_group: str, devices: set[HashableDevice]):
        item, widget = self.device_groups_list.add_item(
            device_group, self.device_groups_list, device_group, devices, expanded=False
        )
        item.setData(CONFIG_DATA_ROLE, widget.create_mime_data())

    def _reset_devices_state(self):
        for device_group in self.device_groups_list.widgets():
            device_group.reset_devices_state()

    def set_devices_state(self, devices: Iterable[HashableDevice], included: bool):
        for device in devices:
            for device_group in self.device_groups_list.widgets():
                device_group.set_item_state(hash(device), included)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for list_item, device_group_widget in self.device_groups_list.item_widget_pairs():
            list_item.setSizeHint(device_group_widget.sizeHint())

    @SafeSlot(list)
    def update_devices_state(self, config_list: list[dict[str, Any]]):
        self.set_devices_state(yield_only_passing(HashableDevice.model_validate, config_list), True)

    @SafeSlot(str)
    def _grouping_selection_changed(self, sort_key: str):
        self.search_box.setText("")
        if sort_key == "deviceTags":
            device_groups = self._backend.tag_groups
        else:
            device_groups = self._backend.group_by_key(sort_key)
        self.refresh_full_list(device_groups)


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
