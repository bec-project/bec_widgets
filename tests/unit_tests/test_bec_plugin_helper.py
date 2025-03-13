from importlib.machinery import FileFinder, SourceFileLoader
from types import ModuleType
from unittest import mock

from bec_widgets.utils.bec_plugin_helper import BECWidget, _all_widgets_from_all_submods


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
            side_effect=[{"TestWidget": BECWidget}, {"SubWidget": BECWidget}],
        ),
    ):
        widgets = _all_widgets_from_all_submods(module)

    assert widgets == {"TestWidget": BECWidget, "SubWidget": BECWidget}


def test_all_widgets_from_module_no_widgets():
    """
    Test _all_widgets_from_all_submodules with a module that has no widgets.
    """
    module = mock.MagicMock()

    with mock.patch(
        "bec_widgets.utils.bec_plugin_helper._get_widgets_from_module", return_value={}
    ):
        widgets = _all_widgets_from_all_submods(module)

    assert widgets == {}
