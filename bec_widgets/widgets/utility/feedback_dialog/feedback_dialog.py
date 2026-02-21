from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor, QFont
from qtpy.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from bec_widgets.utils.error_popups import SafeConnect, SafeSlot


class StarRating(QWidget):
    """
    A star rating widget that allows users to rate from 0 to 5 stars.
    """

    rating_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rating = 0
        self._hovered_star = 0
        self._star_buttons = []

        # Get theme colors
        theme = getattr(QApplication.instance(), "theme", None)
        if theme:
            SafeConnect(self, theme.theme_changed, self._update_theme_colors)
        self._update_theme_colors()

        # Enable mouse tracking to handle hover across the entire widget
        self.setMouseTracking(True)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        for i in range(5):
            btn = QPushButton("★")
            btn.setFixedSize(30, 30)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, idx=i + 1: self._set_rating(idx))
            layout.addWidget(btn)
            self._star_buttons.append(btn)

        self.setLayout(layout)
        self._update_display()

    @SafeSlot(str)
    def _update_theme_colors(self, _theme: str | None = None):
        """Update colors based on theme."""
        theme = getattr(QApplication.instance(), "theme", None)
        colors = theme.colors if theme else {}

        self._inactive_color = colors.get("SEPARATOR", QColor(200, 200, 200))
        self._active_color = colors.get("ACCENT_WARNING", QColor(255, 193, 7))

        # Update display if already initialized
        if hasattr(self, "_star_buttons") and self._star_buttons:
            self._update_display()

    def _set_rating(self, rating: int):
        """Set the rating and emit the signal."""
        if self._rating != rating:
            self._rating = rating
            self.rating_changed.emit(rating)
            self._update_display()

    def mouseMoveEvent(self, event):
        """Handle mouse movement to update hovered star."""
        # Calculate which star is being hovered based on mouse position
        x_pos = event.pos().x()
        star_idx = 0

        # Find which star region we're in (including gaps between stars)
        for i, btn in enumerate(self._star_buttons):
            btn_geometry = btn.geometry()
            # If we're to the right of this button's left edge, this is the current star
            # (including the gap before the next button)
            if x_pos >= btn_geometry.left():
                star_idx = i + 1
            else:
                break

        if star_idx != self._hovered_star:
            self._hovered_star = star_idx
            self._update_display()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leaving the widget."""
        self._hovered_star = 0
        self._update_display()
        super().leaveEvent(event)

    def _update_display(self):
        """Update the visual display of stars."""
        display_rating = self._hovered_star if self._hovered_star > 0 else self._rating
        inactive_color_name = self._inactive_color.name()
        active_color_name = self._active_color.name()

        for i, btn in enumerate(self._star_buttons):
            if i < display_rating:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        border: none;
                        background: transparent;
                        font-size: 24px;
                        color: {active_color_name};
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        border: none;
                        background: transparent;
                        font-size: 24px;
                        color: {inactive_color_name};
                    }}
                    QPushButton:hover {{
                        color: {active_color_name};
                    }}
                """)

    def rating(self) -> int:
        """Get the current rating."""
        return self._rating

    def set_rating(self, rating: int):
        """Set the rating programmatically."""
        if 0 <= rating <= 5:
            self._set_rating(rating)


class FeedbackDialog(QDialog):
    """
    A feedback dialog widget containing a comment field, star rating, and optional email field.

    Signals:
        feedback_submitted: Emitted when feedback is submitted (rating: int, comment: str, email: str)
    """

    feedback_submitted = Signal(int, str, str)
    ICON_NAME = "feedback"
    PLUGIN = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Feedback")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMinimumHeight(300)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # Title
        title_label = QLabel("We'd love to hear your feedback!")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Star rating section
        rating_layout = QVBoxLayout()
        rating_label = QLabel("Rating:")
        rating_layout.addWidget(rating_label)

        self._star_rating = StarRating()
        rating_layout.addWidget(self._star_rating)
        layout.addLayout(rating_layout)

        # Comment section
        comment_label = QLabel("Comments:")
        layout.addWidget(comment_label)

        self._comment_field = QTextEdit()
        self._comment_field.setPlaceholderText("Please share your thoughts...")
        self._comment_field.setMaximumHeight(150)
        layout.addWidget(self._comment_field)

        # Email section (optional)
        email_label = QLabel("Email (optional, for follow-up):")
        layout.addWidget(email_label)

        self._email_field = QLineEdit()
        self._email_field.setPlaceholderText("your.email@example.com")
        layout.addWidget(self._email_field)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_button)

        self._submit_button = QPushButton("Submit")
        self._submit_button.setDefault(True)
        self._submit_button.clicked.connect(self._on_submit)
        button_layout.addWidget(self._submit_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _on_submit(self):
        """Handle submit button click."""
        rating = self._star_rating.rating()
        comment = self._comment_field.toPlainText().strip()
        email = self._email_field.text().strip()

        # Emit the feedback signal
        self.feedback_submitted.emit(rating, comment, email)

        # Accept the dialog
        self.accept()

    def get_feedback(self) -> tuple[int, str, str]:
        """
        Get the current feedback values.

        Returns:
            tuple: (rating, comment, email)
        """
        return (
            self._star_rating.rating(),
            self._comment_field.toPlainText().strip(),
            self._email_field.text().strip(),
        )

    def set_rating(self, rating: int):
        """Set the star rating."""
        self._star_rating.set_rating(rating)

    def set_comment(self, comment: str):
        """Set the comment text."""
        self._comment_field.setPlainText(comment)

    def set_email(self, email: str):
        """Set the email text."""
        self._email_field.setText(email)

    @staticmethod
    def show_feedback_dialog(parent=None) -> tuple[int, str, str] | None:
        """
        Show the feedback dialog and return the feedback if submitted.

        Args:
            parent: Parent widget

        Returns:
            tuple: (rating, comment, email) if submitted, None if cancelled
        """
        dialog = FeedbackDialog(parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_feedback()
        return None


if __name__ == "__main__":  # pragma: no cover
    import sys

    from bec_widgets.utils.colors import apply_theme

    app = QApplication(sys.argv)
    apply_theme("dark")
    dialog = FeedbackDialog()

    def on_feedback(rating, comment, email):
        print(f"Rating: {rating}")
        print(f"Comment: {comment}")
        print(f"Email: {email}")

    dialog.feedback_submitted.connect(on_feedback)
    dialog.exec()
    sys.exit(app.exec())
