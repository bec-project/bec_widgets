from __future__ import annotations

from bec_lib import bec_logger

from bec_widgets.widgets.containers.advanced_dock_area.advanced_dock_area import AdvancedDockArea
from bec_widgets.widgets.containers.auto_update.auto_updates import AutoUpdates

logger = bec_logger.logger


def dock_area(object_name: str | None = None, profile: str | None = None) -> AdvancedDockArea:
    """
    Create an advanced dock area using Qt Advanced Docking System.

    Args:
        object_name(str): The name of the advanced dock area.
        profile(str|None): Optional profile to load; if None the last profile is restored.

    Returns:
        AdvancedDockArea: The created advanced dock area.
    """
    widget = AdvancedDockArea(
        object_name=object_name,
        restore_initial_profile=(profile is None),
        root_widget=True,
        profile_namespace="bec",
    )
    if profile:
        widget.load_profile(profile)
    logger.info(f"Created advanced dock area with profile: {profile}")
    return widget


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
