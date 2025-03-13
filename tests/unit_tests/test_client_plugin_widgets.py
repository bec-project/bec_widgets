import enum
import inspect
import sys
from importlib import reload
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from bec_widgets.cli import client
from bec_widgets.cli.rpc.rpc_base import RPCBase


class _TestGlobalPlugin(RPCBase): ...


mock_client_module_globals = SimpleNamespace()
_TestGlobalPlugin.__name__ = "Widgets"
mock_client_module_globals.Widgets = _TestGlobalPlugin


@patch("bec_lib.logger.bec_logger")
@patch(
    "bec_widgets.utils.bec_plugin_helper.get_plugin_client_module",
    lambda: mock_client_module_globals,
)
def test_plugins_dont_clobber_client_globals(bec_logger: MagicMock):
    reload(client)
    bec_logger.logger.warning.assert_called_with(
        "Plugin widget Widgets from namespace(Widgets=<class 'tests.unit_tests.test_client_plugin_widgets._TestGlobalPlugin'>) conflicts with a built-in class!"
    )
    if sys.version_info >= (3, 11):  # No EnumType in python3.10
        assert isinstance(client.Widgets, enum.EnumType)


class _TestDuplicatePlugin(RPCBase): ...


mock_client_module_duplicate = SimpleNamespace()
_TestDuplicatePlugin.__name__ = "DeviceComboBox"

mock_client_module_duplicate.DeviceComboBox = _TestDuplicatePlugin


@patch("bec_lib.logger.bec_logger")
@patch(
    "bec_widgets.utils.bec_plugin_helper.get_plugin_client_module",
    lambda: mock_client_module_duplicate,
)
@patch(
    "bec_widgets.utils.bec_plugin_helper.get_all_plugin_widgets",
    return_value={"DeviceComboBox": _TestDuplicatePlugin},
)
def test_duplicate_plugins_not_allowed(_, bec_logger: MagicMock):
    reload(client)
    assert (
        call(
            f"Detected duplicate widget DeviceComboBox in plugin repo file: {inspect.getfile(_TestDuplicatePlugin)} !"
        )
        in bec_logger.logger.warning.mock_calls
    )
    assert client.BECDock is not _TestDuplicatePlugin
