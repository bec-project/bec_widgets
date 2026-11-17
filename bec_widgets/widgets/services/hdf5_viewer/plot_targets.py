"""
The other plots of the application that scans of the viewer can be added to.

Scans go there as ordinary history curves of the Waveform, so they stay with the plot,
show up in its curve dialog and are saved with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.rpc_register import RPCRegister
from bec_widgets.widgets.plots.waveform.waveform import Waveform

#: (scan id, device, signal) of one history curve.
CurveSource = tuple[str, str, str]


@dataclass
class AddResult:
    """What happened when curves were added to a plot."""

    added: int = 0
    already: int = 0
    errors: list[str] = field(default_factory=list)

    def message(self, plot_name: str) -> str:
        """
        One line about the result, for a button or a note.

        Args:
            plot_name (str): Name of the plot the curves went to.

        Returns:
            str: For example ``"Added 2 curves to Waveform 1"``.
        """
        if self.added:
            count = "1 curve" if self.added == 1 else f"{self.added} curves"
            text = f"Added {count} to {plot_name}"
            if self.errors:
                text += f", {len(self.errors)} could not be added"
            return text
        if self.errors:
            return f"Could not add to {plot_name}: {self.errors[0]}"
        if self.already:
            return f"Already on {plot_name}"
        return f"Nothing to add to {plot_name}"


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
