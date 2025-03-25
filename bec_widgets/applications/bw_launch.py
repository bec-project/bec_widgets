from bec_widgets.widgets.containers.dock.dock_area import BECDockArea


def dock_area(name: str | None = None):
    _dock_area = BECDockArea(name=name)
    return _dock_area
