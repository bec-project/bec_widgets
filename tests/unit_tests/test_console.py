import sys
import threading
import time

import pytest
from pygments.token import Token
from qtpy.QtCore import QEventLoop

from bec_widgets.utils.colors import apply_theme
from bec_widgets.widgets.editors.console.console import BECConsole


@pytest.fixture
def console_widget(qtbot):
    apply_theme("light")
    console = BECConsole()
    console.set_cmd(sys.executable)  # will launch Python interpreter
    console.set_prompt_tokens((Token.Prompt, ">>>"))
    qtbot.addWidget(console)
    console.show()
    qtbot.waitExposed(console)
    yield console
    console.terminate()


def test_console_widget(console_widget, qtbot, tmp_path):
    def wait_prompt(command_to_execute=None, busy=False):
        signal_waiter = QEventLoop()

        def exit_loop(idle):
            if busy and not idle:
                signal_waiter.quit()
            elif not busy and idle:
                signal_waiter.quit()

        console_widget.prompt.connect(exit_loop)
        if command_to_execute:
            if callable(command_to_execute):
                command_to_execute()
            else:
                console_widget.execute_command(command_to_execute)
        signal_waiter.exec_()

    console_widget.start()
    wait_prompt()

    # use console to write something to a tmp file
    tmp_filename = str(tmp_path / "console_test.txt")
    wait_prompt(f"f = open('{tmp_filename}', 'wt'); f.write('HELLO CONSOLE'); f.close()")
    # check the code has been executed by console, by checking the tmp file contents
    with open(tmp_filename, "rt") as f:
        assert f.read() == "HELLO CONSOLE"

    # execute a sleep
    t0 = time.perf_counter()
    wait_prompt("import time; time.sleep(1)")
    assert time.perf_counter() - t0 >= 1

    # test ctrl-c
    t0 = time.perf_counter()
    wait_prompt("time.sleep(5)", busy=True)
    wait_prompt(console_widget.send_ctrl_c)
    assert (
        time.perf_counter() - t0 < 1
    )  # in reality it will be almost immediate, but ok we can say less than 1 second compared to 5
