from typing import NamedTuple

from bec_qthemes import material_icon
from qtpy.QtCore import QSize
from qtpy.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidgetItem, QVBoxLayout, QWidget

from bec_widgets.widgets.control.device_manager.components.available_device_resources.device_resource_backend import (
    HashableDevice,
)
from bec_widgets.widgets.control.device_manager.components.available_device_resources.device_tag_group_item_ui import (
    Ui_DeviceTagGroup,
)

DEVICE_HASH_ROLE = 101


def _warning_string(spec: HashableDevice):

    names_str = "\n  ".join(spec.names)
    msg = (
        f"Device defined with multiple names! Please check:\n  {names_str}\n"
        if len(spec.names) > 1
        else ""
    )

    source_str = "\n  ".join(spec.source_files)
    source_warning = (
        f"Device found in multiple source files! Please check:\n  {source_str}"
        if len(spec.source_files) > 1
        else ""
    )
    return f"{msg}{source_warning}"


class _DeviceEntryWidget(QFrame):
    _grid_size = QSize(120, 80)

    def __init__(self, device_spec: HashableDevice, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._device_spec = device_spec
        self.included: bool = False

        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)

        self._layout = QVBoxLayout()
        self._layout.setContentsMargins(5, 5, 5, 5)
        self.setLayout(self._layout)
        self.setMinimumSize(self._grid_size)

        self.setup_title_layout(device_spec)
        self.check_and_display_warning()

        self.setToolTip(device_spec.rich_text())

        self.details = QLabel(f"Tags:\n{', '.join(device_spec.deviceTags)}")
        self.details.setStyleSheet("QLabel { font-size: 8pt; }")
        self.details.setWordWrap(True)
        self._layout.addWidget(self.details)

    def setup_title_layout(self, device_spec: HashableDevice):
        self._title_layout = QHBoxLayout()
        self._title_layout.setContentsMargins(0, 0, 0, 0)
        self._title_container = QWidget(parent=self)
        self._title_container.setLayout(self._title_layout)

        self._warning_label = QLabel()
        self._title_layout.addWidget(self._warning_label)

        self.title = QLabel(device_spec.name)
        self.title.setToolTip(device_spec.name)
        self.title.setStyleSheet(self.title_style("#FF0000"))
        self._title_layout.addWidget(self.title)

        self._layout.addWidget(self._title_container)

    def check_and_display_warning(self):
        if len(self._device_spec.names) == 1 and len(self._device_spec.source_files) == 1:
            self._warning_label.setText("")
            self._warning_label.setToolTip("")
        else:
            self._warning_label.setPixmap(material_icon("warning", size=(12, 12), color="#FFAA00"))
            self._warning_label.setToolTip(_warning_string(self._device_spec))

    @property
    def device_hash(self):
        return hash(self._device_spec)

    def title_style(self, color: str) -> str:
        return f"QLabel {{ color: {color}; font-weight: bold; font-size: 10pt; }}"

    def setTitle(self, text: str):
        self.title.setText(text)

    def set_included(self, included: bool):
        self.included = included
        self.title.setStyleSheet(self.title_style("#00FF00" if included else "#FF0000"))


class _DeviceEntry(NamedTuple):
    list_item: QListWidgetItem
    widget: _DeviceEntryWidget


class DeviceTagGroup(QWidget, Ui_DeviceTagGroup):
    def __init__(
        self, parent=None, name: str = "TagGroupTitle", data: set[HashableDevice] = set(), **kwargs
    ):
        super().__init__(parent=parent, **kwargs)
        self.setupUi(self)
        self.device_list.setGridSize(_DeviceEntryWidget._grid_size)
        self.title.setText(name)
        self._devices: dict[str, _DeviceEntry] = {}
        for device in data:
            self._add_item(device)
        self.device_list.sortItems()
        self._update_num_included()

        self.add_to_composition_button.clicked.connect(self.test)

    def _add_item(self, device: HashableDevice):
        item = QListWidgetItem(self.device_list)
        widget = _DeviceEntryWidget(device, self)
        item.setSizeHint(QSize(widget.width(), widget.height()))
        self.device_list.setItemWidget(item, widget)
        self.device_list.addItem(item)
        self._devices[device.name] = _DeviceEntry(item, widget)

    def reset_devices_state(self):
        for dev in self._devices.values():
            dev.widget.set_included(False)
        self._update_num_included()

    def set_item_state(self, /, device_hash: int, included: bool):
        for dev in self._devices.values():
            if dev.widget.device_hash == device_hash:
                dev.widget.set_included(included)
        self._update_num_included()

    def _update_num_included(self):
        n_included = sum(int(dev.widget.included) for dev in self._devices.values())
        if n_included == 0:
            color = "#FF0000"
        elif n_included == len(self._devices):
            color = "#00FF00"
        else:
            color = "#FFAA00"
        self.n_included.setText(f"{n_included} / {len(self._devices)}")
        self.n_included.setStyleSheet(f"QLabel {{ color: {color}; }}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setMinimumHeight(self.sizeHint().height())
        self.setMaximumHeight(self.sizeHint().height())

    def get_selection(self) -> set[HashableDevice]:
        selection = self.device_list.selectedItems()
        widgets = (w.widget for _, w in self._devices.items() if w.list_item in selection)
        return set(w._device_spec for w in widgets)

    def test(self, *args):
        print(self.get_selection())

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self.title.text()}"


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = DeviceTagGroup(name="Tag group 1")
    for item in [
        HashableDevice(
            **{
                "name": f"test_device_{i}",
                "deviceClass": "TestDeviceClass",
                "readoutPriority": "baseline",
                "enabled": True,
            }
        )
        for i in range(5)
    ]:
        widget._add_item(item)
    widget._update_num_included()
    widget.show()
    sys.exit(app.exec())
