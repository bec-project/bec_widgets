def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Cannot patch designer.")
        return
    from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

    from bec_widgets.widgets.control.device_control.positioner_box.positioner_box_2d.positioner_box2_d_plugin import (
        PositionerBox2DPlugin,
    )

    QPyDesignerCustomWidgetCollection.addCustomWidget(PositionerBox2DPlugin())


if __name__ == "__main__":  # pragma: no cover
    main()
