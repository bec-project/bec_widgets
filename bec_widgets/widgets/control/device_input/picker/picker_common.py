"""Combobox and popup base classes of the device and signal pickers.

:class:`DevicePickerBase` and :class:`SignalPickerBase` subclass :class:`DeviceComboBox` and
:class:`SignalComboBox`, keep their API and add a faster refresh path and the wiring of the
searchable popup. The concrete pickers in :mod:`picker_qwidget` and :mod:`picker_qml` only choose
the popup. The toolkit-independent model lives in :mod:`picker_model`.
"""

from __future__ import annotations

import weakref

from bec_lib.endpoints import MessageEndpoints
from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QPainter, QPen
from qtpy.QtWidgets import QComboBox, QWidget

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.filter_io import get_bec_signals_for_classes
from bec_widgets.utils.quick.host import ThemeTokens
from bec_widgets.widgets.control.device_input.device_combobox.device_combobox import DeviceComboBox
from bec_widgets.widgets.control.device_input.picker.picker_model import (
    DEVICE_KIND_LABELS,
    DeviceSnapshot,
    PickerController,
    PickerEntry,
    device_snapshot,
    invalidate_device_snapshot,
    recent_picks,
    remember_pick,
)
from bec_widgets.widgets.control.device_input.signal_combobox.signal_combobox import SignalComboBox

# ---- combobox base classes ----------------------------------------------------------------------


