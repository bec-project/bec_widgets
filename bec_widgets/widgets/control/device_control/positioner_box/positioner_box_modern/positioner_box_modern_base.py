"""Shared logic for the modernized positioner boxes (QML and QWidget versions).

Both views render the same state and call the same actions, so the BEC handling lives here once
and the comparison between the two versions is only about the view layer.
"""

from __future__ import annotations

import math

from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, QObject, QPoint, Qt, Signal, Slot
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import QFrame, QLineEdit, QListWidget, QVBoxLayout, QWidget

from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_base import (
    PositionerBoxBase,
)

logger = bec_logger.logger

MOVING_UNKNOWN = -1
MOVING_IDLE = 0
MOVING_ACTIVE = 1


def _format(value: float | None, precision: int) -> str:
    if value is None:
        return "—"
    return f"{value:.{precision}f}"


class PositionerState(QObject):
    """Read-only view state of a positioner box, exposed to QML as ``box``.

    Every property shares the single ``changed`` signal, so a readback update costs one
    notification regardless of how many fields changed.
    """

    changed = Signal()

    def __init__(self, box: "ModernPositionerBoxBase"):
        super().__init__(box)
        self._box = box

    def _prop(name, type_, notify=changed):  # pylint: disable=no-self-argument
        # pylint: disable=protected-access
        return Property(type_, lambda self: getattr(self._box, name), notify=notify)

    device = _prop("_device", str)
    units = _prop("_units", str)
    readbackText = _prop("readback_text", str)
    targetText = _prop("target_text", str)
    hasTarget = _prop("has_target", bool)
    moving = _prop("_moving", int)
    hasLimits = _prop("has_limits", bool)
    lowText = _prop("low_text", str)
    highText = _prop("high_text", str)
    position = _prop("position_fraction", float)
    targetPosition = _prop("target_fraction", float)
    outOfLimits = _prop("out_of_limits", bool)
    stepText = _prop("step_text", str)
    deviceSelectable = _prop("device_selectable", bool)
    ready = _prop("ready", bool)

    # pylint: disable=invalid-name
    @Slot(str, result=str)
    def validate(self, text: str) -> str:
        """Return an error message for a target text, or an empty string if it is valid."""
        return self._box.validate_target(text)

    @Slot(str, result=bool)
    def moveTo(self, text: str) -> bool:
        """Move to the typed target. Returns True if a move was sent."""
        return self._box.move_to_text(text)

    @Slot(int)
    def tweak(self, direction: int):
        """Tweak by one step in the given direction (+1 or -1)."""
        self._box.tweak(direction)

    @Slot()
    def stop(self):
        """Stop the device."""
        self._box.on_stop()

    @Slot(str)
    def setStepText(self, text: str):
        """Set the step size from text; invalid text is ignored."""
        self._box.set_step_text(text)

    @Slot(float)
    def scaleStep(self, factor: float):
        """Multiply the step size, e.g. by 10 or 0.1."""
        self._box.scale_step(factor)

    @Slot()
    def pickDevice(self):
        """Open the device picker at the mouse position."""
        self._box.open_device_picker(QCursor.pos())


class DevicePickerPopup(QFrame):
    """Searchable popup list of positioners. Click or Enter picks, Esc closes."""

    def __init__(self, names: list[str], current: str, on_pick, parent: QWidget | None = None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._on_pick = on_pick
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search positioners")
        self.search.setClearButtonEnabled(True)
        self.list = QListWidget(self)
        self.list.addItems(names)
        layout.addWidget(self.search)
        layout.addWidget(self.list)
        self.setFixedSize(220, min(320, 60 + 24 * max(len(names), 3)))
        matches = self.list.findItems(current, Qt.MatchFlag.MatchExactly)
        if matches:
            self.list.setCurrentItem(matches[0])
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._pick_current)
        self.list.itemClicked.connect(lambda item: self._pick(item.text()))
        self.list.itemActivated.connect(lambda item: self._pick(item.text()))
        self.search.setFocus()

    def _filter(self, text: str):
        first = None
        for row in range(self.list.count()):
            item = self.list.item(row)
            hidden = text.lower() not in item.text().lower()
            item.setHidden(hidden)
            if not hidden and first is None:
                first = item
        if first is not None:
            self.list.setCurrentItem(first)

    def _pick_current(self):
        item = self.list.currentItem()
        if item is not None and not item.isHidden():
            self._pick(item.text())

    def _pick(self, name: str):
        self.close()
        self._on_pick(name)


