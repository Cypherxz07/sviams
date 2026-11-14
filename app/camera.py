from picamera2 import Picamera2
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QSizePolicy

class Camera:
    def __init__(self):
        self.picam2 = Picamera2()
        self.preview_cfg = self.picam2.create_preview_configuration(
            main={"size": (640, 480), "format": "RGB888"})
        self.still_cfg = self.picam2.create_still_configuration()
        self.picam2.configure(self.preview_cfg)
        self.widget = QLabel()
        self.widget.setAlignment(Qt.AlignCenter)
        self.widget.setStyleSheet("background:black")
        self.widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.timer = QTimer()
        self.timer.timeout.connect(self._update)

    def start(self):
        self.picam2.start()
        self.timer.start(80)          # about 12 fps

    def _update(self):
        arr = self.picam2.capture_array("main")
        h, w = arr.shape[:2]
        img = QImage(arr.data, w, h, 3 * w, QImage.Format_BGR888)
        pix = QPixmap.fromImage(img).scaled(
            self.widget.size(), Qt.KeepAspectRatio, Qt.FastTransformation)
        self.widget.setPixmap(pix)

    def capture(self, callback):
        self.timer.stop()
        arr = self.picam2.switch_mode_and_capture_array(self.still_cfg, "main")
        callback(arr)

    def resume(self):
        self.timer.start(80)

    def pause(self):
        self.timer.stop()

    def to_pixmap(self, arr, size):
        h, w = arr.shape[:2]
        img = QImage(arr.data, w, h, 3 * w, QImage.Format_BGR888)
        return QPixmap.fromImage(img).scaled(size, Qt.KeepAspectRatio, Qt.FastTransformation)