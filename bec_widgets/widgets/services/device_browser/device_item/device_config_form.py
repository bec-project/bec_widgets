from __future__ import annotations

from functools import partial

from bec_lib.atlas_models import Device as DeviceConfigModel
from pydantic import BaseModel
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.colors import get_theme_name
from bec_widgets.utils.forms_from_types import styles
from bec_widgets.utils.forms_from_types.forms import PydanticModelForm
from bec_widgets.utils.forms_from_types.items import (
    DEFAULT_WIDGET_TYPES,
    BoolFormItem,
    BoolToggleFormItem,
    widget_from_type,
)


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
        self._widget_types["bool"] = (lambda anno: anno is bool, BoolToggleFormItem)
        self._widget_types["optional_bool"] = (lambda anno: anno == bool | None, BoolFormItem)
        self._validity.setVisible(False)
        self._connect_to_theme_change()
        self.populate()

    def _post_init(self): ...

    def set_pretty_display_theme(self, theme: str | None = None):
        if theme is None:
            theme = get_theme_name()
        self.setStyleSheet(styles.pretty_display_theme(theme))

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self.set_pretty_display_theme)  # type: ignore

    def set_schema(self, schema: type[BaseModel]):
        raise TypeError("This class doesn't support changing the schema")

    def set_data(self, data: DeviceConfigModel):  # type: ignore # This class locks the type
        super().set_data(data)
