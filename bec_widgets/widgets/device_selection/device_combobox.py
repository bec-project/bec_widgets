from qtpy.QtWidgets import QComboBox

from bec_widgets.utils import BECConnector, ConnectionConfig


class DeviceCombobox(BECConnector, QComboBox):
    def __init__(self, parent=None, client=None, config=None, gui_id=None):
        super().__init__(client=client, config=config, gui_id=gui_id)
        QComboBox.__init__(self, parent=parent)

        self.get_bec_shortcuts()

        def get_device(self):
            return getattr(self.dev, self.text().lower())
