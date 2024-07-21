def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Cannot patch designer.")
        return
    from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

    from bec_widgets.widgets.text_box.text_box_plugin import TextBoxPlugin

    QPyDesignerCustomWidgetCollection.addCustomWidget(TextBoxPlugin())


if __name__ == "__main__":  # pragma: no cover
    main()
