"""Logic shared by the QML and QWidget ports of the positioner box.

The ports keep the public API of :class:`PositionerBox` (``set_positioner``, ``device``,
``hide_device_selection``, ``device_changed``, ``position_update``, ...) but hold the device state
in a plain dictionary that both renderers draw from. Readback parsing, move validation, tweak
and stop are implemented once here.
"""

from __future__ import annotations

import math

from bec_lib.device import Positioner
from bec_lib.endpoints import MessageEndpoints
from bec_lib.logger import bec_logger
from qtpy.QtCore import Signal

from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.utils.ux_kit import PortedPropertiesMixin
from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_base import (
    PositionerBoxBase,
)

logger = bec_logger.logger

DEFAULT_PRECISION = 8


def device_precision(device_obj) -> int:
    """Precision of a device, falling back to 8 like :class:`PositionerBox`."""
    precision = getattr(device_obj, "precision", DEFAULT_PRECISION)
    try:
        return int(precision)
    except (TypeError, ValueError):
        return DEFAULT_PRECISION


def parse_readback(device: str, hints: list[str], signals: dict) -> dict:
    """Extract readback, setpoint and motion state from a device readback message.

    Mirrors :meth:`PositionerBoxBase._on_device_readback`.

    Returns:
        dict: ``readback``, ``setpoint`` and ``moving`` entries; each may be ``None`` when the
        message does not contain the value.
    """
    readback = None
    if len(hints) == 1:
        readback = signals.get(hints[0], {}).get("value")
    setpoint = None
    for setpoint_signal in ("setpoint", "user_setpoint"):
        setpoint = signals.get(f"{device}_{setpoint_signal}", {}).get("value")
        if setpoint is not None:
            break
    if f"{device}_motor_done_move" in signals:
        moving = not signals[f"{device}_motor_done_move"].get("value")
    elif f"{device}_motor_is_moving" in signals:
        moving = bool(signals[f"{device}_motor_is_moving"].get("value"))
    else:
        moving = None
    return {"readback": readback, "setpoint": setpoint, "moving": moving}


def format_value(value: float | None, precision: int) -> str:
    """Format a position with the device precision, or an em dash when unknown."""
    if value is None:
        return "—"
    return f"{value:.{precision}f}"


def format_step(step: float) -> str:
    """Compact representation of a step size for button labels (``0.01``, ``1e-06``)."""
    return f"{step:g}"


