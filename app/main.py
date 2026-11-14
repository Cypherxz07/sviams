import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)
import sys
from PyQt5.QtWidgets import QApplication
import db, config
from ui import MainWindow
from camera import Camera

db.init_db()
db.purge_old()
app = QApplication(sys.argv)
cam = Camera()
w = MainWindow(cam)
cam.start()
w.showFullScreen()
sys.exit(app.exec_())