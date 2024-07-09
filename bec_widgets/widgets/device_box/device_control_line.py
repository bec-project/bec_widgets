from bec_widgets.widgets.device_box.device_box import DeviceBox


class DeviceControlLine(DeviceBox):
    """A widget that controls a single device."""

    ui_file = "device_control_line.ui"
    dimensions = (70, 800)  # height, width


if __name__ == "__main__":  # pragma: no cover
    import sys

    import qdarktheme
    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    qdarktheme.setup_theme("light")
    widget = DeviceControlLine(device="samy")

    widget.show()
    sys.exit(app.exec_())
