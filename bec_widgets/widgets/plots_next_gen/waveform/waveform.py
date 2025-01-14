from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from bec_lib.device import ReadoutPriority
from bec_widgets.utils import ConnectionConfig
from bec_widgets.widgets.plots_next_gen.plot_base import PlotBase


class BECWaveform(PlotBase):
    PLUGIN = False
    ICON_NAME = "show_chart"

    READOUT_PRIORITY_HANDLER = {
        ReadoutPriority.ON_REQUEST: "on_request",
        ReadoutPriority.BASELINE: "baseline",
        ReadoutPriority.MONITORED: "monitored",
        ReadoutPriority.ASYNC: "async",
        ReadoutPriority.CONTINUOUS: "continuous",
    }

    # TODO implement signals
    # scan_signal_update = Signal()
    # async_signal_update = Signal()
    # dap_params_update = Signal(dict, dict)
    # dap_summary_update = Signal(dict, dict)
    # autorange_signal = Signal()
    # new_scan = Signal()
    # roi_changed = Signal(tuple)
    # roi_active = Signal(bool)
    # request_dap_refresh = Signal()
    def __init__(
        self,
        parent: QWidget | None = None,
        config: ConnectionConfig | None = None,
        client=None,
        gui_id: str | None = None,
    ):
        if config is None:
            config = ConnectionConfig(widget_class=self.__class__.__name__)
        super().__init__(parent=parent, config=config, client=client, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)

        # For PropertyManager identification
        self.setObjectName("Waveform")
