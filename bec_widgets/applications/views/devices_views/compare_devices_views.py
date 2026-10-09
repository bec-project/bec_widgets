"""Side-by-side demo, screenshots and timings of the Devices and Config views.

Runs on a fake BEC session (fakeredis) holding the 215 devices of BEC's ``demo_config.yaml``, so it
needs no running BEC::

    python -m bec_widgets.applications.views.devices_views.compare_devices_views --view qml
    python -m bec_widgets.applications.views.devices_views.compare_devices_views \
        --screenshots ./shots --theme dark
    python -m bec_widgets.applications.views.devices_views.compare_devices_views --bench

``--view`` is ``qml``, ``qwidget`` or ``legacy`` (today's Device Manager). Requires the ``dev``
extra (fakeredis).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import resource
import sys
import time
from pathlib import Path
from unittest import mock

from bec_lib.bec_yaml_loader import yaml_load
from bec_lib.device import ReadoutPriority
from bec_lib.endpoints import MessageEndpoints
from bec_lib.messages import DeviceMessage, ScanStatusMessage

DEMO_CONFIG = Path(__file__).resolve().parents[5] / "bec" / "bec_lib" / "bec_lib" / "configs"


def _demo_config_path() -> Path:
    try:
        import bec_lib.configs  # pylint: disable=import-outside-toplevel

        return Path(bec_lib.configs.__file__).parent / "demo_config.yaml"
    except ImportError:  # pragma: no cover
        return DEMO_CONFIG / "demo_config.yaml"


def fake_session():
    """Return a BEC dispatcher whose client holds the demo config devices on fakeredis."""
    from bec_widgets.tests.fake_devices import (  # pylint: disable=import-outside-toplevel
        FakeDevice,
        FakePositioner,
    )
    from bec_widgets.tests.utils import mock_client  # pylint: disable=import-outside-toplevel
    from bec_widgets.utils import bec_dispatcher as dispatcher_module  # pylint: disable=C0415

    with mock.patch.object(dispatcher_module, "BECClient", mock_client):
        dispatcher = dispatcher_module.BECDispatcher()
    client = dispatcher.client
    devices = client.device_manager.devices
    for name in list(devices):
        devices.pop(name, None)
    config = yaml_load(str(_demo_config_path()))
    for i, (name, cfg) in enumerate(config.items()):
        cfg = dict(cfg)
        cfg["deviceConfig"] = cfg.get("deviceConfig") or {}
        cls = str(cfg.get("deviceClass", ""))
        priority = ReadoutPriority(cfg.get("readoutPriority", "baseline"))
        if "Positioner" in cls or "Motor" in cls:
            limits = cfg["deviceConfig"].get("limits", [-50, 50])
            dev = FakePositioner(name, limits=limits, read_value=round(math.sin(i) * 5, 3))
            dev._readout_priority = priority  # pylint: disable=protected-access
        else:
            dev = FakeDevice(name, readout_priority=priority)
        dev._config = {"name": name, **cfg}  # pylint: disable=protected-access
        devices[name] = dev
        value = round(math.sin(i) * 5, 3) if isinstance(dev, FakePositioner) else 1000 + i * 7.5
        client.connector.set_and_publish(
            MessageEndpoints.device_readback(name),
            DeviceMessage(signals={name: {"value": value}}, metadata={}),
        )
    return dispatcher


def demo_edits(editor) -> None:
    """The three edits of the audit mockup, a device that cannot connect, a scan running."""
    work = editor.work
    if "samx" in work:
        editor.set_field("samx", "readoutPriority", "monitored")
    if "eiger" in work:
        editor.set_field("eiger", "enabled", False)
    editor.add_device("newmot", "ophyd.EpicsMotor", "X05LA-ES-PH:Z")
    editor.set_field("newmot", "description", "Pinhole Z (new)")
    editor.add_tag("newmot", "user motors")
    if "bpm5i" in work:
        editor.status["bpm5i"] = "unreach"
        editor.messages["bpm5i"] = (
            "Cannot connect — readback timed out after 5 s (IOC X05LA-BPM5 not responding)"
        )
    editor.undo_stack.clear()
    editor.select("samx")


def build(view: str, page: str, client):
    """Create one view: ``page`` is ``devices`` or ``config``."""
    # pylint: disable=import-outside-toplevel
    if view == "legacy":
        from bec_widgets.applications.views.device_manager_view.device_manager_widget import (
            DeviceManagerWidget,
        )

        widget = DeviceManagerWidget(client=client)
        widget._load_config_clicked()  # pylint: disable=protected-access
        return widget
    if view == "qml":
        from bec_widgets.applications.views.devices_views.devices_qml import (
            DeviceConfigViewQML as ConfigView,
        )
        from bec_widgets.applications.views.devices_views.devices_qml import (
            DevicesViewQML as DevicesView,
        )
    else:
        from bec_widgets.applications.views.devices_views.devices_qwidget import (
            DeviceConfigViewQWidget as ConfigView,
        )
        from bec_widgets.applications.views.devices_views.devices_qwidget import (
            DevicesViewQWidget as DevicesView,
        )
    if page == "devices":
        widget = DevicesView(client=client)
        widget.browser.select("samx")
        return widget
    widget = ConfigView(client=client)
    demo_edits(widget.editor)
    return widget


def _settle(app, ms: int = 300) -> None:
    end = time.perf_counter() + ms / 1000
    while time.perf_counter() < end:
        app.processEvents()
        time.sleep(0.01)


def screenshots(app, client, out: Path, theme: str) -> None:
    """Grab every view in one theme into ``out``."""
    from bec_qthemes import apply_theme  # pylint: disable=import-outside-toplevel

    apply_theme(theme)
    out.mkdir(parents=True, exist_ok=True)
    jobs = [("legacy", "config")] + [
        (v, p) for v in ("qml", "qwidget") for p in ("devices", "config")
    ]
    for view, page in jobs:
        widget = build(view, page, client)
        widget.resize(1500, 900)
        widget.show()
        _settle(app, 900)
        widget.grab().save(str(out / f"{theme}_{view}_{page}.png"))
        if view != "legacy" and page == "config":
            sheet = widget.open_review()
            _settle(app, 500)
            grab_sheet(widget, sheet).save(str(out / f"{theme}_{view}_review.png"))
            close_sheet(widget, sheet)
            widget.editor.set_query("sam")
            widget.editor.toggle_facet("st", "changed", True)
            _settle(app, 400)
            widget.grab().save(str(out / f"{theme}_{view}_config_filtered.png"))
        if view != "legacy" and page == "devices":
            widget.browser.set_kind("monitor")
            widget.browser.select("bpm4i")
            for k in range(60):
                widget.browser.on_readback(
                    {"signals": {"bpm4i": {"value": 1000 + 40 * math.sin(k / 6) + k}}}, {}
                )
            _settle(app, 600)
            widget.grab().save(str(out / f"{theme}_{view}_devices_monitor.png"))
        widget.close()
        widget.deleteLater()
        _settle(app, 200)


def grab_sheet(widget, sheet):
    """Picture of a sheet: QWidget dialogs grab themselves, QML popups are inside the view."""
    if hasattr(sheet, "grab"):
        return sheet.grab()
    return widget.grab()


def close_sheet(widget, sheet) -> None:
    """Close a sheet opened with ``open_review``."""
    if hasattr(sheet, "reject"):
        sheet.reject()
    else:
        widget.close_sheet()


def bench(app, client) -> dict:
    """First show, second instance, edit-to-repaint and filter timings plus memory."""
    results = {}
    for view in ("legacy", "qml", "qwidget"):
        for page in ("devices", "config") if view != "legacy" else ("config",):
            rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            t0 = time.perf_counter()
            widget = build(view, page, client)
            widget.resize(1500, 900)
            widget.show()
            app.processEvents()
            first = (time.perf_counter() - t0) * 1000
            _settle(app, 300)
            rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            t0 = time.perf_counter()
            second = build(view, page, client)
            second.resize(1500, 900)
            second.show()
            app.processEvents()
            again = (time.perf_counter() - t0) * 1000
            entry = {
                "first_show_ms": round(first, 1),
                "second_show_ms": round(again, 1),
                "rss_growth_mb": round(rss1 - rss0, 1),
            }
            if view != "legacy" and page == "config":
                editor = widget.editor
                t0 = time.perf_counter()
                for k in range(20):
                    editor.set_field("samy", "description", f"edit {k}")
                    app.processEvents()
                entry["edit_ms"] = round((time.perf_counter() - t0) * 1000 / 20, 2)
                t0 = time.perf_counter()
                for q in ("s", "sa", "sam", "samx", ""):
                    editor.set_query(q)
                    app.processEvents()
                entry["filter_ms"] = round((time.perf_counter() - t0) * 1000 / 5, 2)
            if view != "legacy" and page == "devices":
                browser = widget.browser
                browser.set_kind("any")
                app.processEvents()
                t0 = time.perf_counter()
                for k in range(50):
                    for name in list(browser.values)[:150]:
                        browser.on_readback({"signals": {name: {"value": k}}}, {})
                    browser._flush_values()  # pylint: disable=protected-access
                    app.processEvents()
                entry["refresh_150_values_ms"] = round((time.perf_counter() - t0) * 1000 / 50, 2)
            results[f"{view}/{page}"] = entry
            for w in (widget, second):
                w.close()
                w.deleteLater()
            _settle(app, 200)
    return results


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--view", choices=["qml", "qwidget", "legacy"], default="qml")
    parser.add_argument("--page", choices=["devices", "config"], default="config")
    parser.add_argument("--theme", choices=["light", "dark"], default="dark")
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--bench", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("OPHYD_CONTROL_LAYER", "dummy")
    from bec_qthemes import apply_theme  # pylint: disable=import-outside-toplevel
    from qtpy.QtWidgets import QApplication  # pylint: disable=import-outside-toplevel

    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(args.theme)
    dispatcher = fake_session()
    client = dispatcher.client
    client.connector.set_and_publish(
        MessageEndpoints.scan_status(),
        ScanStatusMessage(scan_id="x", status="closed", info={}, scan_number=1285),
    )
    if args.screenshots:
        for theme in ("light", "dark"):
            screenshots(app, client, args.screenshots, theme)
    if args.bench:
        print(json.dumps(bench(app, client), indent=2))
    if args.screenshots or args.bench:
        os._exit(0)  # pylint: disable=protected-access
    widget = build(args.view, args.page, client)
    widget.resize(1500, 900)
    widget.show()
    sys.exit(app.exec())


if __name__ == "__main__":  # pragma: no cover
    main()
