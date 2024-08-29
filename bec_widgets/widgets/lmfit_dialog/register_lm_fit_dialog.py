def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Cannot patch designer.")
        return
    from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

    from bec_widgets.widgets.lmfit_dialog.lm_fit_dialog_plugin import LMFitDialogPlugin

    QPyDesignerCustomWidgetCollection.addCustomWidget(LMFitDialogPlugin())


if __name__ == "__main__":  # pragma: no cover
    main()
