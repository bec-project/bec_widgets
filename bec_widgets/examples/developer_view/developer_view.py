from qtpy.QtWidgets import QWidget

from bec_widgets.applications.views.view import ViewBase
from bec_widgets.examples.developer_view.developer_widget import DeveloperWidget


class DeveloperView(ViewBase):
    """
    A view for users to write scripts and macros and execute them within the application.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        content: QWidget | None = None,
        *,
        id: str | None = None,
        title: str | None = None,
    ):
        super().__init__(parent=parent, content=content, id=id, title=title)
        self.developer_widget = DeveloperWidget(parent=self)
        self.set_content(self.developer_widget)

        # Apply stretch after the layout is done
        self.set_default_view([2, 5, 3], [7, 3])


if __name__ == "__main__":
    import sys

    from bec_qthemes import apply_theme
    from qtpy.QtWidgets import QApplication

    from bec_widgets.applications.main_app import BECMainApp

    app = QApplication(sys.argv)
    apply_theme("dark")

    _app = BECMainApp()
    screen = app.primaryScreen()
    screen_geometry = screen.availableGeometry()
    screen_width = screen_geometry.width()
    screen_height = screen_geometry.height()
    # 70% of screen height, keep 16:9 ratio
    height = int(screen_height * 0.9)
    width = int(height * (16 / 9))

    # If width exceeds screen width, scale down
    if width > screen_width * 0.9:
        width = int(screen_width * 0.9)
        height = int(width / (16 / 9))

    _app.resize(width, height)
    developer_view = DeveloperView()
    _app.add_view(
        icon="code_blocks", title="IDE", widget=developer_view, id="developer_view", exclusive=True
    )
    _app.show()
    # developer_view.show()
    # developer_view.setWindowTitle("Developer View")
    # developer_view.resize(1920, 1080)
    # developer_view.set_stretch(horizontal=[1, 3, 2], vertical=[5, 5]) #can be set during runtime
    sys.exit(app.exec_())
