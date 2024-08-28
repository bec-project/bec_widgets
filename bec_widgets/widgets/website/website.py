from qtpy.QtCore import QUrl, qInstallMessageHandler
from qtpy.QtWebEngineWidgets import QWebEngineView
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

    ICON_NAME = "travel_explore"
    USER_ACCESS = ["set_url", "get_url", "reload", "back", "forward"]

    def __init__(self, parent=None, url: str = None, config=None, client=None, gui_id=None):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QWidget.__init__(self, parent=parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.website = QWebEngineView()
        layout.addWidget(self.website)
        self.setLayout(layout)
        self.set_url(url)

    def set_url(self, url: str) -> None:
        """
        Set the url of the website widget

        Args:
            url (str): The url to set
        """
        if not url:
            return
        self.website.setUrl(QUrl(url))

    def get_url(self) -> str:
        """
        Get the current url of the website widget

        Returns:
            str: The current url
        """
        return self.website.url().toString()

    def reload(self):
        """
        Reload the website
        """
        QWebEngineView.reload(self.website)

    def back(self):
        """
        Go back in the history
        """
        QWebEngineView.back(self.website)

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
