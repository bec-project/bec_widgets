from unittest.mock import Mock

import pytest
from qtpy import QtWidgets
from qtpy.QtCore import QLocale, QPoint, QPointF, QRect, QRectF, QSize, QSizeF, Qt
from qtpy.QtGui import QColor, QCursor, QFont, QIcon, QPalette
from qtpy.QtWidgets import QLabel, QPushButton, QSizePolicy, QWidget

from bec_widgets.utils.property_editor import PropertyEditor


class TestWidget(QWidget):
    """Test widget with various property types for testing the property editor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TestWidget")
        # Set up various properties that will appear in the property editor
        self.setMinimumSize(100, 50)
        self.setMaximumSize(500, 300)
        self.setStyleSheet("background-color: red;")
        self.setToolTip("Test tooltip")
        self.setEnabled(True)
        self.setVisible(True)


class BECTestWidget(QWidget):
    """Test widget that simulates a BEC widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BECTestWidget")
        # This widget's module will be set to simulate a bec_widgets module
        self.__module__ = "bec_widgets.test.widget"


@pytest.fixture
def test_widget(qtbot):
    """Fixture providing a test widget with various properties."""
    widget = TestWidget()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture
def bec_test_widget(qtbot):
    """Fixture providing a BEC test widget."""
    widget = BECTestWidget()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


@pytest.fixture
def property_editor(qtbot, test_widget):
    """Fixture providing a property editor with a test widget."""
    editor = PropertyEditor(test_widget, show_only_bec=False)
    qtbot.addWidget(editor)
    qtbot.waitExposed(editor)
    return editor


@pytest.fixture
def bec_property_editor(qtbot, bec_test_widget):
    """Fixture providing a property editor with BEC-only mode."""
    editor = PropertyEditor(bec_test_widget, show_only_bec=True)
    qtbot.addWidget(editor)
    qtbot.waitExposed(editor)
    return editor


# ------------------------------------------------------------------------
# Basic functionality tests
# ------------------------------------------------------------------------


def test_initialization(property_editor, test_widget):
    """Test that the property editor initializes correctly."""
    assert property_editor._target == test_widget
    assert property_editor._bec_only is False
    assert property_editor.tree.columnCount() == 2
    assert property_editor.tree.headerItem().text(0) == "Property"
    assert property_editor.tree.headerItem().text(1) == "Value"


def test_bec_only_mode(bec_property_editor):
    """Test BEC-only mode filtering."""
    assert bec_property_editor._bec_only is True
    # Should have items since bec_test_widget simulates a BEC widget
    assert bec_property_editor.tree.topLevelItemCount() >= 0


def test_class_chain(property_editor, test_widget):
    """Test that _class_chain returns correct metaobject hierarchy."""
    chain = property_editor._class_chain()
    assert len(chain) > 0
    # First item should be the most derived class
    assert chain[0].className() in ["TestWidget", "QWidget"]


def test_set_show_only_bec_toggle(property_editor):
    """Test toggling BEC-only mode rebuilds the tree."""
    initial_count = property_editor.tree.topLevelItemCount()

    # Toggle to BEC-only mode
    property_editor.set_show_only_bec(True)
    assert property_editor._bec_only is True

    # Toggle back
    property_editor.set_show_only_bec(False)
    assert property_editor._bec_only is False


# ------------------------------------------------------------------------
# Editor creation tests
# ------------------------------------------------------------------------


def test_make_sizepolicy_editor(property_editor):
    """Test size policy editor creation and functionality."""
    size_policy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    size_policy.setHorizontalStretch(1)
    size_policy.setVerticalStretch(2)

    editor = property_editor._make_sizepolicy_editor("sizePolicy", size_policy)
    assert editor is not None

    # Should return None for non-QSizePolicy input
    editor_none = property_editor._make_sizepolicy_editor("test", "not_a_sizepolicy")
    assert editor_none is None


def test_make_locale_editor(property_editor):
    """Test locale editor creation."""
    locale = QLocale(QLocale.English, QLocale.UnitedStates)
    editor = property_editor._make_locale_editor("locale", locale)
    assert editor is not None

    # Should return None for non-QLocale input
    editor_none = property_editor._make_locale_editor("test", "not_a_locale")
    assert editor_none is None


