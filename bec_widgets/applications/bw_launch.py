from __future__ import annotations

from bec_lib import bec_logger

from bec_widgets.widgets.containers.auto_update.auto_updates import AutoUpdates
from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea

logger = bec_logger.logger


def dock_area(
    object_name: str | None = None, profile: str | None = None, start_empty: bool = False
) -> BECDockArea:
    """
    Create an advanced dock area using Qt Advanced Docking System.

    Args:
        object_name(str): The name of the advanced dock area.
        profile(str|None): Optional profile to load; if None the "general" profile is used.
        start_empty(bool): If True, start with an empty dock area when loading specified profile.

    Returns:
        BECDockArea: The created advanced dock area.

    Note:
        The "general" profile is mandatory and will always exist. If manually deleted,
        it will be automatically recreated.
    """
    # Default to "general" profile when called from CLI without specifying a profile
    effective_profile = profile if profile is not None else "general"

    widget = BECDockArea(
        object_name=object_name,
        restore_initial_profile=True,
        root_widget=True,
        profile_namespace="bec",
        init_profile=effective_profile,
        start_empty=start_empty,
    )
    logger.info(
        f"Created advanced dock area with profile: {effective_profile}, start_empty: {start_empty}"
    )
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
