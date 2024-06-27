from qtpy.QtCore import QUrl, qInstallMessageHandler
from qtpy.QtWebEngineWidgets import QWebEngineView
from qtpy.QtWidgets import QApplication

from bec_widgets.utils import BECConnector


def suppress_qt_messages(type_, context, msg):
    if context.category in ["js", "default"]:
        return
    print(msg)


qInstallMessageHandler(suppress_qt_messages)


class WebsiteWidget(BECConnector, QWebEngineView):
    """
    A simple widget to display a website
    """

    USER_ACCESS = ["set_url", "get_url", "reload", "back", "forward"]

    def __init__(self, parent=None, url: str = None, config=None, client=None, gui_id=None):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWebEngineView.__init__(self, parent=parent)
        self.set_url(url)

    def set_url(self, url: str) -> None:
        """
        Set the url of the website widget

        Args:
            url (str): The url to set
        """
        if not url:
            return
        self.setUrl(QUrl(url))

    def get_url(self) -> str:
        """
        Get the current url of the website widget

        Returns:
            str: The current url
        """
        return self.url().toString()

    def reload(self):
        """
        Reload the website
        """
        QWebEngineView.reload(self)

    def back(self):
        """
        Go back in the history
        """
        QWebEngineView.back(self)

    def forward(self):
        """
        Go forward in the history
        """
        QWebEngineView.forward(self)


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    mainWin = WebsiteWidget("https://scilog.psi.ch")
    mainWin.show()
    sys.exit(app.exec())
