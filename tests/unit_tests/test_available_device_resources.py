from copy import copy

import pytest

from bec_widgets.widgets.control.device_manager.components.available_device_resources.device_resource_backend import (
    HashableDevice,
    _HashableDeviceSet,
)

TEST_DEVICE_DICT = {
    "name": "test_device",
    "deviceClass": "TestDeviceClass",
    "readoutPriority": "baseline",
    "enabled": True,
}


def _test_device_dict(**kwargs):
    new = copy(TEST_DEVICE_DICT)
    new.update(kwargs)
    return new


@pytest.mark.parametrize(
    "kwargs_1, kwargs_2, kwargs_3, kwargs_4, n",
    [
        ({}, {}, {}, {}, 1),
        ({}, {}, {}, {"deviceConfig": {"a": 1}}, 1),
        ({}, {}, {}, {"name": "test_device_2"}, 2),
        ({}, {}, {"name": "test_device_2"}, {"deviceClass": "OtherDeviceClass"}, 3),
    ],
)
def test_hashable_device_set_merges_equal(kwargs_1, kwargs_2, kwargs_3, kwargs_4, n):
    item_1 = HashableDevice(**_test_device_dict(**kwargs_1))
    item_2 = HashableDevice(**_test_device_dict(**kwargs_2))
    item_3 = HashableDevice(**_test_device_dict(**kwargs_3))
    item_4 = HashableDevice(**_test_device_dict(**kwargs_4))

    test_set = _HashableDeviceSet((item_1, item_2, item_3, item_4))
    assert len(test_set) == n


def test_hashable_device_set_or_adds_sources():
    item_1 = HashableDevice(**_test_device_dict(), source_files={"a", "b"})
    item_2 = HashableDevice(**_test_device_dict(), source_files={"c", "d"})

    set_1 = _HashableDeviceSet((item_1,))
    set_2 = _HashableDeviceSet((item_2,))

    combined = set_1 | set_2
    assert len(combined) == 1
    assert combined.pop().source_files == {"a", "b", "c", "d"}


def test_hashable_device_set_or_adds_tags():
    item_1 = HashableDevice(
        **_test_device_dict(deviceTags={"tag1"}, deviceConfig={"param": "value"}),
        source_files={"a", "b"},
    )
    item_2 = HashableDevice(
        **_test_device_dict(deviceTags={"tag2"}, deviceConfig={"param": "value"}),
        source_files={"c", "d"},
    )
    item_3 = HashableDevice(
        **_test_device_dict(deviceTags={"tag3"}, deviceConfig={"param": "other_value"}),
        source_files={"q"},
    )

    set_1 = _HashableDeviceSet((item_1,))
    set_2 = _HashableDeviceSet((item_2,))
    set_3 = _HashableDeviceSet((item_3,))

    combined = sorted(set_1 | set_2 | set_3, key=lambda hd: hd.deviceConfig["param"])
    assert len(combined) == 2
    assert combined[0].source_files == {"q"}
    assert combined[0].deviceTags == {"tag3"}
    assert combined[1].source_files == {"a", "b", "c", "d"}
    assert combined[1].deviceTags == {"tag1", "tag2"}
