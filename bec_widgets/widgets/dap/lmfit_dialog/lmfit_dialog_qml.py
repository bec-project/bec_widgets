"""Redesigned LMFit dialog drawn in QML and hosted in a QQuickWidget."""

from __future__ import annotations

from pathlib import Path

from bec_lib.logger import bec_logger
from qtpy.QtCore import Property, QObject, QUrl, Signal, Slot
from qtpy.QtQuickWidgets import QQuickWidget
from qtpy.QtWidgets import QVBoxLayout

from bec_widgets.utils.error_popups import SafeSlot
from bec_widgets.utils.qml_host import create_quick_widget
from bec_widgets.widgets.dap.lmfit_dialog.fit_dialog_base import FitDialogBase
from bec_widgets.widgets.dap.lmfit_dialog.fit_summary import QUALITY_LABELS
from bec_widgets.widgets.dap.lmfit_dialog.fit_theme import fit_dialog_palette

logger = bec_logger.logger

QML_FILE = Path(__file__).parent / "qml" / "FitDialog.qml"


class FitDialogBridge(QObject):
    """Exposes the dialog state and actions to QML."""

    stateChanged = Signal()
    paletteChanged = Signal()

    def __init__(self, dialog: LMFitDialogQml):
        super().__init__(dialog)
        self._dialog = dialog
        self._state: dict = {}
        self._palette: dict = {}

    @Property("QVariantMap", notify=stateChanged)
    def state(self) -> dict:
        """Everything the view shows, as plain maps and lists."""
        return self._state

    @Property("QVariantMap", notify=paletteChanged)
    def palette(self) -> dict:
        """Theme colour roles."""
        return self._palette

    def set_state(self, state: dict):
        """Replace the view state and notify QML."""
        self._state = state
        self.stateChanged.emit()

    def set_palette(self, palette: dict):
        """Replace the colour roles and notify QML."""
        self._palette = palette
        self.paletteChanged.emit()

    @Slot(str)
    def selectCurve(self, curve_id: str):  # pylint: disable=invalid-name
        """Select a curve from QML."""
        self._dialog.select_curve(curve_id)

    @Slot(str)
    def move(self, param_name: str):
        """Request a move from QML."""
        self._dialog.request_move(param_name)

    @Slot(str)
    def copy(self, text: str):
        """Copy text from QML."""
        self._dialog.copy_to_clipboard(text)


class LMFitDialogQml(FitDialogBase):
    """Fit summary and parameters of LMFit DAP processes, drawn in QML."""

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent=parent, **kwargs)
        self.bridge = FitDialogBridge(self)
        self.bridge.set_palette(fit_dialog_palette())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.quick = create_quick_widget(self, QML_FILE, {"fit": self.bridge})
        if self.quick.status() == QQuickWidget.Status.Error:
            for error in self.quick.errors():
                logger.error(f"FitDialog.qml: {error.toString()}")
        layout.addWidget(self.quick)
        self._render()

    def _render(self):
        if not hasattr(self, "bridge"):
            return
        self.bridge.set_state(self._build_state())

    def _build_state(self) -> dict:
        palette = self.bridge.palette
        summary = self.current_summary
        curves = [
            {
                "id": cid,
                "color": palette.get(f"quality_{quality}", palette.get("muted", "#888")),
                "tip": f"{cid}: {QUALITY_LABELS[quality]}",
            }
            for cid, quality in ((cid, self.curve_quality(cid)) for cid in self.curve_ids)
        ]
        state = {
            "hasData": summary is not None,
            "compact": self.compact,
            "showCurves": self.show_curve_selection(),
            "showSummary": not self.hide_summary,
            "showParams": not self.hide_parameters,
            "actionsEnabled": self.enable_actions,
            "currentCurve": self.fit_curve_id or "",
            "curves": curves,
        }
        if summary is None:
            return state
        message = summary.message if summary.show_message else ""
        if not message and summary.loose_params:
            message = f"Poorly constrained: {', '.join(summary.loose_params)}"
        state.update(
            {
                "model": summary.model_name,
                "modelFull": summary.model,
                "quality": summary.quality,
                "qualityLabel": summary.quality_label,
                "qualityColor": palette.get(f"quality_{summary.quality}", "#888"),
                "details": summary.details_text,
                "metrics": [
                    {"label": label, "value": value, "tip": tip}
                    for label, value, tip in summary.metrics
                ],
                "message": message,
                "params": [
                    {
                        "name": p.name,
                        "value": p.value_text,
                        "raw": str(p.value),
                        "error": p.stderr_text,
                        "rel": p.relative_error_text,
                        "state": p.state,
                        "tip": p.tooltip,
                        "movable": p.name in self.active_action_list,
                    }
                    for p in summary.params
                ],
            }
        )
        return state

    @SafeSlot(str)
    def apply_theme(self, theme: str):
        """Push the theme colours to QML.

        Args:
            theme (str): "dark" or "light".
        """
        if hasattr(self, "bridge"):
            self.bridge.set_palette(fit_dialog_palette())
            self._render()

    def cleanup(self):
        """Release the QML scene before the widget goes away."""
        if hasattr(self, "quick"):
            self.quick.setSource(QUrl())
        super().cleanup()
