from random import randint
from typing import Any, Iterable
from uuid import uuid4

from qtpy.QtCore import QItemSelection, Signal  # type: ignore
from qtpy.QtWidgets import QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_manager.components._util import (
    SharedSelectionSignal,
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

    selected_devices = Signal(list)  # list[dict[str,Any]] of device configs currently selected
    add_selected_devices = Signal(list)
    del_selected_devices = Signal(list)

    def __init__(self, parent=None, shared_selection_signal=SharedSelectionSignal(), **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.setupUi(self)
        self._backend = get_backend()
        self._shared_selection_signal = shared_selection_signal
        self._shared_selection_uuid = str(uuid4())
        self._shared_selection_signal.proc.connect(self._handle_shared_selection_signal)
        self.device_groups_list.selectionModel().selectionChanged.connect(
            self._on_selection_changed
        )
        self.grouping_selector.addItem("deviceTags")
        self.grouping_selector.addItems(self._backend.allowed_sort_keys)
        self._grouping_selection_changed("deviceTags")
        self.grouping_selector.currentTextChanged.connect(self._grouping_selection_changed)
        self.search_box.textChanged.connect(self.device_groups_list.update_filter)

        self.tb_add_selected.action.triggered.connect(self._add_selected_action)
        self.tb_del_selected.action.triggered.connect(self._del_selected_action)

    def refresh_full_list(self, device_groups: dict[str, set[HashableDevice]]):
        self.device_groups_list.clear()
        for device_group, devices in device_groups.items():
            self._add_device_group(device_group, devices)
        if self.grouping_selector.currentText == "deviceTags":
            self._add_device_group("Untagged devices", self._backend.untagged_devices)
        self.device_groups_list.sortItems()

    def _add_device_group(self, device_group: str, devices: set[HashableDevice]):
        item, widget = self.device_groups_list.add_item(
            device_group,
            self.device_groups_list,
            device_group,
            devices,
            shared_selection_signal=self._shared_selection_signal,
            expanded=False,
        )
        item.setData(CONFIG_DATA_ROLE, widget.create_mime_data())
        # Re-emit the selected items from a subgroup - all other selections should be disabled anyway
        widget.selected_devices.connect(self.selected_devices)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for list_item, device_group_widget in self.device_groups_list.item_widget_pairs():
            list_item.setSizeHint(device_group_widget.sizeHint())

    @SafeSlot()
    def _add_selected_action(self):
        self.add_selected_devices.emit(self.device_groups_list.any_selected_devices())

    @SafeSlot()
    def _del_selected_action(self):
        self.del_selected_devices.emit(self.device_groups_list.any_selected_devices())

    @SafeSlot(QItemSelection, QItemSelection)
    def _on_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        self.selected_devices.emit(self.device_groups_list.selected_devices_from_groups())
        self._shared_selection_signal.proc.emit(self._shared_selection_uuid)

    @SafeSlot(str)
    def _handle_shared_selection_signal(self, uuid: str):
        if uuid != self._shared_selection_uuid:
            self.device_groups_list.clearSelection()

    def _set_devices_state(self, devices: Iterable[HashableDevice], included: bool):
        for device in devices:
            for device_group in self.device_groups_list.widgets():
                device_group.set_item_state(hash(device), included)

    @SafeSlot(list)
    def mark_devices_used(self, config_list: list[dict[str, Any]], used: bool):
        """Set the display color of individual devices and update the group display of numbers
        included. Accepts a list of dicts with the complete config as used in
        bec_lib.atlas_models.Device."""
        self._set_devices_state(
            yield_only_passing(HashableDevice.model_validate, config_list), used
        )

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
    widget._set_devices_state(
        list(filter(lambda _: randint(0, 1) == 1, widget._backend.all_devices)), True
    )
    widget.show()
    sys.exit(app.exec())
