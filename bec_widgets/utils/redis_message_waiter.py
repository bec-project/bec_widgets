from bec_lib.serialization import MsgpackSerialization
from bec_lib.utils import lazy_import_from
from qtpy.QtCore import QEventLoop, QSocketNotifier, QTimer

MessageObject = lazy_import_from("bec_lib.connector", ("MessageObject",))


class QtRedisMessageWaiter:
    def __init__(self, redis_connector, message_to_wait):
        self.ev_loop = QEventLoop()
        self.response = None
        self.connector = redis_connector
        self.message_to_wait = message_to_wait
        self.pubsub = redis_connector._redis_conn.pubsub()
        self.pubsub.subscribe(self.message_to_wait.endpoint)
        fd = self.pubsub.connection._sock.fileno()
        self.notifier = QSocketNotifier(fd, QSocketNotifier.Read)
        self.notifier.activated.connect(self._pubsub_readable)

    def _msg_received(self, msg_obj):
        self.response = msg_obj.value
        self.ev_loop.quit()

    def wait(self, timeout=1):
        timer = QTimer()
        timer.singleShot(timeout * 1000, self.ev_loop.quit)
        self.ev_loop.exec_()
        timer.stop()
        self.notifier.setEnabled(False)
        self.pubsub.close()
        return self.response

    def _pubsub_readable(self, fd):
        while True:
            msg = self.pubsub.get_message()
            if msg:
                if msg["type"] == "subscribe":
                    # get_message buffers, so we may already have the answer
                    # let's check...
                    continue
                else:
                    break
            else:
                return
        channel = msg["channel"].decode()
        msg = MessageObject(topic=channel, value=MsgpackSerialization.loads(msg["data"]))
        self.connector._execute_callback(self._msg_received, msg, {})
