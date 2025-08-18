from __future__ import annotations

import operator
import os
from enum import Enum, auto
from functools import partial, reduce
from glob import glob
from pathlib import Path
from typing import Protocol

import bec_lib
from bec_lib.atlas_models import HashableDevice, HashableDeviceSet
from bec_lib.bec_yaml_loader import yaml_load
from bec_lib.logger import bec_logger
from bec_lib.plugin_helper import plugin_package_name, plugin_repo_path

logger = bec_logger.logger

_BASE_REPO_PATH = Path(os.path.dirname(bec_lib.__file__)) / "../.."


class HashModel(str, Enum):
    DEFAULT = auto()
    DEFAULT_DEVICECONFIG = auto()
    DEFAULT_EPICS = auto()


class DeviceResourceBackend(Protocol):
    @property
    def tag_groups(self) -> dict[str, set[HashableDevice]]:
        """A dictionary of all availble devices separated by tag groups. The same device may
        appear more than once (in different groups)."""
        ...

    @property
    def all_devices(self) -> set[HashableDevice]:
        """A set of all availble devices. The same device may not appear more than once."""
        ...

    @property
    def untagged_devices(self) -> set[HashableDevice]:
        """A set of all untagged devices. The same device may not appear more than once."""
        ...

    def tags(self) -> set[str]:
        """Returns a set of all the tags in all available devices."""
        ...

    def tag_group(self, tag: str) -> set[HashableDevice]:
        """Returns a set of the devices in the tag group with the given key."""
        ...


def _devices_from_file(file: str, include_source: bool = True):
    data = yaml_load(file, process_includes=False)
    return HashableDeviceSet(
        HashableDevice.model_validate(
            dev | {"name": name, "source_files": {file} if include_source else set()}
        )
        for name, dev in data.items()
    )


class _ConfigFileBackend(DeviceResourceBackend):
    def __init__(self) -> None:
        self._raw_device_set: set[
            HashableDevice
        ] = self._get_config_from_backup_files() | self._get_configs_from_plugin_files(
            Path(plugin_repo_path()) / plugin_package_name() / "device_configs/"
        )
        self._tag_groups = self._get_tag_groups()

    def _get_config_from_backup_files(self):
        dir = _BASE_REPO_PATH / "logs/device_configs/recovery_configs"
        files = glob("*.yaml", root_dir=dir)
        return reduce(
            operator.or_,
            map(partial(_devices_from_file, include_source=False), (str(dir / f) for f in files)),
        )

    def _get_configs_from_plugin_files(self, dir: Path):
        files = glob("*.yaml", root_dir=dir, recursive=True)
        return reduce(operator.or_, map(_devices_from_file, (str(dir / f) for f in files)))

    def _get_tag_groups(self) -> dict[str, set[HashableDevice]]:
        return {
            tag: set(filter(lambda dev: tag in dev.deviceTags, self._raw_device_set))
            for tag in self.tags()
        }

    @property
    def tag_groups(self):
        return self._tag_groups

    @property
    def all_devices(self):
        return self._raw_device_set

    @property
    def untagged_devices(self):
        return {d for d in self._raw_device_set if d.deviceTags == set()}

    def tags(self) -> set[str]:
        return reduce(operator.or_, (dev.deviceTags for dev in self._raw_device_set))

    def tag_group(self, tag: str) -> set[HashableDevice]:
        return self.tag_groups[tag]


def get_backend() -> DeviceResourceBackend:
    return _ConfigFileBackend()
