from __future__ import annotations

from qtpy.QtCore import QEventLoop
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox
from bec_widgets.widgets.plots.waveform.waveform import Waveform


class ViewBase(QWidget):
    """Wrapper for a content widget used inside the main app's stacked view.

    Subclasses can implement `on_enter` and `on_exit` to run custom logic when the view becomes visible or is about to be hidden.

    Args:
        content (QWidget): The actual view widget to display.
        parent (QWidget | None): Parent widget.
        id (str | None): Optional view id, useful for debugging or introspection.
        title (str | None): Optional human-readable title.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        content: QWidget | None = None,
        *,
        id: str | None = None,
        title: str | None = None,
    ):
        super().__init__(parent=parent)
        self.content: QWidget | None = None
        self.view_id = id
        self.view_title = title

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        if content is not None:
            self.set_content(content)

    def set_content(self, content: QWidget) -> None:
        """Replace the current content widget with a new one."""
        if self.content is not None:
            self.content.setParent(None)
        self.content = content
        self.layout().addWidget(content)

    @SafeSlot()
    def on_enter(self) -> None:
        """Called after the view becomes current/visible.

        Default implementation does nothing. Override in subclasses.
        """
        pass

    @SafeSlot()
    def on_exit(self) -> bool:
        """Called before the view is switched away/hidden.

        Return True to allow switching, or False to veto.
        Default implementation allows switching.
        """
        return True


####################################################################################################
# Example views for demonstration/testing purposes
####################################################################################################


# --- Popup UI version ---
class WaveformViewPopup(ViewBase):  # pragma: no cover
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        self.waveform = Waveform(parent=self)
        self.set_content(self.waveform)

    @SafeSlot()
    def on_enter(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Configure Waveform View")

        label = QLabel("Select device and signal for the waveform plot:", parent=dialog)

        # same as in the CurveRow used in waveform
        self.device_edit = DeviceComboBox(parent=self)
        self.device_edit.insertItem(0, "")
        self.device_edit.setEditable(True)
        self.device_edit.setCurrentIndex(0)
        self.signal_edit = SignalComboBox(parent=self)
        self.signal_edit.include_config_signals = False
        self.signal_edit.insertItem(0, "")
        self.signal_edit.setEditable(True)
        self.device_edit.currentTextChanged.connect(self.signal_edit.set_device)
        self.device_edit.device_reset.connect(self.signal_edit.reset_selection)

        form = QFormLayout()
        form.addRow(label)
        form.addRow("Device", self.device_edit)
        form.addRow("Signal", self.signal_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        v = QVBoxLayout(dialog)
        v.addLayout(form)
        v.addWidget(buttons)

        if dialog.exec_() == QDialog.Accepted:
            self.waveform.plot(
                device_y=self.device_edit.currentText(), signal_y=self.signal_edit.currentText()
            )

    @SafeSlot()
    def on_exit(self) -> bool:
        ans = QMessageBox.question(
            self,
            "Switch and clear?",
            "Do you want to switch views and clear the plot?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self.waveform.clear_all()
            return True
        return False


# --- Inline stacked UI version ---
class WaveformViewInline(ViewBase):  # pragma: no cover
    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent=parent, *args, **kwargs)

        # Root layout for this view uses a stacked layout
        self.stack = QStackedLayout()
        container = QWidget(self)
        container.setLayout(self.stack)
        self.set_content(container)

        # --- Page 0: Settings page (inline form)
        self.settings_page = QWidget()
        sp_layout = QVBoxLayout(self.settings_page)
        sp_layout.setContentsMargins(16, 16, 16, 16)
        sp_layout.setSpacing(12)

        title = QLabel("Select device and signal for the waveform plot:", parent=self.settings_page)
        self.device_edit = DeviceComboBox(parent=self.settings_page)
        self.device_edit.insertItem(0, "")
        self.device_edit.setEditable(True)
        self.device_edit.setCurrentIndex(0)

        self.entry_edit = SignalComboBox(parent=self.settings_page)
        self.entry_edit.include_config_signals = False
        self.entry_edit.insertItem(0, "")
        self.entry_edit.setEditable(True)
        self.device_edit.currentTextChanged.connect(self.entry_edit.set_device)
        self.device_edit.device_reset.connect(self.entry_edit.reset_selection)

        form = QFormLayout()
        form.addRow(title)
        form.addRow("Device", self.device_edit)
        form.addRow("Signal", self.entry_edit)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("OK", parent=self.settings_page)
        cancel_btn = QPushButton("Cancel", parent=self.settings_page)
        btn_row.addStretch(1)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)

        sp_layout.addLayout(form)
        sp_layout.addLayout(btn_row)

        # --- Page 1: Waveform page
        self.waveform_page = QWidget()
        wf_layout = QVBoxLayout(self.waveform_page)
        wf_layout.setContentsMargins(0, 0, 0, 0)
        self.waveform = Waveform(parent=self.waveform_page)
        wf_layout.addWidget(self.waveform)

        # --- Page 2: Exit confirmation page (inline)
        self.confirm_page = QWidget()
        cp_layout = QVBoxLayout(self.confirm_page)
        cp_layout.setContentsMargins(16, 16, 16, 16)
        cp_layout.setSpacing(12)
        qlabel = QLabel("Do you want to switch views and clear the plot?", parent=self.confirm_page)
        cp_buttons = QHBoxLayout()
        no_btn = QPushButton("No", parent=self.confirm_page)
        yes_btn = QPushButton("Yes", parent=self.confirm_page)
        cp_buttons.addStretch(1)
        cp_buttons.addWidget(no_btn)
        cp_buttons.addWidget(yes_btn)
        cp_layout.addWidget(qlabel)
        cp_layout.addLayout(cp_buttons)

        # Add pages to the stack
        self.stack.addWidget(self.settings_page)  # index 0
        self.stack.addWidget(self.waveform_page)  # index 1
        self.stack.addWidget(self.confirm_page)  # index 2

        # Wire settings buttons
        ok_btn.clicked.connect(self._apply_settings_and_show_waveform)
        cancel_btn.clicked.connect(self._show_waveform_without_changes)

        # Prepare result holder for the inline confirmation
        self._exit_choice_yes = None
        yes_btn.clicked.connect(lambda: self._exit_reply(True))
        no_btn.clicked.connect(lambda: self._exit_reply(False))

    @SafeSlot()
    def on_enter(self) -> None:
        # Always start on the settings page when entering
        self.stack.setCurrentIndex(0)

    @SafeSlot()
    def on_exit(self) -> bool:
        # Show inline confirmation page and synchronously wait for a choice
        # -> trick to make the choice blocking, however popup would be cleaner solution
        self._exit_choice_yes = None
        self.stack.setCurrentIndex(2)
        loop = QEventLoop()
        self._exit_loop = loop
        loop.exec_()

        if self._exit_choice_yes:
            self.waveform.clear_all()
            return True
        # Revert to waveform view if user cancelled switching
        self.stack.setCurrentIndex(1)
        return False

    def _apply_settings_and_show_waveform(self):
        dev = self.device_edit.currentText()
        sig = self.entry_edit.currentText()
        if dev and sig:
            self.waveform.plot(device_y=dev, signal_y=sig)
        self.stack.setCurrentIndex(1)

    def _show_waveform_without_changes(self):
        # Just show waveform page without plotting
        self.stack.setCurrentIndex(1)

    def _exit_reply(self, yes: bool):
        self._exit_choice_yes = bool(yes)
        if hasattr(self, "_exit_loop") and self._exit_loop.isRunning():
            self._exit_loop.quit()
