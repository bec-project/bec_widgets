"""Pick which fit dialog implementation the waveform uses (for comparing the redesigns)."""

from __future__ import annotations

import os

from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog import LMFitDialog

FIT_DIALOG_ENV = "BEC_FIT_DIALOG"


def fit_dialog_class() -> type:
    """Return the fit dialog class selected by the ``BEC_FIT_DIALOG`` environment variable.

    ``qml`` selects the QML redesign, ``qwidget`` the QWidget redesign; anything else keeps the
    current LMFitDialog.

    Returns:
        type: The dialog class.
    """
    choice = os.environ.get(FIT_DIALOG_ENV, "").strip().lower()
    if choice == "qml":
        from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog_qml import LMFitDialogQml

        return LMFitDialogQml
    if choice == "qwidget":
        from bec_widgets.widgets.dap.lmfit_dialog.lmfit_dialog_qwidget import LMFitDialogQWidget

        return LMFitDialogQWidget
    return LMFitDialog


def create_fit_dialog(*args, **kwargs):
    """Create the fit dialog selected by ``BEC_FIT_DIALOG`` with LMFitDialog's arguments."""
    return fit_dialog_class()(*args, **kwargs)
