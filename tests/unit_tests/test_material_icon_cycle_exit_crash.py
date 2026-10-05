"""
F18: segfault in the QIcon destructor when material icons held by a widget are collected as
cyclic garbage (seen at interpreter exit after DeviceManagerWidget or BECMainApp tests).

The crash happens in a child process so that it turns into a failing test instead of killing
pytest. The child uses the real icon dictionaries of the device manager components, which are
built as dict literals (icons first, dict afterwards) - the order that makes the garbage
collector clear the icon engine before its QIcon.
"""

import os
import subprocess
import sys
import textwrap

import pytest

_SCRIPT = textwrap.dedent("""
    import faulthandler
    import gc
    import os

    faulthandler.enable(all_threads=False)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from qtpy.QtWidgets import QApplication

    app = QApplication([])

    from bec_widgets.utils.colors import get_accent_colors
    from bec_widgets.widgets.control.device_manager.components.ophyd_validation.ophyd_validation_utils import (
        get_validation_icons,
    )


    class IconOwner:
        '''Stands in for a widget that caches icons and ends up in a reference cycle.'''


    # Icons first, owner afterwards: the collector then visits every icon engine before the
    # QIcon and the dicts that hold it, as it did for the DeviceTable/OphydValidation icon caches
    # at interpreter exit.
    icons = get_validation_icons(get_accent_colors(), (18, 18))
    owner = IconOwner()
    owner._icons = icons
    owner.cycle = owner
    del owner, icons
    gc.collect()
    print("collected", flush=True)
    """)


@pytest.mark.timeout(180)
def test_material_icons_in_cyclic_garbage_do_not_crash():
    """Collecting a cycle that holds material QIcons must not segfault."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT], capture_output=True, text=True, timeout=150, env=env
    )
    assert (
        proc.returncode == 0 and "collected" in proc.stdout
    ), f"child exited with {proc.returncode}\n{proc.stdout[-2000:]}\n{proc.stderr[:4000]}"
