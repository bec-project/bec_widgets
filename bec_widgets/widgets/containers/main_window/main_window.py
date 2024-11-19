from qtpy.QtWidgets import QMainWindow

from bec_widgets.utils import BECConnector


class BECMainWindow(QMainWindow, BECConnector):
    def __init__(self, *args, **kwargs):
        BECConnector.__init__(self, **kwargs)
        QMainWindow.__init__(self, *args, **kwargs)
