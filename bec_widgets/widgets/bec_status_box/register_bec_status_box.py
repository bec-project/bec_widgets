def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Cannot patch designer.")
        return
    from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

    from bec_widgets.widgets.bec_status_box.bec_status_box_plugin import BECStatusBoxPlugin

    QPyDesignerCustomWidgetCollection.addCustomWidget(BECStatusBoxPlugin())


if __name__ == "__main__":  # pragma: no cover
    main()
