import json
from pathlib import Path

import jedi
from qtpy.QtCore import Property, QObject, QUrl, Signal, Slot
from qtpy.QtWebChannel import *
from qtpy.QtWebEngineWidgets import *


class BaseBridge(QObject):
    initialized = Signal()
    sendDataChanged = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.active = False
        self.queue = []

    def send_to_js(self, name, value):
        if self.active:
            data = json.dumps(value)
            self.sendDataChanged.emit(name, data)
        else:
            self.queue.append((name, value))

    @Slot(str, str)
    def receive_from_js(self, name, value):
        if name == "completion":
            print("Completer received:", value)
            return
        data = json.loads(value)
        self.setProperty(name, data)

    @Slot(str, result="QVariant")
    def requestCompletions(self, json_str):
        import json

        data = json.loads(json_str)
        if data["context"].get("triggerCharacter") != ".":
            return json.dumps([])

        print("Received completion request:", data)
        script = jedi.Script(data["code"], path="placeholder.py")
        completions = script.complete(data["line"], data["column"] - 1)
        infer_result = script.infer(data["line"], data["column"] - 2)
        if infer_result:
            inferred_type = infer_result[0].name
            devices = bec.device_manager.devices
            if inferred_type == "DeviceContainer":
                return json.dumps(
                    [
                        {
                            "label": device.name,
                            "kind": 9,
                            "insertText": device.name,
                            "documentation": device.name,
                        }
                        for device_name, device in devices.items()
                    ]
                )
            print("Inferred type:", inferred_type)
        return json.dumps(
            [
                {
                    "label": completion.name,
                    "kind": 6,
                    "insertText": completion.name,
                    "documentation": completion.description,
                }
                for completion in completions
            ]
        )

    @Slot()
    def init(self):
        self.initialized.emit()
        self.active = True
        for name, value in self.queue:
            self.send_to_js(name, value)

        self.queue.clear()


class EditorBridge(BaseBridge):
    valueChanged = Signal()
    languageChanged = Signal()
    themeChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._value = ""
        self._language = ""
        self._theme = ""

    def getValue(self):
        return self._value

    def setValue(self, value):
        self._value = value
        self.valueChanged.emit()

    def getLanguage(self):
        return self._language

    def setLanguage(self, language):
        self._language = language
        self.languageChanged.emit()

    def getTheme(self):
        return self._theme

    def setTheme(self, theme):
        self._theme = theme
        self.themeChanged.emit()

    value = Property(str, fget=getValue, fset=setValue, notify=valueChanged)
    language = Property(str, fget=getLanguage, fset=setLanguage, notify=languageChanged)
    theme = Property(str, fget=getTheme, fset=setTheme, notify=themeChanged)


index = Path(__file__).parent / "index.html"

with open(index) as f:
    raw_html = f.read()


class MonacoPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        print(f"[JS Console] {level.name} at line {line} in {source}: {message}")


class MonacoWidget(QWebEngineView):
    initialized = Signal()
    textChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)

        page = MonacoPage(parent=self)
        self.setPage(page)

        filename = Path(__file__).parent / "index.html"
        self.setHtml(raw_html, QUrl.fromLocalFile(filename.as_posix()))

        self._channel = QWebChannel(self)
        self._bridge = EditorBridge()

        self.page().setWebChannel(self._channel)
        self._channel.registerObject("bridge", self._bridge)

        self._bridge.initialized.connect(self.initialized)
        self._bridge.valueChanged.connect(lambda: self.textChanged.emit(self._bridge.value))

    def text(self):
        return self._bridge.value

    def setText(self, text):
        self._bridge.send_to_js("value", text)

    def language(self):
        return self._bridge.language

    def setLanguage(self, language):
        self._bridge.send_to_js("language", language)

    def theme(self):
        return self._bridge.theme

    def setTheme(self, theme):
        self._bridge.send_to_js("theme", theme)
