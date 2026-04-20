from unittest.mock import patch

from bec_widgets.utils import plugin_utils
from bec_widgets.utils.rpc_widget_handler import RPCWidgetHandler


def test_rpc_widget_handler():
    handler = RPCWidgetHandler()
    assert "Image" in handler.widget_classes
    assert "RingProgressBar" in handler.widget_classes
    assert "BECDockArea" in handler.widget_classes
    assert isinstance(handler.widget_classes["Image"], tuple)


@patch(
    "bec_widgets.utils.bec_plugin_helper.get_plugin_rpc_widget_registry",
    return_value={
        "Image": ("plugin.module", "PluginImage"),
        "NewPluginWidget": ("plugin.module", "NewPluginWidget"),
    },
)
def test_duplicate_plugins_not_allowed(_):
    plugin_utils.rpc_widget_registry.cache_clear()

    try:
        handler = RPCWidgetHandler()
        assert handler.widget_classes["Image"] != ("plugin.module", "PluginImage")
        assert handler.widget_classes["NewPluginWidget"] == ("plugin.module", "NewPluginWidget")
    finally:
        plugin_utils.rpc_widget_registry.cache_clear()
