"""One shared error dialog per application, used by :mod:`bec_widgets.utils.error_popups`."""

from __future__ import annotations

import shiboken6
from qtpy.QtCore import QObject, Qt

from bec_widgets.utils.error_dialog.error_dialog_qwidget import ErrorDialogWidget

_DIALOGS: dict[str, QObject] = {}


def show_error_dialog(
    title: str, traceback_text: str, source: str = "", parent=None, ui: str = "qwidget"
):
    """Show an error in the application's error dialog, creating it on first use.

    There is one dialog per application and version; further errors join its list.

    Args:
        title(str): Kind of error, e.g. ``"Method error"`` or ``"Application error"``.
        traceback_text(str): Formatted traceback.
        source(str): Where the error was raised.
        parent(QWidget | None): Parent used when the dialog is created.
        ui(str): ``"qwidget"`` or ``"qml"``.

    Returns:
        The dialog.
    """
    dialog = _DIALOGS.get(ui)
    if dialog is not None and not shiboken6.isValid(dialog):
        dialog = None
    if dialog is None:
        if ui == "qml":
            # only the QML version pulls in Qt Quick
            # pylint: disable=import-outside-toplevel
            from bec_widgets.utils.error_dialog.error_dialog_qml import ErrorDialogQML

            dialog = ErrorDialogQML(parent)
        else:
            dialog = ErrorDialogWidget(parent)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        _DIALOGS[ui] = dialog
    dialog.show_error(title, traceback_text, source)
    return dialog


def reset_error_dialogs() -> None:
    """Close and forget the shared dialogs, e.g. between tests."""
    for dialog in list(_DIALOGS.values()):
        if shiboken6.isValid(dialog):
            dialog.close()
            cleanup = getattr(dialog, "cleanup", None)
            if callable(cleanup):
                cleanup()
            dialog.deleteLater()
    _DIALOGS.clear()
