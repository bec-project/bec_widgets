class BECWidget:
    """Base class for all BEC widgets."""

    def closeEvent(self, event):
        if hasattr(self, "cleanup"):
            self.cleanup()
        if hasattr(super(), "closeEvent"):
            super().closeEvent(event)
