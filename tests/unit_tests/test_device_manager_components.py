"""Unit tests for device_manager_components module."""

from unittest import mock

import pytest
import yaml
from bec_lib.atlas_models import Device as DeviceModel
from qtpy import QtCore, QtGui, QtWidgets

from bec_widgets.widgets.control.device_manager.components.constants import HEADERS_HELP_MD
from bec_widgets.widgets.control.device_manager.components.device_table_view import (
    USER_CHECK_DATA_ROLE,
    BECTableView,
    CenterCheckBoxDelegate,
    CustomDisplayDelegate,
    DeviceFilterProxyModel,
    DeviceTableModel,
    DeviceTableView,
    DeviceValidatedDelegate,
    DictToolTipDelegate,
    WrappingTextDelegate,
)
from bec_widgets.widgets.control.device_manager.components.dm_config_view import DMConfigView
from bec_widgets.widgets.control.device_manager.components.dm_docstring_view import (
    DocstringView,
    docstring_to_markdown,
)
from bec_widgets.widgets.control.device_manager.components.dm_ophyd_test import ValidationStatus


### Constants ####
def test_constants_headers_help_md():
    """Test that HEADERS_HELP_MD is a dictionary with expected keys and markdown format."""
    assert isinstance(HEADERS_HELP_MD, dict)
    expected_keys = {
        "status",
        "name",
        "deviceClass",
        "readoutPriority",
        "deviceTags",
        "enabled",
        "readOnly",
        "onFailure",
        "softwareTrigger",
        "description",
    }
    assert set(HEADERS_HELP_MD.keys()) == expected_keys
    for _, value in HEADERS_HELP_MD.items():
        assert isinstance(value, str)
        assert value.startswith("## ")  # Each entry should start with a markdown header


### DM Docstring View ####


@pytest.fixture
def docstring_view(qtbot):
    """Fixture to create a DocstringView instance."""
    view = DocstringView()
    qtbot.addWidget(view)
    qtbot.waitExposed(view)
    yield view


class NumPyStyleClass:
    """Perform simple signal operations.

    Parameters
    ----------
    data : numpy.ndarray
        Input signal data.

    Attributes
    ----------
    data : numpy.ndarray
        The original signal data.

    Returns
    -------
    SignalProcessor
        An initialized signal processor instance.
    """


class GoogleStyleClass:
    """Analyze spectral properties of a signal.

    Args:
        frequencies (list[float]): Frequency bins.
        amplitudes (list[float]): Corresponding amplitude values.

    Returns:
        dict: A dictionary with spectral analysis results.

    Raises:
        ValueError: If input lists are of unequal length.
    """


def test_docstring_view_docstring_to_markdown():
    """Test the docstring_to_markdown function with a sample class."""
    numpy_md = docstring_to_markdown(NumPyStyleClass)
    assert "# NumPyStyleClass" in numpy_md
    assert "### Parameters" in numpy_md
    assert "### Attributes" in numpy_md
    assert "### Returns" in numpy_md
    assert "```" in numpy_md  # Check for code block formatting

    google_md = docstring_to_markdown(GoogleStyleClass)
    assert "# GoogleStyleClass" in google_md
    assert "### Args" in google_md
    assert "### Returns" in google_md
    assert "### Raises" in google_md
    assert "```" in google_md  # Check for code block formatting


def test_docstring_view_on_select_config(docstring_view):
    """Test the DocstringView on_select_config method. Called with single and multiple devices."""
    with (
        mock.patch.object(docstring_view, "set_device_class") as mock_set_device_class,
        mock.patch.object(docstring_view, "_set_text") as mock_set_text,
    ):
        # Test with single device
        docstring_view.on_select_config([{"deviceClass": "NumPyStyleClass"}])
        mock_set_device_class.assert_called_once_with("NumPyStyleClass")

        mock_set_device_class.reset_mock()
        # Test with multiple devices, should not show anything
        docstring_view.on_select_config(
            [{"deviceClass": "NumPyStyleClass"}, {"deviceClass": "GoogleStyleClass"}]
        )
        mock_set_device_class.assert_not_called()
        mock_set_text.assert_called_once_with("")


