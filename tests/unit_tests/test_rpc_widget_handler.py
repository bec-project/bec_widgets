import enum
from importlib import reload
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from bec_widgets.cli import client
from bec_widgets.cli.rpc.rpc_base import RPCBase
from bec_widgets.cli.rpc.rpc_widget_handler import RPCWidgetHandler
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.widgets.containers.dock.dock import BECDock


def test_rpc_widget_handler():
    handler = RPCWidgetHandler()
    assert "Image" in handler.widget_classes
    assert "RingProgressBar" in handler.widget_classes


class _TestPluginWidget(BECWidget): ...


@patch(
    "bec_widgets.cli.rpc.rpc_widget_handler.get_all_plugin_widgets",
    return_value={"DeviceComboBox": _TestPluginWidget, "NewPluginWidget": _TestPluginWidget},
)
def test_duplicate_plugins_not_allowed(_):
    handler = RPCWidgetHandler()
    assert handler.widget_classes["DeviceComboBox"] is not _TestPluginWidget
    assert handler.widget_classes["NewPluginWidget"] is _TestPluginWidget
