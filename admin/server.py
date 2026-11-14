import sys
from pathlib import Path
from functools import wraps
from flask import Flask, request, redirect, render_template_string, Response

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
import db

ADMIN_USER = "admin"
ADMIN_PASS = "sviams123"   # change this

app = Flask(__name__)
db.init_db()

def auth(f):
    @wraps(f)
    def wrapper(*a, **kw):
        c = request.authorization
        if not c or c.username != ADMIN_USER or c.password != ADMIN_PASS:
            return Response("Login required", 401,
                            {"WWW-Authenticate": 'Basic realm="SVIAMS"'})
        return f(*a, **kw)
    return wrapper

PAGE = """
<!doctype html><title>SVIAMS Admin</title>
<style>
body{font-family:sans-serif;margin:20px;max-width:900px}
table{border-collapse:collapse;width:100%;margin-bottom:24px}
td,th{border:1px solid #ccc;padding:6px;text-align:left}
th{background:#eee} nav a{margin-right:14px}
</style>
<nav><a href="/">Tags</a><a href="/visits">Visits</a><a href="/events">Events</a></nav>
{{ body|safe }}
"""

@app.route("/")
@auth
def tags():
    rows = "".join(
        f"<tr><td>{t['uid']}</td><td>{t['label'] or ''}</td><td>{t['status']}</td>"
        f"<td><form method=post action=/tags/{t['uid']}/status style='display:inline'>"
        f"<select name=status>"
        f"<option>available</option><option>lost</option></select>"
        f"<button>Set</button></form></td></tr>"
        for t in db.list_tags())
    body = f"""
    <h2>Tags</h2>
    <form method=post action=/tags>
      UID <input name=uid required> Label <input name=label>
      <button>Add tag</button>
    </form><br>
    <table><tr><th>UID</th><th>Label</th><th>Status</th><th>Change</th></tr>{rows}</table>
    """
    return render_template_string(PAGE, body=body)

@app.post("/tags")
@auth
def add_tag():
    db.add_tag(request.form["uid"].strip().upper(), request.form.get("label", "").strip())
    return redirect("/")

@app.post("/tags/<uid>/status")
@auth
def tag_status(uid):
    db.set_tag_status(uid, request.form["status"])
    return redirect("/")

@app.route("/visits")
@auth
def visits():
    rows = "".join(
        f"<tr><td>{v['plate']}</td><td>{v['tag_uid']}</td><td>{v['entry_time']}</td>"
        f"<td>{v['exit_time'] or 'INSIDE'}</td>"
        f"<td>{'edited' if v['edited_by_guard'] else ''}</td></tr>"
        for v in db.list_visits())
    body = f"<h2>Visits</h2><table><tr><th>Plate</th><th>Tag</th><th>Entry</th><th>Exit</th><th>Note</th></tr>{rows}</table>"
    return render_template_string(PAGE, body=body)

@app.route("/events")
@auth
def events():
    rows = "".join(
        f"<tr><td>{e['time']}</td><td>{e['type']}</td><td>{e['plate'] or ''}</td><td>{e['tag_uid'] or ''}</td></tr>"
        for e in db.list_events())
    body = f"<h2>Events</h2><table><tr><th>Time</th><th>Type</th><th>Plate</th><th>Tag</th></tr>{rows}</table>"
    return render_template_string(PAGE, body=body)

if __name__ == "__main__":
    db.purge_old()
    app.run(host="0.0.0.0", port=5000)