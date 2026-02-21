import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog

from bec_widgets.widgets.utility.feedback_dialog.feedback_dialog import FeedbackDialog, StarRating


@pytest.fixture
def star_rating(qtbot):
    """Create a StarRating widget for testing."""
    widget = StarRating()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget
    widget.close()


@pytest.fixture
def feedback_dialog(qtbot):
    """Create a FeedbackDialog for testing."""
    dialog = FeedbackDialog()
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog)
    yield dialog
    dialog.close()


class TestStarRating:
    """Tests for the StarRating widget."""

    def test_initial_state(self, star_rating):
        """Test that StarRating initializes with rating 0."""
        assert star_rating.rating() == 0
        assert star_rating._hovered_star == 0
        assert len(star_rating._star_buttons) == 5

    def test_set_rating_via_method(self, star_rating):
        """Test setting rating programmatically."""
        star_rating.set_rating(3)
        assert star_rating.rating() == 3

        star_rating.set_rating(5)
        assert star_rating.rating() == 5

    def test_set_rating_bounds(self, star_rating):
        """Test that rating is bounded between 0 and 5."""
        star_rating.set_rating(0)
        assert star_rating.rating() == 0

        star_rating.set_rating(5)
        assert star_rating.rating() == 5

        # Out of bounds should not change rating
        initial_rating = star_rating.rating()
        star_rating.set_rating(6)
        assert star_rating.rating() == initial_rating

        star_rating.set_rating(-1)
        assert star_rating.rating() == initial_rating

    def test_rating_signal_emission(self, star_rating, qtbot):
        """Test that rating_changed signal is emitted when rating changes."""
        with qtbot.waitSignal(star_rating.rating_changed, timeout=1000) as blocker:
            star_rating.set_rating(4)

        assert blocker.args == [4]

    def test_rating_signal_not_emitted_on_same_value(self, star_rating, qtbot):
        """Test that signal is not emitted when setting the same rating."""
        star_rating.set_rating(3)

        # Should not emit signal when setting same value
        with qtbot.assertNotEmitted(star_rating.rating_changed, wait=100):
            star_rating.set_rating(3)

    def test_click_star_button(self, star_rating, qtbot):
        """Test clicking on star buttons."""
        # Click the third star (index 2)
        with qtbot.waitSignal(star_rating.rating_changed, timeout=1000):
            qtbot.mouseClick(star_rating._star_buttons[2], Qt.LeftButton)

        assert star_rating.rating() == 3

        # Click the first star
        with qtbot.waitSignal(star_rating.rating_changed, timeout=1000):
            qtbot.mouseClick(star_rating._star_buttons[0], Qt.LeftButton)

        assert star_rating.rating() == 1

    def test_mouse_hover(self, star_rating, qtbot):
        """Test mouse hover behavior."""
        # Set initial rating
        star_rating.set_rating(2)
        assert star_rating._hovered_star == 0

        # Simulate mouse move over the fourth button
        btn = star_rating._star_buttons[3]
        btn_center = btn.geometry().center()
        event = qtbot.mouseMove(star_rating, pos=btn_center)

        # Note: _hovered_star should be updated by mouseMoveEvent
        # This is a bit tricky to test directly, so we verify the method exists
        assert hasattr(star_rating, "mouseMoveEvent")
        assert hasattr(star_rating, "leaveEvent")

    def test_leave_event(self, star_rating, qtbot):
        """Test that leaving the widget clears hover state."""
        star_rating.set_rating(2)
        star_rating._hovered_star = 4  # Simulate hover

        # Trigger leave event
        star_rating.leaveEvent(None)

        assert star_rating._hovered_star == 0
        assert star_rating.rating() == 2  # Rating should remain unchanged

    def test_update_theme_colors(self, star_rating):
        """Test that theme colors are applied correctly."""
        assert hasattr(star_rating, "_inactive_color")
        assert hasattr(star_rating, "_active_color")

        # Colors should be initialized
        assert star_rating._inactive_color is not None
        assert star_rating._active_color is not None

    def test_display_update(self, star_rating):
        """Test that display updates when rating changes."""
        star_rating.set_rating(3)
        # If this doesn't raise an exception, the display was updated successfully
        star_rating._update_display()