def test_docstring_view_set_device_class(docstring_view):
    """Test the DocstringView set_device_class method with valid and invalid class names."""
    with mock.patch(
        "bec_widgets.widgets.control.device_manager.components.dm_docstring_view.get_plugin_class"
    ) as mock_get_plugin_class:

        # Mock a valid class retrieval
        mock_get_plugin_class.return_value = NumPyStyleClass
        docstring_view.set_device_class("NumPyStyleClass")
        assert "NumPyStyleClass" in docstring_view.toPlainText()
        assert "Parameters" in docstring_view.toPlainText()

        # Mock an invalid class retrieval
        mock_get_plugin_class.side_effect = ImportError("Class not found")
        docstring_view.set_device_class("NonExistentClass")
        assert "Error retrieving docstring for NonExistentClass" == docstring_view.toPlainText()

        # Test if READY_TO_VIEW is False
        with mock.patch(
            "bec_widgets.widgets.control.device_manager.components.dm_docstring_view.READY_TO_VIEW",
            False,
        ):
            call_count = mock_get_plugin_class.call_count
            docstring_view.set_device_class("NumPyStyleClass")  # Should do nothing
            assert mock_get_plugin_class.call_count == call_count  # No new calls made


#### DM Config View ####


@pytest.fixture
def dm_config_view(qtbot):
    """Fixture to create a DMConfigView instance."""
    view = DMConfigView()
    qtbot.addWidget(view)
    qtbot.waitExposed(view)
    yield view


def test_dm_config_view_initialization(dm_config_view):
    """Test DMConfigView proper initialization."""
    # Check that the stacked layout is set up correctly
    assert dm_config_view.stacked_layout is not None
    assert dm_config_view.stacked_layout.count() == 2
    # Assert Monaco editor is initialized
    assert dm_config_view.monaco_editor.get_language() == "yaml"
    assert dm_config_view.monaco_editor.editor._readonly is True

    # Check overlay widget
    assert dm_config_view._overlay_widget is not None
    assert dm_config_view._overlay_widget.text() == "Select single device to show config"

    # Check that overlay is initially shown
    assert dm_config_view.stacked_layout.currentWidget() == dm_config_view._overlay_widget


def test_dm_config_view_on_select_config(dm_config_view):
    """Test DMConfigView on_select_config with empty selection."""
    # Test with empty list of configs
    dm_config_view.on_select_config([])
    assert dm_config_view.stacked_layout.currentWidget() == dm_config_view._overlay_widget

    # Test with a single config
    cfgs = [{"name": "test_device", "deviceClass": "TestClass", "enabled": True}]
    dm_config_view.on_select_config(cfgs)
    assert dm_config_view.stacked_layout.currentWidget() == dm_config_view.monaco_editor
    text = yaml.dump(cfgs[0], default_flow_style=False)
    assert text.strip("\n") == dm_config_view.monaco_editor.get_text().strip("\n")

    # Test with multiple configs
    cfgs = 2 * [{"name": "test_device", "deviceClass": "TestClass", "enabled": True}]
    dm_config_view.on_select_config(cfgs)
    assert dm_config_view.stacked_layout.currentWidget() == dm_config_view._overlay_widget
    assert dm_config_view.monaco_editor.get_text() == ""  # Should remain unchanged


### Device Table View ####
# Not sure how to nicely test the delegates.


@pytest.fixture
def mock_table_view(qtbot):
    """Create a mock table view for delegate testing."""
    table = BECTableView()
    qtbot.addWidget(table)
    qtbot.waitExposed(table)
    yield table


@pytest.fixture
def device_table_model(qtbot, mock_table_view):
    """Fixture to create a DeviceTableModel instance."""
    model = DeviceTableModel(mock_table_view)
    yield model


@pytest.fixture
def device_proxy_model(qtbot, mock_table_view, device_table_model):
    """Fixture to create a DeviceFilterProxyModel instance."""
    model = DeviceFilterProxyModel(mock_table_view)
    model.setSourceModel(device_table_model)
    mock_table_view.setModel(model)
    yield model


@pytest.fixture
def qevent_mock() -> QtCore.QEvent:
    """Create a mock QEvent for testing."""
    event = mock.MagicMock(spec=QtCore.QEvent)
    yield event