class PickerPopupMixin:
    """Popup wiring and the cheaper validity styling shared by both picker comboboxes.

    The class using it must be a :class:`QComboBox` subclass and implement
    :meth:`_picker_entries`, :meth:`_select_value` and :meth:`_create_popup`.
    """

    PICKER_NOUN = "items"
    RECENT_KIND = "items"

    def _init_picker(self) -> None:
        self._picker_popup = None
        self._picker_controller: PickerController | None = None
        self._picker_text_before = ""
        self._live_topics: list = []
        self._live_entry: PickerEntry | None = None
        self._show_invalid = False
        self._last_valid_text = self.currentText() if self._is_valid_input else ""
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(8)
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.textEdited.connect(self._on_field_edited)
            line_edit.setPlaceholderText(f"Select {self.PICKER_NOUN[:-1]}…")
        # the validity of the current text may have been styled with the old stylesheet
        self._update_validity_style(self._is_valid_input)

    # ---- styling -------------------------------------------------------------------------
    # The field keeps the application style; a per-widget stylesheet costs several
    # milliseconds per picker to parse and polish, so the error state is painted instead.

    def _update_validity_style(self, is_valid: bool) -> None:
        if not hasattr(self, "_picker_popup"):
            # still inside the parent constructor; styled once in _init_picker
            return
        if is_valid and not self.is_popup_open():
            self._last_valid_text = self.currentText()
        show = bool(self.currentText()) and not is_valid and self.isEnabled()
        if show != self._show_invalid:
            self._show_invalid = show
            self.update()

    @property
    def shows_invalid(self) -> bool:
        """Whether the field is drawn with the error border."""
        return self._show_invalid

    def paintEvent(self, event):  # pylint: disable=invalid-name
        """Paint the field and, for invalid text, a danger-coloured border on top."""
        super().paintEvent(event)  # type: ignore[misc]
        if not self._show_invalid:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(ThemeTokens().danger, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 4, 4)
        painter.end()

    def apply_theme(self, theme: str):
        """Re-style the popup for the new theme."""
        super().apply_theme(theme)  # type: ignore[misc]
        if self._picker_popup is not None:
            self._picker_popup.refresh_theme()
        self.update()

    # ---- popup -------------------------------------------------------------------------------

    @property
    def picker_controller(self) -> PickerController:
        """Controller of the popup, created on first use."""
        if self._picker_controller is None:
            self._picker_controller = PickerController(
                self.PICKER_NOUN, self._read_live_value, self._watch_live_value, self
            )
            self._picker_controller.picked.connect(self._on_picked)
            self._picker_controller.dismissed.connect(self._on_dismissed)
        return self._picker_controller

    @property
    def picker_popup(self):
        """The popup window, created on first use."""
        if self._picker_popup is None:
            self._picker_popup = self._create_popup()
        return self._picker_popup

    def is_popup_open(self) -> bool:
        """Whether the picker popup is showing."""
        return self._picker_popup is not None and self._picker_popup.isVisible()

    def showPopup(self) -> None:  # pylint: disable=invalid-name
        """Open the searchable popup instead of the plain drop-down list."""
        self.open_picker()

    def hidePopup(self) -> None:  # pylint: disable=invalid-name
        """Close the popup."""
        if self.is_popup_open():
            self._picker_popup.hide()
        super().hidePopup()  # type: ignore[misc]

    def open_picker(self, query: str = "") -> None:
        """Open the popup, optionally with a search text already entered.

        Args:
            query(str): Initial search text.
        """
        if not self.isEnabled():
            return
        if not self.is_popup_open():
            # text typed to start a search is not a selection; cancelling reverts to the last
            # valid one
            self._picker_text_before = (
                self._last_valid_text
                if query and query == self.currentText()
                else self.currentText()
            )
        controller = self.picker_controller
        controller.open(
            self._picker_entries(), self._picker_text_before, query, recent_picks(self.RECENT_KIND)
        )
        popup = self.picker_popup
        popup.show_below(self)

    @SafeSlot(str)
    def _on_field_edited(self, text: str) -> None:
        if text and not self.is_popup_open():
            self.open_picker(query=text)

    @SafeSlot(str)
    def _on_picked(self, value: str) -> None:
        self._picker_text_before = value
        if self._picker_popup is not None:
            self._picker_popup.hide()
        remember_pick(self.RECENT_KIND, value)
        self._select_value(value)
        self.setFocus()

    @SafeSlot()
    def _on_dismissed(self) -> None:
        if self._picker_popup is not None:
            self._picker_popup.hide()
        self.setFocus()

    def _on_popup_hidden(self) -> None:
        """Called by the popup window when it hides for any reason, e.g. a click outside.

        Text typed into the field to start a search is reverted unless an entry was picked.
        """
        if self._picker_controller is not None:
            self._picker_controller.close()
        if self.currentText() != self._picker_text_before:
            self.setCurrentText(self._picker_text_before)

    # ---- live value --------------------------------------------------------------------------

    def _read_live_value(self, entry: PickerEntry) -> dict | None:
        connector = getattr(self.client, "connector", None)
        if connector is None or not entry.device:
            return None
        for endpoint in (
            MessageEndpoints.device_readback(entry.device),
            MessageEndpoints.device_read_configuration(entry.device),
        ):
            msg = connector.get(endpoint)
            signals = getattr(msg, "signals", None) or {}
            reading = _pick_reading(signals, entry)
            if reading is not None:
                return reading
        return None

    def _watch_live_value(self, entry: PickerEntry | None) -> None:
        if self._live_topics:
            self.bec_dispatcher.disconnect_slot(self._on_live_message, self._live_topics)
            self._live_topics = []
        self._live_entry = entry
        if entry is None or not entry.device:
            return
        self._live_topics = [
            MessageEndpoints.device_readback(entry.device),
            MessageEndpoints.device_read_configuration(entry.device),
        ]
        self.bec_dispatcher.connect_slot(self._on_live_message, self._live_topics, owner=self)

    @SafeSlot(dict, dict)
    def _on_live_message(self, content: dict, _metadata: dict) -> None:
        entry = self._live_entry
        if entry is None or self._picker_controller is None:
            return
        reading = _pick_reading(content.get("signals", {}) or {}, entry)
        if reading is not None:
            self._picker_controller.update_live_value(entry, reading)

    def cleanup(self):
        """Close the popup and drop the live subscription."""
        if self._picker_controller is not None:
            self._picker_controller.close()
        if self._picker_popup is not None:
            self._picker_popup.hide()
            self._picker_popup.release()
            self._picker_popup.deleteLater()
            self._picker_popup = None
        super().cleanup()  # type: ignore[misc]

    # ---- to implement ------------------------------------------------------------------------

    def _picker_entries(self) -> list[PickerEntry]:
        raise NotImplementedError

    def _select_value(self, value: str) -> None:
        raise NotImplementedError

    def _create_popup(self):
        raise NotImplementedError


