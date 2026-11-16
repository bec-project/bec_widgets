"""The plot of the scan desk: a Waveform whose legend shows short names."""

from __future__ import annotations

from html import escape

from bec_widgets.widgets.plots.waveform.waveform import Waveform


class ScanWaveform(Waveform):
    """
    Waveform that shows a short name for a curve in its legend.

    BEC names the curve of a stored scan ``<device>-<signal>-scan-<number>``. That name stays
    what it is, because the curve is found by it. Only the text in the legend changes.
    """

    PLUGIN = False
    RPC = False

    # Class-level default: the base class refreshes the legend while it is being built.
    _legend_names: dict[str, str] = {}

    def set_legend_names(self, names: dict[str, str]) -> None:
        """
        Set the texts the legend shows.

        Args:
            names (dict[str, str]): Short name by name of the curve. Curves that are not
                listed keep their own name.
        """
        self._legend_names = dict(names)
        self._refresh_live_legend()

    def _refresh_live_legend(self, scan_id: str | None = None, running: bool | None = None):
        super()._refresh_live_legend(scan_id, running)
        legend = self.plot_item.legend
        if legend is None or not self._legend_names:
            return
        changed = False
        for curve in self.curves:
            short = self._legend_names.get(curve.name())
            label = legend.getLabel(curve)
            if short is None or label is None:
                continue
            name = escape(curve.name())
            if label.text.startswith(name):
                label.setText(escape(short) + label.text[len(name) :])
                changed = True
        if changed:
            legend.updateSize()
