from bec_widgets.widgets.device_inputs import DeviceLineEdit

if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = DeviceLineEdit()
    w.show()
    sys.exit(app.exec_())
