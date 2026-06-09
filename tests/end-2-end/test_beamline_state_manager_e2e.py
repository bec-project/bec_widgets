from __future__ import annotations

import uuid

import pytest
from bec_lib.bl_states import DeviceWithinLimitsStateConfig

# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=protected-access


def _delete_state_if_present(bec, state_name: str) -> None:
    if hasattr(bec.beamline_states, state_name):
        bec.beamline_states.delete(state_name)


@pytest.mark.timeout(100)
def test_beamline_state_manager_adds_updates_and_deletes_state_e2e(
    qtbot, bec_client_lib, connected_client_gui_obj
):
    """
    Verify the real BEC beamline-state flow is reflected by a BeamlineStateManager
    running in the GUI server, accessed through the dock area RPC interface.
    """
    gui = connected_client_gui_obj
    dock_area = gui.bec
    bec = bec_client_lib
    dev = bec.device_manager.devices
    scans = bec.scans

    state_name = f"samx_widget_limits_{uuid.uuid4().hex[:8]}"
    config = DeviceWithinLimitsStateConfig(
        name=state_name, device="samx", signal="samx", low_limit=0.0, high_limit=10.0, tolerance=1.0
    )

    manager = dock_area.new("BeamlineStateManager")
    qtbot.waitUntil(lambda: manager._gui_id in gui._server_registry, timeout=5000)

    def state_entry() -> dict[str, str]:
        return manager.state_summary().get(state_name, {})

    _delete_state_if_present(bec, state_name)

    try:
        bec.beamline_states.add(config)

        qtbot.waitUntil(lambda: hasattr(bec.beamline_states, state_name), timeout=10000)
        qtbot.waitUntil(lambda: state_name in manager.state_summary(), timeout=10000)

        scans.umv(dev.samx, 5, relative=False).wait()
        qtbot.waitUntil(
            lambda: getattr(bec.beamline_states, state_name).get()["status"] == "valid",
            timeout=10000,
        )
        qtbot.waitUntil(lambda: state_entry().get("status") == "valid", timeout=10000)
        assert state_entry()["label"] == "Device samx within limits"

        scans.umv(dev.samx, 20, relative=False).wait()
        qtbot.waitUntil(
            lambda: getattr(bec.beamline_states, state_name).get()["status"] == "invalid",
            timeout=10000,
        )
        qtbot.waitUntil(lambda: state_entry().get("status") == "invalid", timeout=10000)
        assert state_entry()["label"] == "Device samx out of limits"

        bec.beamline_states.delete(state_name)
        qtbot.waitUntil(lambda: not hasattr(bec.beamline_states, state_name), timeout=10000)
        qtbot.waitUntil(lambda: state_name not in manager.state_summary(), timeout=10000)

    finally:
        _delete_state_if_present(bec, state_name)
        scans.umv(dev.samx, 0, relative=False).wait()
