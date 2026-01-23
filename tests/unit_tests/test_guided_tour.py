from unittest import mock

import pytest
from qtpy.QtCore import QRect
from qtpy.QtWidgets import QAction, QVBoxLayout, QWidget

from bec_widgets.utils.guided_tour import GuidedTour
from bec_widgets.utils.toolbars.actions import ExpandableMenuAction, MaterialIconAction
from bec_widgets.utils.toolbars.toolbar import ModularToolBar


@pytest.fixture
def main_window(qtbot):
    """Create a main window for testing."""
    window = QWidget()
    window.resize(800, 600)
    qtbot.addWidget(window)
    return window


@pytest.fixture
def guided_help(main_window):
    """Create a GuidedTour instance for testing."""
    return GuidedTour(main_window, enforce_visibility=False)


@pytest.fixture
def test_widget(main_window):
    """Create a test widget."""
    widget = QWidget(main_window)
    widget.resize(100, 50)
    widget.show()
    return widget


class DummyWidget(QWidget):
    """A dummy widget for testing purposes."""

    def isVisible(self) -> bool:
        """Override isVisible to always return True for testing."""
        return True


class DummyAction(QAction):
    """A dummy action for testing purposes."""


class TestGuidedTour:
    """Test the GuidedTour class core functionality."""

    def test_initialization(self, guided_help):
        """Test GuidedTour is properly initialized."""
        assert guided_help.main_window is not None
        assert guided_help._registered_widgets == {}
        assert guided_help._tour_steps == []
        assert guided_help._current_index == 0
        assert guided_help._active is False

    def test_register_widget(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test widget registration creates weak references."""
        widget_id = guided_help.register_widget(
            widget=test_widget, text="Test widget", title="TestWidget"
        )

        assert widget_id in guided_help._registered_widgets
        registered = guided_help._registered_widgets[widget_id]
        assert registered["text"] == "Test widget"
        assert registered["title"] == "TestWidget"
        # Check that widget_ref is callable (weak reference)
        assert callable(registered["widget_ref"])
        # Check that we can dereference the weak reference
        assert registered["widget_ref"]() is test_widget

    def test_register_widget_auto_name(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test widget registration with automatic naming."""
        widget_id = guided_help.register_widget(widget=test_widget, text="Test widget")

        registered = guided_help._registered_widgets[widget_id]
        assert registered["title"] == "QWidget"

    def test_create_tour_valid_ids(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test creating tour with valid widget IDs."""
        widget_id = guided_help.register_widget(widget=test_widget, text="Test widget")

        result = guided_help.create_tour([widget_id])

        assert result is True
        assert len(guided_help._tour_steps) == 1
        assert guided_help._tour_steps[0]["text"] == "Test widget"

    def test_create_tour_invalid_ids(self, guided_help: GuidedTour):
        """Test creating tour with invalid widget IDs."""
        result = guided_help.create_tour(["invalid_id"])

        assert result is False
        assert len(guided_help._tour_steps) == 0

    def test_start_tour_no_steps(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test starting tour with no steps will add all registered widgets."""
        # Register a widget
        guided_help.register_widget(widget=test_widget, text="Test widget")
        guided_help.start_tour()

        assert guided_help._active is True
        assert guided_help._current_index == 0
        assert len(guided_help._tour_steps) == 1

    def test_start_tour_success(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test successful tour start."""
        widget_id = guided_help.register_widget(widget=test_widget, text="Test widget")
        guided_help.create_tour([widget_id])

        guided_help.start_tour()

        assert guided_help._active is True
        assert guided_help._current_index == 0
        assert guided_help.overlay is not None

    def test_stop_tour(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test stopping a tour."""
        widget_id = guided_help.register_widget(widget=test_widget, text="Test widget")
        guided_help.start_tour()

        guided_help.stop_tour()

        assert guided_help._active is False

    def test_next_step(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test moving to next step."""
        widget1 = DummyWidget(test_widget)
        widget2 = DummyWidget(test_widget)
        guided_help.register_widget(widget=widget1, text="Step 1", title="Widget1")
        guided_help.register_widget(widget=widget2, text="Step 2", title="Widget2")

        guided_help.start_tour()

        assert guided_help._current_index == 0

        guided_help.next_step()

        assert guided_help._current_index == 1

    def test_next_step_finish_tour(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test next step on last step finishes tour."""
        widget_id = guided_help.register_widget(widget=test_widget, text="Test widget")
        guided_help.start_tour()

        guided_help.next_step()

        assert guided_help._active is False

    def test_prev_step(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test moving to previous step."""
        widget1 = DummyWidget(test_widget)
        widget2 = DummyWidget(test_widget)

        guided_help.register_widget(widget=widget1, text="Step 1", title="Widget1")
        guided_help.register_widget(widget=widget2, text="Step 2", title="Widget2")

        guided_help.start_tour()
        guided_help.next_step()

        assert guided_help._current_index == 1

        guided_help.prev_step()

        assert guided_help._current_index == 0

    def test_get_registered_widgets(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test getting registered widgets."""
        widget_id = guided_help.register_widget(widget=test_widget, text="Test widget")

        registered = guided_help.get_registered_widgets()

        assert widget_id in registered
        assert registered[widget_id]["text"] == "Test widget"

    def test_clear_registrations(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test clearing all registrations."""
        guided_help.register_widget(widget=test_widget, text="Test widget")

        guided_help.clear_registrations()

        assert len(guided_help._registered_widgets) == 0
        assert len(guided_help._tour_steps) == 0

    def test_weak_reference_main_window(self, main_window: QWidget):
        """Test that main window is stored as weak reference."""
        guided_help = GuidedTour(main_window)

        # Should be able to get main window through weak reference
        assert guided_help.main_window is not None
        assert guided_help.main_window == main_window

    def test_complete_tour_flow(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test complete tour workflow."""
        # Create widgets
        widget1 = DummyWidget(test_widget)
        widget2 = DummyWidget(test_widget)

        # Register widgets
        id1 = guided_help.register_widget(widget=widget1, text="First widget", title="Widget1")
        id2 = guided_help.register_widget(widget=widget2, text="Second widget", title="Widget2")

        # Create and start tour
        guided_help.start_tour()

        assert guided_help._active is True
        assert guided_help._current_index == 0

        # Move through tour
        guided_help.next_step()
        assert guided_help._current_index == 1

        # Finish tour
        guided_help.next_step()
        assert guided_help._active is False

    def test_finish_button_on_last_step(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test that the Next button changes to Finish on the last step."""
        widget1 = DummyWidget(test_widget)
        widget2 = DummyWidget(test_widget)

        guided_help.register_widget(widget=widget1, text="First widget", title="Widget1")
        guided_help.register_widget(widget=widget2, text="Second widget", title="Widget2")
        guided_help.start_tour()

        overlay = guided_help.overlay
        assert overlay is not None

        # First step should show "Next"
        assert "Next" in overlay.next_btn.text()

        # Navigate to last step
        guided_help.next_step()

        # Last step should show "Finish"
        assert "Finish" in overlay.next_btn.text()

    def test_step_counter_display(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test that step counter is properly displayed."""
        widget1 = DummyWidget(test_widget)
        widget2 = DummyWidget(test_widget)

        guided_help.register_widget(widget=widget1, text="First widget", title="Widget1")
        guided_help.register_widget(widget=widget2, text="Second widget", title="Widget2")

        guided_help.start_tour()

        overlay = guided_help.overlay
        assert overlay is not None
        assert overlay.step_label.text() == "Step 1 of 2"

    def test_register_expandable_menu_action(self, qtbot):
        """Ensure toolbar menu actions can be registered directly."""
        window = QWidget()
        layout = QVBoxLayout(window)
        toolbar = ModularToolBar(parent=window)
        layout.addWidget(toolbar)
        qtbot.addWidget(window)

        tools_action = ExpandableMenuAction(
            label="Tools ",
            actions={
                "notes": MaterialIconAction(
                    icon_name="note_add", tooltip="Add note", filled=True, parent=window
                )
            },
        )
        toolbar.components.add_safe("menu_tools", tools_action)
        bundle = toolbar.new_bundle("menu_tools")
        bundle.add_action("menu_tools")
        toolbar.show_bundles(["menu_tools"])

        guided = GuidedTour(window, enforce_visibility=False)
        guided.register_widget(widget=tools_action, text="Toolbar tools menu")
        guided.start_tour()

        assert guided._active is True

    @mock.patch("bec_widgets.utils.guided_tour.logger")
    def test_error_handling(self, mock_logger, guided_help):
        """Test error handling and logging."""
        # Test with invalid step ID
        result = guided_help.create_tour(["invalid_id"])
        assert result is False
        mock_logger.error.assert_called()

    def test_memory_safety_widget_deletion(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test memory safety when widget is deleted."""
        widget = QWidget(test_widget)

        # Register widget
        widget_id = guided_help.register_widget(widget=widget, text="Test widget")

        # Verify weak reference works
        registered = guided_help._registered_widgets[widget_id]
        assert registered["widget_ref"]() is widget

        # Delete widget
        widget.close()
        widget.setParent(None)
        del widget

        # The weak reference should now return None
        # This tests that our weak reference implementation is working
        assert widget_id in guided_help._registered_widgets
        registered = guided_help._registered_widgets[widget_id]
        assert registered["widget_ref"]() is None

    def test_unregister_widget(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test unregistering a widget."""
        widget_id = guided_help.register_widget(widget=test_widget, text="Test widget")

        # Unregister the widget
        guided_help.unregister_widget(widget_id)

        assert widget_id not in guided_help._registered_widgets

    def test_unregister_nonexistent_widget(self, guided_help: GuidedTour):
        """Test unregistering a widget that does not exist."""
        # Should not raise an error
        assert guided_help.unregister_widget("nonexistent_id") is False

    def test_unregister_widget_removes_from_tour(
        self, guided_help: GuidedTour, test_widget: QWidget
    ):
        """Test that unregistering a widget also removes it from the tour steps."""
        widget_id = guided_help.register_widget(widget=test_widget, text="Test widget")
        guided_help.create_tour([widget_id])

        # Unregister the widget
        guided_help.unregister_widget(widget_id)

        # The tour steps should no longer contain the unregistered widget
        assert len(guided_help._tour_steps) == 0

    def test_unregister_widget_during_tour_raises(
        self, guided_help: GuidedTour, test_widget: QWidget
    ):
        """Test that unregistering a widget during an active tour raises an error."""
        widget_id = guided_help.register_widget(widget=test_widget, text="Test widget")
        guided_help.start_tour()

        with pytest.raises(RuntimeError):
            guided_help.unregister_widget(widget_id)

    def test_register_lambda_function(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test registering a lambda function as a widget."""
        widget_id = guided_help.register_widget(
            widget=lambda: (test_widget, "test text"), text="Lambda widget", title="LambdaWidget"
        )

        assert widget_id in guided_help._registered_widgets
        registered = guided_help._registered_widgets[widget_id]
        assert registered["text"] == "Lambda widget"
        assert registered["title"] == "LambdaWidget"
        # Check that widget_ref is callable (weak reference)
        assert callable(registered["widget_ref"])
        # Check that we can dereference the weak reference
        assert registered["widget_ref"]()[0] is test_widget
        assert registered["widget_ref"]()[1] == "test text"

    def test_register_widget_local_function(self, guided_help: GuidedTour, test_widget: QWidget):
        """Test registering a local function as a widget."""

        def local_widget_function():
            return test_widget, "local text"

        widget_id = guided_help.register_widget(
            widget=local_widget_function, text="Local function widget", title="LocalWidget"
        )

        assert widget_id in guided_help._registered_widgets
        registered = guided_help._registered_widgets[widget_id]
        assert registered["text"] == "Local function widget"
        assert registered["title"] == "LocalWidget"
        # Check that widget_ref is callable (weak reference)
        assert callable(registered["widget_ref"])
        # Check that we can dereference the weak reference
        assert registered["widget_ref"]()[0] is test_widget
        assert registered["widget_ref"]()[1] == "local text"

    def test_text_accepts_html_content(self, guided_help: GuidedTour, test_widget: QWidget, qtbot):
        """Test that registered text can contain HTML content."""
        html_text = (
            "<b>Bold Text</b> with <i>Italics</i> and a <a href='https://example.com'>link</a>."
        )
        widget_id = guided_help.register_widget(
            widget=test_widget, text=html_text, title="HTMLWidget"
        )

        assert widget_id in guided_help._registered_widgets
        registered = guided_help._registered_widgets[widget_id]
        assert registered["text"] == html_text

    def test_overlay_painter(self, guided_help: GuidedTour, test_widget: QWidget, qtbot):
        """
        Test that the overlay painter works without errors.
        While we cannot directly test the visual output, we can ensure
        that calling the paintEvent does not raise exceptions.
        """
        widget_id = guided_help.register_widget(
            widget=test_widget, text="Test widget for overlay", title="OverlayWidget"
        )
        widget = guided_help._registered_widgets[widget_id]["widget_ref"]()
        with mock.patch.object(widget, "isVisible", return_value=True):
            guided_help.start_tour()
            guided_help.overlay.paintEvent(None)  # Force paint event to render text
            qtbot.wait(300)  # Wait for rendering

    def test_advanced_past_invalid_tour_step(
        self, guided_help: GuidedTour, test_widget: QWidget, qtbot
    ):
        """Test that an invalid tour step is handled gracefully."""
        widget_id_valid = guided_help.register_widget(
            widget=test_widget, text="Test widget for overlay", title="OverlayWidget"
        )
        widget_id_invalid = guided_help.register_widget(
            widget=lambda: None, text="Test2", title="something"
        )
        widget_id_valid2 = guided_help.register_widget(
            widget=test_widget, text="Test3", title="something"
        )

        widget_valid = guided_help._registered_widgets[widget_id_valid]["widget_ref"]()
        widget_valid2 = guided_help._registered_widgets[widget_id_valid2]["widget_ref"]()

        with (
            mock.patch.object(widget_valid, "isVisible", return_value=True),
            mock.patch.object(widget_valid2, "isVisible", return_value=True),
        ):
            guided_help.create_tour(
                [widget_id_valid, widget_id_invalid, widget_id_valid2, "nonexistent_id"]
            )

            with qtbot.waitSignal(guided_help.tour_started, timeout=2000) as blocker:
                guided_help.start_tour()

                assert blocker.signal_triggered
                with qtbot.waitSignal(guided_help.step_changed) as step_blocker:
                    guided_help.next_step()  # Move to step 2 (invalid, should skip)
                assert step_blocker.signal_triggered
                assert step_blocker.args == [3, 3]

                with qtbot.waitSignal(guided_help.step_changed) as step_blocker:
                    guided_help.prev_step()  # Move back to step 1
                assert step_blocker.signal_triggered
                assert step_blocker.args == [1, 3]

    def test_get_highlight_rect(self, guided_help: GuidedTour, test_widget: QWidget, qtbot):
        """Test that _get_highlight_rect returns a QRect for a valid widget."""
        widget = DummyWidget(test_widget)  # Use a dummy widget that is always visible
        action = DummyAction(test_widget)
        test_rect = QRect(10, 10, 100, 50)

        with mock.patch.object(widget, "isVisible", return_value=True):
            rect = guided_help._get_highlight_rect(guided_help.main_window, widget, "Test step")

        assert isinstance(rect, QRect)

        rect = guided_help._get_highlight_rect(guided_help.main_window, test_rect, "Test step")

        assert isinstance(rect, QRect)

        # QAction should not be available, thus skipped

        with mock.patch.object(guided_help, "_advance_past_invalid_step") as mock_advance:
            rect = guided_help._get_highlight_rect(
                guided_help.main_window, action, "Test step", direction="next"
            )
            assert rect is None
            mock_advance.assert_called_once()

            mock_advance.reset_mock()
            rect = guided_help._get_highlight_rect(
                guided_help.main_window, action, "Test step", direction="prev"
            )
            assert rect is None
            mock_advance.assert_called_once()
