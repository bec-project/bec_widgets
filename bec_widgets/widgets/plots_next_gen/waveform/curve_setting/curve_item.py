import os

from PySide6.QtWidgets import QVBoxLayout, QWidget

from bec_widgets.utils import UILoader


class CurveItem(QWidget):
    """
    #TODO change this nonsense docstring
        Widget that lets a user set up curves for the Waveform widget.
    It allows:
      - Selecting color palette for the entire widget
      - Choosing x-axis mode
      - Selecting device and signal
      - Adding a new curve
      - Viewing existing curves in a QTreeWidget
    """

    def __init__(self, parent=None, target_widget=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.setObjectName("CurveSettings")
        current_path = os.path.dirname(__file__)
        self.ui = UILoader().load_ui(os.path.join(current_path, "curve_settings.ui"), self)

        self.target_widget = target_widget

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.ui)
