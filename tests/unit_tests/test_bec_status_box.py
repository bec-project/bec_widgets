import re
from unittest import mock

import pytest
from bec_lib.messages import BECStatus, ServiceMetricMessage, StatusMessage
from qtpy.QtCore import QMetaMethod

from bec_widgets.widgets.bec_status_box.bec_status_box import BECServiceInfoContainer, BECStatusBox

from .client_mocks import mocked_client


@pytest.fixture
def status_box(qtbot, mocked_client):
    with mock.patch(
        "bec_widgets.widgets.bec_status_box.bec_status_box.BECServiceStatusMixin"
    ) as mock_service_status_mixin:
        widget = BECStatusBox(client=mocked_client)
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        yield widget


def test_status_box_init(qtbot, mocked_client):
    with mock.patch(
        "bec_widgets.widgets.bec_status_box.bec_status_box.BECServiceStatusMixin"
    ) as mock_service_status_mixin:
        name = "my test"
        widget = BECStatusBox(parent=None, service_name=name, client=mocked_client)
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        assert widget.tree_widget.headerItem().DontShowIndicator.value == 1
        assert widget.tree_widget.children()[0].children()[0].config.service_name == name


def test_update_top_item(qtbot, mocked_client):
    with (
        mock.patch(
            "bec_widgets.widgets.bec_status_box.bec_status_box.BECServiceStatusMixin"
        ) as mock_service_status_mixin,
        mock.patch(
            "bec_widgets.widgets.bec_status_box.status_item.StatusItem.update_config"
        ) as mock_update,
    ):
        name = "my test"
        widget = BECStatusBox(parent=None, service_name=name, client=mocked_client)
        qtbot.addWidget(widget)
        qtbot.waitExposed(widget)
        widget.update_top_item_status(status="RUNNING")
        assert widget.bec_service_info_container[name].status == "RUNNING"
        assert mock_update.call_args == mock.call(widget.bec_service_info_container[name].dict())


def test_create_status_widget(status_box):
    name = "test_service"
    status = BECStatus.IDLE
    info = {"test": "test"}
    metrics = {"metric": "test_metric"}
    item = status_box._create_status_widget(name, status, info, metrics)
    assert item.config.service_name == name
    assert item.config.status == status.name
    assert item.config.info == info
    assert item.config.metrics == metrics


def test_bec_service_container(status_box):
    name = "test_service"
    status = BECStatus.IDLE
    info = {"test": "test"}
    metrics = {"metric": "test_metric"}
    expected_return = BECServiceInfoContainer(
        service_name=name, status=status, info=info, metrics=metrics
    )
    assert status_box.service_name in status_box.bec_service_info_container
    assert len(status_box.bec_service_info_container) == 1
    status_box._update_bec_service_container(name, status, info, metrics)
    assert len(status_box.bec_service_info_container) == 2
    assert status_box.bec_service_info_container[name] == expected_return


def test_add_tree_item(status_box):
    name = "test_service"
    status = BECStatus.IDLE
    info = {"test": "test"}
    metrics = {"metric": "test_metric"}
    assert len(status_box.tree_widget.children()[0].children()) == 1
    status_box.add_tree_item(name, status, info, metrics)
    assert len(status_box.tree_widget.children()[0].children()) == 2
    assert name in status_box.tree_items


def test_update_service_status(status_box):
    """Also checks check redundant tree items"""
    name = "test_service"
    status = BECStatus.IDLE
    info = {"test": "test"}
    metrics = {"metric": "test_metric"}
    status_box.add_tree_item(name, status, info, {})
    not_connected_name = "invalid_service"
    status_box.add_tree_item(not_connected_name, status, info, metrics)

    services_status = {name: StatusMessage(name=name, status=status, info=info)}
    services_metrics = {name: ServiceMetricMessage(name=name, metrics=metrics)}

    with mock.patch.object(status_box, "update_core_services", return_value=services_status):
        assert not_connected_name in status_box.tree_items
        status_box.update_service_status(services_status, services_metrics)
        assert status_box.tree_items[name][1].config.metrics == metrics
        assert not_connected_name not in status_box.tree_items


def test_update_core_services(qtbot, mocked_client):
    with (
        mock.patch(
            "bec_widgets.widgets.bec_status_box.bec_status_box.BECServiceStatusMixin"
        ) as mock_service_status_mixin,
        mock.patch(
            "bec_widgets.widgets.bec_status_box.bec_status_box.BECStatusBox.update_top_item_status"
        ) as mock_update,
    ):
        name = "my test"
        status_box = BECStatusBox(parent=None, service_name=name, client=mocked_client)
        qtbot.addWidget(status_box)
        qtbot.waitExposed(status_box)
        status_box.CORE_SERVICES = ["test_service"]
        name = "test_service"
        status = BECStatus.RUNNING
        info = {"test": "test"}
        metrics = {"metric": "test_metric"}
        services_status = {name: StatusMessage(name=name, status=status, info=info)}
        services_metrics = {name: ServiceMetricMessage(name=name, metrics=metrics)}

        status_box.update_core_services(services_status, services_metrics)
        assert mock_update.call_args == mock.call(status.name)

        status = BECStatus.IDLE
        services_status = {name: StatusMessage(name=name, status=status, info=info)}
        services_metrics = {name: ServiceMetricMessage(name=name, metrics=metrics)}
        status_box.update_core_services(services_status, services_metrics)
        assert mock_update.call_args == mock.call("ERROR")


def test_double_click_item(status_box):
    name = "test_service"
    status = BECStatus.IDLE
    info = {"test": "test"}
    metrics = {"MyData": "This should be shown nicely"}
    status_box.add_tree_item(name, status, info, metrics)
    item, status_item = status_box.tree_items[name]
    with mock.patch.object(status_item, "show_popup") as mock_show_popup:
        status_box.tree_widget.itemDoubleClicked.emit(item, 0)
        assert mock_show_popup.call_count == 1
