"""
The other plots of the application that what the viewer shows can be sent to.

Signals of listed scans go there backed by the scan history, so they stay with the plot and
are saved with it: as history curves of a Waveform, or as the stored scan a Heatmap or a
ScatterWaveform shows. Data of other files can only be copied: a line to a Waveform, a frame
to an Image.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.rpc_register import RPCRegister
from bec_widgets.widgets.plots.waveform.waveform import Waveform

#: (scan id, device, signal) of one history curve.
CurveSource = tuple[str, str, str]

#: The kinds of plot the viewer sends to: widget class name and the name in the menus, as the
#: dock area's own menu names them, in its order.
PLOT_KINDS: dict[str, str] = {
    "Heatmap": "Heatmap",
    "ScatterWaveform": "Scatter Waveform",
    "Waveform": "Waveform",
    "Image": "Image",
}

#: Kinds whose plot shows one thing, so that sending to them replaces it.
REPLACING_KINDS = frozenset({"Heatmap", "ScatterWaveform", "Image"})


def plot_kind(obj: object) -> str | None:
    """
    The kind of plot a widget is.

    Args:
        obj (object): The widget.

    Returns:
        str | None: A key of :data:`PLOT_KINDS`, or None for any other widget.
    """
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.plots.heatmap.heatmap import Heatmap
    from bec_widgets.widgets.plots.image.image import Image
    from bec_widgets.widgets.plots.scatter_waveform.scatter_waveform import ScatterWaveform

    for kind, cls in (
        ("Heatmap", Heatmap),
        ("ScatterWaveform", ScatterWaveform),
        ("Image", Image),
        ("Waveform", Waveform),
    ):
        if isinstance(obj, cls):
            return kind
    return None


def signal_label(key: tuple[str, str]) -> str:
    """
    The name of a signal: the device for its readback, else ``device.signal``.

    Args:
        key (tuple[str, str]): (device, signal).

    Returns:
        str: For example ``bpm4i`` or ``mca.counts``.
    """
    return key[0] if key[0] == key[1] else f"{key[0]}.{key[1]}"


@dataclass(frozen=True)
class MapSource:
    """A signal of a scan as colour over two motors, as a Heatmap or a ScatterWaveform shows it."""

    #: The stored scan, or empty to follow the running scan.
    scan_id: str
    x: tuple[str, str]
    y: tuple[str, str]
    z: tuple[str, str]

    def over(self) -> str:
        """
        The signal and the axes in words.

        Returns:
            str: For example ``bpm4i over samx, samy``.
        """
        return f"{signal_label(self.z)} over {signal_label(self.x)}, {signal_label(self.y)}"


@dataclass
class Offer:
    """What the viewer sends to plots of one kind."""

    #: What a plot of that kind gets, for the tooltip of its menu entry.
    describe: str
    #: The same in a few words, at the right of the entry, e.g. ``bpm3a as a line``.
    hint: str
    #: Sends it to a plot with this name and says how it went.
    send: Callable[[QWidget, str], object]
    #: What happens to an open plot, e.g. ``adds 1 curve``.
    effect: Callable[[QWidget], str]
    #: Sets up a plot opened for it before it is sent, e.g. the x axis of a new Waveform.
    prepare: Callable[[QWidget], None] | None = None


@dataclass
class Undo:
    """How to give a plot back what it showed before something replaced it."""

    plot: QWidget
    #: The menu entry, e.g. ``Undo: Heatmap 1 back to bpm4i of scan 20``.
    text: str
    restore: Callable[[], None]
    #: What the plot shows once undone, e.g. ``Heatmap 1 shows bpm4i of scan 20 again``.
    done: str = ""
    #: The same in fewer words, for a narrow button, e.g. ``Heatmap 1 shows scan 20 again``.
    done_short: str = ""


@dataclass
class AddResult:
    """What happened when curves were added to a plot."""

    added: int = 0
    already: int = 0
    errors: list[str] = field(default_factory=list)

    def message(self, plot_name: str = "") -> str:
        """
        One line about the result, for a button or a note.

        Args:
            plot_name (str): Name of the plot the curves went to. Without it the line is short.

        Returns:
            str: For example ``"Added 2 curves to Waveform 1"``, or ``"Added 2 curves"``.
        """
        to = f" to {plot_name}" if plot_name else ""
        if self.added:
            count = "1 curve" if self.added == 1 else f"{self.added} curves"
            text = f"Added {count}{to}"
            if self.errors:
                text += f", {len(self.errors)} could not be added"
            return text
        if self.errors:
            return f"Could not add{to}: {self.errors[0]}"
        if self.already:
            return f"Already on {plot_name}" if plot_name else "Already there"
        return f"Nothing to add{to}"


def plot_name(plot: QWidget) -> str:
    """
    The name a person sees for a plot: the title of its dock, else its object name.

    Args:
        plot (QWidget): The plot.

    Returns:
        str: The name.
    """
    widget = plot.parentWidget()
    while widget is not None:
        if type(widget).__name__ == "CDockWidget" and widget.windowTitle():
            return widget.windowTitle()
        widget = widget.parentWidget()
    return plot.objectName() or type(plot).__name__


def other_plots(owner: QWidget) -> list[tuple[str, Waveform]]:
    """
    The Waveform plots of the application that are not part of ``owner``.

    Args:
        owner (QWidget): The widget whose own plots are left out, e.g. the viewer.

    Returns:
        list[tuple[str, Waveform]]: Name and plot, sorted by name.
    """
    plots = []
    for obj in RPCRegister().list_all_connections().values():
        if not isinstance(obj, Waveform) or obj is owner or owner.isAncestorOf(obj):
            continue
        if getattr(obj, "_destroyed", False):
            continue
        plots.append((plot_name(obj), obj))
    return sorted(plots, key=lambda pair: pair[0].lower())


def open_plots(owner: QWidget) -> list[tuple[str, QWidget, str]]:
    """
    The plots of every kind the viewer sends to that are open and not part of ``owner``.

    Args:
        owner (QWidget): The widget whose own plots are left out, e.g. the viewer.

    Returns:
        list[tuple[str, QWidget, str]]: Name, plot and kind, sorted by name.
    """
    plots = []
    for obj in RPCRegister().list_all_connections().values():
        if not isinstance(obj, QWidget) or obj is owner or owner.isAncestorOf(obj):
            continue
        if getattr(obj, "_destroyed", False):
            continue
        kind = plot_kind(obj)
        if kind is not None:
            plots.append((plot_name(obj), obj, kind))
    return sorted(plots, key=lambda item: item[0].lower())


def curves_effect(plot: Waveform, sources: list[CurveSource]) -> str:
    """
    What adding history curves does to a plot, in words.

    Args:
        plot (Waveform): The plot.
        sources (list[CurveSource]): The curves.

    Returns:
        str: ``adds 2 curves``, ``adds 1 curve`` or ``has them already``.
    """
    held = held_history_curves(plot)
    new = sum(1 for source in sources if source not in held)
    if not new:
        return "has it already" if len(sources) == 1 else "has them already"
    return "adds 1 curve" if new == 1 else f"adds {new} curves"


def shown_map(plot: QWidget) -> MapSource | None:
    """
    What a Heatmap or a ScatterWaveform shows.

    Args:
        plot (QWidget): The plot.

    Returns:
        MapSource | None: Its scan and signals, or None when it shows no signals.
    """
    try:
        keys = [
            (getattr(plot, f"device_{axis}"), getattr(plot, f"signal_{axis}"))
            for axis in ("x", "y", "z")
        ]
        scan_id = plot.history_scan_id
    except AttributeError:
        return None
    if not all(device and signal for device, signal in keys):
        return None
    return MapSource(scan_id or "", *keys)


def show_map(plot: QWidget, source: MapSource) -> None:
    """
    Let a Heatmap or a ScatterWaveform show a signal of a scan. Its colour map stays.

    Args:
        plot (QWidget): The plot.
        source (MapSource): What it shows from now on.

    Raises:
        RuntimeError: When the plot could not take it.
    """
    options = {
        "device_x": source.x[0],
        "signal_x": source.x[1],
        "device_y": source.y[0],
        "signal_y": source.y[1],
        "device_z": source.z[0],
        "signal_z": source.z[1],
        "color_map": plot.color_map,
        "validate_bec": False,
        "scan_id": source.scan_id or None,
        "_override_slot_params": {"popup_error": False, "raise_error": True},
    }
    if plot_kind(plot) == "ScatterWaveform":
        if plot.plot(**options, label=signal_label(source.z)) is None:
            raise RuntimeError(f"{signal_label(source.z)} could not be plotted")
        return
    plot.plot(**options)


def show_image_copy(image: QWidget, data: np.ndarray, title: str) -> Callable[[], None]:
    """
    Let an Image show a copy of a frame instead of what it showed. A device it watched is let
    go, so that its next frame does not cover the copy.

    Args:
        image (QWidget): The Image.
        data (np.ndarray): The frame.
        title (str): The title of the plot from now on.

    Returns:
        Callable[[], None]: Gives the Image back what it showed and watched before.
    """
    before = image.main_image.raw_data
    before = None if before is None else np.array(before, copy=True)
    device, signal, old_title = image.device, image.signal, image.title
    if device:
        image.device = ""
    image.main_image.set_data(np.asarray(data))
    image.title = title

    def restore() -> None:
        if before is not None:
            image.main_image.set_data(before)
        else:
            image.main_image.clear()
        image.title = old_title
        if device:
            image.device = device
            image.signal = signal

    return restore


def dock_area_for(owner: QWidget):
    """
    The dock area a new plot can be opened in: the one ``owner`` is docked in, else the one of
    the main window (as the status pills find it).

    Args:
        owner (QWidget): The widget that asks, e.g. the viewer.

    Returns:
        BECDockArea | None: The dock area, or None when there is none.
    """
    # pylint: disable=import-outside-toplevel
    from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea

    widget = owner.parentWidget()
    while widget is not None:
        if isinstance(widget, BECDockArea):
            return widget
        widget = widget.parentWidget()
    windows = [owner.window(), *QApplication.topLevelWidgets()]
    for window in windows:
        finder = getattr(window, "status_dock_area", None)
        if callable(finder):
            area = finder()
            if area is not None:
                return area
    return None


def add_history_curves(plot: Waveform, sources: list[CurveSource]) -> AddResult:
    """
    Add history curves to a plot. Curves the plot holds already are skipped; its x axis is
    left as it is.

    Args:
        plot (Waveform): The plot.
        sources (list[CurveSource]): (scan id, device, signal) of each curve.

    Returns:
        AddResult: How many were added, were there already, or failed and why.
    """
    result = AddResult()
    held = held_history_curves(plot)
    for scan_id, device, signal in sources:
        if (scan_id, device, signal) in held:
            result.already += 1
            continue
        try:
            curve = plot.plot(
                device_y=device,
                signal_y=signal,
                scan_id=scan_id,
                _override_slot_params={"popup_error": False, "raise_error": True},
            )
        except Exception as exc:  # pylint: disable=broad-except
            result.errors.append(f"{device}: {exc}")
            continue
        if curve is None:
            result.errors.append(f"{device} could not be plotted")
            continue
        held.add((scan_id, device, signal))
        result.added += 1
    return result


def held_history_curves(plot: Waveform) -> set[CurveSource]:
    """
    The history curves a plot holds.

    Args:
        plot (Waveform): The plot.

    Returns:
        set[CurveSource]: (scan id, device, signal) of each.
    """
    held = set()
    for curve in plot.curves:
        config = curve.config
        if config.source == "history" and config.signal is not None:
            held.add((config.scan_id, config.signal.device, config.signal.signal))
    return held


def shown_signals(plot: Waveform) -> list[tuple[str, str]]:
    """
    The signals a plot shows: those of its live curves, or, without any, those of its history
    curves.

    Args:
        plot (Waveform): The plot.

    Returns:
        list[tuple[str, str]]: (device, signal), in the order of the plot.
    """
    signals: dict[tuple[str, str], None] = {}
    for source in ("device", "history"):
        for curve in plot.curves:
            config = curve.config
            if config.source == source and config.signal is not None:
                signals[(config.signal.device, config.signal.signal)] = None
        if signals:
            break
    return list(signals)


def signal_of_dataset(path: str) -> tuple[str, str] | None:
    """
    The BEC signal whose values a dataset of a scan file holds.

    BEC stores the values of a signal at ``/entry/collection/devices/<device>/<signal>/value``
    and links them from ``/entry/collection/readout_groups/<group>/<device>``. Only that
    ``value`` dataset is the signal; its ``timestamp`` and everything else are not.

    Args:
        path (str): Path of the dataset in the file.

    Returns:
        tuple[str, str] | None: (device, signal), or None for any other dataset.
    """
    parts = [part for part in path.split("/") if part]
    if len(parts) < 5 or parts[-1] != "value":
        return None
    if parts[-4] == "devices" and parts[-5] == "collection":
        return parts[-3], parts[-2]
    if len(parts) >= 6 and parts[-5] == "readout_groups" and parts[-6] == "collection":
        return parts[-3], parts[-2]
    return None


def copy_label(file_path: str, path: str, index: tuple[int, ...] = ()) -> str:
    """
    Name of a copied dataset on another plot: the file, the dataset and the row of a stack.

    Args:
        file_path (str): Path of the file.
        path (str): Path of the dataset in the file.
        index (tuple[int, ...]): Position along the axes before the last one.

    Returns:
        str: For example ``"S00011_master.h5 /entry/data/counts [3]"``.
    """
    label = f"{Path(file_path).name} {path}"
    if index:
        label += f" [{', '.join(str(i) for i in index)}]"
    return label


def has_curve(plot: Waveform, label: str) -> bool:
    """
    Whether a plot holds a curve with this name.

    Args:
        plot (Waveform): The plot.
        label (str): The name.

    Returns:
        bool: True when it does.
    """
    return any(curve.name() == label for curve in plot.curves)
