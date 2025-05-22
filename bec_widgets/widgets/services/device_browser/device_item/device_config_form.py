from __future__ import annotations

from bec_lib.atlas_models import Device as DeviceConfigModel

from bec_widgets.utils.forms_from_types.forms import PydanticModelForm


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
        self._validity.setVisible(False)
