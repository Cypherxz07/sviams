import subprocess
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (QStackedWidget, QWidget, QVBoxLayout, QPushButton,
                             QLabel, QLineEdit, QMessageBox, QSizePolicy)
import db, recognizer, config, rfid

STYLE = """
QPushButton{font-size:34px;padding:12px;border-radius:14px;background:#2d6cdf;color:white}
QLabel{font-size:30px}
QLineEdit{font-size:40px;padding:8px}
"""

def label(text, size=30):
    l = QLabel(text)
    l.setStyleSheet(f"font-size:{size}px")
    l.setAlignment(Qt.AlignCenter)
    l.setWordWrap(True)
    return l

def button(text, colour, size=34):
    b = QPushButton(text)
    b.setStyleSheet(f"background:{colour};font-size:{size}px")
    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return b

class MainWindow(QStackedWidget):
    HOME, CAMERA, CONFIRM, TAG, RESULT, REGISTER = range(6)

    def __init__(self, cam):
        super().__init__()
        self.cam = cam
        self.setStyleSheet(STYLE)
        self.mode = "entry"
        self.plate = self.raw = ""
        self.conf = 0.0
        self.edited = False
        self.visit_id = None
        for build in (self._home, self._camera, self._confirm, self._tag, self._result, self._register):
            self.addWidget(build())

    def _page(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(10)
        return w, lay

    # ---------- pages ----------
    def _home(self):
        w, lay = self._page()
        entry = button("ENTRY", "#2d6cdf", 44)
        entry.clicked.connect(lambda: self.start_mode("entry"))
        exit_ = button("EXIT", "#8e44ad", 44)
        exit_.clicked.connect(lambda: self.start_mode("exit"))
        reg = button("Register tag", "#555", 28)
        reg.clicked.connect(self.go_register)
        pwr = button("Power", "#777", 28)
        pwr.clicked.connect(self.power_menu)
        lay.addWidget(label("SVIAMS", 40), 1)
        lay.addWidget(entry, 4)
        lay.addWidget(exit_, 4)
        lay.addWidget(reg, 1)
        lay.addWidget(pwr, 1)
        return w

    def _camera(self):
        w, lay = self._page()
        self.mode_lbl = label("", 32)
        self.cam.widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        cap = button("CAPTURE", "#1a9e4b", 44)
        cap.clicked.connect(self.capture)
        back = button("Back", "#777", 28)
        back.clicked.connect(self.go_home)
        lay.addWidget(self.mode_lbl, 1)
        lay.addWidget(self.cam.widget, 8)
        lay.addWidget(cap, 3)
        lay.addWidget(back, 1)
        return w

    def _confirm(self):
        w, lay = self._page()
        self.photo = QLabel()
        self.photo.setAlignment(Qt.AlignCenter)
        self.photo.setStyleSheet("background:black")
        self.photo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.conf_info = label("", 26)
        self.plate_edit = QLineEdit()
        self.plate_edit.setAlignment(Qt.AlignCenter)
        ok = button("Confirm", "#1a9e4b")
        ok.clicked.connect(self.confirm_plate)
        retake = button("Retake", "#777", 28)
        retake.clicked.connect(self.go_camera)
        lay.addWidget(self.photo, 6)
        lay.addWidget(self.plate_edit, 1)
        lay.addWidget(self.conf_info, 1)
        lay.addWidget(ok, 2)
        lay.addWidget(retake, 1)
        return w

    def _tag(self):
        w, lay = self._page()
        self.uid_edit = QLineEdit()
        self.uid_edit.setPlaceholderText("DEV: type tag UID")
        self.uid_edit.setAlignment(Qt.AlignCenter)
        go = button("Tag tapped", "#2d6cdf")
        go.clicked.connect(self.process_tag)
        cancel = button("Cancel", "#777", 28)
        cancel.clicked.connect(self.go_home)
        lay.addWidget(label("Tap the tag on the reader", 36), 4)
        lay.addWidget(self.uid_edit, 1)
        lay.addWidget(go, 2)
        lay.addWidget(cancel, 1)
        self.tag_timer = QTimer(self)
        self.tag_timer.timeout.connect(self.poll_tag)
        return w

    def _result(self):
        w, lay = self._page()
        self.result_page = w
        self.result_lbl = label("", 40)
        self.override_btn = button("Override (log it)", "#c77700", 30)
        self.override_btn.clicked.connect(self.override)
        done = button("Done", "#2d6cdf")
        done.clicked.connect(self.go_camera)
        lay.addWidget(self.result_lbl, 5)
        lay.addWidget(self.override_btn, 2)
        lay.addWidget(done, 2)
        return w

    def _register(self):
        w, lay = self._page()
        self.reg_lbl = label("Tap a new tag on the reader", 36)
        back = button("Back", "#777", 28)
        back.clicked.connect(self.stop_register)
        lay.addWidget(self.reg_lbl, 6)
        lay.addWidget(back, 1)
        self.reg_timer = QTimer(self)
        self.reg_timer.timeout.connect(self.poll_register)
        self.reg_last = None
        return w

    # ---------- navigation ----------
    def start_mode(self, mode):
        self.mode = mode
        self.go_camera()

    def go_camera(self):
        self.tag_timer.stop()
        colour = "#2d6cdf" if self.mode == "entry" else "#8e44ad"
        self.mode_lbl.setText(self.mode.upper())
        self.mode_lbl.setStyleSheet(f"font-size:32px;color:{colour};font-weight:bold")
        self.setCurrentIndex(self.CAMERA)
        self.cam.resume()

    def go_home(self):
        self.tag_timer.stop()
        self.reg_timer.stop()
        self.cam.pause()
        self.setCurrentIndex(self.HOME)

    # ---------- actions ----------
    def capture(self):
        self.cam.capture(self.on_captured)

    def on_captured(self, image):
        self.setCurrentIndex(self.CONFIRM)
        self.photo.setPixmap(self.cam.to_pixmap(image, self.photo.size()))
        r = recognizer.read_plate(image)
        self.plate, self.raw, self.conf = r["plate"], r["raw"], r["confidence"]
        self.plate_edit.setText(self.plate)
        if self.conf >= config.CONF_OK:
            self.conf_info.setText(f"High confidence ({self.conf:.0%})")
        else:
            self.conf_info.setText(f"LOW confidence ({self.conf:.0%}). Check carefully.")

    def confirm_plate(self):
        typed = self.plate_edit.text().strip().upper().replace(" ", "")
        if not typed:
            return
        self.edited = typed != self.plate
        self.plate = typed
        self.uid_edit.clear()
        self.setCurrentIndex(self.TAG)
        self.tag_timer.start(200)

    def poll_tag(self):
        uid = rfid.read_uid()
        if uid:
            self.tag_timer.stop()
            self.handle_tag(uid)

    def process_tag(self):  # typed-UID fallback button
        uid = self.uid_edit.text().strip().upper()
        if uid:
            self.tag_timer.stop()
            self.handle_tag(uid)

    def handle_tag(self, uid):
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

    def go_register(self):
        self.cam.pause()
        self.reg_last = None
        self.reg_lbl.setText("Tap a new tag on the reader")
        self.setCurrentIndex(self.REGISTER)
        self.reg_timer.start(200)

    def stop_register(self):
        self.reg_timer.stop()
        self.go_home()

    def poll_register(self):
        uid = rfid.read_uid()
        if uid and uid != self.reg_last:
            if db.get_tag(uid):
                self.reg_lbl.setText(f"{uid}\nAlready registered")
            else:
                db.add_tag(uid, f"Tag {len(db.list_tags()) + 1}")
                self.reg_lbl.setText(f"{uid}\nRegistered. Tap another or go Back.")
        self.reg_last = uid

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
            print("DEV mode: would run power", flag)
            return
        cmd = "poweroff" if flag == "-h" else "reboot"
        r = subprocess.run(["sudo", "-n", "systemctl", cmd], capture_output=True, text=True)
        if r.returncode:
            QMessageBox.warning(self, "Power failed", r.stderr or "unknown error")