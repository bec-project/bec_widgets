from bec_lib.config_helper import ConfigHelper
from bec_lib.logger import bec_logger
from bec_lib.messages import ConfigAction
from qtpy.QtCore import QObject, QRunnable, Signal

from bec_widgets.utils.error_popups import SafeSlot

logger = bec_logger.logger


class _CommSignals(QObject):
    error = Signal(Exception)
    done = Signal()


class CommunicateConfigAction(QRunnable):

    def __init__(
        self,
        config_helper: ConfigHelper,
        device: str | None,
        config: dict | None,
        action: ConfigAction,
    ) -> None:
        super().__init__()
        self.config_helper = config_helper
        if action in ["add", "update"] and config is None:
            raise ValueError("Must supply config to add or update a device")
        self.device = device
        self.config = config or {}
        self.action = action
        self.signals = _CommSignals()

    @SafeSlot()
    def run(self):
        try:
            if self.action in ["add", "update", "remove"]:
                if (dev_name := self.device or self.config.get("name")) is None:
                    raise ValueError(
                        "Must be updating a device or be supplied a name for a new device"
                    )
                if "deviceConfig" not in self.config or self.action in ["add", "remove"]:
                    self.process_simple_action(dev_name)
                else:
                    # updating an existing device, but need to recreate it for this change
                    self.process_remove_readd(dev_name)
            else:
                raise ValueError(f"action {self.action} is not supported")
        except Exception as e:
            self.signals.error.emit(e)
        else:
            self.signals.done.emit()

    def process_simple_action(self, dev_name: str, action: ConfigAction | None = None):
        req_args = {
            "action": action or self.action,
            "config": {dev_name: self.config},
            "wait_for_response": False,
        }
        timeout = (
            self.config_helper.suggested_timeout_s(self.config) if self.config is not None else 20
        )
        RID = self.config_helper.send_config_request(**req_args)
        logger.info("Waiting for config reply")
        reply = self.config_helper.wait_for_config_reply(RID, timeout=timeout)
        self.config_helper.handle_update_reply(reply, RID, timeout)
        logger.info("Done updating config!")

    def process_remove_readd(self, dev_name: str):
        logger.info(f"Removing and readding device: {dev_name}")
        self.process_simple_action(dev_name, "remove")
        self.process_simple_action(dev_name, "add")
        logger.info(f"Reinstated {dev_name} successfully!")
