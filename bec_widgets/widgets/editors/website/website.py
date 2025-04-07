from qtpy.QtCore import Property, QUrl, Slot, qInstallMessageHandler
from qtpy.QtWebEngineWidgets import QWebEngineSettings, QWebEngineView
from qtpy.QtWidgets import QApplication, QVBoxLayout, QWidget

from bec_widgets.utils.bec_widget import BECWidget


def suppress_qt_messages(type_, context, msg):
    if context.category in ["js", "default"]:
        return
    print(msg)


qInstallMessageHandler(suppress_qt_messages)


class WebsiteWidget(BECWidget, QWidget):
    """
    A simple widget to display a website
    """

    PLUGIN = True
    ICON_NAME = "travel_explore"
    USER_ACCESS = ["set_url", "get_url", "reload", "back", "forward"]

    def __init__(
        self, parent=None, url: str = None, config=None, client=None, gui_id=None, **kwargs
    ):
        super().__init__(parent=parent, client=client, gui_id=gui_id, config=config, **kwargs)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.website = QWebEngineView()
        layout.addWidget(self.website)
        self.setLayout(layout)
        self.set_url(url)

        self._loaded = False
        self.website.loadFinished.connect(self._on_load_finished)

    def wait_until_loaded(self):
        while not self._loaded:
            QApplication.processEvents()

    def _on_load_finished(self):
        """
        Callback when the website has finished loading
        """
        self._loaded = True

    @Property(str)
    def url(self) -> str:
        """
        The url of the website widget

        Returns:
            str: The url
        """
        return self.get_url()

    @url.setter
    def url(self, url: str) -> None:
        """
        Set the url of the website widget

        Args:
            url (str): The url to set
        """
        self.set_url(url)

    @Slot(str)
    def set_url(self, url: str) -> None:
        """
        Set the url of the website widget

        Args:
            url (str): The url to set
        """
        if not url:
            return
        if not isinstance(url, str):
            return
        self._loaded = False
        self.website.setUrl(QUrl(url))

    def get_url(self) -> str:
        """
        Get the current url of the website widget

        Returns:
            str: The current url
        """
        return self.website.url().toString()

    @Slot()
    def reload(self):
        """
        Reload the website
        """
        QWebEngineView.reload(self.website)

    @Slot()
    def back(self):
        """
        Go back in the history
        """
        QWebEngineView.back(self.website)

    @Slot()
    def forward(self):
        """
        Go forward in the history
        """
        QWebEngineView.forward(self.website)

    def cleanup(self):
        """
        Cleanup the widget
        """
        self.website.page().deleteLater()


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    mainWin = WebsiteWidget(url="https://scilog.psi.ch")
    mainWin.show()
    sys.exit(app.exec())
