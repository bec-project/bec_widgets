from bec_widgets.cli.auto_updates import AutoUpdates
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea


def dock_area(object_name: str | None = None):
    _dock_area = BECDockArea(object_name=object_name)
    return _dock_area


def auto_update_dock_area(object_name: str | None = None) -> BECDockArea:
    """
    Create a dock area with auto update enabled.

    Args:
        object_name(str): The name of the dock area.

    Returns:
        BECDockArea: The created dock area.
    """
    _dock_area = BECDockArea(object_name=object_name)
    _dock_area.set_auto_update(AutoUpdates)
    _dock_area.auto_update.enabled = True  # type:ignore
    return _dock_area
