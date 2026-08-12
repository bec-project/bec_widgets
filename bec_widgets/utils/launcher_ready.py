from __future__ import annotations

from typing import Any

from bec_lib.logger import bec_logger

from bec_widgets.utils.launch_progress import launch_progress

logger = bec_logger.logger


def notify_launcher_ready(app_name: str, window: Any | None = None) -> bool:
    """
    Notify bec_launcher that the GUI window for this launch is visible.

    Sends the final ``ready`` edge over the per-launch progress socket that
    bec_launcher opened for this process (see
    :mod:`bec_widgets.utils.launch_progress`). This resolves the launcher's
    loading banner and lets it close itself.

    The call is intentionally a no-op returning ``False`` unless bec_launcher
    provided the socket + token through the environment, and it never raises:
    all socket errors are swallowed by the client.

    Args:
        app_name(str): The launched app identifier (informational).
        window(Any | None): The visible top-level window, if available (informational).

    Returns:
        bool: True if the ready edge was delivered to the launcher, else False.
    """
    if launch_progress is None or not launch_progress.enabled:
        return False
    delivered = launch_progress.emit_ready()
    if not delivered:
        logger.debug(f"Launcher ready edge not delivered for '{app_name}'.")
    return delivered
