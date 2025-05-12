def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Cannot patch designer.")
        return
    from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

    from bec_widgets.widgets.utility.visual.color_button_native.color_button_native_plugin import (
        ColorButtonNativePlugin,
    )

    QPyDesignerCustomWidgetCollection.addCustomWidget(ColorButtonNativePlugin())


if __name__ == "__main__":  # pragma: no cover
    main()