def _pick_reading(signals: dict, entry: PickerEntry) -> dict | None:
    if not signals:
        return None
    key = entry.signal
    if not key:
        key = entry.device if entry.device in signals else next(iter(signals))
    reading = signals.get(key)
    return reading if isinstance(reading, dict) else None


class DevicePickerBase(PickerPopupMixin, DeviceComboBox):  # pylint: disable=abstract-method
    """:class:`DeviceComboBox` with the searchable popup and a cheaper refresh.

    Differences to the base class, all invisible to callers:

    * enabling several filters at once (e.g. the five readout priorities in the constructor)
      refreshes the list once instead of once per filter;
    * the enabled devices are read from a snapshot shared by all pickers and only re-read when
      the device configuration changes;
    * an unchanged device list does not rebuild the items or re-emit the selection signals;
    * the error state is a dynamic property, not a new stylesheet per validity check.
    """

    PLUGIN = False
    RPC = False
    PICKER_NOUN = "devices"
    RECENT_KIND = "devices"

    _batching_filters = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device_config_update.disconnect(self.update_devices_from_filters)
        self.device_config_update.connect(self._refresh_after_config_update)
        self._init_picker()

    # ---- faster refresh --------------------------------------------------------------------

    def set_device_filter(self, filter_selection):
        self._batching_filters = True
        try:
            super().set_device_filter(filter_selection)
        finally:
            self._batching_filters = False
        self.update_devices_from_filters()

    def set_readout_priority_filter(self, filter_selection):
        self._batching_filters = True
        try:
            super().set_readout_priority_filter(filter_selection)
        finally:
            self._batching_filters = False
        self.update_devices_from_filters()

    @SafeSlot()
    def update_devices_from_filters(self):
        """Refresh the available device list from the current filters."""
        self._refresh(force=False)

    def on_device_update(self, action: str, content: dict) -> None:
        """Invalidate the shared snapshot, then refresh like :class:`DeviceComboBox`."""
        invalidate_device_snapshot(self.client)
        super().on_device_update(action, content)

    @SafeSlot()
    def _refresh_after_config_update(self):
        self._refresh(force=False)

    def _refresh(self, force: bool) -> None:
        if self._batching_filters:
            return
        self.config.device_filter = [entry.value for entry in self.device_filter]
        self.config.readout_filter = [entry.value for entry in self.readout_filter]
        self.config.signal_class_filter = self.signal_class_filter
        if not self.apply_filter:
            return
        snapshot = device_snapshot(self.client, force=force)
        records = list(snapshot.records.values())
        if self.config.signal_class_filter:
            allowed = self._devices_with_signal_classes(snapshot)
            records = [record for record in records if record.name in allowed]
        wanted = set(self.device_filter)
        readout = self.readout_filter
        names = [
            record.name
            for record in records
            if wanted <= record.filters and record.readout in readout
        ]
        if self.include_signals_with_write_access:
            seen = set(names)
            names.extend(
                record.name
                for record in snapshot.records.values()
                if record.write_access and record.name not in seen
            )
        self.devices = names

    def _devices_with_signal_classes(self, snapshot: DeviceSnapshot) -> set[str]:
        key = tuple(self.config.signal_class_filter)
        cached = snapshot.signal_classes.get(key)
        if cached is None:
            signals = get_bec_signals_for_classes(client=self.client, signal_class_filter=list(key))
            cached = snapshot.signal_classes[key] = [name for name, _, _ in signals]
        return set(cached)

    def _replace_items(self, devices: list[str]):
        items = [""] + list(devices) if self._set_first_element_as_empty else list(devices)
        if self.count() == len(items) and all(
            self.itemText(row) == text for row, text in enumerate(items)
        ):
            # nothing changed: keep the items, the completer and the emitted state
            return
        current = self.currentText()
        self.blockSignals(True)
        try:
            self.clear()
            self.addItems(items)
            self.setCurrentText(current)
        finally:
            self.blockSignals(False)
        self._completer_model.setStringList(list(devices))
        self.check_validity(self.currentText())

    def validate_device(self, device: str | None) -> bool:
        """Validate a device against the current filtered device selection."""
        if not device:
            return False
        device_name = self._device_name_from_text(device)
        if device_name not in self.devices:
            return False
        return device_name in device_snapshot(self.client).records

    # ---- popup -------------------------------------------------------------------------------

    def _picker_entries(self) -> list[PickerEntry]:
        records = device_snapshot(self.client).records
        entries = []
        for name in self.devices:
            record = records.get(name)
            if record is None:
                entries.append(PickerEntry(value=name, title=name, device=name))
                continue
            group, icon = DEVICE_KIND_LABELS[record.kind]
            readout = getattr(record.readout, "value", record.readout) or ""
            details = record.description or ", ".join(record.tags)
            entries.append(
                PickerEntry(
                    value=name,
                    title=name,
                    subtitle=record.device_class,
                    group=group,
                    badge=str(readout),
                    icon=icon,
                    device=name,
                    details=details,
                )
            )
        return entries

    def _select_value(self, value: str) -> None:
        self.setCurrentText(value)