@pytest.fixture
def view_mock() -> QtWidgets.QAbstractItemView:
    """Create a mock QAbstractItemView for testing."""
    view = mock.MagicMock(spec=QtWidgets.QAbstractItemView)
    yield view


@pytest.fixture
def index_mock(device_proxy_model) -> QtCore.QModelIndex:
    """Create a mock QModelIndex for testing."""
    index = mock.MagicMock(spec=QtCore.QModelIndex)
    index.model.return_value = device_proxy_model
    yield index


@pytest.fixture
def option_mock() -> QtWidgets.QStyleOptionViewItem:
    """Create a mock QStyleOptionViewItem for testing."""
    option = mock.MagicMock(spec=QtWidgets.QStyleOptionViewItem)
    yield option


@pytest.fixture
def painter_mock() -> QtGui.QPainter:
    """Create a mock QPainter for testing."""
    painter = mock.MagicMock(spec=QtGui.QPainter)
    yield painter


def test_tooltip_delegate(
    mock_table_view, qevent_mock, view_mock, option_mock, index_mock, device_proxy_model
):
    """Test DictToolTipDelegate tooltip generation."""
    # No ToolTip event
    delegate = DictToolTipDelegate(mock_table_view)
    qevent_mock.type.return_value = QtCore.QEvent.Type.TouchCancel
    # nothing should happen
    with mock.patch.object(
        QtWidgets.QStyledItemDelegate, "helpEvent", return_value=False
    ) as super_mock:
        result = delegate.helpEvent(qevent_mock, view_mock, option_mock, index_mock)

        super_mock.assert_called_once_with(qevent_mock, view_mock, option_mock, index_mock)
        assert result is False

    # ToolTip event
    qevent_mock.type.return_value = QtCore.QEvent.Type.ToolTip
    qevent_mock.globalPos = mock.MagicMock(return_value=QtCore.QPoint(10, 20))

    source_model = device_proxy_model.sourceModel()
    with (
        mock.patch.object(
            source_model, "get_row_data", return_value={"description": "Mock description"}
        ),
        mock.patch.object(device_proxy_model, "mapToSource", return_value=index_mock),
        mock.patch.object(QtWidgets.QToolTip, "showText") as show_text_mock,
    ):
        result = delegate.helpEvent(qevent_mock, view_mock, option_mock, index_mock)
        show_text_mock.assert_called_once_with(QtCore.QPoint(10, 20), "Mock description", view_mock)
        assert result is True


def test_custom_display_delegate(qtbot, mock_table_view, painter_mock, option_mock, index_mock):
    """Test CustomDisplayDelegate initialization."""
    delegate = CustomDisplayDelegate(mock_table_view)

    # Test _test_custom_paint, with None and a value
    def _return_data():
        yield None
        yield "Test Value"

    proxy_model = index_mock.model()
    with (
        mock.patch.object(proxy_model, "data", side_effect=_return_data()),
        mock.patch.object(
            QtWidgets.QStyledItemDelegate, "paint", return_value=None
        ) as super_paint_mock,
        mock.patch.object(delegate, "_do_custom_paint", return_value=None) as custom_paint_mock,
    ):
        delegate.paint(painter_mock, option_mock, index_mock)
        super_paint_mock.assert_called_once_with(painter_mock, option_mock, index_mock)
        custom_paint_mock.assert_not_called()
        # Call again for the value case
        delegate.paint(painter_mock, option_mock, index_mock)
        super_paint_mock.assert_called_with(painter_mock, option_mock, index_mock)
        assert super_paint_mock.call_count == 2
        custom_paint_mock.assert_called_once_with(
            painter_mock, option_mock, index_mock, "Test Value"
        )


