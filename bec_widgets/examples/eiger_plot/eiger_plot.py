import csv
import json
import os
import threading
import time
from functools import partial

import h5py
import numpy as np
import pyqtgraph as pg
import zmq
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import (
    QWidget,
    QFileDialog,
)
from pyqtgraph.Qt import QtWidgets, uic

from scipy.stats import multivariate_normal


class EigerPlot(QWidget):
    update_signale = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # pg.setConfigOptions(background="w", foreground="k", antialias=True)

        current_path = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_path, "eiger_plot.ui"), self)

        self.hist_lims = None
        self.mask = None
        self.image = None

        # UI
        self.init_ui()
        self.hook_signals()

        # ZMQ Consumer
        self.start_zmq_consumer()

    def init_ui(self):
        # Create Plot and add ImageItem
        self.plot_item = pg.PlotItem()
        self.plot_item.setAspectLocked(True)
        self.imageItem = pg.ImageItem()
        self.plot_item.addItem(self.imageItem)

        # Setting up histogram
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.imageItem)
        self.hist.gradient.loadPreset("magma")
        self.update_hist()

        # Adding Items to Graphical Layout
        self.glw.addItem(self.plot_item)
        self.glw.addItem(self.hist)

    def hook_signals(self):
        # Buttons
        self.pushButton_test.clicked.connect(self.start_sim_stream)
        self.pushButton_mask.clicked.connect(self.load_mask_dialog)
        self.pushButton_delete_mask.clicked.connect(self.delete_mask)

        # SpinBoxes
        self.doubleSpinBox_hist_min.valueChanged.connect(self.update_hist)
        self.doubleSpinBox_hist_max.valueChanged.connect(self.update_hist)

        # Signal/Slots
        self.update_signale.connect(self.on_image_update)

    def update_hist(self):
        self.hist_levels = [
            self.doubleSpinBox_hist_min.value(),
            self.doubleSpinBox_hist_max.value(),
        ]
        self.hist.setLevels(min=self.hist_levels[0], max=self.hist_levels[1])
        self.hist.setHistogramRange(
            self.hist_levels[0] - 0.1 * self.hist_levels[0],
            self.hist_levels[1] + 0.1 * self.hist_levels[1],
        )

    def load_mask_dialog(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select Mask File", "", "H5 Files (*.h5);;All Files (*)", options=options
        )
        if file_name:
            self.load_mask(file_name)

    def load_mask(self, path):
        with h5py.File(path, "r") as f:
            self.mask = f["data"][...]

    def delete_mask(self):
        self.mask = None

    @pyqtSlot()
    def on_image_update(self):
        # TODO first rotate then transpose
        if self.mask is not None:
            # self.image = np.ma.masked_array(self.image, mask=self.mask) #TODO test if np works
            self.image = self.image * (1 - self.mask) + 1

        if self.comboBox_rotation.currentIndex() > 0:  # rotate
            self.image = np.rot90(self.image, k=self.comboBox_rotation.currentIndex(), axes=(0, 1))

        if self.checkBox_transpose.isChecked():  # transpose
            self.image = np.transpose(self.image)

        if self.checkBox_log.isChecked():
            self.image = np.log(self.image)

        self.imageItem.setImage(self.image, autoLevels=False)

    ###############################
    # ZMQ Consumer
    ###############################

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
                meta = json.loads(raw_meta.decode("utf-8"))
                self.image = np.frombuffer(raw_data, dtype=meta["type"]).reshape(meta["shape"])
                self.update_signale.emit()

        finally:
            receiver.disconnect(live_stream_url)
            receiver.context.term()

    ###############################
    # just simulations from here
    ###############################
    def start_sim_stream(self):
        sim_stream_thread = threading.Thread(target=self.sim_stream, daemon=True)
        sim_stream_thread.start()

    def sim_stream(self):
        for i in range(100):
            # Generate 100x100 image of random noise
            self.image = np.random.rand(100, 100) * 0.2

            # Define Gaussian parameters
            x, y = np.mgrid[0:50, 0:50]
            pos = np.dstack((x, y))

            # Center at (25, 25) longer along y-axis
            rv = multivariate_normal(mean=[25, 25], cov=[[25, 0], [0, 80]])

            # Generate Gaussian in the first quadrant
            gaussian_quadrant = rv.pdf(pos) * 40

            # Place Gaussian in the first quadrant
            self.image[0:50, 0:50] += gaussian_quadrant * 10

            self.update_signale.emit()
            time.sleep(0.1)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    plot = EigerPlot()
    plot.show()
    sys.exit(app.exec_())
