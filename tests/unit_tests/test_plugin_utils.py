from bec_widgets.utils.plugin_utils import get_custom_classes


def test_client_generator_classes():
    out = get_custom_classes("bec_widgets")
    connector_cls_names = [cls.__name__ for cls in out.connector_classes]
    plugins = [cls.__name__ for cls in out.plugins]

    assert "BECFigure" in connector_cls_names
    assert "BECWaveform" in connector_cls_names
    assert "BECDockArea" in plugins
    assert "BECWaveform" not in plugins
