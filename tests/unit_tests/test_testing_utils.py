from unittest.mock import MagicMock

from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECServiceStatusMixin


def test_qtimer_uses_testable_qtimer():
    service_status = BECServiceStatusMixin(None, MagicMock())
    assert service_status._service_update_timer.__class__.__name__ != "QTimer"
    assert service_status._service_update_timer.__class__.__name__ == "TestableQTimer"
    service_status.cleanup()
