def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Cannot patch designer.")
        return
    from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

    from bec_widgets.widgets.editors.web_console.web_console_plugin import WebConsolePlugin

    QPyDesignerCustomWidgetCollection.addCustomWidget(WebConsolePlugin())


if __name__ == "__main__":  # pragma: no cover
    main()
