import inspect
import os
import re

from qtpy.QtCore import QObject

EXCLUDED_PLUGINS = ["BECConnector", "BECDockArea", "BECDock"]


class DesignerPluginInfo:
    def __init__(self, plugin_class):
        self.plugin_class = plugin_class
        self.plugin_name_pascal = plugin_class.__name__
        self.plugin_name_snake = self.pascal_to_snake(self.plugin_name_pascal)
        self.widget_import = f"from {plugin_class.__module__} import {self.plugin_name_pascal}"
        plugin_module = (
            ".".join(plugin_class.__module__.split(".")[:-1]) + f".{self.plugin_name_snake}_plugin"
        )
        self.plugin_import = f"from {plugin_module} import {self.plugin_name_pascal}Plugin"

        # first sentence / line of the docstring is used as tooltip
        self.plugin_tooltip = (
            plugin_class.__doc__.split("\n")[0].strip().replace('"', "'")
            if plugin_class.__doc__
            else self.plugin_name_pascal
        )

        self.base_path = os.path.dirname(inspect.getfile(plugin_class))

    @staticmethod
    def pascal_to_snake(name: str) -> str:
        """
        Convert PascalCase to snake_case.

        Args:
            name (str): The name to be converted.

        Returns:
            str: The converted name.
        """
        s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
        s2 = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s1)
        return s2.lower()


class DesignerPluginGenerator:
    def __init__(self, widget: type):
        self._excluded = False
        self.widget = widget
        self.info = DesignerPluginInfo(widget)
        if widget.__name__ in EXCLUDED_PLUGINS:

            self._excluded = True
            return

        self.templates = {}
        self.template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "plugin_templates"
        )

    def run(self):
        if self._excluded:
            print(f"Plugin {self.widget.__name__} is excluded from generation.")
            return
        self._check_class_validity()
        self._load_templates()
        self._write_templates()

    def _check_class_validity(self):

        # Check if the widget is a QWidget subclass
        if not issubclass(self.widget, QObject):
            return

        # Check if the widget class has parent as the first argument. This is a strict requirement of Qt!
        signature = list(inspect.signature(self.widget.__init__).parameters.values())
        if len(signature) == 1 or signature[1].name != "parent":
            raise ValueError(
                f"Widget class {self.widget.__name__} must have parent as the first argument."
            )

        base_cls = [val for val in self.widget.__bases__ if issubclass(val, QObject)]
        if not base_cls:
            raise ValueError(
                f"Widget class {self.widget.__name__} must inherit from a QObject subclass."
            )

        # Check if the widget class calls the super constructor with parent argument
        init_source = inspect.getsource(self.widget.__init__)
        cls_init_found = (
            bool(init_source.find(f"{base_cls[0].__name__}.__init__(self, parent=parent") > 0)
            or bool(init_source.find(f"{base_cls[0].__name__}.__init__(self, parent)") > 0)
            or bool(init_source.find(f"{base_cls[0].__name__}.__init__(self, parent,") > 0)
        )
        super_init_found = (
            bool(
                init_source.find(f"super({base_cls[0].__name__}, self).__init__(parent=parent") > 0
            )
            or bool(init_source.find(f"super({base_cls[0].__name__}, self).__init__(parent,") > 0)
            or bool(init_source.find(f"super({base_cls[0].__name__}, self).__init__(parent)") > 0)
        )
        if issubclass(self.widget.__bases__[0], QObject) and not super_init_found:
            super_init_found = (
                bool(init_source.find("super().__init__(parent=parent") > 0)
                or bool(init_source.find("super().__init__(parent,") > 0)
                or bool(init_source.find("super().__init__(parent)") > 0)
            )

        if not cls_init_found and not super_init_found:
            raise ValueError(
                f"Widget class {self.widget.__name__} must call the super constructor with parent."
            )

    def _write_templates(self):
        self._write_register()
        self._write_plugin()
        self._write_pyproject()

    def _write_register(self):
        file_path = os.path.join(self.info.base_path, f"register_{self.info.plugin_name_snake}.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.templates["register"].format(**self.info.__dict__))

    def _write_plugin(self):
        file_path = os.path.join(self.info.base_path, f"{self.info.plugin_name_snake}_plugin.py")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.templates["plugin"].format(**self.info.__dict__))

    def _write_pyproject(self):
        file_path = os.path.join(self.info.base_path, f"{self.info.plugin_name_snake}.pyproject")
        out = {"files": [f"{self.info.plugin_class.__module__.split('.')[-1]}.py"]}
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(str(out))

    def _load_templates(self):
        for file in os.listdir(self.template_path):
            if not file.endswith(".template"):
                continue
            with open(os.path.join(self.template_path, file), "r", encoding="utf-8") as f:
                self.templates[file.split(".")[0]] = f.read()


if __name__ == "__main__":  # pragma: no cover
    # from bec_widgets.widgets.bec_queue.bec_queue import BECQueue
    from bec_widgets.widgets.dock import BECDockArea

    generator = DesignerPluginGenerator(BECDockArea)
    generator.run()
