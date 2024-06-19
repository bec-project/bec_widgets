from bec_widgets.cli.rpc_wigdet_handler import RPCWidgetHandler


def test_rpc_widget_handler():
    handler = RPCWidgetHandler()
    assert "BECFigure" in handler.widget_classes
    assert "SpiralProgressBar" in handler.widget_classes