def test_center_checkbox_delegate(
    mock_table_view, qevent_mock, painter_mock, option_mock, index_mock
):
    """Test CenterCheckBoxDelegate initialization."""
    delegate = CenterCheckBoxDelegate(mock_table_view)

    option_mock.rect = QtCore.QRect(0, 0, 100, 20)
    delegate._do_custom_paint(painter_mock, option_mock, index_mock, QtCore.Qt.CheckState.Checked)
    # Check that the checkbox is centered
    pixrect = delegate._icon_checked.rect()
    pixrect.moveCenter(option_mock.rect.center())
    painter_mock.drawPixmap.assert_called_once_with(pixrect.topLeft(), delegate._icon_checked)

    model = index_mock.model()

    # Editor event with non-check state role
    qevent_mock.type.return_value = QtCore.QEvent.Type.MouseTrackingChange
    assert not delegate.editorEvent(qevent_mock, model, option_mock, index_mock)

    # Editor event with check state role but not mouse button event
    qevent_mock.type.return_value = QtCore.QEvent.Type.MouseButtonRelease
    with (
        mock.patch.object(model, "data", return_value=QtCore.Qt.CheckState.Checked),
        mock.patch.object(model, "setData") as mock_model_set,
    ):
        delegate.editorEvent(qevent_mock, model, option_mock, index_mock)
        mock_model_set.assert_called_once_with(
            index_mock, QtCore.Qt.CheckState.Unchecked, USER_CHECK_DATA_ROLE
        )


def test_device_validated_delegate(
    mock_table_view, qevent_mock, painter_mock, option_mock, index_mock
):
    """Test DeviceValidatedDelegate initialization."""
    # Invalid value
    delegate = DeviceValidatedDelegate(mock_table_view)
    delegate._do_custom_paint(painter_mock, option_mock, index_mock, "wrong_value")
    painter_mock.drawPixmap.assert_not_called()

    # Valid value
    option_mock.rect = QtCore.QRect(0, 0, 100, 20)
    delegate._do_custom_paint(painter_mock, option_mock, index_mock, ValidationStatus.VALID.value)
    icon = delegate._icons[ValidationStatus.VALID.value]
    pixrect = icon.rect()
    pixrect.moveCenter(option_mock.rect.center())
    painter_mock.drawPixmap.assert_called_once_with(pixrect.topLeft(), icon)


def test_wrapping_text_delegate_do_custom_paint(
    mock_table_view, painter_mock, option_mock, index_mock
):
    """Test WrappingTextDelegate _do_custom_paint method."""
    delegate = WrappingTextDelegate(mock_table_view)

    # First case, empty text, nothing should happen
    delegate._do_custom_paint(painter_mock, option_mock, index_mock, "")
    painter_mock.setPen.assert_not_called()
    layout_mock = mock.MagicMock()

    def _layout_comput_return(*args, **kwargs):
        return layout_mock

    layout_mock.draw.return_value = None
    with mock.patch.object(delegate, "_compute_layout", side_effect=_layout_comput_return):
        delegate._do_custom_paint(painter_mock, option_mock, index_mock, "New Docstring")
        layout_mock.draw.assert_called_with(painter_mock, option_mock.rect.topLeft())


TEST_RECT_FOR = QtCore.QRect(0, 0, 100, 20)
TEST_TEXT_WITH_4_LINES = "This is a test string to check text wrapping in the delegate."


def test_wrapping_text_delegate_compute_layout(mock_table_view, option_mock):
    """Test WrappingTextDelegate _compute_layout method."""
    delegate = WrappingTextDelegate(mock_table_view)
    layout_mock = mock.MagicMock(spec=QtGui.QTextLayout)

    # This combination should yield 4 lines
    with mock.patch.object(delegate, "_get_layout", return_value=layout_mock):
        layout_mock.createLine.return_value = mock_line = mock.MagicMock(spec=QtGui.QTextLine)
        mock_line.height.return_value = 10
        mock_line.isValid = mock.MagicMock(side_effect=[True, True, True, False])

        option_mock.rect = TEST_RECT_FOR
        option_mock.font = QtGui.QFont()
        layout: QtGui.QTextLayout = delegate._compute_layout(TEST_TEXT_WITH_4_LINES, option_mock)
        assert layout.createLine.call_count == 4  # pylint: disable=E1101
        assert mock_line.setPosition.call_count == 3
        assert mock_line.setPosition.call_args_list[-1] == mock.call(
            QtCore.QPointF(delegate.margin / 2, 20)  # 0, 10, 20 # Then false and exit
        )


