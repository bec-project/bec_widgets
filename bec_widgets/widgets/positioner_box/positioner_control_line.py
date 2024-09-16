from bec_lib.device import Positioner

from bec_widgets.widgets.positioner_box.positioner_box import PositionerBox


class PositionerControlLine(PositionerBox):
    """A widget that controls a single device."""

    ui_file = "positioner_control_line.ui"
    dimensions = (60, 600)  # height, width

    ICON_NAME = "switch_left"

    def __init__(self, parent=None, device: Positioner = None, *args, **kwargs):
        """Initialize the DeviceControlLine.

        Args:
            parent: The parent widget.
            device (Positioner): The device to control.
        """
        super().__init__(parent=parent, device=device, *args, **kwargs)


if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    widget = PositionerControlLine(device="samy")

    widget.show()
    sys.exit(app.exec_())
