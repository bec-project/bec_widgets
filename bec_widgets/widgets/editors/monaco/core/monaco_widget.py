import functools
import json
import multiprocessing
import threading
import time
from pathlib import Path

import jedi
from bec_lib.client import BECClient
from qtpy.QtCore import Property, QObject, QUrl, Signal, Slot
from qtpy.QtWebChannel import *
from qtpy.QtWebEngineWidgets import *


class CompletionItemKind:
    Text = 1
    Method = 2
    Function = 3
    Constructor = 4
    Field = 5
    Variable = 6
    Class = 7
    Interface = 8
    Module = 9
    Property = 10
    Unit = 11
    Value = 12
    Enum = 13
    Keyword = 14
    Snippet = 15
    Color = 16
    File = 17
    Reference = 18
    Folder = 19
    EnumMember = 20
    Constant = 21
    Struct = 22
    Event = 23
    Operator = 24
    TypeParameter = 25


def completion_worker(request_queue, response_queue):
    client = BECClient()
    client.start()
    while True:
        json_str = request_queue.get()
        if json_str is None:
            continue
        if json_str == "exit":
            break

        data = json.loads(json_str)
        # if data["context"].get("triggerCharacter") != ".":
        #     response_queue.put(json.dumps([]))
        print(client.device_manager.devices)

        print("Received completion request:", data)
        start = time.time()
        script = jedi.Script(data["code"])
        print("Script created in:", time.time() - start)

        start = time.time()
        completions = script.complete(data["line"], data["column"] - 1)
        print("Completions created in:", time.time() - start)
        start = time.time()
        infer_result = script.infer(data["line"], data["column"] - 2)
        print("Infer result created in:", time.time() - start)

        if infer_result:
            inferred_type = infer_result[0].name
            devices = client.device_manager.devices
            if inferred_type == "DeviceContainer":
                completions = [
                    {
                        "label": device.name,
                        "kind": 9,
                        "insertText": device.name,
                        "documentation": device.name,
                    }
                    for device_name, device in devices.items()
                ]
                response_queue.put(completions)
                continue
            if inferred_type == "Scans":
                completions = [
                    {
                        "label": scan_name,
                        "kind": CompletionItemKind.Method,
                        "insertText": scan_name,
                        "documentation": scan_name,
                    }
                    for scan_name, scan in client.scans._available_scans.items()
                ]
                response_queue.put(completions)
                continue
            print("Inferred type:", inferred_type)

        if completions:
            # sort completions to have private methods at the end
            completions = sorted(completions, key=lambda x: (x.name.startswith("_"), x.name))

        completions = [
            {
                "label": completion.name,
                "kind": 6,
                "insertText": completion.name,
                "documentation": completion.description,
            }
            for completion in completions
        ]
        # out = {"id": data["id"], "completions": completions}
        print("result:", completions, infer_result)
        response_queue.put(completions)
    client.shutdown()


class BaseBridge(QObject):
    initialized = Signal()
    sendDataChanged = Signal(str, str)
    completion = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.shutdown_event = threading.Event()
        self.active = False
        self.queue = []
        self.request_queue = multiprocessing.Queue()
        self.response_queue = multiprocessing.Queue()
        self.process = multiprocessing.Process(
            target=completion_worker, args=(self.request_queue, self.response_queue)
        )
        self.process.start()

        self.emitter_thread = threading.Thread(target=self.emitter)
        self.emitter_thread.start()

    def emitter(self):
        while not self.shutdown_event.is_set():
            try:
                data = self.response_queue.get(timeout=0.1)
                if data is None:
                    continue
                print("Received data from process:", data)
                self.completion.emit(json.dumps(data))
            except multiprocessing.queues.Empty:
                continue

    def send_to_js(self, name, value):
        if self.active:
            data = json.dumps(value)
            self.sendDataChanged.emit(name, data)
        else:
            self.queue.append((name, value))

    @Slot(str, str)
    def receive_from_js(self, name, value):
        if name == "completion":
            self.request_queue.put(value)
            return
        data = json.loads(value)
        self.setProperty(name, data)

    @Slot(str, result="QVariant")
    def requestCompletions(self, json_str):
        self.request_queue.put(json_str)
        out = self.response_queue.get(timeout=10)
        return json.dumps(out)
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

    def shutdown(self):
        self.request_queue.put("exit")
        self.shutdown_event.set()
        self.emitter_thread.join()
        self.process.join()


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

    def shutdown(self):
        self._bridge.shutdown()