class PositionerBoxPortBase(PortedPropertiesMixin, PositionerBoxBase):
    """Shared implementation of the positioner box ports.

    Subclasses build the renderer in :meth:`_init_view` and redraw it from :attr:`state` in
    :meth:`_sync_view`.
    """

    PLUGIN = False
    RPC = False
    rpc_widget_class = "PositionerBox"
    USER_ACCESS = ["set_positioner", "attach", "detach", "screenshot"]

    device_changed = Signal(str, str)
    position_update = Signal(float)

    def __init__(self, parent=None, device: Positioner | str | None = None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self._device = ""
        self._limits = None
        self._hide_device_selection = False
        self._error = ""
        self.state: dict = self._empty_state()
        self.device_changed.connect(self.on_device_change)
        self._init_view()
        self._sync_view()
        if isinstance(device, Positioner):
            device = device.name
        self.device = device

    # ---- state ---------------------------------------------------------------------------

    @staticmethod
    def _empty_state() -> dict:
        return {
            "device": "",
            "readback": None,
            "setpoint": None,
            "moving": None,
            "limits": None,
            "precision": DEFAULT_PRECISION,
            "units": "",
            "step": 10**-DEFAULT_PRECISION * 10,
        }

    def view_state(self) -> dict:
        """Display-ready state shared by both renderers."""
        state = self.state
        precision = state["precision"]
        limits = state["limits"]
        has_limits = limits is not None and limits[0] != limits[1]
        readback = state["readback"]
        setpoint = state["setpoint"]

        def fraction(value):
            if not has_limits or value is None:
                return -1.0
            return max(0.0, min(1.0, (value - limits[0]) / (limits[1] - limits[0])))

        at_limit = False
        if has_limits and readback is not None:
            span = abs(limits[1] - limits[0])
            tolerance = max(span * 1e-6, 10**-precision)
            at_limit = (
                abs(readback - limits[0]) <= tolerance or abs(readback - limits[1]) <= tolerance
            )

        moving = state["moving"]
        if not state["device"]:
            status, tone = "No device", "muted"
        elif moving is None:
            status, tone = "Unknown", "muted"
        elif moving:
            status, tone = "Moving", "primary"
        elif at_limit:
            status, tone = "At limit", "warning"
        else:
            status, tone = "Idle", "success"

        target_differs = (
            setpoint is not None
            and readback is not None
            and not math.isclose(setpoint, readback, abs_tol=10**-precision)
        )
        step = state["step"]
        return {
            "device": state["device"],
            "hasDevice": bool(state["device"]),
            "readbackText": format_value(readback, precision),
            "setpointText": format_value(setpoint, precision),
            "showTarget": bool(moving) or target_differs,
            "units": state["units"],
            "status": status,
            "statusTone": tone,
            "moving": bool(moving),
            "hasLimits": has_limits,
            "limitLowText": format_value(limits[0], min(precision, 3)) if has_limits else "",
            "limitHighText": format_value(limits[1], min(precision, 3)) if has_limits else "",
            "position": fraction(readback),
            "target": fraction(setpoint),
            "atLimit": at_limit,
            "step": step,
            "stepText": format_step(step),
            "decimals": precision,
            "error": self._error,
            "selectable": not self._hide_device_selection,
        }

    def positioner_names(self) -> list[str]:
        """Names of all positioners known to the device manager, sorted."""
        try:
            devices = self.dev
            return sorted(name for name in devices.keys() if isinstance(devices[name], Positioner))
        except Exception:  # pylint: disable=broad-except
            return []

    def _set_state(self, **values) -> None:
        self.state.update(values)
        self._sync_view()

    def _set_error(self, message: str) -> None:
        self._error = message
        self._sync_view()

    # ---- device handling -----------------------------------------------------------------

    @SafeProperty(str)
    def device(self) -> str:
        """Name of the controlled positioner."""
        return self._device

    @device.setter
    def device(self, value: str):
        if not value or not isinstance(value, str):
            return
        if not self._check_device_is_valid(value):
            return
        old_device = self._device
        self._device = value
        self.device_changed.emit(old_device, value)

    @SafeProperty(bool)
    def hide_device_selection(self) -> bool:
        """Hide the device selector; the device name is still shown."""
        return self._hide_device_selection

    @hide_device_selection.setter
    def hide_device_selection(self, value: bool):
        self._hide_device_selection = bool(value)
        self._sync_view()

    @SafeSlot(bool)
    def show_device_selection(self, value: bool):
        """Show the device selection.

        Args:
            value (bool): Show the device selection
        """
        self.hide_device_selection = not value

    @SafeSlot(str)
    def set_positioner(self, positioner: str | Positioner):
        """Set the device.

        Args:
            positioner (Positioner | str) : Positioner to set, accepts str or the device
        """
        if isinstance(positioner, Positioner):
            positioner = positioner.name
        self.device = positioner

    @SafeSlot(str, str)
    def on_device_change(self, old_device: str, new_device: str):
        """Reset the state for the new device and move the readback subscription.

        Args:
            old_device (str): The old device name.
            new_device (str): The new device name.
        """
        if not self._check_device_is_valid(new_device):
            return
        device_obj = self.dev[new_device]
        precision = device_precision(device_obj)
        try:
            units = str(device_obj.egu() or "")
        except Exception:  # pylint: disable=broad-except
            units = ""
        self._limits = None
        self._error = ""
        self.state = self._empty_state()
        self.state.update(
            device=new_device, precision=precision, units=units, step=10**-precision * 10
        )
        if old_device:
            self._swap_readback_signal_connection(self.on_device_readback, old_device, new_device)
        else:
            self.bec_dispatcher.connect_slot(
                self.on_device_readback, MessageEndpoints.device_readback(new_device)
            )
        self.force_update_readback()

    def force_update_readback(self):
        """Read the cached device values and refresh the view."""
        if not self._device or not self._check_device_is_valid(self._device):
            return
        data = self.dev[self._device].read(cached=True)
        self.on_device_readback({"signals": data}, {})

    @SafeSlot(dict, dict)
    def on_device_readback(self, msg_content: dict, metadata: dict):
        """Callback for device readback.

        Args:
            msg_content (dict): The message content.
            metadata (dict): The message metadata.
        """
        device = self._device
        if not device:
            return
        # pylint: disable=protected-access
        parsed = parse_readback(device, self.dev[device]._hints, msg_content.get("signals", {}))
        self.state.update({key: value for key, value in parsed.items() if value is not None})
        self.update_limits(self.dev[device].limits)
        if parsed["readback"] is not None:
            self.position_update.emit(parsed["readback"])
        self._sync_view()

    def update_limits(self, limits: tuple | list | None):
        """Update limits.

        Args:
            limits (tuple): Limits of the positioner
        """
        if limits == self._limits:
            return
        self._limits = limits
        self.state["limits"] = tuple(limits) if limits is not None else None
        self._sync_view()

    # ---- actions -------------------------------------------------------------------------

    @property
    def step_size(self) -> float:
        """Step size for tweak."""
        return self.state["step"]

    @step_size.setter
    def step_size(self, value: float):
        value = abs(float(value))
        if value > 0:
            self._set_state(step=value)

    def validate_target(self, text: str) -> str:
        """Return an error message for a move target, or an empty string when it is valid."""
        text = text.strip()
        if not text:
            return ""
        try:
            value = float(text)
        except ValueError:
            return "Enter a number"
        limits = self.state["limits"]
        if limits is not None and limits[0] != limits[1]:
            low, high = sorted(limits)
            if not low <= value <= high:
                precision = min(self.state["precision"], 3)
                return (
                    f"Outside limits {format_value(low, precision)} … "
                    f"{format_value(high, precision)}"
                )
        return ""

    def move_to(self, text: str) -> bool:
        """Move to the absolute position in ``text`` if it is valid.

        Returns:
            bool: True if the move was requested.
        """
        error = self.validate_target(text)
        if error or not text.strip() or not self._device:
            self._set_error(error or ("Enter a target position" if self._device else ""))
            return False
        self._set_error("")
        self.scans.mv(self.dev[self._device], float(text), relative=False)
        return True

    @SafeSlot()
    def on_stop(self):
        """Stop the device."""
        self._stop_device(self.device)

    @SafeSlot()
    def on_tweak_right(self):
        """Tweak motor right."""
        self._tweak(1)

    @SafeSlot()
    def on_tweak_left(self):
        """Tweak motor left."""
        self._tweak(-1)

    def _tweak(self, direction: int) -> None:
        if not self._device:
            return
        step = direction * self.step_size
        setpoint = self._get_setpoint()
        if setpoint is None:
            self.scans.mv(self.dev[self._device], step, relative=True)
            return
        self.scans.mv(self.dev[self._device], setpoint + step, relative=False)

    def _get_setpoint(self) -> float | None:
        """Get the setpoint of the motor."""
        setpoint = getattr(self.dev[self._device], "setpoint", None)
        if not setpoint:
            setpoint = getattr(self.dev[self._device], "user_setpoint", None)
        if not setpoint:
            return None
        try:
            return float(setpoint.get())
        except Exception:  # pylint: disable=broad-except
            return None

    # The ports do not use the .ui based helpers of PositionerBoxBase.
    def _device_ui_components(self, device: str):
        raise NotImplementedError

    # ---- renderer hooks ------------------------------------------------------------------

    def _init_view(self) -> None:
        """Create the renderer and add it to ``self.main_layout``."""
        raise NotImplementedError

    def _sync_view(self) -> None:
        """Redraw the renderer from :meth:`view_state`."""
        raise NotImplementedError


PositionerBoxPortBase.PORTED_FROM = PositionerBoxPortBase
