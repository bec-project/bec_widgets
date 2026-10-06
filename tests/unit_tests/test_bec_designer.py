import sys
from types import SimpleNamespace
from unittest import mock

import pytest
from qtpy.QtCore import SIGNAL, QObject, Qt, Signal

from bec_widgets.utils import bec_designer


class _DesignerStyleHints(QObject):
    colorSchemeChanged = Signal(object)


class _DesignerApplication(QObject):
    """Private signal sources: emitting quit must never shut down pytest's qapp."""

    aboutToQuit = Signal()
    paletteChanged = Signal(object)

    def __init__(self):
        super().__init__()
        self._style_hints = _DesignerStyleHints(self)

    def styleHints(self):
        return self._style_hints


@pytest.mark.parametrize("theme_signal", ["colorSchemeChanged", "paletteChanged"])
def test_designer_disconnects_pyqtgraph_callbacks_on_quit(qapp, monkeypatch, theme_signal):
    """Theme updates work until quit, then only pyqtgraph's callback is released."""
    app = _DesignerApplication()
    callback = mock.Mock()
    unrelated = mock.Mock()
    real_shutdown = mock.Mock()
    qapp.aboutToQuit.connect(real_shutdown)
    if theme_signal == "colorSchemeChanged":
        signal = app.styleHints().colorSchemeChanged
        value = Qt.ColorScheme.Dark
        callback_name = "_onColorSchemeChange"
    else:
        signal = app.paletteChanged
        value = qapp.palette()
        callback_name = "_onPaletteChange"

    pg_qt = SimpleNamespace(QAPP=app, **{callback_name: callback})
    signal.connect(callback)
    signal.connect(unrelated)
    try:
        # Restore QApplication.instance before the shared Qt fixtures tear down.
        with mock.patch.object(bec_designer.QApplication, "instance", return_value=app):
            bec_designer._install_designer_cleanup()
            # Several plugins ask for icons. Only one shutdown callback is needed.
            bec_designer._install_designer_cleanup()
            assert app.receivers(SIGNAL("aboutToQuit()")) == 1
            # pyqtgraph may be imported after the first plugin's icon is requested.
            monkeypatch.setitem(sys.modules, "pyqtgraph.Qt", pg_qt)
            signal.emit(value)
            callback.assert_called_once()

            app.aboutToQuit.emit()
            assert not app._bec_designer_cleanup_installed
            assert app.receivers(SIGNAL("aboutToQuit()")) == 0
            signal.emit(value)
            callback.assert_called_once()
            assert unrelated.call_count == 2
            # Self-disconnection also makes a repeated private quit harmless.
            app.aboutToQuit.emit()
        real_shutdown.assert_not_called()
    finally:
        signal.disconnect(unrelated)
        if getattr(app, "_bec_designer_cleanup_installed", False):
            app.aboutToQuit.emit()
        qapp.aboutToQuit.disconnect(real_shutdown)
        app.deleteLater()


def test_designer_cleanup_without_application(monkeypatch):
    with mock.patch.object(bec_designer.QApplication, "instance", return_value=None):
        bec_designer._install_designer_cleanup()
