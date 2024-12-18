from bec_widgets.cli.rpc.rpc_widget_handler import RPCWidgetHandler


def test_rpc_widget_handler():
    handler = RPCWidgetHandler()
    assert "BECFigure" in handler.widget_classes
    assert "RingProgressBar" in handler.widget_classes
