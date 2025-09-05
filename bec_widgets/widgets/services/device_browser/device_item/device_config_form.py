from __future__ import annotations

from functools import partial

from bec_lib.atlas_models import Device as DeviceConfigModel
from pydantic import BaseModel
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.colors import get_theme_name
from bec_widgets.utils.forms_from_types import styles
from bec_widgets.utils.forms_from_types.forms import PydanticModelForm, PydanticModelFormItem
from bec_widgets.utils.forms_from_types.items import (
    DEFAULT_WIDGET_TYPES,
    BoolFormItem,
    BoolToggleFormItem,
    DictFormItem,
    FormItemSpec,
)


class DeviceConfigForm(PydanticModelForm):
    RPC = False
    PLUGIN = False

    def __init__(
        self,
        parent=None,
        client=None,
        pretty_display=False,
        class_deviceconfig_item: type[BaseModel] | None = None,
        **kwargs,
    ):
        super().__init__(
            parent=parent,
            data_model=DeviceConfigModel,
            pretty_display=pretty_display,
            client=client,
            **kwargs,
        )
        self._class_deviceconfig_item: type[BaseModel] | None = class_deviceconfig_item
        self._widget_types = DEFAULT_WIDGET_TYPES.copy()
        self._widget_types["bool"] = (lambda spec: spec.item_type is bool, BoolToggleFormItem)
        self._widget_types["optional_bool"] = (
            lambda spec: spec.item_type == bool | None,
            BoolFormItem,
        )
        pred, _ = self._widget_types["dict"]
        self._widget_types["dict"] = pred, self._custom_device_config_item
        self._validity.setVisible(True)
        self._connect_to_theme_change()
        self.populate()

    def _post_init(self): ...

    def _custom_device_config_item(self, spec: FormItemSpec):
        if spec.name != "deviceConfig":
            return DictFormItem
        if self._class_deviceconfig_item is not None:
            return partial(PydanticModelFormItem, model=self._class_deviceconfig_item)
        return DictFormItem

    def set_pretty_display_theme(self, theme: str | None = None):
        if theme is None:
            theme = get_theme_name()
        self.setStyleSheet(styles.pretty_display_theme(theme))
        self._validity.setVisible(False)

    def get_form_data(self):
        """Get the entered metadata as a dict."""
        return self._md_schema.model_validate(super().get_form_data()).model_dump()

    def _connect_to_theme_change(self):
        """Connect to the theme change signal."""
        qapp = QApplication.instance()
        if hasattr(qapp, "theme_signal"):
            qapp.theme_signal.theme_updated.connect(self.set_pretty_display_theme)  # type: ignore

    def set_schema(self, schema: type[BaseModel]):
        if not issubclass(schema, DeviceConfigModel):
            raise TypeError("This class doesn't support changing the schema")
        super().set_schema(schema)

    def set_data(self, data: DeviceConfigModel):  # type: ignore # This class locks the type
        super().set_data(data)
