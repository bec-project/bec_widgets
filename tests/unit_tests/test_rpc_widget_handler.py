from unittest.mock import patch

from bec_widgets.cli.rpc.rpc_widget_handler import RPCWidgetHandler
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.plugin_utils import BECClassContainer, BECClassInfo


def test_rpc_widget_handler():
    handler = RPCWidgetHandler()
    assert "Image" in handler.widget_classes
    assert "RingProgressBar" in handler.widget_classes
    assert "AdvancedDockArea" in handler.widget_classes


class _TestPluginWidget(BECWidget): ...


@patch(
    "bec_widgets.cli.rpc.rpc_widget_handler.get_all_plugin_widgets",
    return_value=BECClassContainer(
        [
            BECClassInfo(name="DeviceComboBox", obj=_TestPluginWidget, module="", file=""),
            BECClassInfo(name="NewPluginWidget", obj=_TestPluginWidget, module="", file=""),
        ]
    ),
)
def test_duplicate_plugins_not_allowed(_):
    handler = RPCWidgetHandler()
    assert handler.widget_classes["DeviceComboBox"] is not _TestPluginWidget
    assert handler.widget_classes["NewPluginWidget"] is _TestPluginWidget
