from qtpy.QtCore import QUrl
from qtpy.QtWebEngineWidgets import QWebEngineView
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget


class WebsiteWidget(QWidget):
    def __init__(self, url):
        super().__init__()
        self.editor = QWebEngineView(self)

        layout = QVBoxLayout()
        layout.addWidget(self.editor)
        self.setLayout(layout)
        self.editor.setUrl(QUrl(url))


class VSCodeEditor(WebsiteWidget):
    token = "bec"
    host = "localhost"
    port = 7000

    def __init__(self):
        super().__init__(f"http://{self.host}:{self.port}?tkn={self.token}")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    mainWin = WebsiteWidget("https://scilog.psi.ch")
    mainWin.show()
    sys.exit(app.exec())
