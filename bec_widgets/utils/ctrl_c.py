# TODO haven't found yet how to deal with QAbstractSocket in qtpy
# import signal
# import socket
# from PyQt5.QtNetwork import QAbstractSocket
#
#
# def setup(app):
#     app.signalwatchdog = SignalWatchdog()  # need to store to keep socket pair alive
#     signal.signal(signal.SIGINT, make_quit_handler(app))
#
#
# def make_quit_handler(app):
#     def handler(*args):
#         print()  # make ^C appear on its own line
#         app.quit()
#
#     return handler
#
#
# class SignalWatchdog(QAbstractSocket):
#     def __init__(self):
#         """
#         Propagates system signals from Python to QEventLoop
#         adapted from https://stackoverflow.com/a/65802260/655404
#         """
#         super().__init__(QAbstractSocket.SctpSocket, None)
#
#         self.writer, self.reader = writer, reader = socket.socketpair()
#         writer.setblocking(False)
#
#         fd_writer = writer.fileno()
#         fd_reader = reader.fileno()
#
#         signal.set_wakeup_fd(fd_writer)  # Python hook
#         self.setSocketDescriptor(fd_reader)  # Qt hook
#
#         self.readyRead.connect(
#             lambda: None
#         )  # dummy function call that lets the Python interpreter run
