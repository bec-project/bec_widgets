from __future__ import annotations

from bec_lib.atlas_models import Device as DeviceConfigModel
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.colors import get_theme_name
from bec_widgets.utils.forms_from_types import styles
from bec_widgets.utils.forms_from_types.forms import PydanticModelForm
from bec_widgets.utils.forms_from_types.items import DEFAULT_WIDGET_TYPES, BoolMetadataField


class DeviceConfigForm(PydanticModelForm):
    RPC = False
    PLUGIN = False

    def __init__(self, parent=None, client=None, pretty_display=False, **kwargs):
        super().__init__(
            parent=parent,
            data_model=DeviceConfigModel,
            pretty_display=pretty_display,
            client=client,
            **kwargs,
        )
        self._widget_types = DEFAULT_WIDGET_TYPES.copy()
        self._widget_types["optional_bool"] = (lambda anno: anno is bool | None, BoolMetadataField)
        self._validity.setVisible(False)
        self._connect_to_theme_change()

    def set_pretty_display_theme(self, theme: str | None = None):
        if theme is None:
            theme = get_theme_name()
        self.setStyleSheet(styles.pretty_display_theme(theme))

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self.set_pretty_display_theme)  # type: ignore