def test_wrapping_text_delegate_size_hint(mock_table_view, option_mock, index_mock):
    """Test WrappingTextDelegate sizeHint method. Use the test text that should wrap to 4 lines."""
    delegate = WrappingTextDelegate(mock_table_view)
    assert delegate.margin == 6
    with (
        mock.patch.object(mock_table_view, "initViewItemOption"),
        mock.patch.object(mock_table_view, "isColumnHidden", side_effect=[False, False]),
        mock.patch.object(mock_table_view, "isVisible", side_effect=[True, True]),
    ):
        # Test with empty text, should return height + 2*margin
        index_mock.data.return_value = ""
        option_mock.rect = TEST_RECT_FOR
        font_metrics = option_mock.fontMetrics = QtGui.QFontMetrics(QtGui.QFont())
        size = delegate.sizeHint(option_mock, index_mock)
        assert size == QtCore.QSize(0, font_metrics.height() + 2 * delegate.margin)

        # Now test with the text that should wrap to 4 lines
        index_mock.data.return_value = TEST_TEXT_WITH_4_LINES
        size = delegate.sizeHint(option_mock, index_mock)
        # The estimate goes to 5 lines + 2* margin
        expected_lines = 5
        assert size == QtCore.QSize(
            100, font_metrics.height() * expected_lines + 2 * delegate.margin
        )


def test_wrapping_text_delegate_update_row_heights(mock_table_view, device_proxy_model):
    """Test WrappingTextDelegate update_row_heights method."""
    device_cfg = DeviceModel(
        name="test_device", deviceClass="TestClass", enabled=True, readoutPriority="baseline"
    ).model_dump()
    # Add single device to config
    delegate = WrappingTextDelegate(mock_table_view)
    row_heights = [25, 40]

    with mock.patch.object(
        delegate,
        "sizeHint",
        side_effect=[QtCore.QSize(100, row_heights[0]), QtCore.QSize(100, row_heights[1])],
    ):
        mock_table_view.setItemDelegateForColumn(5, delegate)
        mock_table_view.setItemDelegateForColumn(6, delegate)
        device_proxy_model.sourceModel().set_device_config([device_cfg])
        assert delegate._wrapping_text_columns is None
        assert mock_table_view.rowHeight(0) == 30  # Default height
        delegate._update_row_heights()
        assert delegate._wrapping_text_columns == [5, 6]
        assert mock_table_view.rowHeight(0) == max(row_heights)


def test_device_validation_delegate(
    mock_table_view, qevent_mock, painter_mock, option_mock, index_mock
):
    """Test DeviceValidatedDelegate initialization."""
    delegate = DeviceValidatedDelegate(mock_table_view)

    option_mock.rect = QtCore.QRect(0, 0, 100, 20)
    delegate._do_custom_paint(painter_mock, option_mock, index_mock, ValidationStatus.VALID)
    # Check that the checkbox is centered

    pixrect = delegate._icons[ValidationStatus.VALID.value].rect()
    pixrect.moveCenter(option_mock.rect.center())
    painter_mock.drawPixmap.assert_called_once_with(
        pixrect.topLeft(), delegate._icons[ValidationStatus.VALID.value]
    )

    # Should not be called if invalid value
    delegate._do_custom_paint(painter_mock, option_mock, index_mock, 10)

    # Check that the checkbox is centered
    assert painter_mock.drawPixmap.call_count == 1


###
# Test DeviceTableModel & DeviceFilterProxyModel
###


def test_device_table_model_data(device_proxy_model):
    """Test the device table model data retrieval."""
    source_model = device_proxy_model.sourceModel()
    test_device = {
        "status": ValidationStatus.PENDING,
        "name": "test_device",
        "deviceClass": "TestClass",
        "readoutPriority": "baseline",
        "onFailure": "retry",
        "enabled": True,
        "readOnly": False,
        "softwareTrigger": True,
        "deviceTags": ["tag1", "tag2"],
        "description": "Test device",
    }
    source_model.add_device_configs([test_device])
    assert source_model.rowCount() == 1
    assert source_model.columnCount() == 10

    # Check data retrieval for each column
    expected_data = {
        0: ValidationStatus.PENDING,  # Default status
        1: "test_device",  # name
        2: "TestClass",  # deviceClass
        3: "baseline",  # readoutPriority
        4: "retry",  # onFailure
        5: "tag1, tag2",  # deviceTags
        6: "Test device",  # description
        7: True,  # enabled
        8: False,  # readOnly
        9: True,  # softwareTrigger
    }

    for col, expected in expected_data.items():
        index = source_model.index(0, col)
        data = source_model.data(index, QtCore.Qt.DisplayRole)
        assert data == expected