SIGNAL_KIND_ICONS = {"hinted": "star", "normal": "sensors", "config": "tune"}


class SignalPickerBase(PickerPopupMixin, SignalComboBox):  # pylint: disable=abstract-method
    """:class:`SignalComboBox` with the searchable popup and cheaper validity styling.

    Signals of one device are grouped by kind (hinted, normal, config); signals listed by class
    are grouped by their device.
    """

    PLUGIN = False
    RPC = False
    PICKER_NOUN = "signals"
    RECENT_KIND = "signals"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_picker()

    def _on_device_update(self, action: str, content: dict) -> None:
        invalidate_device_snapshot(self.client)
        super()._on_device_update(action, content)

    def _replace_signal_items(self, items=None):
        combo_items = self._signals if items is None else items
        display_items = [""] + combo_items if self._set_first_element_as_empty else combo_items
        current = self.currentText()
        keep_text = bool(current)
        self.blockSignals(True)
        try:
            self.clear()
            plain = [entry for entry in display_items if isinstance(entry, str)]
            if len(plain) == len(display_items):
                self.addItems(plain)
            else:
                for entry in display_items:
                    if isinstance(entry, str):
                        self.addItem(entry)
                    else:
                        self.addItem(*entry)
            if keep_text:
                self.setCurrentText(current)
        finally:
            self.blockSignals(False)
        self._completer_model.setStringList(
            [entry if isinstance(entry, str) else entry[0] for entry in combo_items]
        )

    def _picker_entries(self) -> list[PickerEntry]:
        entries: list[PickerEntry] = []
        if self._signal_class_filter:
            device_names = sorted(device_snapshot(self.client).records, key=len, reverse=True)
            for item in self._signals:
                text, info = (item, {}) if isinstance(item, str) else item
                obj_name = info.get("obj_name") or text
                device = self._device or next(
                    (name for name in device_names if obj_name.startswith(name)), ""
                )
                describe = info.get("describe", {}).get("signal_info", {}) or {}
                ndim = describe.get("ndim")
                subtitle = info.get("signal_class", "")
                if ndim is not None:
                    subtitle = f"{subtitle} · {ndim}D" if subtitle else f"{ndim}D"
                entries.append(
                    PickerEntry(
                        value=text,
                        title=text,
                        subtitle=subtitle,
                        group=device or "Signals",
                        badge=info.get("kind_str", ""),
                        icon=SIGNAL_KIND_ICONS.get(info.get("kind_str", ""), "sensors"),
                        device=device,
                        signal=obj_name,
                        details=info.get("storage_name", ""),
                    )
                )
            return entries
        groups = (
            ("Hinted", "hinted", self._hinted_signals),
            ("Normal", "normal", self._normal_signals),
            ("Config", "config", self._config_signals),
        )
        for group, kind, signals in groups:
            for text, info in signals:
                obj_name = info.get("obj_name") or text
                component = info.get("component_name") or ""
                subtitle = obj_name if obj_name != text else component
                if subtitle == text:
                    subtitle = ""
                entries.append(
                    PickerEntry(
                        value=text,
                        title=text,
                        subtitle=subtitle,
                        group=group,
                        badge=kind,
                        icon=SIGNAL_KIND_ICONS[kind],
                        device=self._device or "",
                        signal=obj_name,
                        details=info.get("signal_class", "") or info.get("doc", "") or "",
                    )
                )
        if not entries and self._signals:
            # a plain signal device lists itself without signal info
            for item in self._signals:
                text = item if isinstance(item, str) else item[0]
                entries.append(
                    PickerEntry(value=text, title=text, icon="sensors", device=self._device or text)
                )
        return entries

    def _select_value(self, value: str) -> None:
        index = self.findText(value)
        if index >= 0:
            self.setCurrentIndex(index)
        else:
            self.setCurrentText(value)


