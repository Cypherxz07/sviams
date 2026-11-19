import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)
import sys
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication
import db, config
from ui import MainWindow
from camera import Camera

db.init_db()
db.purge_old()
app = QApplication(sys.argv)
purge_timer = QTimer()
purge_timer.timeout.connect(db.purge_old)
purge_timer.start(3600000)
cam = Camera()
w = MainWindow(cam)
cam.start()
w.showFullScreen()
sys.exit(app.exec_())