def test_device_table_model_with_data(device_table_model, device_proxy_model):
    """Test (A): DeviceTableModel and DeviceFilterProxyModel with 3 rows of data."""
    # Create 3 test devices - names NOT alphabetically sorted
    test_devices = [
        {
            "name": "zebra_device",
            "deviceClass": "TestClass1",
            "enabled": True,
            "readOnly": False,
            "readoutPriority": "baseline",
            "deviceTags": ["tag1", "tag2"],
            "description": "Test device Z",
        },
        {
            "name": "alpha_device",
            "deviceClass": "TestClass2",
            "enabled": False,
            "readOnly": True,
            "readoutPriority": "primary",
            "deviceTags": ["tag3"],
            "description": "Test device A",
        },
        {
            "name": "beta_device",
            "deviceClass": "TestClass3",
            "enabled": True,
            "readOnly": False,
            "readoutPriority": "secondary",
            "deviceTags": [],
            "description": "Test device B",
        },
    ]

    # Add devices to source model
    device_table_model.add_device_configs(test_devices)

    # Check source model has 3 rows and proper columns
    assert device_table_model.rowCount() == 3
    assert device_table_model.columnCount() == 10

    # Check proxy model propagates the data
    assert device_proxy_model.rowCount() == 3
    assert device_proxy_model.columnCount() == 10

    # Verify data propagation through proxy - check names in original order
    for i, expected_device in enumerate(test_devices):
        proxy_index = device_proxy_model.index(i, 1)  # Column 1 is name
        source_index = device_proxy_model.mapToSource(proxy_index)
        source_data = device_table_model.data(source_index, QtCore.Qt.DisplayRole)
        assert source_data == expected_device["name"]

        # Check proxy data matches source
        proxy_data = device_proxy_model.data(proxy_index, QtCore.Qt.DisplayRole)
        assert proxy_data == source_data

    # Verify all columns are accessible
    headers = device_table_model.headers
    for col, header in enumerate(headers):
        header_data = device_table_model.headerData(
            col, QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole
        )
        assert header_data is not None


def test_device_table_sorting(qtbot, mock_table_view, device_table_model, device_proxy_model):
    """Test (B): Sorting functionality - original row 2 (alpha) should become row 0 after sort."""
    # Use same test data as above - zebra, alpha, beta (not alphabetically sorted)
    test_devices = [
        {
            "status": ValidationStatus.VALID,
            "name": "zebra_device",
            "deviceClass": "TestClass1",
            "enabled": True,
        },
        {
            "status": ValidationStatus.PENDING,
            "name": "alpha_device",
            "deviceClass": "TestClass2",
            "enabled": False,
        },
        {
            "status": ValidationStatus.FAILED,
            "name": "beta_device",
            "deviceClass": "TestClass3",
            "enabled": True,
        },
    ]

    device_table_model.add_device_configs(test_devices)

    # Verify initial order (unsorted)
    assert (
        device_proxy_model.data(device_proxy_model.index(0, 1), QtCore.Qt.DisplayRole)
        == "zebra_device"
    )
    assert (
        device_proxy_model.data(device_proxy_model.index(1, 1), QtCore.Qt.DisplayRole)
        == "alpha_device"
    )
    assert (
        device_proxy_model.data(device_proxy_model.index(2, 1), QtCore.Qt.DisplayRole)
        == "beta_device"
    )

    # Enable sorting and sort by name column (column 1)
    mock_table_view.setSortingEnabled(True)
    # header = mock_table_view.horizontalHeader()
    # qtbot.mouseClick(header.sectionPosition(1), QtCore.Qt.LeftButton)
    device_proxy_model.sort(1, QtCore.Qt.AscendingOrder)

    # After sorting, verify alphabetical order: alpha, beta, zebra
    assert (
        device_proxy_model.data(device_proxy_model.index(0, 1), QtCore.Qt.DisplayRole)
        == "alpha_device"
    )
    assert (
        device_proxy_model.data(device_proxy_model.index(1, 1), QtCore.Qt.DisplayRole)
        == "beta_device"
    )
    assert (
        device_proxy_model.data(device_proxy_model.index(2, 1), QtCore.Qt.DisplayRole)
        == "zebra_device"
    )