class PickerPopupBase(QWidget):
    """Top-level popup window shared by the QWidget and QML popups.

    Subclasses fill the window; this class positions it under the field, follows the theme
    and reports when it hides.
    """

    WIDTH = 380
    MAX_HEIGHT = 440
    MIN_HEIGHT = 240
    # search row, separators and footer around the list
    CHROME_HEIGHT = 136
    ROW_HEIGHTS = {"header": 28, "empty": 96, "item": 34}

    def __init__(self, picker: PickerPopupMixin):
        # parented so it is destroyed with the picker; the Popup flag keeps it a separate window
        super().__init__(picker, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._picker = weakref.ref(picker)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setObjectName("pickerPopup")

    @property
    def controller(self) -> PickerController:
        """Controller of the picker this popup belongs to."""
        return self._picker().picker_controller

    def show_below(self, anchor: QWidget) -> None:
        """Show under ``anchor``, flipping above it if there is no room below."""
        width = max(anchor.width(), self.WIDTH)
        height = self.preferred_height()
        origin = anchor.mapToGlobal(anchor.rect().bottomLeft())
        screen = anchor.screen().availableGeometry() if anchor.screen() is not None else None
        x, y = origin.x(), origin.y() + 2
        if screen is not None:
            if y + height > screen.bottom():
                y = max(screen.top(), anchor.mapToGlobal(anchor.rect().topLeft()).y() - height - 2)
            x = max(screen.left(), min(x, screen.right() - width))
        self.setGeometry(x, y, width, height)
        if not self.isVisible():
            self.show()
        self.activateWindow()
        self.focus_search()

    def preferred_height(self) -> int:
        """Height that fits the current rows, between ``MIN_HEIGHT`` and ``MAX_HEIGHT``."""
        model = self.controller.model
        rows = sum(
            self.ROW_HEIGHTS.get(model.row(row).get("rowType"), 34)
            for row in range(model.rowCount())
        )
        return max(self.MIN_HEIGHT, min(self.MAX_HEIGHT, rows + self.CHROME_HEIGHT + 8))

    def focus_search(self) -> None:
        """Move keyboard focus to the search field."""

    def refresh_theme(self) -> None:
        """Apply the current theme."""

    def release(self) -> None:
        """Release resources before deletion."""

    def hideEvent(self, event):  # pylint: disable=invalid-name
        picker = self._picker()
        if picker is not None:
            picker._on_popup_hidden()  # pylint: disable=protected-access
        super().hideEvent(event)


__all__ = ["DevicePickerBase", "PickerPopupBase", "PickerPopupMixin", "SignalPickerBase"]