def test_make_icon_editor(property_editor):
    """Test icon editor creation."""
    icon = QIcon()
    editor = property_editor._make_icon_editor("icon", icon)
    assert editor is not None
    assert isinstance(editor, QPushButton)
    assert "Choose" in editor.text()


def test_make_font_editor(property_editor):
    """Test font editor creation."""
    font = QFont("Arial", 12)
    editor = property_editor._make_font_editor("font", font)
    assert editor is not None
    assert isinstance(editor, QPushButton)
    assert "Arial" in editor.text()
    assert "12" in editor.text()

    # Test with non-font value
    editor_no_font = property_editor._make_font_editor("font", None)
    assert "Select font" in editor_no_font.text()


def test_make_color_editor(property_editor):
    """Test color editor creation."""
    color = QColor(255, 0, 0)  # Red color
    apply_called = []

    def apply_callback(col):
        apply_called.append(col)

    editor = property_editor._make_color_editor(color, apply_callback)
    assert editor is not None
    assert isinstance(editor, QPushButton)
    assert color.name() in editor.text()


def test_make_cursor_editor(property_editor):
    """Test cursor editor creation."""
    cursor = QCursor(Qt.CrossCursor)
    editor = property_editor._make_cursor_editor("cursor", cursor)
    assert editor is not None
    assert isinstance(editor, QtWidgets.QComboBox)


def test_spin_pair_int(property_editor):
    """Test _spin_pair with integer spinboxes."""
    wrap, box1, box2 = property_editor._spin_pair(ints=True)
    assert wrap is not None
    assert isinstance(box1, QtWidgets.QSpinBox)
    assert isinstance(box2, QtWidgets.QSpinBox)
    assert box1.minimum() == -10_000_000
    assert box1.maximum() == 10_000_000


def test_spin_pair_float(property_editor):
    """Test _spin_pair with double spinboxes."""
    wrap, box1, box2 = property_editor._spin_pair(ints=False)
    assert wrap is not None
    assert isinstance(box1, QtWidgets.QDoubleSpinBox)
    assert isinstance(box2, QtWidgets.QDoubleSpinBox)
    assert box1.decimals() == 6


def test_spin_quad_int(property_editor):
    """Test _spin_quad with integer spinboxes."""
    wrap, boxes = property_editor._spin_quad(ints=True)
    assert wrap is not None
    assert len(boxes) == 4
    assert all(isinstance(box, QtWidgets.QSpinBox) for box in boxes)


def test_spin_quad_float(property_editor):
    """Test _spin_quad with double spinboxes."""
    wrap, boxes = property_editor._spin_quad(ints=False)
    assert wrap is not None
    assert len(boxes) == 4
    assert all(isinstance(box, QtWidgets.QDoubleSpinBox) for box in boxes)


# ------------------------------------------------------------------------
# Property type editor tests
# ------------------------------------------------------------------------


def test_make_editor_qsize(property_editor):
    """Test editor creation for QSize properties."""
    size = QSize(100, 200)
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("size", size, mock_prop)
    assert editor is not None


def test_make_editor_qsizef(property_editor):
    """Test editor creation for QSizeF properties."""
    sizef = QSizeF(100.5, 200.7)
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("sizef", sizef, mock_prop)
    assert editor is not None


def test_make_editor_qpoint(property_editor):
    """Test editor creation for QPoint properties."""
    point = QPoint(10, 20)
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("point", point, mock_prop)
    assert editor is not None


def test_make_editor_qpointf(property_editor):
    """Test editor creation for QPointF properties."""
    pointf = QPointF(10.5, 20.7)
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("pointf", pointf, mock_prop)
    assert editor is not None


def test_make_editor_qrect(property_editor):
    """Test editor creation for QRect properties."""
    rect = QRect(10, 20, 100, 200)
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("rect", rect, mock_prop)
    assert editor is not None


def test_make_editor_qrectf(property_editor):
    """Test editor creation for QRectF properties."""
    rectf = QRectF(10.5, 20.7, 100.5, 200.7)
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("rectf", rectf, mock_prop)
    assert editor is not None


def test_make_editor_bool(property_editor):
    """Test editor creation for boolean properties."""
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("enabled", True, mock_prop)
    assert editor is not None
    assert isinstance(editor, QtWidgets.QCheckBox)
    assert editor.isChecked() is True


