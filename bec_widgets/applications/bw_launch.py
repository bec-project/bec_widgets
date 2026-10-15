from __future__ import annotations

from typing import Literal

from bec_lib import bec_logger

from bec_widgets.widgets.containers.dock_area.dock_area import BECDockArea

logger = bec_logger.logger


def dock_area(
    object_name: str | None = None, startup_profile: str | Literal["restore", "skip"] | None = None
) -> BECDockArea:
    """
    Create an advanced dock area using Qt Advanced Docking System.

    Args:
        object_name(str): The name of the advanced dock area.
        startup_profile(str | Literal["restore", "skip"] | None): Startup mode for
            the workspace:
              - None: start empty
              - "restore": restore last used profile
              - "skip": do not initialize profile state
              - "<name>": load specific profile

    Returns:
        BECDockArea: The created advanced dock area.

    """

    widget = BECDockArea(
        object_name=object_name,
        root_widget=True,
        profile_namespace="bec",
        startup_profile=startup_profile,
    )
    logger.info(f"Created advanced dock area with startup_profile: {startup_profile}")
    return widget
