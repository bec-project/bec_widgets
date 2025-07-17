from bec_lib.device import Device
from bec_qthemes import material_icon
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from bec_widgets.utils.bec_connector import ConnectionConfig
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.ophyd_kind_util import Kind
from bec_widgets.widgets.containers.dock.dock import BECDock
from bec_widgets.widgets.utility.signal_label.signal_label import SignalLabel


class SignalDisplay(BECWidget, QWidget):
    RPC = False

    def __init__(
        self,
        client=None,
        device: str = "",
        config: ConnectionConfig = None,
        gui_id: str | None = None,
        theme_update: bool = False,
        parent_dock: BECDock | None = None,
        **kwargs,
    ):
        """A widget to display all the signals from a given device, and allow getting
        a fresh reading."""
        super().__init__(client, config, gui_id, theme_update, parent_dock, **kwargs)
        self.get_bec_shortcuts()
        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self._content = QWidget()
        self._layout.addWidget(self._content)
        self._device = device
        self.device = device

    @SafeSlot()
    def _refresh(self):
        if (dev := self.dev.get(self.device)) is not None:
            dev.read()
            dev.read_configuration()

    def _add_refresh_button(self):
        button_holder = QWidget()
        button_holder.setLayout(QHBoxLayout())
        button_holder.layout().setAlignment(Qt.AlignmentFlag.AlignRight)
        button_holder.layout().setContentsMargins(0, 0, 0, 0)
        refresh_button = QToolButton()
        refresh_button.setIcon(
            material_icon(icon_name="refresh", size=(20, 20), convert_to_pixmap=False)
        )
        refresh_button.clicked.connect(self._refresh)
        button_holder.layout().addWidget(refresh_button)
        self._content_layout.addWidget(button_holder)

    def _populate(self):
        self._content.deleteLater()
        self._content = QWidget()
        self._layout.addWidget(self._content)
        self._content_layout = QVBoxLayout()
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content.setLayout(self._content_layout)

        self._add_refresh_button()

        if self._device in self.dev:
            if isinstance(self.dev[self.device], Device):
                for sig, info in self.dev[self.device]._info.get("signals", {}).items():
                    if info.get("kind_str") in [
                        Kind.hinted.name,
                        Kind.normal.name,
                        Kind.config.name,
                    ]:
                        self._content_layout.addWidget(
                            SignalLabel(
                                device=self._device,
                                signal=sig,
                                show_select_button=False,
                                show_default_units=True,
                            )
                        )
            else:
                self._content_layout.addWidget(
                    SignalLabel(
                        device=self._device,
                        signal=self._device,
                        show_select_button=False,
                        show_default_units=True,
                    )
                )
            self._content_layout.addStretch(1)
        else:
            self._content_layout.addWidget(
                QLabel(f"Device {self.device} not found in device manager!")
            )

    @SafeProperty(str)
    def device(self):
        return self._device

    @device.setter
    def device(self, value: str):
        self._device = value
        self._populate()


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    from bec_widgets.utils.colors import set_theme

    app = QApplication(sys.argv)
    set_theme("light")
    widget = SignalDisplay(device="samx")
    widget.show()
    sys.exit(app.exec_())
