import threading
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import pyqtProperty, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QWidget, QCheckBox

import zmq
import json
import h5py
import os




class EigerPlot(QWidget):
    update_signale = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mask_file = os.path.expanduser('~/Data10/software/radial_integration_scipts/bad_pix_map_Eiger9M.h5')

        pg.setConfigOptions(background="w", foreground="k", antialias=True)

        self.layout = QHBoxLayout()

        self.setLayout(self.layout)

        self.hist_lim = [0,20]


        self.glw = pg.GraphicsLayoutWidget()
        self.use_fft = False

        # self.glw.show()
        # self.setCentralItem(self.glw)

        self.checkBox_FFT = QCheckBox("FFT")
        self.checkBox_FFT.stateChanged.connect(self.on_fft_changed)

        self.layout.addWidget(self.checkBox_FFT)

        self.layout.addWidget(self.glw)
        
        
        self.plot_item = pg.PlotItem()
        self.plot_item.setAspectLocked(True)
        self.imageItem = pg.ImageItem()
        self.plot_item.addItem(self.imageItem)

        self.glw.addItem(self.plot_item)

        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.imageItem)
        self.hist.setLevels(min=self.hist_lim[0],max=self.hist_lim[1])
        self.hist.setHistogramRange(self.hist_lim[0] - 0.1 * self.hist_lim[0],self.hist_lim[1] + 0.1 * self.hist_lim[1])
        self.hist.disableAutoHistogramRange()

        self.hist.gradient.loadPreset('magma')

        self.glw.addItem(self.hist)

        # self.plot_item.addItem(self.hist)

        # add plot and histogram to glw
        # self.glw.addItem(self.plot_item)
        # self.glw.addItem(self.hist)

        # self.imageItem.setImage([[0,1,2],[4,5,6]])
        self.update_signale.connect(self.on_image_update)
        self.mask = None
        self._load_mask()

        self.start_zmq_consumer()

    def start_zmq_consumer(self):
        consumer_thread = threading.Thread(target=self.zmq_consumer, daemon=True).start()

    def _load_mask(self):
        with h5py.File(self.mask_file, "r") as f:
            self.mask = f["data"][...]

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
    def on_fft_changed(self):
        self.update_signale.emit()

    @pyqtSlot()
    def on_image_update(self):
        # if self.checkBox_FFT.isChecked():
        #     img = np.log10(np.abs(np.fft.fftshift(np.fft.fft2(self.image*(1-self.mask.T)))))
        # else:

        img = np.log10(self.image*(1-self.mask)+1)
        self.imageItem.setImage(img,autoLevels=False)

        # hardcoded hist level
        # self.hist.setLevels(min=self.hist_lim[0],max=self.hist_lim[1])
        # self.hist.setHistogramRange(self.hist_lim[0] - 0.1 * self.hist_lim[0],self.hist_lim[1] + 0.1 * self.hist_lim[1])

if __name__ == "__main__":
    import sys

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    plot = EigerPlot()

    plot.show()

    sys.exit(app.exec_())