class ModernPositionerBoxBase(PositionerBoxBase):
    """Positioner box with the modernized UX. Subclasses only build the view.

    Keeps the public API of :class:`PositionerBox`: ``device``, ``hide_device_selection``,
    ``set_positioner``, ``show_device_selection``, ``step_size``, ``on_stop``,
    ``force_update_readback`` and the ``device_changed`` and ``position_update`` signals.
    """

    PLUGIN = False
    RPC = False
    USER_ACCESS = ["set_positioner", "attach", "detach", "screenshot"]

    device_changed = Signal(str, str)
    position_update = Signal(float)

    def __init__(self, parent=None, device: Positioner | str | None = None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self._device = ""
        self._units = ""
        self._precision = 8
        self._readback: float | None = None
        self._setpoint: float | None = None
        self._moving = MOVING_UNKNOWN
        self._limits: tuple[float, float] | None = None
        self._step = 0.1
        self._hide_device_selection = False
        self.state = PositionerState(self)
        self._picker: DevicePickerPopup | None = None
        self.init_view()
        if isinstance(device, Positioner):
            device = device.name
        self.device = device

    def init_view(self):
        """Build the view and add it to ``self.main_layout``."""
        raise NotImplementedError

    def _device_ui_components(self, device: str):  # pragma: no cover - not used by these views
        return {}

    ##########################################
    # Public API, same as PositionerBox
    ##########################################

    @SafeProperty(str)
    def device(self):
        """Name of the controlled positioner."""
        return self._device

    @device.setter
    def device(self, value: str):
        if not value or not isinstance(value, str):
            return
        if not self._check_device_is_valid(value):
            return
        old_device = self._device
        if old_device:
            self.bec_dispatcher.disconnect_slot(
                self.on_device_readback, MessageEndpoints.device_readback(old_device)
            )
        self._device = value
        self._load_device_info()
        self.bec_dispatcher.connect_slot(
            self.on_device_readback, MessageEndpoints.device_readback(value)
        )
        self.force_update_readback()
        self.device_changed.emit(old_device, value)

    @SafeProperty(bool)
    def hide_device_selection(self):
        """Hide the device picker."""
        return self._hide_device_selection

    @hide_device_selection.setter
    def hide_device_selection(self, value: bool):
        self._hide_device_selection = value
        self.state.changed.emit()

    @SafeSlot(bool)
    def show_device_selection(self, value: bool):
        """Show the device picker.

        Args:
            value (bool): Show the device picker.
        """
        self.hide_device_selection = not value

    @SafeSlot(str)
    def set_positioner(self, positioner: str | Positioner):
        """Set the device.

        Args:
            positioner (Positioner | str): Positioner to set, accepts str or the device.
        """
        if isinstance(positioner, Positioner):
            positioner = positioner.name
        self.device = positioner

    @property
    def step_size(self) -> float:
        """Step size for tweak."""
        return self._step

    def force_update_readback(self):
        """Read the cached device values and refresh the view."""
        if not self._device:
            return
        data = self.dev[self._device].read(cached=True)
        self.on_device_readback({"signals": data}, {})

    @SafeSlot()
    def on_stop(self):
        """Stop the device."""
        self._stop_device(self._device)

    ##########################################
    # Readback
    ##########################################

    def _load_device_info(self):
        device = self.dev[self._device]
        precision = getattr(device, "precision", 8)
        try:
            self._precision = int(precision)
        except (TypeError, ValueError):
            self._precision = 8
        self._step = 10**-self._precision * 10
        try:
            self._units = str(device.egu() or "")
        except Exception:  # pylint: disable=broad-except
            self._units = ""
        self._readback = None
        self._setpoint = None
        self._moving = MOVING_UNKNOWN

    # pylint: disable=unused-argument
    @SafeSlot(dict, dict)
    def on_device_readback(self, msg_content: dict, metadata: dict):
        """Callback for device readback.

        Args:
            msg_content (dict): The message content.
            metadata (dict): The message metadata.
        """
        if not self._device:
            return
        device = self._device
        signals = msg_content.get("signals", {})
        # pylint: disable=protected-access
        hinted_signals = self.dev[device]._hints
        if len(hinted_signals) == 1:
            value = signals.get(hinted_signals[0], {}).get("value")
            if value is not None:
                self._readback = float(value)
        for name in ("setpoint", "user_setpoint"):
            value = signals.get(f"{device}_{name}", {}).get("value")
            if value is not None:
                self._setpoint = float(value)
                break
        if f"{device}_motor_done_move" in signals:
            self._moving = int(not signals[f"{device}_motor_done_move"].get("value"))
        elif f"{device}_motor_is_moving" in signals:
            self._moving = int(bool(signals[f"{device}_motor_is_moving"].get("value")))
        limits = self.dev[device].limits
        self._limits = tuple(limits) if limits is not None and limits[0] != limits[1] else None
        self.state.changed.emit()
        if self._readback is not None:
            self.position_update.emit(self._readback)

    ##########################################
    # Derived view state
    ##########################################

    @property
    def ready(self) -> bool:
        return bool(self._device)

    @property
    def device_selectable(self) -> bool:
        return not self._hide_device_selection

    @property
    def readback_text(self) -> str:
        return _format(self._readback, self._precision)

    @property
    def target_text(self) -> str:
        return _format(self._setpoint, self._precision)

    @property
    def has_target(self) -> bool:
        """True while the setpoint differs from the readback by more than the precision."""
        if self._setpoint is None or self._readback is None:
            return False
        return abs(self._setpoint - self._readback) >= 10**-self._precision

    @property
    def has_limits(self) -> bool:
        return self._limits is not None

    @property
    def low_text(self) -> str:
        return _format(self._limits[0], self._precision) if self._limits else ""

    @property
    def high_text(self) -> str:
        return _format(self._limits[1], self._precision) if self._limits else ""

    def _fraction(self, value: float | None) -> float:
        if self._limits is None or value is None:
            return -1.0
        low, high = self._limits
        return min(max((value - low) / (high - low), 0.0), 1.0)

    @property
    def position_fraction(self) -> float:
        return self._fraction(self._readback)

    @property
    def target_fraction(self) -> float:
        return self._fraction(self._setpoint) if self.has_target else -1.0

    @property
    def out_of_limits(self) -> bool:
        if self._limits is None or self._readback is None:
            return False
        return not self._limits[0] <= self._readback <= self._limits[1]

    @property
    def step_text(self) -> str:
        return f"{self._step:g}"

    ##########################################
    # Actions
    ##########################################

    def validate_target(self, text: str) -> str:
        """Check a typed target.

        Args:
            text (str): The typed target.

        Returns:
            str: An error message, or an empty string if the target can be sent.
        """
        text = text.strip()
        if not text:
            return ""
        try:
            value = float(text)
        except ValueError:
            return "Enter a number"
        if not math.isfinite(value):
            return "Enter a number"
        if self._limits is not None and not self._limits[0] <= value <= self._limits[1]:
            return f"Outside limits {self.low_text} … {self.high_text}"
        return ""

    def move_to_text(self, text: str) -> bool:
        """Move to a typed target if it is valid.

        Args:
            text (str): The typed target.

        Returns:
            bool: True if the move was sent.
        """
        if not self._device or not text.strip() or self.validate_target(text):
            return False
        self.move_to(float(text))
        return True

    @SafeSlot(float)
    def move_to(self, value: float):
        """Move the device to an absolute position.

        Args:
            value (float): Target position.
        """
        self.scans.mv(self.dev[self._device], value, relative=False)

    @SafeSlot(int)
    def tweak(self, direction: int):
        """Move by one step from the current setpoint.

        Args:
            direction (int): +1 or -1.
        """
        if not self._device:
            return
        step = self._step if direction > 0 else -self._step
        setpoint = self._get_setpoint()
        if setpoint is None:
            self.scans.mv(self.dev[self._device], step, relative=True)
            return
        self.scans.mv(self.dev[self._device], setpoint + step, relative=False)

    def _get_setpoint(self) -> float | None:
        device = self.dev[self._device]
        setpoint = getattr(device, "setpoint", None) or getattr(device, "user_setpoint", None)
        if not setpoint:
            return None
        try:
            return float(setpoint.get())
        except Exception:  # pylint: disable=broad-except
            return None

    def set_step_text(self, text: str):
        """Set the tweak step from text. Non-positive or invalid values are ignored.

        Args:
            text (str): Step size as text.
        """
        try:
            value = float(text)
        except ValueError:
            return
        if math.isfinite(value) and value > 0:
            self._step = value
            self.state.changed.emit()

    def scale_step(self, factor: float):
        """Multiply the tweak step.

        Args:
            factor (float): Factor, e.g. 10 or 0.1.
        """
        self._step = float(f"{self._step * factor:.12g}")
        self.state.changed.emit()

    def positioner_names(self) -> list[str]:
        """Names of all enabled positioners, sorted."""
        return sorted(
            name
            for name, dev in self.dev.items()
            if isinstance(dev, Positioner) and getattr(dev, "enabled", True)
        )

    def open_device_picker(self, global_pos: QPoint):
        """Open the searchable device picker.

        Args:
            global_pos (QPoint): Screen position of the popup's top-left corner.
        """
        if self._hide_device_selection:
            return
        self._picker = DevicePickerPopup(
            self.positioner_names(), self._device, self.set_positioner, self
        )
        self._picker.destroyed.connect(self._on_picker_destroyed)
        self._picker.move(global_pos)
        self._picker.show()

    def _on_picker_destroyed(self):
        self._picker = None

    def cleanup(self):
        if self._picker is not None:
            self._picker.close()
        super().cleanup()
