from qtpy.QtGui import QWindow
from qtpy.QtWidgets import QWidget, QMainWindow, QApplication, QVBoxLayout
import wmctrl
import subprocess
import os
import sys
import time

bec_window_title = f"BEC_{os.getpid()}"
terminal_cmd = ["xfce4-terminal", "--hide-borders","--hide-toolbar", "--hide-menubar", "--title", bec_window_title]
terminal_process = subprocess.Popen(terminal_cmd)

def find_bec_terminal_wid():
    t0 = time.perf_counter()
    while True:
        for win in wmctrl.Window.list():
            if win.wm_name == bec_window_title:
                return int(win.id, 16)
            if time.perf_counter() - t0 > 3:
                print("do not see terminal after 3 seconds, giving up")
                return None
            time.sleep(0.1)

wid = find_bec_terminal_wid()
if wid is None:
    sys.exit(1)

app = QApplication([])
mw = QMainWindow()
win = QWindow.fromWinId(wid)
central = QWidget(mw)
layout = QVBoxLayout(central)
mw.setCentralWidget(central)
container = QWidget.createWindowContainer(win, central)
layout.addWidget(container)

mw.show()

app.exec_()




