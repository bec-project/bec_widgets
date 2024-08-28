import pytest
from qtpy.QtCore import QUrl

from bec_widgets.widgets.website.website import WebsiteWidget

from .client_mocks import mocked_client


@pytest.fixture
def website_widget(qtbot, mocked_client):
    widget = WebsiteWidget(client=mocked_client)
    qtbot.addWidget(widget)
    qtbot.waitExposed(widget)
    yield widget


def test_website_widget_set_url(website_widget):
    website_widget.set_url("https://scilog.psi.ch")
    assert website_widget.website.url() == QUrl("https://scilog.psi.ch")

    website_widget.set_url(None)
    assert website_widget.website.url() == QUrl("https://scilog.psi.ch")

    website_widget.set_url("https://google.com")
    assert website_widget.get_url() == "https://google.com"
