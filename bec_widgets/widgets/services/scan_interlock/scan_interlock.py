from bec_lib.builtin_actor_hli import ScanInterlockHli
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import BlStateStatus
from qtpy import QtGui, QtWidgets
from qtpy.QtCore import Qt

from bec_widgets.utils.bec_widget import BECWidget, ConnectionConfig
from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.utility.toggle.toggle import ToggleSwitch


class ScanInterlockToggle(ToggleSwitch):
    def __init__(self, interlock: ScanInterlockHli, parent):
        super().__init__(parent=parent)
        self._interlock = interlock

    def mousePressEvent(self, event):
        if self.isEnabled() and event.button() == Qt.MouseButton.LeftButton:
            self._interlock.enabled = not self.checked


class BlStateList(QtWidgets.QListWidget):
    def __init__(self, interlock: ScanInterlockHli, parent):
        super().__init__(parent)
        self._interlock = interlock

    def dropEvent(self, event: QtGui.QDropEvent, /) -> None:
        data = event.mimeData()
        if not data.hasText():
            return
        self._interlock.add_state_to_interlock(data.text(), "valid")


class ScanInterlockControl(BECWidget, QtWidgets.QWidget):
    """
    ScanInterlockControl can be used to enable/disable the scan interlock actor,
    and add/remove beamline states for it to watch.
    """

    RPC = False
    PLUGIN = True

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        client=None,
        config: ConnectionConfig | None = None,
        gui_id: str | None = None,
        theme_update: bool = False,
        **kwargs,
    ):
        """
        Args:
            parent (QtWidgets.QWidget, optional): The parent widget.
            client: The BEC client.
            config (ConnectionConfig, optional): The connection configuration.
            gui_id (str, optional): The GUI ID.
            theme_update (bool, optional): Whether to subscribe to theme updates. Defaults to False.
        """
        super().__init__(
            parent=parent,
            client=client,
            config=config,
            gui_id=gui_id,
            theme_update=theme_update,
            **kwargs,
        )
        self._interlock = self.client.builtin_actors.scan_interlock
        self._layout = QtWidgets.QVBoxLayout(self)
        self._setup_control_layout()
        self._setup_list_layout()
        self.bec_dispatcher.connect_slot(
            self._update_all_content,
            MessageEndpoints.builtin_actor_update_notif("ScanInterlockActor"),
        )
        self._update_all_content()

    def _setup_control_layout(self):
        self._controls_layout = QtWidgets.QHBoxLayout()
        self._layout.addLayout(self._controls_layout)
        self._enabled_text = QtWidgets.QLabel()
        self._enabled_text.setText("Widget Uninitialised")
        self._enabled_toggle = ScanInterlockToggle(self._interlock, parent=self)
        self._controls_layout.addWidget(self._enabled_text)
        self._controls_layout.addWidget(self._enabled_toggle)
        self._enabled_toggle

    def _set_enabled_text(self, enabled: bool):
        self._enabled_text.setText(
            "Scan Interlock Enabled" if enabled else "Scan Interlock Disabled"
        )

    def _setup_list_layout(self):
        self._list_layout = QtWidgets.QVBoxLayout()
        self._layout.addLayout(self._list_layout)
        self._list_layout.addWidget(QtWidgets.QLabel("Beamline states watched:"))
        self._bl_states_list = BlStateList(self._interlock, self)
        self._bl_states_list.setDragDropMode(QtWidgets.QListWidget.DragDropMode.DropOnly)
        self._list_layout.addWidget(self._bl_states_list)

        self._delete_button_layout = QtWidgets.QHBoxLayout()
        self._list_layout.addLayout(self._delete_button_layout)

        self._delete_button = QtWidgets.QPushButton("Remove selected states from interlock")
        self._delete_button_layout.addWidget(self._delete_button)
        self._delete_button.clicked.connect(self._delete_selected)

        self._delete_all_button = QtWidgets.QPushButton("Remove all states")
        self._delete_button_layout.addWidget(self._delete_all_button)
        self._delete_all_button.clicked.connect(self._delete_all)

    @SafeSlot()
    def _delete_selected(self):
        to_delete = [i.text() for i in self._bl_states_list.selectedItems()]
        for state in to_delete:
            self._interlock.remove_state_from_interlock(state)

    @SafeSlot()
    def _delete_all(self):
        self._interlock.clear_all()

    def _update_list(self, list_content: dict[str, BlStateStatus]):
        self._bl_states_list.clear()
        for item in list_content:
            self._bl_states_list.addItem(item)

    @SafeSlot()
    def _update_all_content(self, *_, **__):
        self._set_enabled_text(self._interlock.enabled)
        self._enabled_toggle.setChecked(self._interlock.enabled)
        self._update_list(self._interlock.states_watched)


if __name__ == "__main__":  # pragma: no cover
    # pylint: disable=import-outside-toplevel

    from qtpy.QtWidgets import QApplication

    from bec_widgets.widgets.utility.visual.dark_mode_button.dark_mode_button import DarkModeButton

    app = QApplication([])
    main_window = QtWidgets.QMainWindow()

    central_widget = QtWidgets.QWidget()
    button = DarkModeButton()
    layout = QtWidgets.QVBoxLayout(central_widget)
    main_window.setCentralWidget(central_widget)
    scan_interlock_control = ScanInterlockControl()  # type: ignore
    layout.addWidget(button)
    layout.addWidget(scan_interlock_control)

    class TestList(QtWidgets.QListWidget):
        def mimeData(self, items, /):
            mimedata = super().mimeData(items)
            text = ",".join([i.text() for i in items])
            mimedata.setText(text)
            return mimedata

    test_list = TestList()
    test_list.addItems(["samx_in_limits", "samy_in_limits"])
    test_list.setDragEnabled(True)

    layout.addWidget(test_list)
    lineedit = QtWidgets.QLineEdit()
    lineedit.setDragEnabled(True)
    layout.addWidget(lineedit)
    main_window.setWindowTitle("Scan Interlock Control")
    main_window.resize(800, 400)
    main_window.show()
    app.exec_()
