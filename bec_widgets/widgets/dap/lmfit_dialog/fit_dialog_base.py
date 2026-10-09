"""Shared state and public API for the redesigned LMFit dialogs (QML and QWidget views)."""

from __future__ import annotations

from qtpy.QtCore import Signal
from qtpy.QtWidgets import QApplication, QWidget

from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.error_popups import SafeProperty, SafeSlot
from bec_widgets.widgets.dap.lmfit_dialog.fit_summary import FitSummary


class MoveActionHandle:
    """Button-like handle for a parameter's move action.

    It keeps the legacy ``action_buttons[name].isEnabled()`` / ``.click()`` contract working for
    views that do not create one QPushButton per parameter.
    """

    def __init__(self, dialog: FitDialogBase, param_name: str):
        self._dialog = dialog
        self.param_name = param_name

    def isEnabled(self) -> bool:  # pylint: disable=invalid-name
        """Whether the move action can be triggered."""
        return self._dialog.enable_actions

    def click(self):
        """Trigger the move action, as a click on the button would."""
        if self.isEnabled():
            self._dialog.request_move(self.param_name)


class FitDialogBase(BECWidget, QWidget):
    """Base for fit dialogs: keeps the LMFitDialog public API and delegates drawing to a view.

    Subclasses implement ``_render()`` (redraw everything from ``self``) and may override
    ``_render_actions()`` for the cheaper case where only the move-button state changed.
    """

    PLUGIN = False
    RPC = False
    ICON_NAME = "monitoring"
    # Signal to emit the currently selected fit curve_id
    selected_fit = Signal(str)
    # Signal to emit a move action in form of a tuple (param_name, value)
    move_action = Signal(tuple)

    def __init__(
        self,
        parent=None,
        client=None,
        config=None,
        target_widget=None,
        gui_id: str | None = None,
        ui_file: str | None = None,
        compact: bool | None = None,
        **kwargs,
    ):
        """
        Args:
            parent (QWidget): The parent widget.
            client: BEC client object.
            config: Configuration of the widget.
            target_widget: The widget that the settings will be taken from and applied to.
            gui_id (str): GUI ID.
            ui_file (str): Accepted for compatibility with LMFitDialog; a name containing
                "compact" selects the compact layout.
            compact (bool): Use the side-by-side layout for short embedded panels.
        """
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        self.setProperty("skip_settings", True)
        self.target_widget = target_widget
        if compact is None:
            compact = bool(ui_file and "compact" in ui_file)
        self.compact = compact
        self.summary_data: dict[str, dict | None] = {}
        self._fit_curve_id: str | None = None
        self._active_actions: list[str] = []
        self._enable_actions = True
        self._always_show_latest = False
        self._hide_curve_selection = False
        self._hide_summary = False
        self._hide_parameters = False

    ################################################################################
    # Public API (same as LMFitDialog)

    @property
    def enable_actions(self) -> bool:
        """Whether the move buttons are enabled."""
        return self._enable_actions

    @enable_actions.setter
    def enable_actions(self, enable: bool):
        self._enable_actions = bool(enable)
        self._render_actions()

    @SafeProperty(list)
    def active_action_list(self) -> list[str]:
        """Names of the fit parameters that get a move button."""
        return self._active_actions

    @active_action_list.setter
    def active_action_list(self, actions: list[str]):
        self._active_actions = list(actions or [])
        self._render()

    @SafeProperty(bool)
    def always_show_latest(self) -> bool:
        """Whether the dialog follows the most recently updated fit."""
        return self._always_show_latest

    @always_show_latest.setter
    def always_show_latest(self, show: bool):
        self._always_show_latest = show

    @SafeProperty(bool)
    def hide_curve_selection(self) -> bool:
        """Whether the curve selector is hidden."""
        return self._hide_curve_selection

    @hide_curve_selection.setter
    def hide_curve_selection(self, hide: bool):
        self._hide_curve_selection = hide
        self._render()

    @SafeProperty(bool)
    def hide_summary(self) -> bool:
        """Whether the fit summary card is hidden."""
        return self._hide_summary

    @hide_summary.setter
    def hide_summary(self, hide: bool):
        self._hide_summary = hide
        self._render()

    @SafeProperty(bool)
    def hide_parameters(self) -> bool:
        """Whether the parameter table is hidden."""
        return self._hide_parameters

    @hide_parameters.setter
    def hide_parameters(self, hide: bool):
        self._hide_parameters = hide
        self._render()

    @property
    def fit_curve_id(self) -> str | None:
        """The curve_id of the displayed fit."""
        return self._fit_curve_id

    @fit_curve_id.setter
    def fit_curve_id(self, curve_id: str | None):
        changed = curve_id != self._fit_curve_id
        self._fit_curve_id = curve_id
        if curve_id is not None:
            self.selected_fit.emit(curve_id)
        if changed:
            self._render()

    @property
    def action_buttons(self) -> dict[str, MoveActionHandle]:
        """Move actions of the displayed fit, keyed by parameter name."""
        summary = self.current_summary
        if summary is None:
            return {}
        names = {p.name for p in summary.params}
        return {
            name: MoveActionHandle(self, name) for name in self._active_actions if name in names
        }

    @SafeSlot(str)
    def remove_dap_data(self, curve_id: str):
        """Remove the DAP data for the given curve_id.

        Args:
            curve_id (str): The curve_id of the DAP data to be removed.
        """
        self.summary_data.pop(curve_id, None)
        if self._fit_curve_id == curve_id:
            remaining = list(self.summary_data)
            if remaining:
                self.fit_curve_id = remaining[0]
                return
            self._fit_curve_id = None
        self._render()

    @SafeSlot(str)
    def select_curve(self, curve_id: str):
        """Select the curve whose fit is displayed.

        Args:
            curve_id (str): curve_id to be selected.
        """
        self.fit_curve_id = curve_id

    @SafeSlot(dict, dict)
    def update_summary_tree(self, data: dict, metadata: dict):
        """Store a new fit summary and show it if its curve is selected.

        Args:
            data (dict): Data for the DAP Summary.
            metadata (dict): Metadata of the fit curve.
        """
        curve_id = metadata.get("curve_id", "")
        self.summary_data[curve_id] = data
        if self._fit_curve_id is None or self._always_show_latest:
            self._fit_curve_id = curve_id
            self.selected_fit.emit(curve_id)
        self._render()

    def refresh_curve_list(self):
        """Redraw the curve selector from ``summary_data``."""
        self._render()

    ################################################################################
    # Helpers for views

    @property
    def curve_ids(self) -> list[str]:
        """The curves with fit data, in arrival order."""
        return list(self.summary_data)

    @property
    def current_summary(self) -> FitSummary | None:
        """The parsed summary of the selected curve, or None."""
        if self._fit_curve_id is None or self._fit_curve_id not in self.summary_data:
            return None
        return FitSummary.from_dap(self._fit_curve_id, self.summary_data[self._fit_curve_id])

    def curve_quality(self, curve_id: str) -> str:
        """Quality verdict for a curve's fit, used to colour the curve selector."""
        return FitSummary.from_dap(curve_id, self.summary_data.get(curve_id)).quality

    def show_curve_selection(self) -> bool:
        """Show the selector only when it helps: not hidden and more than one fit."""
        return not self._hide_curve_selection and len(self.summary_data) > 1

    def request_move(self, param_name: str):
        """Emit move_action for a parameter of the displayed fit.

        Args:
            param_name (str): The parameter to move to.
        """
        if not self._enable_actions:
            return
        summary = self.current_summary
        if summary is None:
            return
        for param in summary.params:
            if param.name == param_name:
                self.move_action.emit((param.name, param.value))
                return

    @staticmethod
    def copy_to_clipboard(text: str):
        """Put text on the clipboard.

        Args:
            text (str): The text to copy.
        """
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)

    def _render(self):  # pragma: no cover - implemented by views
        raise NotImplementedError

    def _render_actions(self):
        self._render()