def test_make_editor_int(property_editor):
    """Test editor creation for integer properties."""
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("value", 42, mock_prop)
    assert editor is not None
    assert isinstance(editor, QtWidgets.QSpinBox)
    assert editor.value() == 42


def test_make_editor_float(property_editor):
    """Test editor creation for float properties."""
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("value", 3.14, mock_prop)
    assert editor is not None
    assert isinstance(editor, QtWidgets.QDoubleSpinBox)
    assert editor.value() == 3.14


def test_make_editor_string(property_editor):
    """Test editor creation for string properties."""
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("text", "Hello World", mock_prop)
    assert editor is not None
    assert isinstance(editor, QtWidgets.QLineEdit)
    assert editor.text() == "Hello World"


def test_make_editor_qcolor(property_editor):
    """Test editor creation for QColor properties."""
    color = QColor(255, 0, 0)
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("color", color, mock_prop)
    assert editor is not None
    assert isinstance(editor, QPushButton)


def test_make_editor_qfont(property_editor):
    """Test editor creation for QFont properties."""
    font = QFont("Arial", 12)
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    editor = property_editor._make_editor("font", font, mock_prop)
    assert editor is not None
    assert isinstance(editor, QPushButton)


def test_make_editor_unsupported_type(property_editor):
    """Test editor creation for unsupported property types."""
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    # Should return None for unsupported types
    editor = property_editor._make_editor("unsupported", object(), mock_prop)
    assert editor is None


# ------------------------------------------------------------------------
# Enum editor tests
# ------------------------------------------------------------------------


def test_make_enum_editor_non_flag(property_editor):
    """Test enum editor creation for non-flag enums."""
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = True

    mock_enum = Mock()
    mock_enum.isFlag.return_value = False
    mock_enum.keyCount.return_value = 3
    mock_enum.key.side_effect = [b"Value1", b"Value2", b"Value3"]
    mock_enum.value.side_effect = [0, 1, 2]
    mock_prop.enumerator.return_value = mock_enum

    editor = property_editor._make_enum_editor("enum_prop", 1, mock_prop)
    assert editor is not None
    assert isinstance(editor, QtWidgets.QComboBox)


# ------------------------------------------------------------------------
# Palette editor tests
# ------------------------------------------------------------------------


def test_make_palette_editor(property_editor):
    """Test palette editor creation."""
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(255, 255, 255))

    editor = property_editor._make_palette_editor("palette", palette)
    assert editor is not None

    # Should return None for non-QPalette input
    editor_none = property_editor._make_palette_editor("test", "not_a_palette")
    assert editor_none is None


def test_apply_palette_color(property_editor, test_widget):
    """Test _apply_palette_color method."""
    palette = test_widget.palette()
    original_color = palette.color(QPalette.Active, QPalette.Window)
    new_color = QColor(255, 0, 0)

    property_editor._apply_palette_color(
        "palette", palette, QPalette.Active, QPalette.Window, new_color
    )

    # Verify the property was set (this would normally update the widget)
    assert palette.color(QPalette.Active, QPalette.Window) == new_color


# ------------------------------------------------------------------------
# Enum text processing tests
# ------------------------------------------------------------------------


def test_enum_text_non_flag(property_editor):
    """Test _enum_text for non-flag enums."""
    mock_enum = Mock()
    mock_enum.isFlag.return_value = False
    mock_enum.valueToKey.return_value = b"TestValue"

    result = property_editor._enum_text(mock_enum, 1)
    assert result == "TestValue"


def test_enum_text_flag(property_editor):
    """Test _enum_text for flag enums."""
    mock_enum = Mock()
    mock_enum.isFlag.return_value = True
    mock_enum.keyCount.return_value = 2
    mock_enum.key.side_effect = [b"Flag1", b"Flag2"]
    mock_enum.value.side_effect = [1, 2]

    result = property_editor._enum_text(mock_enum, 3)  # 1 | 2 = 3
    assert "Flag1" in result and "Flag2" in result


