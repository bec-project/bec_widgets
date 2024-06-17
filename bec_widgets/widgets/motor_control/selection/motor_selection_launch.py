import qdarktheme
from qtpy.QtWidgets import QApplication

from bec_widgets.utils.bec_dispatcher import BECDispatcher
from bec_widgets.widgets.motor_control.selection.selection import MotorControlSelection

CONFIG_DEFAULT = {
    "motor_control": {
        "motor_x": "samx",
        "motor_y": "samy",
        "step_size_x": 3,
        "step_size_y": 5,
        "precision": 4,
        "step_x_y_same": False,
        "move_with_arrows": False,
    }
}
if __name__ == "__main__":
    bec_dispatcher = BECDispatcher()
    # BECclient global variables
    client = bec_dispatcher.client
    client.start()

    app = QApplication([])
    qdarktheme.setup_theme("auto")
    motor_control = MotorControlSelection(client=client, config=CONFIG_DEFAULT)

    window = motor_control
    window.show()
    app.exec()
