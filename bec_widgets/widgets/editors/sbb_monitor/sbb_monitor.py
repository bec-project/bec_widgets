from bec_widgets.widgets.editors.website.website import WebsiteWidget


class SBBMonitor(WebsiteWidget):
    """
    A widget to display the SBB monitor website.
    """

    PLUGIN = True
    ICON_NAME = "train"
    USER_ACCESS = []

    def __init__(self, parent=None, **kwargs):
        url = "https://free.oevplus.ch/monitor/?viewType=splitView&layout=1&showClock=true&showPerron=true&stationGroup1Title=Villigen%2C%20PSI%20West&stationGroup2Title=Siggenthal-Würenlingen&station_1_id=85%3A3592&station_1_name=Villigen%2C%20PSI%20West&station_1_quantity=5&station_1_group=1&station_2_id=85%3A3502&station_2_name=Siggenthal-Würenlingen&station_2_quantity=5&station_2_group=2"
        super().__init__(parent=parent, url=url, **kwargs)
