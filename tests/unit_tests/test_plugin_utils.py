from bec_widgets.utils.plugin_utils import get_rpc_classes


def test_client_generator_classes():
    out = get_rpc_classes("bec_widgets")
    assert list(out.keys()) == ["connector_classes", "top_level_classes"]
    connector_cls_names = [cls.__name__ for cls in out["connector_classes"]]
    top_level_cls_names = [cls.__name__ for cls in out["top_level_classes"]]

    assert "BECFigure" in connector_cls_names
    assert "BECWaveform" in connector_cls_names
    assert "BECDockArea" in top_level_cls_names
    assert "BECFigure" in top_level_cls_names
    assert "BECWaveform" not in top_level_cls_names
