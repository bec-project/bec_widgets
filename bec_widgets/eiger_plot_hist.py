import threading
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import pyqtProperty, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QWidget, QCheckBox

import zmq
import json






class EigerPlot(QWidget):
    update_signale = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)

        pg.setConfigOptions(background="w", foreground="k", antialias=True)

        self.layout = QHBoxLayout()

        self.setLayout(self.layout)


        self.glw = pg.GraphicsLayoutWidget()

        # self.glw.show()
        # self.setCentralItem(self.glw)

        self.checkBox_FFT = QCheckBox("FFT")

        self.layout.addWidget(self.checkBox_FFT)

        self.layout.addWidget(self.glw)
        
        
        self.plot_item = pg.PlotItem()
        self.plot_item.setAspectLocked(True)
        self.imageItem = pg.ImageItem()
        self.plot_item.addItem(self.imageItem)

        self.glw.addItem(self.plot_item)

        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.imageItem)
        self.hist.setLevels(min=0,max=100)
        self.hist.gradient.loadPreset('magma')

        self.glw.addItem(self.hist)

        # self.plot_item.addItem(self.hist)

        # add plot and histogram to glw
        # self.glw.addItem(self.plot_item)
        # self.glw.addItem(self.hist)

        # self.imageItem.setImage([[0,1,2],[4,5,6]])
        self.update_signale.connect(self.on_image_update)
        self.start_zmq_consumer()

    def start_zmq_consumer(self):
        consumer_thread = threading.Thread(target=self.zmq_consumer, daemon=True).start()

    def zmq_consumer(self):
        try:
            print("starting consumer")
            live_stream_url = "tcp://129.129.95.38:20000"
            receiver = zmq.Context().socket(zmq.SUB)
            receiver.connect(live_stream_url)
            receiver.setsockopt_string(zmq.SUBSCRIBE, "")

            while True:

                raw_meta, raw_data = receiver.recv_multipart()
                meta = json.loads(raw_meta.decode('utf-8'))
                self.image = np.frombuffer(raw_data, dtype=meta['type']).reshape(meta['shape'])
                self.update_signale.emit()

        finally:
            receiver.disconnect(live_stream_url)
            receiver.context.term()



    @pyqtSlot()
    def on_image_update(self):
        self.imageItem.setImage(self.image)



if __name__ == "__main__":
    import sys

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    plot = EigerPlot()

    plot.show()

    sys.exit(app.exec_())