def test_bec_table_view_remove_rows(qtbot, mock_table_view, device_table_model, device_proxy_model):
    """Test (C): Remove rows from BECTableView and verify propagation."""
    # Set up test data
    test_devices = [
        {"name": "device_to_keep", "deviceClass": "KeepClass", "enabled": True},
        {"name": "device_to_remove", "deviceClass": "RemoveClass", "enabled": False},
        {"name": "another_keeper", "deviceClass": "KeepClass2", "enabled": True},
    ]

    device_table_model.add_device_configs(test_devices)
    assert device_table_model.rowCount() == 3
    assert device_proxy_model.rowCount() == 3

    # Mock the confirmation dialog to first cancel, then confirm
    with mock.patch.object(
        mock_table_view, "_remove_rows_msg_dialog", side_effect=[False, True]
    ) as mock_confirm:

        # Create mock selection for middle device (device_to_remove at row 1)
        selection_model = mock.MagicMock()
        proxy_index_to_remove = device_proxy_model.index(1, 0)  # Row 1, any column
        selection_model.selectedRows.return_value = [proxy_index_to_remove]

        mock_table_view.selectionModel = mock.MagicMock(return_value=selection_model)

        # Verify the device we're about to remove
        device_name_to_remove = device_proxy_model.data(
            device_proxy_model.index(1, 1), QtCore.Qt.DisplayRole
        )
        assert device_name_to_remove == "device_to_remove"

        # Call delete_selected method
        mock_table_view.delete_selected()

        # Verify confirmation was called
        mock_confirm.assert_called_once()

        assert device_table_model.rowCount() == 3  # No change on first call
        assert device_proxy_model.rowCount() == 3

        # Call delete_selected again, this time it should confirm
        mock_table_view.delete_selected()

        # Check that the device was removed from source model
        assert device_table_model.rowCount() == 2
        assert device_proxy_model.rowCount() == 2

        # Verify the remaining devices are correct
        remaining_names = []
        for i in range(device_proxy_model.rowCount()):
            name = device_proxy_model.data(device_proxy_model.index(i, 1), QtCore.Qt.DisplayRole)
            remaining_names.append(name)

        assert "device_to_remove" not in remaining_names


def test_device_filter_proxy_model_filtering(device_table_model, device_proxy_model):
    """Test DeviceFilterProxyModel text filtering functionality."""
    # Set up test data with different device names and classes
    test_devices = [
        {"name": "motor_x", "deviceClass": "EpicsMotor", "description": "X-axis motor"},
        {"name": "detector_main", "deviceClass": "EpicsDetector", "description": "Main detector"},
        {"name": "motor_y", "deviceClass": "EpicsMotor", "description": "Y-axis motor"},
    ]

    device_table_model.add_device_configs(test_devices)
    assert device_proxy_model.rowCount() == 3

    # Test filtering by name
    device_proxy_model.setFilterText("motor")
    assert device_proxy_model.rowCount() == 2
    # Should show 2 rows (motor_x and motor_y)
    visible_count = 0
    for i in range(device_proxy_model.rowCount()):
        if not device_proxy_model.filterAcceptsRow(i, QtCore.QModelIndex()):
            continue
        visible_count += 1

    # Test filtering by device class
    device_proxy_model.setFilterText("EpicsDetector")
    # Should show 1 row (detector_main)
    detector_visible = False
    assert device_proxy_model.rowCount() == 1
    for i in range(device_table_model.rowCount()):
        if device_proxy_model.filterAcceptsRow(i, QtCore.QModelIndex()):
            source_index = device_table_model.index(i, 1)  # Name column
            name = device_table_model.data(source_index, QtCore.Qt.DisplayRole)
            if name == "detector_main":
                detector_visible = True
                break
    assert detector_visible

    # Clear filter
    device_proxy_model.setFilterText("")
    assert device_proxy_model.rowCount() == 3
    # Should show all 3 rows again
    all_visible = all(
        device_proxy_model.filterAcceptsRow(i, QtCore.QModelIndex())
        for i in range(device_table_model.rowCount())
    )
    assert all_visible


