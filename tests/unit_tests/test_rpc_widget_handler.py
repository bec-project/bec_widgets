import sys
from types import ModuleType
from unittest.mock import patch

from bec_widgets.cli.rpc.rpc_widget_handler import RPCWidgetHandler
from bec_widgets.utils.plugin_utils import BECClassReference


def test_rpc_widget_handler():
    handler = RPCWidgetHandler()
    assert "Image" in handler.widget_classes
    assert "RingProgressBar" in handler.widget_classes
    assert "BECDockArea" in handler.widget_classes


def test_duplicate_plugins_not_allowed(monkeypatch):
    builtin_module = ModuleType("builtin_test_widgets")
    plugin_module = ModuleType("plugin_test_widgets")

    SharedWidgetBuiltin = type("SharedWidget", (), {})
    SharedWidgetBuiltin.__module__ = builtin_module.__name__
    setattr(builtin_module, "SharedWidget", SharedWidgetBuiltin)

    SharedWidgetPlugin = type("SharedWidget", (), {})
    SharedWidgetPlugin.__module__ = plugin_module.__name__
    setattr(plugin_module, "SharedWidget", SharedWidgetPlugin)

    NewPluginWidget = type("NewPluginWidget", (), {})
    NewPluginWidget.__module__ = plugin_module.__name__
    setattr(plugin_module, "NewPluginWidget", NewPluginWidget)

    monkeypatch.setitem(sys.modules, builtin_module.__name__, builtin_module)
    monkeypatch.setitem(sys.modules, plugin_module.__name__, plugin_module)

    with (
        patch(
            "bec_widgets.cli.rpc.rpc_widget_handler.get_all_plugin_widget_references",
            return_value=[
                BECClassReference(name="SharedWidget", module=plugin_module.__name__),
                BECClassReference(name="NewPluginWidget", module=plugin_module.__name__),
            ],
        ),
        patch(
            "bec_widgets.cli.rpc.rpc_widget_handler.get_custom_class_references",
            return_value=[BECClassReference(name="SharedWidget", module=builtin_module.__name__)],
        ),
    ):
        handler = RPCWidgetHandler()
        assert handler.widget_classes["SharedWidget"].__module__ == builtin_module.__name__
        assert handler.widget_classes["NewPluginWidget"].__module__ == plugin_module.__name__
