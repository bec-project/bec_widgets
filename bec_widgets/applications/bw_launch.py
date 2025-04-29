from __future__ import annotations

from bec_widgets.widgets.containers.auto_update.auto_updates import AutoUpdates
from bec_widgets.widgets.containers.dock.dock_area import BECDockArea


def dock_area(object_name: str | None = None) -> BECDockArea:
    _dock_area = BECDockArea(object_name=object_name, root_widget=True)
    return _dock_area


def auto_update_dock_area(object_name: str | None = None) -> AutoUpdates:
    """
    Create a dock area with auto update enabled.

    Args:
        object_name(str): The name of the dock area.

    Returns:
        BECDockArea: The created dock area.
    """
    _auto_update = AutoUpdates(object_name=object_name)
    return _auto_update
