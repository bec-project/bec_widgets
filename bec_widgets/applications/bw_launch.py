from bec_widgets.widgets.containers.dock.dock_area import BECDockArea


def dock_area(object_name: str | None = None):
    _dock_area = BECDockArea(object_name=object_name)
    return _dock_area
