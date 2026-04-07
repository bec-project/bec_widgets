if __name__ == "__main__":  # pragma: no cover
    import sys

    from pyside6_qtermwidget import QTermWidget  # pylint: disable=ungrouped-imports
    from qtpy.QtWidgets import QApplication  # pylint: disable=ungrouped-imports

    app = QApplication(sys.argv)
    widget = QTermWidget()

    widget.show()
    sys.exit(app.exec())
