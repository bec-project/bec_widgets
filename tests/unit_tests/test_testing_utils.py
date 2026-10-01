import sys
from unittest.mock import MagicMock

from bec_widgets.tests.testable_qtimer import TestableQTimer
from bec_widgets.widgets.services.bec_status_box.bec_status_box import BECServiceStatusMixin


def test_qtimer_uses_testable_qtimer():
    service_status = BECServiceStatusMixin(None, MagicMock())
    assert service_status._service_update_timer.__class__.__name__ != "QTimer"
    assert service_status._service_update_timer.__class__.__name__ == "TestableQTimer"
    service_status.cleanup()


def test_no_module_binds_the_unpatched_qtimer():
    """bec_widgets.tests.fixtures must patch QTimer before anything imports it by name."""
    unpatched_qtimer = TestableQTimer.__bases__[0]
    bound = [
        name
        for name, module in list(sys.modules.items())
        if name.startswith(("bec_widgets", "bec_qthemes"))
        and name != "bec_widgets.tests.testable_qtimer"
        and getattr(module, "QTimer", None) is unpatched_qtimer
    ]
    assert bound == []
