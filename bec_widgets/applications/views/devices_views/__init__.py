"""The device manager split into two views, as proposed in the bec-app UX audit.

* **Devices** (everyone): search, read and move devices of the running session.
* **Config** (staff): edit a copy of the session config, review exactly what differs from the
  running session and apply only those changes.

Both views exist as a QML and a QWidget implementation on top of the same controllers in
:mod:`devices_core`. The legacy :class:`DeviceManagerView` is kept untouched.
"""
