from __future__ import annotations

import operator
from functools import reduce
from glob import glob
from pathlib import Path
from textwrap import dedent
from typing import AbstractSet, Protocol

from bec_lib.atlas_models import Device
from bec_lib.bec_yaml_loader import yaml_load
from bec_lib.plugin_helper import plugin_package_name, plugin_repo_path
from pydantic import model_validator


class HashableDevice(Device):
    source_files: set[str] = set()
    names: set[str] = set()

    @model_validator(mode="after")
    def add_name(self) -> HashableDevice:
        self.names.add(self.name)
        return self

    def as_normal_device(self):
        return Device.model_validate(self)

    def __hash__(self) -> int:
        config_values = sorted(
            (str(kv) for kv in self.deviceConfig.items()) if self.deviceConfig else []
        )
        return (reduce(operator.add, (self.name, self.deviceClass, *config_values))).__hash__()

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, self.__class__):
            return False
        if hash(self) == hash(value):
            return True
        return False

    def rich_text(self) -> str:
        return dedent(
            f"""
        <b><u><h2> {self.name}: </h2></u></b>
        <table>
        <tr><td> description: </td><td><i> {self.description}  </i></td></tr>
        <tr><td> config:      </td><td><i> {self.deviceConfig} </i></td></tr>
        <tr><td> enabled:     </td><td><i> {self.enabled}      </i></td></tr>
        <tr><td> read only:   </td><td><i> {self.readOnly}     </i></td></tr>
        </table>
        """
        )

    def add_sources(self, other: HashableDevice):
        self.source_files.update(other.source_files)

    def add_tags(self, other: HashableDevice):
        self.deviceTags.update(other.deviceTags)

    def add_names(self, other: HashableDevice):
        self.names.update(other.names)


class _HashableDeviceSet(set):
    def __or__(self, value: AbstractSet) -> _HashableDeviceSet:
        for item in self:
            if item in value:
                for other_item in value:
                    if other_item == item:
                        item.add_sources(other_item)
                        item.add_tags(other_item)
                        item.add_names(other_item)
        for other_item in value:
            if other_item not in self:
                self.add(other_item)
        return self


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

    def tags(self) -> set[str]:
        """Returns a set of all the tags in all available devices."""
        ...

    def tag_group(self, tag: str) -> set[HashableDevice]:
        """Returns a set of the devices in the tag group with the given key."""
        ...


class _ConfigFileBackend(DeviceResourceBackend):
    def __init__(self) -> None:
        self._raw_device_set: set[HashableDevice] = self._get_config_from_files(
            Path(plugin_repo_path()) / plugin_package_name() / "device_configs/"
        )
        self._tag_groups = self._get_tag_groups()

    def _get_config_from_files(self, dir: Path):
        files = glob("*.yaml", root_dir=dir, recursive=True)

        def devices_from_file(file: str):
            data = yaml_load(str(dir / file))
            return set(
                HashableDevice.model_validate(
                    dev | {"name": name, "source_files": {str(dir / file)}}
                )
                for name, dev in data.items()
            )

        return reduce(operator.or_, map(devices_from_file, files))

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

    def tags(self) -> set[str]:
        return reduce(operator.or_, (dev.deviceTags for dev in self._raw_device_set))

    def tag_group(self, tag: str) -> set[HashableDevice]:
        return self.tag_groups[tag]


def get_backend() -> DeviceResourceBackend:
    return _ConfigFileBackend()