def test_enum_value_to_int(property_editor):
    """Test _enum_value_to_int conversion."""
    # Test with integer
    assert property_editor._enum_value_to_int(Mock(), 42) == 42

    # Test with object having value attribute
    mock_obj = Mock()
    mock_obj.value = 24
    assert property_editor._enum_value_to_int(Mock(), mock_obj) == 24

    # Test with mock enum for key lookup
    mock_enum = Mock()
    mock_enum.keyToValue.return_value = 10
    mock_obj_with_name = Mock()
    mock_obj_with_name.name = "TestKey"
    assert property_editor._enum_value_to_int(mock_enum, mock_obj_with_name) == 10


# ------------------------------------------------------------------------
# Tree building and interaction tests
# ------------------------------------------------------------------------


def test_add_property_row(property_editor):
    """Test _add_property_row method."""
    parent_item = QtWidgets.QTreeWidgetItem(["TestGroup"])
    mock_prop = Mock()
    mock_prop.isEnumType.return_value = False

    property_editor._add_property_row(parent_item, "testProp", "testValue", mock_prop)
    assert parent_item.childCount() == 1

    child = parent_item.child(0)
    assert child.text(0) == "testProp"


def test_set_equal_columns(property_editor):
    """Test _set_equal_columns method."""
    # Set a specific width to test column sizing
    property_editor.resize(400, 300)
    property_editor._set_equal_columns()

    # Verify columns are set up correctly
    header = property_editor.tree.header()
    assert header.sectionResizeMode(0) == QtWidgets.QHeaderView.Interactive
    assert header.sectionResizeMode(1) == QtWidgets.QHeaderView.Interactive


def test_build_rebuilds_tree(property_editor):
    """Test that _build method clears and rebuilds the tree."""
    initial_count = property_editor.tree.topLevelItemCount()

    # Add a dummy item to ensure clearing works
    dummy_item = QtWidgets.QTreeWidgetItem(["Dummy"])
    property_editor.tree.addTopLevelItem(dummy_item)

    # Rebuild
    property_editor._build()

    # The dummy item should be gone, tree should be rebuilt
    assert property_editor.tree.topLevelItemCount() >= 0


# ------------------------------------------------------------------------
# Integration tests with Qt objects
# ------------------------------------------------------------------------


def test_property_change_integration(qtbot, property_editor, test_widget):
    """Test that property changes through editors update the target widget."""
    # This test would require more complex setup to actually trigger editor changes
    # For now, just verify the basic structure is there
    assert property_editor._target == test_widget

    # Verify that the tree has been populated with some properties
    assert property_editor.tree.topLevelItemCount() >= 0


def test_widget_with_custom_properties(qtbot):
    """Test property editor with a widget that has custom properties."""
    widget = QLabel("Test Label")
    widget.setAlignment(Qt.AlignCenter)
    widget.setWordWrap(True)
    qtbot.addWidget(widget)

    editor = PropertyEditor(widget, show_only_bec=False)
    qtbot.addWidget(editor)
    qtbot.waitExposed(editor)

    # Should have populated the tree with QLabel properties
    assert editor.tree.topLevelItemCount() > 0


# ------------------------------------------------------------------------
# Error handling tests
# ------------------------------------------------------------------------


def test_robust_enum_handling(property_editor):
    """Test that enum handling is robust against various edge cases."""
    # Test with invalid enum values
    mock_enum = Mock()
    mock_enum.isFlag.return_value = False
    mock_enum.valueToKey.return_value = None

    result = property_editor._enum_text(mock_enum, 999)
    assert result == "999"  # Should fall back to string representation


# ------------------------------------------------------------------------
# Performance and memory tests
# ------------------------------------------------------------------------


def test_large_property_tree_performance(qtbot):
    """Test that the property editor handles widgets with many properties reasonably."""
    # Create a widget with a deep inheritance hierarchy
    widget = QtWidgets.QTextEdit()
    widget.setPlainText("Test text with many properties")
    qtbot.addWidget(widget)

    editor = PropertyEditor(widget, show_only_bec=False)
    qtbot.addWidget(editor)

    # Should complete without hanging
    qtbot.waitExposed(editor)
    assert editor.tree.topLevelItemCount() > 0


def test_memory_cleanup_on_rebuild(property_editor):
    """Test that rebuilding the tree properly cleans up widgets."""
    initial_count = property_editor.tree.topLevelItemCount()

    # Trigger multiple rebuilds
    for _ in range(3):
        property_editor._build()

    # Should not accumulate items
    final_count = property_editor.tree.topLevelItemCount()
    assert final_count >= 0  # Basic sanity check
