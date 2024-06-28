import importlib
import inspect
import os
import sys

import pytest

from bec_widgets.utils.generate_designer_plugin import DesignerPluginGenerator


def load_plugin(dir_path, content, plugin_name="MyWidget"):
    plugin_path = dir_path.mkdir("plugin").join("plugin.py")
    plugin_path.write(content)
    sys.path.append(str(dir_path))
    plugin = importlib.import_module("plugin.plugin")
    importlib.reload(plugin)
    yield getattr(plugin, plugin_name)
    sys.path.pop()


@pytest.fixture(
    params=[
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
""",
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)
""",
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
""",
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
""",
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, parent=None):
        super(QWidget, self).__init__(parent)"""
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, parent=None):
        super(QWidget, self).__init__(parent=parent)
""",
    ]
)
def plugin_with_correct_parent(tmpdir, request):
    yield from load_plugin(tmpdir, request.param)


@pytest.fixture(
    params=[
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self)
""",
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__()
""",
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, parent=None):
        super(QWidget, self).__init__()
        """,
    ]
)
def plugin_with_missing_parent(tmpdir, request):
    yield from load_plugin(tmpdir, request.param)


def test_generate_plugin(plugin_with_correct_parent):
    generator = DesignerPluginGenerator(plugin_with_correct_parent)
    generator.run()
    assert os.path.exists(f"{generator.info.base_path}/register_my_widget.py")
    assert os.path.exists(f"{generator.info.base_path}/my_widget_plugin.py")
    assert os.path.exists(f"{generator.info.base_path}/my_widget.pyproject")


def test_generate_plugin_with_missing_parent(plugin_with_missing_parent):
    with pytest.raises(ValueError) as excinfo:
        generator = DesignerPluginGenerator(plugin_with_missing_parent)
        generator.run()
    assert "Widget class MyWidget must call the super constructor with parent." in str(
        excinfo.value
    )


@pytest.fixture()
def plugin_with_excluded_widget(tmpdir):
    content = """
from qtpy.QtWidgets import QWidget
class BECDock(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
"""
    yield from load_plugin(tmpdir, content, plugin_name="BECDock")


def test_generate_plugin_with_excluded_widget(plugin_with_excluded_widget, capsys):
    generator = DesignerPluginGenerator(plugin_with_excluded_widget)
    generator.run()
    captured = capsys.readouterr()

    assert "Plugin BECDock is excluded from generation." in captured.out
    assert not os.path.exists(f"{generator.info.base_path}/register_bec_dock.py")
    assert not os.path.exists(f"{generator.info.base_path}/bec_dock_plugin.py")
    assert not os.path.exists(f"{generator.info.base_path}/bec_dock.pyproject")


@pytest.fixture(
    params=[
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self):
        QWidget.__init__(self)
""",
        """
from qtpy.QtWidgets import QWidget
class MyWidget(QWidget):
    def __init__(self, config, parent=None):
        super().__init__()
""",
    ]
)
def plugin_with_no_parent_as_first_arg(tmpdir, request):
    yield from load_plugin(tmpdir, request.param)


def test_generate_plugin_raises_exception_when_first_argument_is_not_parent(
    plugin_with_no_parent_as_first_arg,
):
    with pytest.raises(ValueError) as excinfo:
        generator = DesignerPluginGenerator(plugin_with_no_parent_as_first_arg)
        generator.run()
    assert "Widget class MyWidget must have parent as the first argument." in str(excinfo.value)
