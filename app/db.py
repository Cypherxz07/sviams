import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path.home() / "sviams" / "data" / "sviams.db"
RETENTION_DAYS = 7

FUZZY = 1  # max character differences accepted at exit

def _lev(a, b):
    d = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, cb in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (ca != cb))
    return d[-1]

def now():
    return datetime.now().isoformat(timespec="seconds")

def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS tags(
            uid TEXT PRIMARY KEY,
            label TEXT,
            status TEXT NOT NULL DEFAULT 'available'
        );
        CREATE TABLE IF NOT EXISTS visits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate TEXT NOT NULL,
            tag_uid TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            plate_raw TEXT,
            confidence REAL,
            edited_by_guard INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            type TEXT NOT NULL,
            plate TEXT,
            tag_uid TEXT
        );
        """)
        cols = [r["name"] for r in c.execute("PRAGMA table_info(visits)")]
        if "override" not in cols:
            c.execute("ALTER TABLE visits ADD COLUMN override INTEGER DEFAULT 0")

def log_event(c, type_, plate=None, tag_uid=None):
    c.execute("INSERT INTO events(time,type,plate,tag_uid) VALUES(?,?,?,?)",
              (now(), type_, plate, tag_uid))

# ---- tags ----
def add_tag(uid, label=None):
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO tags(uid,label) VALUES(?,?)", (uid, label))

def get_tag(uid):
    with conn() as c:
        return c.execute("SELECT * FROM tags WHERE uid=?", (uid,)).fetchone()

def set_tag_status(uid, status):
    with conn() as c:
        c.execute("UPDATE tags SET status=? WHERE uid=? AND status!='issued'", (status, uid))

def list_tags():
    with conn() as c:
        return c.execute("SELECT * FROM tags ORDER BY label").fetchall()

def delete_tag(uid):
    with conn() as c:
        c.execute("DELETE FROM tags WHERE uid=? AND status!='issued'", (uid,))

# ---- entry ----
def record_entry(plate, uid, plate_raw=None, confidence=None, edited=False):
    """Returns (ok, message)."""
    with conn() as c:
        tag = c.execute("SELECT * FROM tags WHERE uid=?", (uid,)).fetchone()
        if tag is None:
            log_event(c, "unknown_tag", plate, uid)
            return False, "Unknown tag"
        if tag["status"] != "available":
            log_event(c, "tag_unavailable", plate, uid)
            return False, "Tag already in use or lost"
        if c.execute("SELECT 1 FROM visits WHERE plate=? AND exit_time IS NULL",
                     (plate,)).fetchone():
            log_event(c, "plate_already_inside", plate, uid)
            return False, "Vehicle already inside"
        c.execute("""INSERT INTO visits(plate,tag_uid,entry_time,plate_raw,confidence,edited_by_guard)
                     VALUES(?,?,?,?,?,?)""",
                  (plate, uid, now(), plate_raw, confidence, int(edited)))
        c.execute("UPDATE tags SET status='issued' WHERE uid=?", (uid,))
        log_event(c, "entry", plate, uid)
        return True, "Entry recorded"

# ---- exit ----
def check_exit(plate, uid):
    """Returns (result, visit_id) where result is 'match', 'mismatch',
    'unknown_tag' or 'no_open_visit'. Does not change data except logging."""
    with conn() as c:
        if c.execute("SELECT 1 FROM tags WHERE uid=?", (uid,)).fetchone() is None:
            log_event(c, "unknown_tag", plate, uid)
            return "unknown_tag", None
        v = c.execute("SELECT * FROM visits WHERE tag_uid=? AND exit_time IS NULL",
                      (uid,)).fetchone()
        if v is None:
            log_event(c, "no_open_visit", plate, uid)
            return "no_open_visit", None
        if v["plate"] == plate or _lev(v["plate"], plate) <= FUZZY:
            return "match", v["id"]
        log_event(c, "exit_mismatch", plate, uid)
        return "mismatch", v["id"]

def complete_exit(visit_id, override=False):
    with conn() as c:
        v = c.execute("SELECT * FROM visits WHERE id=?", (visit_id,)).fetchone()
        c.execute("UPDATE visits SET exit_time=?, override=? WHERE id=?",
                  (now(), int(override), visit_id))
        c.execute("UPDATE tags SET status='available' WHERE uid=? AND status='issued'",
                  (v["tag_uid"],))
        log_event(c, "exit_override" if override else "exit_ok", v["plate"], v["tag_uid"])

def force_exit(visit_id):
    with conn() as c:
        v = c.execute("SELECT * FROM visits WHERE id=? AND exit_time IS NULL",
                      (visit_id,)).fetchone()
        if v is None:
            return
        c.execute("UPDATE visits SET exit_time=?, override=1 WHERE id=?", (now(), visit_id))
        c.execute("UPDATE tags SET status='available' WHERE uid=? AND status='issued'",
                  (v["tag_uid"],))
        log_event(c, "force_exit", v["plate"], v["tag_uid"])

# ---- reading ----
def list_visits(limit=200):
    with conn() as c:
        return c.execute("SELECT * FROM visits ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

def list_events(limit=200):
    with conn() as c:
        return c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

# ---- retention ----
def purge_old():
    cutoff = (datetime.now() - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")
    with conn() as c:
        c.execute("DELETE FROM visits WHERE exit_time IS NOT NULL AND exit_time < ?", (cutoff,))
        c.execute("DELETE FROM events WHERE time < ?", (cutoff,))

if __name__ == "__main__":
    init_db()
    print("DB ready:", DB_PATH)