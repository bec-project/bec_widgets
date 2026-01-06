import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from bec_widgets.widgets.utility.widget_finder.widget_finder import WidgetFinderComboBox


@pytest.fixture
def finder_fixture(qtbot):
    central_widget = QWidget()
    central_widget.layout = QVBoxLayout(central_widget)

    # Create some buttons and a label under parent
    btn1 = QPushButton("Button1", central_widget)
    btn1.setObjectName("btn1")
    btn2 = QPushButton("Button2", central_widget)
    btn2.setObjectName("btn2")
    lbl1 = QLabel("Label1", central_widget)
    lbl1.setObjectName("lbl1")

    # Instantiate finder to look for QPushButton
    finder = WidgetFinderComboBox(central_widget, QPushButton)

    # Add buttons and label to the layout
    central_widget.layout.addWidget(btn1)
    central_widget.layout.addWidget(btn2)
    central_widget.layout.addWidget(lbl1)
    central_widget.layout.addWidget(finder)

    qtbot.addWidget(central_widget)
    qtbot.waitExposed(central_widget)

    yield finder, central_widget, btn1, btn2, lbl1

    finder.cleanup()
    central_widget.close()


def test_initial_list_contains_buttons_only(qtbot, finder_fixture):
    finder, parent, btn1, btn2, lbl1 = finder_fixture
    items = [finder.itemText(i) for i in range(finder.count())]
    assert "btn1" in items
    assert "btn2" in items
    assert "lbl1" not in items


def test_refresh_and_show_popup_update_list(finder_fixture, qtbot):
    finder, parent, btn1, btn2, lbl1 = finder_fixture

    # Dynamically add a third button
    btn3 = QPushButton("Button3", parent)
    btn3.setObjectName("btn3")

    # Manual refresh
    qtbot.mouseClick(finder.refresh_button, Qt.LeftButton)
    items = [finder.itemText(i) for i in range(finder.count())]
    assert "btn3" in items

    # And via showPopup
    btn4 = QPushButton("Button4", parent)
    btn4.setObjectName("btn4")
    finder.showPopup()
    items = [finder.itemText(i) for i in range(finder.count())]
    assert "btn4" in items


def test_selected_widget_and_widget_class_name_setter(finder_fixture, qtbot):
    finder, parent, btn1, btn2, lbl1 = finder_fixture

    # Select btn2
    idx = finder.findText("btn2")
    finder.setCurrentIndex(idx)
    qtbot.wait(200)  # allow refresh_list to run
    selected_widget = finder.selected_widget
    assert selected_widget == btn2

    # Now switch to QLabel via the property setter
    finder.widget_class_name = "QLabel"
    qtbot.wait(200)  # allow refresh_list to run
    items = [finder.itemText(i) for i in range(finder.count())]
    assert "lbl1" in items
    assert "btn1" not in items


def test_inspect_widget_highlights_button(qtbot, finder_fixture):
    finder, parent, btn1, btn2, lbl1 = finder_fixture

    # Select btn1 and inspect
    idx = finder.findText("btn1")
    finder.setCurrentIndex(idx)
    finder.inspect_widget()
    qtbot.wait(100)  # allow highlighter to show

    frame = finder.highlighter.frame
    assert frame is not None
    assert frame.isVisible()
    qtbot.wait(500)  # wait ≥ pulse duration
    # Highlighter should match the target widget size
    expected_size = btn1.frameGeometry().size()
    assert frame.geometry().size() == expected_size


def test_inspect_widget_highlights_label(qtbot, finder_fixture):
    finder, parent, btn1, btn2, lbl1 = finder_fixture

    # Switch to QLabel and inspect lbl1
    finder.widget_class_name = "QLabel"
    qtbot.wait(50)  # allow refresh
    idx = finder.findText("lbl1")
    finder.setCurrentIndex(idx)
    finder.inspect_widget()
    qtbot.wait(100)  # allow highlighter to show

    frame = finder.highlighter.frame
    assert frame is not None
    assert frame.isVisible()

    qtbot.wait(500)  # wait ≥ pulse duration
    # Highlighter should match the target widget size
    expected_size = lbl1.frameGeometry().size()
    assert frame.geometry().size() == expected_size
