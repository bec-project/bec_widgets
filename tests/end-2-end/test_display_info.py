"""Display diagnostics from a fresh client attached to an existing GUI server."""

from bec_widgets.cli.client_utils import BECGuiClient


def test_display_info_from_fresh_client(connected_client_gui_obj):
    server_owner = connected_client_gui_obj
    attached = BECGuiClient(gui_id=server_owner._gui_id)
    assert not attached._gui_started_event.is_set()
    assert attached._process is None

    info = attached.get_display_info()

    assert info["pid"] == server_owner._process.pid
    assert info["qt_platform"]
    assert not attached._gui_started_event.is_set()
    assert attached._process is None
