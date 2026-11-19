import sys
from pathlib import Path
from functools import wraps
import os
import re
from markupsafe import escape as esc
from flask import Flask, request, redirect, render_template_string, Response

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
import db

ADMIN_USER = "admin"
ADMIN_PASS = os.environ["SVIAMS_ADMIN_PASS"]

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
    rows = ""
    for t in db.list_tags():
        if t["status"] == "issued":
            delete = "in use"
        else:
            delete = (f"<form method=post action='/tags/{esc(t['uid'])}/delete' style='display:inline' "
                      f"onsubmit=\"return confirm('Delete this tag?')\"><button>Delete</button></form>")
        rows += (f"<tr><td>{esc(t['uid'])}</td><td>{esc(t['label'] or '')}</td><td>{esc(t['status'])}</td>"
                 f"<td><form method=post action='/tags/{esc(t['uid'])}/status' style='display:inline'>"
                 f"<select name=status><option>available</option><option>lost</option></select>"
                 f"<button>Set</button></form></td><td>{delete}</td></tr>")
    body = f"""
    <h2>Tags</h2>
    <form method=post action=/tags>
      UID <input name=uid required> Label <input name=label>
      <button>Add tag</button>
    </form><br>
    <table><tr><th>UID</th><th>Label</th><th>Status</th><th>Change</th><th>Delete</th></tr>{rows}</table>
    """
    return render_template_string(PAGE, body=body)

@app.post("/tags")
@auth
def add_tag():
    uid = request.form["uid"].strip().upper()
    if not re.fullmatch(r"[0-9A-F]{8}", uid):
        return redirect("/")
    db.add_tag(uid, request.form.get("label", "").strip())
    return redirect("/")

@app.post("/tags/<uid>/delete")
@auth
def delete_tag(uid):
    db.delete_tag(uid)
    return redirect("/")

@app.post("/tags/<uid>/status")
@auth
def tag_status(uid):
    if request.form["status"] not in ("available", "lost"):
        return redirect("/")
    db.set_tag_status(uid, request.form["status"])
    return redirect("/")

@app.route("/visits")
@auth
def visits():
    q = request.args.get("q", "").strip().upper()
    day = request.args.get("date", "")
    only = request.args.get("override")
    rows = ""
    for v in db.list_visits(1000):
        if q and q not in v["plate"] and q not in v["tag_uid"]:
            continue
        if day and not v["entry_time"].startswith(day):
            continue
        if only and not v["override"]:
            continue
        flags = ("OVERRIDE " if v["override"] else "") + ("edited" if v["edited_by_guard"] else "")
        if v["exit_time"]:
            action = ""
        else:
            action = (f"<form method=post action='/visits/{v['id']}/close' style='display:inline' "
                      f"onsubmit=\"return confirm('Force exit this visit?')\"><button>Force exit</button></form>")
        rows += (f"<tr><td>{esc(v['plate'])}</td><td>{esc(v['tag_uid'])}</td>"
                 f"<td>{v['entry_time']}</td><td>{v['exit_time'] or 'INSIDE'}</td>"
                 f"<td>{flags}</td><td>{action}</td></tr>")
    body = f"""<h2>Visits</h2>
    <form>Plate/Tag <input name=q value="{esc(q)}"> Date <input type=date name=date value="{esc(day)}">
    <label><input type=checkbox name=override {'checked' if only else ''}> overrides only</label>
    <button>Search</button></form><br>
    <table><tr><th>Plate</th><th>Tag</th><th>Entry</th><th>Exit</th><th>Flags</th><th>Action</th></tr>{rows}</table>"""
    return render_template_string(PAGE, body=body)

@app.post("/visits/<int:visit_id>/close")
@auth
def close_visit(visit_id):
    db.force_exit(visit_id)
    return redirect("/visits")

@app.route("/events")
@auth
def events():
    rows = "".join(
        f"<tr><td>{e['time']}</td><td>{esc(e['type'])}</td><td>{esc(e['plate'] or '')}</td><td>{esc(e['tag_uid'] or '')}</td></tr>"
        for e in db.list_events())
    body = f"<h2>Events</h2><table><tr><th>Time</th><th>Type</th><th>Plate</th><th>Tag</th></tr>{rows}</table>"
    return render_template_string(PAGE, body=body)

if __name__ == "__main__":
    db.purge_old()
    app.run(host="0.0.0.0", port=5000)