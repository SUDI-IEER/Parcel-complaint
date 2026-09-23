import os
import random
import sqlite3
import string
from datetime import datetime

from flask import Flask, flash, g, redirect, render_template, request, url_for

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "complaints.db")

STATUSES = ["Open", "In Review", "Refund Approved", "Resolved", "Rejected"]
ISSUE_TYPES = [
    "Never delivered",
    "Marked delivered but not received",
    "Delivered to wrong address",
    "Package empty or tampered",
    "Partially delivered",
]

app = Flask(__name__)
app.secret_key = "complaint-portal-dev-key"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            order_id TEXT NOT NULL,
            product TEXT NOT NULL,
            amount REAL,
            order_date TEXT,
            expected_date TEXT,
            issue_type TEXT NOT NULL,
            resolution TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (complaint_id) REFERENCES complaints (id)
        )
        """
    )
    db.commit()
    db.close()


def new_ticket():
    return "CMP-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


@app.route("/")
def home():
    db = get_db()
    total = db.execute("SELECT COUNT(*) c FROM complaints").fetchone()["c"]
    resolved = db.execute(
        "SELECT COUNT(*) c FROM complaints WHERE status IN ('Resolved', 'Refund Approved')"
    ).fetchone()["c"]
    return render_template("home.html", total=total, resolved=resolved)


@app.route("/complaint/new", methods=["GET", "POST"])
def new_complaint():
    if request.method == "POST":
        f = request.form
        required = ["name", "email", "order_id", "product", "issue_type", "description"]
        missing = [k for k in required if not f.get(k, "").strip()]
        if missing:
            flash("Please fill in all required fields.", "error")
            return render_template(
                "new.html", issue_types=ISSUE_TYPES, form=f
            )

        amount = None
        if f.get("amount", "").strip():
            try:
                amount = float(f["amount"])
            except ValueError:
                flash("Order amount must be a number.", "error")
                return render_template("new.html", issue_types=ISSUE_TYPES, form=f)

        db = get_db()
        ticket = new_ticket()
        while db.execute("SELECT 1 FROM complaints WHERE ticket = ?", (ticket,)).fetchone():
            ticket = new_ticket()

        ts = now()
        cur = db.execute(
            """
            INSERT INTO complaints (ticket, name, email, phone, order_id, product, amount,
                order_date, expected_date, issue_type, resolution, description, status,
                created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                ticket,
                f["name"].strip(),
                f["email"].strip(),
                f.get("phone", "").strip(),
                f["order_id"].strip(),
                f["product"].strip(),
                amount,
                f.get("order_date", ""),
                f.get("expected_date", ""),
                f["issue_type"],
                f.get("resolution", "Refund"),
                f["description"].strip(),
                "Open",
                ts,
                ts,
            ),
        )
        db.execute(
            "INSERT INTO updates (complaint_id, status, note, created_at) VALUES (?,?,?,?)",
            (cur.lastrowid, "Open", "Complaint received and queued for review.", ts),
        )
        db.commit()
        return redirect(url_for("track", ticket=ticket))

    return render_template("new.html", issue_types=ISSUE_TYPES, form={})


@app.route("/track", methods=["GET", "POST"])
def track_search():
    if request.method == "POST":
        ticket = request.form.get("ticket", "").strip().upper()
        if not ticket:
            flash("Enter a ticket number.", "error")
            return render_template("track_search.html")
        return redirect(url_for("track", ticket=ticket))
    return render_template("track_search.html")


@app.route("/track/<ticket>")
def track(ticket):
    db = get_db()
    c = db.execute("SELECT * FROM complaints WHERE ticket = ?", (ticket.upper(),)).fetchone()
    if not c:
        flash(f"No complaint found for ticket {ticket}.", "error")
        return render_template("track_search.html")
    updates = db.execute(
        "SELECT * FROM updates WHERE complaint_id = ? ORDER BY id DESC", (c["id"],)
    ).fetchall()
    return render_template("track.html", c=c, updates=updates)


@app.route("/admin")
def admin():
    db = get_db()
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    sql = "SELECT * FROM complaints WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if q:
        sql += " AND (ticket LIKE ? OR order_id LIKE ? OR email LIKE ? OR name LIKE ?)"
        params += [f"%{q}%"] * 4
    sql += " ORDER BY id DESC"
    rows = db.execute(sql, params).fetchall()
    counts = {s: 0 for s in STATUSES}
    for r in db.execute("SELECT status, COUNT(*) c FROM complaints GROUP BY status"):
        counts[r["status"]] = r["c"]
    return render_template(
        "admin.html", rows=rows, counts=counts, statuses=STATUSES, status=status, q=q
    )


@app.route("/admin/<int:cid>/update", methods=["POST"])
def admin_update(cid):
    status = request.form.get("status", "")
    note = request.form.get("note", "").strip()
    if status not in STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("admin"))
    db = get_db()
    ts = now()
    db.execute("UPDATE complaints SET status = ?, updated_at = ? WHERE id = ?", (status, ts, cid))
    db.execute(
        "INSERT INTO updates (complaint_id, status, note, created_at) VALUES (?,?,?,?)",
        (cid, status, note or f"Status changed to {status}.", ts),
    )
    db.commit()
    flash("Complaint updated.", "ok")
    return redirect(url_for("admin"))


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
