def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Cannot patch designer.")
        return
    from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

    from bec_widgets.widgets.scan_control.scan_control_plugin import ScanControlPlugin

    QPyDesignerCustomWidgetCollection.addCustomWidget(ScanControlPlugin())


if __name__ == "__main__":  # pragma: no cover
    main()
