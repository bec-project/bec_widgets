"""Tests for the BECList widget."""

from unittest.mock import MagicMock

import pytest
from qtpy import QtWidgets

from bec_widgets.utils.bec_list import BECList


@pytest.fixture
def bec_list(qtbot):
    widget = BECList()
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


@pytest.fixture
def sample_widget(qtbot):
    widget = QtWidgets.QLabel("sample")
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    return widget


class TestBECList:
    def test_add_widget_item(self, bec_list, sample_widget):
        bec_list.add_widget_item("key1", sample_widget)

        assert "key1" in bec_list
        assert bec_list.count() == 1
        retrieved_widget = bec_list.get_widget("key1")
        assert retrieved_widget == sample_widget
        retrieved_item = bec_list.get_item("key1")
        assert retrieved_item is not None
        assert bec_list.itemWidget(retrieved_item) == sample_widget

    def test_add_widget_item_replaces_existing(self, bec_list, sample_widget, qtbot):
        bec_list.add_widget_item("key", sample_widget)
        replacement = QtWidgets.QLabel("replacement")
        qtbot.addWidget(replacement)
        qtbot.waitExposed(replacement)

        bec_list.add_widget_item("key", replacement)

        assert bec_list.count() == 1
        assert bec_list.get_widget("key") == replacement
        # ensure first widget no longer tracked
        assert sample_widget not in bec_list.get_widgets()

    def test_remove_widget_item(self, bec_list, sample_widget, monkeypatch):
        bec_list.add_widget_item("key", sample_widget)

        close_mock = MagicMock()
        delete_mock = MagicMock()
        monkeypatch.setattr(sample_widget, "close", close_mock)
        monkeypatch.setattr(sample_widget, "deleteLater", delete_mock)

        bec_list.remove_widget_item("key")

        assert bec_list.count() == 0
        assert "key" not in bec_list
        close_mock.assert_called_once()
        delete_mock.assert_called_once()

    def test_remove_widget_item_missing_key(self, bec_list):
        bec_list.remove_widget_item("missing")
        assert bec_list.count() == 0

    def test_clear_widgets(self, bec_list, qtbot):
        for key in ["a", "b", "c"]:
            label = QtWidgets.QLabel(key)
            qtbot.addWidget(label)
            qtbot.waitExposed(label)
            bec_list.add_widget_item(key, label)

        bec_list.clear_widgets()

        assert bec_list.count() == 0
        assert bec_list.get_widgets() == []
        assert bec_list.get_all_keys() == []

    def test_get_widget_and_item(self, bec_list, sample_widget):
        bec_list.add_widget_item("key", sample_widget)

        item = bec_list.get_item("key")
        assert item is not None
        assert bec_list.get_widget_for_item(item) == sample_widget
        assert bec_list.get_widget("key") == sample_widget

    def test_get_item_for_widget(self, bec_list, sample_widget):
        bec_list.add_widget_item("key", sample_widget)

        item = bec_list.get_item_for_widget(sample_widget)
        assert item is not None
        assert bec_list.itemWidget(item) == sample_widget

    def test_get_all_keys(self, bec_list, qtbot):
        labels = []
        for key in ["k1", "k2", "k3"]:
            label = QtWidgets.QLabel(key)
            labels.append(label)
            qtbot.addWidget(label)
            qtbot.waitExposed(label)
            bec_list.add_widget_item(key, label)

        assert sorted(bec_list.get_all_keys()) == ["k1", "k2", "k3"]
        assert set(bec_list.get_widgets()) == set(labels)

    def test_get_widget_for_item_unknown(self, bec_list, sample_widget):
        unrelated_item = QtWidgets.QListWidgetItem()
        assert bec_list.get_widget_for_item(unrelated_item) is None

        bec_list.add_widget_item("key", sample_widget)
        other_item = QtWidgets.QListWidgetItem()
        assert bec_list.get_widget_for_item(other_item) is None

    def test_get_item_for_widget_unknown(self, bec_list, qtbot):
        label = QtWidgets.QLabel("orphan")
        qtbot.addWidget(label)
        qtbot.waitExposed(label)
        assert bec_list.get_item_for_widget(label) is None

    def test_contains(self, bec_list, sample_widget):
        assert "key" not in bec_list
        bec_list.add_widget_item("key", sample_widget)
        assert "key" in bec_list
