import subprocess
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QMessageBox)
import db, recognizer, config

STYLE = """
QPushButton{font-size:18px;padding:8px;border-radius:8px;background:#2d6cdf;color:white}
QLabel{font-size:20px}
QLineEdit{font-size:26px;padding:6px}
"""

def label(text, size=20, center=True):
    l = QLabel(text)
    l.setStyleSheet(f"font-size:{size}px")
    if center:
        l.setAlignment(Qt.AlignCenter)
    l.setWordWrap(True)
    return l

class MainWindow(QStackedWidget):
    HOME, CONFIRM, TAG, RESULT = range(4)

    def __init__(self, cam):
        super().__init__()
        self.cam = cam
        self.setStyleSheet(STYLE)
        self.mode = "entry"
        self.plate = self.raw = ""
        self.conf = 0.0
        self.edited = False
        self.visit_id = None
        for build in (self._home, self._confirm, self._tag, self._result):
            self.addWidget(build())

    # ---------- page builders ----------
    def _page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        return w, lay

    def _home(self):
        w, lay = self._page()
        lay.setContentsMargins(4, 4, 4, 4)
        self.cam.widget.setMinimumSize(312, 300)
        lay.addWidget(self.cam.widget, 1)
        self.mode_btn = QPushButton()
        self.mode_btn.clicked.connect(self.toggle_mode)
        self.refresh_mode()
        cap = QPushButton("CAPTURE")
        cap.setStyleSheet("background:#1a9e4b;font-size:26px;padding:22px")
        cap.clicked.connect(self.capture)
        pwr = QPushButton("Power")
        pwr.setStyleSheet("background:#777")
        pwr.clicked.connect(self.power_menu)
        lay.addWidget(self.mode_btn)
        lay.addWidget(cap, 1)
        lay.addWidget(pwr)
        return w

    def _confirm(self):
        w, lay = self._page()
        self.photo = QLabel()
        self.photo.setAlignment(Qt.AlignCenter)
        self.photo.setFixedHeight(200)
        self.photo.setStyleSheet("background:black")
        self.conf_info = label("", 16)
        self.plate_edit = QLineEdit()
        self.plate_edit.setAlignment(Qt.AlignCenter)
        ok = QPushButton("Confirm")
        ok.clicked.connect(self.confirm_plate)
        back = QPushButton("Retake")
        back.setStyleSheet("background:#777")
        back.clicked.connect(self.go_home)
        for x in (self.photo, self.plate_edit, self.conf_info, ok, back):
            lay.addWidget(x)
        return w

    def _tag(self):
        w, lay = self._page()
        self.uid_edit = QLineEdit()
        self.uid_edit.setPlaceholderText("DEV: type tag UID")
        self.uid_edit.setAlignment(Qt.AlignCenter)
        go = QPushButton("Tag tapped")
        go.clicked.connect(self.process_tag)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet("background:#777")
        cancel.clicked.connect(self.go_home)
        for x in (label("Tap the tag on the reader", 24), self.uid_edit, go, cancel):
            lay.addWidget(x)
        return w

    def _result(self):
        w, lay = self._page()
        self.result_page = w
        self.result_lbl = label("", 30)
        self.override_btn = QPushButton("Override (log it)")
        self.override_btn.setStyleSheet("background:#c77700")
        self.override_btn.clicked.connect(self.override)
        done = QPushButton("Done")
        done.clicked.connect(self.go_home)
        for x in (self.result_lbl, self.override_btn, done):
            lay.addWidget(x)
        return w

    # ---------- actions ----------
    def refresh_mode(self):
        if self.mode == "entry":
            self.mode_btn.setText("ENTRY")
            self.mode_btn.setStyleSheet("background:#2d6cdf")
        else:
            self.mode_btn.setText("EXIT")
            self.mode_btn.setStyleSheet("background:#8e44ad")

    def toggle_mode(self):
        self.mode = "exit" if self.mode == "entry" else "entry"
        self.refresh_mode()

    def capture(self):
        self.cam.capture(self.on_captured)

    def go_home(self):
        self.cam.resume()
        self.setCurrentIndex(self.HOME)

    def on_captured(self, image):
        self.photo.setPixmap(self.cam.to_pixmap(image, self.photo.size()))
        r = recognizer.read_plate(image)
        self.plate, self.raw, self.conf = r["plate"], r["raw"], r["confidence"]
        self.plate_edit.setText(self.plate)
        if self.conf >= config.CONF_OK:
            self.conf_info.setText(f"High confidence ({self.conf:.0%})")
        else:
            self.conf_info.setText(f"LOW confidence ({self.conf:.0%}). Check carefully.")
        self.setCurrentIndex(self.CONFIRM)

    def confirm_plate(self):
        typed = self.plate_edit.text().strip().upper().replace(" ", "")
        if not typed:
            return
        self.edited = typed != self.plate
        self.plate = typed
        self.uid_edit.clear()
        self.setCurrentIndex(self.TAG)

    def process_tag(self):
        uid = self.uid_edit.text().strip().upper()
        print("UID received:", repr(uid))
        if not uid:
            return
        self.visit_id = None
        if self.mode == "entry":
            ok, msg = db.record_entry(self.plate, uid, self.raw, self.conf, self.edited)
            self.show_result(ok, f"{self.plate}\n{msg}")
            return
        res, vid = db.check_exit(self.plate, uid)
        if res == "match":
            db.complete_exit(vid)
            self.show_result(True, f"{self.plate}\nMATCH. Exit recorded.")
        elif res == "mismatch":
            self.visit_id = vid
            self.show_result(False, "MISMATCH\nTag belongs to another vehicle", can_override=True)
        elif res == "unknown_tag":
            self.show_result(False, "Unknown tag")
        else:
            self.show_result(False, "No open visit for this tag")

    def show_result(self, ok, text, can_override=False):
        colour = "#1a9e4b" if ok else "#c0392b"
        self.result_page.setStyleSheet(f"background:{colour};color:white")
        self.result_lbl.setText(text)
        self.override_btn.setVisible(can_override)
        self.setCurrentIndex(self.RESULT)

    def override(self):
        db.complete_exit(self.visit_id, override=True)
        self.show_result(True, "Override logged.\nExit recorded.")

    def power_menu(self):
        box = QMessageBox(self)
        box.setText("Power")
        shut = box.addButton("Shutdown", QMessageBox.AcceptRole)
        reb = box.addButton("Reboot", QMessageBox.AcceptRole)
        box.addButton("Cancel", QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is shut:
            self.run_power("-h")
        elif clicked is reb:
            self.run_power("-r")

    def run_power(self, flag):
        if config.DEV:
            print("DEV mode: would run shutdown", flag, "now")
            return
        subprocess.run(["sudo", "shutdown", flag, "now"])