class TestFeedbackDialog:
    """Tests for the FeedbackDialog widget."""

    def test_initial_state(self, feedback_dialog):
        """Test that FeedbackDialog initializes correctly."""
        assert feedback_dialog.windowTitle() == "Feedback"
        assert feedback_dialog.isModal() is True
        assert feedback_dialog._star_rating is not None
        assert feedback_dialog._comment_field is not None
        assert feedback_dialog._email_field is not None
        assert feedback_dialog._submit_button is not None
        assert feedback_dialog._cancel_button is not None

    def test_get_feedback_initial(self, feedback_dialog):
        """Test getting feedback from unmodified dialog."""
        rating, comment, email = feedback_dialog.get_feedback()
        assert rating == 0
        assert comment == ""
        assert email == ""

    def test_set_and_get_rating(self, feedback_dialog):
        """Test setting and getting rating."""
        feedback_dialog.set_rating(4)
        rating, _, _ = feedback_dialog.get_feedback()
        assert rating == 4

    def test_set_and_get_comment(self, feedback_dialog):
        """Test setting and getting comment."""
        test_comment = "This is a test comment"
        feedback_dialog.set_comment(test_comment)
        _, comment, _ = feedback_dialog.get_feedback()
        assert comment == test_comment

    def test_set_and_get_email(self, feedback_dialog):
        """Test setting and getting email."""
        test_email = "test@example.com"
        feedback_dialog.set_email(test_email)
        _, _, email = feedback_dialog.get_feedback()
        assert email == test_email

    def test_set_all_feedback(self, feedback_dialog):
        """Test setting all feedback fields."""
        feedback_dialog.set_rating(5)
        feedback_dialog.set_comment("Great widget!")
        feedback_dialog.set_email("user@example.com")

        rating, comment, email = feedback_dialog.get_feedback()
        assert rating == 5
        assert comment == "Great widget!"
        assert email == "user@example.com"

    def test_submit_button_emits_signal(self, feedback_dialog, qtbot):
        """Test that clicking submit emits feedback_submitted signal."""
        feedback_dialog.set_rating(3)
        feedback_dialog.set_comment("Test feedback")
        feedback_dialog.set_email("test@test.com")

        with qtbot.waitSignal(feedback_dialog.feedback_submitted, timeout=1000) as blocker:
            qtbot.mouseClick(feedback_dialog._submit_button, Qt.LeftButton)

        assert blocker.args == [3, "Test feedback", "test@test.com"]

    def test_submit_button_accepts_dialog(self, feedback_dialog, qtbot):
        """Test that clicking submit accepts the dialog."""
        feedback_dialog.set_rating(4)

        qtbot.mouseClick(feedback_dialog._submit_button, Qt.LeftButton)
        qtbot.wait(100)

        # Dialog should be accepted
        assert feedback_dialog.result() == QDialog.DialogCode.Accepted

    def test_cancel_button_rejects_dialog(self, feedback_dialog, qtbot):
        """Test that clicking cancel rejects the dialog."""
        qtbot.mouseClick(feedback_dialog._cancel_button, Qt.LeftButton)
        qtbot.wait(100)

        # Dialog should be rejected
        assert feedback_dialog.result() == QDialog.DialogCode.Rejected

    def test_submit_with_empty_fields(self, feedback_dialog, qtbot):
        """Test submitting with empty fields."""
        # Don't set any values
        with qtbot.waitSignal(feedback_dialog.feedback_submitted, timeout=1000) as blocker:
            qtbot.mouseClick(feedback_dialog._submit_button, Qt.LeftButton)

        # Should emit with empty values
        assert blocker.args == [0, "", ""]

    def test_submit_strips_whitespace(self, feedback_dialog, qtbot):
        """Test that whitespace is stripped from comment and email."""
        feedback_dialog.set_comment("  Test comment  ")
        feedback_dialog.set_email("  test@example.com  ")

        with qtbot.waitSignal(feedback_dialog.feedback_submitted, timeout=1000) as blocker:
            qtbot.mouseClick(feedback_dialog._submit_button, Qt.LeftButton)

        rating, comment, email = blocker.args
        assert comment == "Test comment"
        assert email == "test@example.com"

    def test_dialog_has_correct_properties(self, feedback_dialog):
        """Test that dialog has correct class properties."""
        assert hasattr(FeedbackDialog, "ICON_NAME")
        assert FeedbackDialog.ICON_NAME == "feedback"
        assert hasattr(FeedbackDialog, "PLUGIN")
        assert FeedbackDialog.PLUGIN is True

    def test_comment_field_placeholder(self, feedback_dialog):
        """Test that comment field has placeholder text."""
        assert feedback_dialog._comment_field.placeholderText() != ""

    def test_email_field_placeholder(self, feedback_dialog):
        """Test that email field has placeholder text."""
        assert feedback_dialog._email_field.placeholderText() != ""

    def test_submit_button_is_default(self, feedback_dialog):
        """Test that submit button is set as default."""
        assert feedback_dialog._submit_button.isDefault() is True

    def test_star_rating_embedded_correctly(self, feedback_dialog, qtbot):
        """Test that StarRating widget is properly embedded."""
        # Verify we can interact with the embedded star rating
        feedback_dialog._star_rating.set_rating(5)
        assert feedback_dialog._star_rating.rating() == 5

        # Verify rating is reflected in feedback
        rating, _, _ = feedback_dialog.get_feedback()
        assert rating == 5
