import pytest
from qtpy.QtCore import QUrl

from bec_widgets.widgets.editors.website.website import WebsiteWidget


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
    website_widget.wait_until_loaded()
    # in case we get https://www.google.com/sorry/index?continue=https://google.com/&q=...
    # because of rate limiting or ddos protections etc
    # e.g. https://github.com/bec-project/bec_widgets/actions/runs/15675153971/job/44172519713?pr=686
    assert website_widget.get_url().startswith("https://www.google.com/")
