def main():  # pragma: no cover
    from qtpy import PYSIDE6

    if not PYSIDE6:
        print("PYSIDE6 is not available in the environment. Cannot patch designer.")
        return
    from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

    from bec_widgets.widgets.progress.scan_progressbar.scan_progress_bar_plugin import (
        ScanProgressBarPlugin,
    )

    QPyDesignerCustomWidgetCollection.addCustomWidget(ScanProgressBarPlugin())


if __name__ == "__main__":  # pragma: no cover
    main()
