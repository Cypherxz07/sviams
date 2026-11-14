from PyQt5.QtWidgets import QApplication, QLabel
a = QApplication([])
l = QLabel('TEST')
l.setStyleSheet('background:red;color:white;font-size:60px')
l.showFullScreen()
a.exec_()