###
# Test DeviceTableView
###


@pytest.fixture
def device_table_view(qtbot):
    """Fixture to create a DeviceTableView instance."""
    view = DeviceTableView()
    qtbot.addWidget(view)
    qtbot.waitExposed(view)
    yield view


def test_device_table_view_initialization(qtbot, device_table_view):
    """Test the DeviceTableView search method."""

    # Check that the search input fields are properly initialized and connected
    qtbot.keyClicks(device_table_view.search_input, "zebra")
    qtbot.waitUntil(lambda: device_table_view.proxy._filter_text == "zebra", timeout=2000)
    qtbot.mouseClick(device_table_view.fuzzy_is_disabled, QtCore.Qt.LeftButton)
    qtbot.waitUntil(lambda: device_table_view.proxy._enable_fuzzy is True, timeout=2000)

    # Check table setup

    # header
    header = device_table_view.table.horizontalHeader()
    assert header.sectionResizeMode(5) == QtWidgets.QHeaderView.ResizeMode.Interactive  #  tags
    assert header.sectionResizeMode(6) == QtWidgets.QHeaderView.ResizeMode.Stretch  #  description

    # table selection
    assert (
        device_table_view.table.selectionBehavior()
        == QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
    )
    assert (
        device_table_view.table.selectionMode()
        == QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
    )


def test_device_table_theme_update(device_table_view):
    """Test DeviceTableView apply_theme method."""
    # Check apply theme propagates
    with (
        mock.patch.object(device_table_view.checkbox_delegate, "apply_theme") as mock_apply,
        mock.patch.object(device_table_view.validated_delegate, "apply_theme") as mock_validated,
    ):
        device_table_view.apply_theme("dark")
        mock_apply.assert_called_once_with("dark")
        mock_validated.assert_called_once_with("dark")


def test_device_table_view_updates(device_table_view):
    """Test DeviceTableView methods that update the view and model."""
    # Test theme update triggered..

    cfgs = [
        {"status": 0, "name": "test_device", "deviceClass": "TestClass", "enabled": True},
        {"status": 1, "name": "another_device", "deviceClass": "AnotherClass", "enabled": False},
        {"status": 2, "name": "zebra_device", "deviceClass": "ZebraClass", "enabled": True},
    ]
    with mock.patch.object(device_table_view, "_request_autosize_columns") as mock_autosize:
        # Should be called once for rowsInserted
        device_table_view.set_device_config(cfgs)
        assert device_table_view.get_device_config() == cfgs
        mock_autosize.assert_called_once()
        # Update validation status, should be called again
        device_table_view.update_device_validation("test_device", ValidationStatus.VALID)
        assert mock_autosize.call_count == 2
        # Remove a device, should triggere also a _request_autosize_columns call
        device_table_view.remove_device_configs([cfgs[0]])
        assert device_table_view.get_device_config() == cfgs[1:]
        assert mock_autosize.call_count == 3
        # Remove one device manually
        device_table_view.remove_device("another_device")  # Should remove the last device
        assert device_table_view.get_device_config() == cfgs[2:]
        assert mock_autosize.call_count == 4
        # Reset the model should call it once again
        device_table_view.clear_device_configs()
        assert mock_autosize.call_count == 5
        assert device_table_view.get_device_config() == []


def test_device_table_view_get_help_md(device_table_view):
    """Test DeviceTableView get_help_md method."""
    with mock.patch.object(device_table_view.table, "indexAt") as mock_index_at:
        mock_index_at.isValid = mock.MagicMock(return_value=True)
        with mock.patch.object(device_table_view, "_model") as mock_model:
            mock_model.headerData = mock.MagicMock(side_effect=["softTrig"])
            # Second call is True, should return the corresponding help md
            assert device_table_view.get_help_md() == HEADERS_HELP_MD["softwareTrigger"]
