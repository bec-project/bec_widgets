from importlib.machinery import FileFinder, SourceFileLoader
from types import ModuleType
from unittest import mock

from bec_widgets.utils.bec_plugin_helper import (
    _all_widgets_from_all_submods,
    get_plugin_widget_icons,
)
from bec_widgets.utils.bec_widget import BECWidget
from bec_widgets.utils.plugin_utils import BECClassContainer, BECClassInfo


def test_all_widgets_from_module_no_submodules():
    """
    Test _all_widgets_from_all_submodules with a module that has no submodules.
    """
    module = mock.MagicMock(spec=ModuleType)

    with mock.patch(
        "bec_widgets.utils.bec_plugin_helper._get_widgets_from_module",
        return_value={"TestWidget": BECWidget},
    ):
        widgets = _all_widgets_from_all_submods(module)

    assert widgets == {"TestWidget": BECWidget}


def test_all_widgets_from_module_with_submodules():
    """
    Test _all_widgets_from_all_submodules with a module that has submodules.
    """
    module = mock.MagicMock()
    module.__path__ = ["path/to/module"]

    submodule = mock.MagicMock()
    submodule.__loader__ = mock.MagicMock(spec=SourceFileLoader)

    finder_mock = mock.MagicMock(spec=FileFinder, return_value=True)
    with (
        mock.patch(
            "pkgutil.iter_modules",
            return_value=[mock.MagicMock(module_finder=finder_mock, name="submodule")],
        ),
        mock.patch("importlib.util.module_from_spec", return_value=submodule),
        mock.patch(
            "bec_widgets.utils.bec_plugin_helper._get_widgets_from_module",
            side_effect=[
                BECClassContainer(
                    [BECClassInfo(name="TestWidget", module="", obj=BECWidget, file="")]
                ),
                BECClassContainer(
                    [BECClassInfo(name="SubWidget", module="", obj=BECWidget, file="")]
                ),
            ],
        ),
    ):
        widgets = _all_widgets_from_all_submods(module).as_dict()

    assert widgets == {"TestWidget": BECWidget, "SubWidget": BECWidget}


def test_all_widgets_from_module_no_widgets():
    """
    Test _all_widgets_from_all_submodules with a module that has no widgets.
    """
    module = mock.MagicMock()

    with mock.patch(
        "bec_widgets.utils.bec_plugin_helper._get_widgets_from_module",
        return_value=BECClassContainer([]),
    ):
        widgets = _all_widgets_from_all_submods(module).as_dict()

    assert widgets == {}


def test_get_plugin_widget_icons_from_designer_module():
    designer_module = mock.MagicMock(spec=ModuleType)
    designer_module.widget_icons = {"PluginWidget": "star"}

    get_plugin_widget_icons.cache_clear()
    try:
        with mock.patch(
            "bec_widgets.utils.bec_plugin_helper.get_plugin_designer_module",
            return_value=designer_module,
        ):
            assert get_plugin_widget_icons() == {"PluginWidget": "star"}
    finally:
        get_plugin_widget_icons.cache_clear()


def test_get_plugin_widget_icons_without_designer_module():
    get_plugin_widget_icons.cache_clear()
    try:
        with mock.patch(
            "bec_widgets.utils.bec_plugin_helper.get_plugin_designer_module", return_value=None
        ):
            assert get_plugin_widget_icons() == {}
    finally:
        get_plugin_widget_icons.cache_clear()
