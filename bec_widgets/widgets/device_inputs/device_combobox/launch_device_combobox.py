from bec_widgets.widgets.device_inputs import DeviceComboBox

if __name__ == "__main__":  # pragma: no cover
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = DeviceComboBox()
    w.show()
    sys.exit(app.exec_())
