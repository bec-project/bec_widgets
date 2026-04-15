import sys

from bec_widgets.utils.plugin_utils import get_custom_class_references, get_custom_classes


def test_client_generator_classes():
    out = get_custom_classes("bec_widgets")
    connector_cls_names = [cls.__name__ for cls in out.connector_classes]
    plugins = [cls.__name__ for cls in out.plugins]

    assert "Image" in connector_cls_names
    assert "Waveform" in connector_cls_names
    assert "MotorMap" in plugins
    assert "NonExisting" not in plugins


def test_get_custom_class_references_avoids_importing_widget_modules():
    target_module = "bec_widgets.widgets.plots.image.image"
    sys.modules.pop(target_module, None)

    references = get_custom_class_references("bec_widgets", use_cache=False)

    assert "Image" in [reference.name for reference in references]
    assert target_module not in sys.modules
