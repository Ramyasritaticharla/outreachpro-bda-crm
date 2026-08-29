import os
import sqlite3
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)

# Secret key
app.secret_key = os.environ.get("SECRET_KEY", "outreachpro-secret")

# SQLite database path
DB = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "outreachpro.db"
)

# Available prospect statuses
STATUSES = [
    "New",
    "Contacted",
    "Interested",
    "Meeting Scheduled",
    "Proposal",
    "Won",
    "Lost"
]

# Available activity types
ACTIVITIES = [
    "Call",
    "Email",
    "WhatsApp",
    "Meeting",
    "Demo",
    "Follow-up"
]


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

def init_db():
    conn = db()

    # Prospects table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            source TEXT,
            status TEXT NOT NULL DEFAULT 'New',
            value REAL DEFAULT 0,
            next_followup TEXT,
            notes TEXT,
            created_at TEXT NOT NULL
        )
    """)

    # Activities table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prospect_id INTEGER NOT NULL,
            activity_type TEXT NOT NULL,
            activity_date TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY(prospect_id) REFERENCES prospects(id)
        )
    """)

    # Add demo data only when database is empty
    if conn.execute("SELECT COUNT(*) FROM prospects").fetchone()[0] == 0:

        today = date.today()

        demo = [
            (
                "Ananya Rao",
                "BrightLearn",
                "ananya@brightlearn.com",
                "9876543210",
                "Website",
                "Interested",
                75000,
                str(today + timedelta(days=2)),
                "Interested in corporate training."
            ),
            (
                "Rahul Mehta",
                "NovaTech",
                "rahul@novatech.com",
                "9123456780",
                "LinkedIn",
                "Meeting Scheduled",
                120000,
                str(today + timedelta(days=1)),
                "Product demo requested."
            ),
            (
                "Sneha Iyer",
                "SkillBridge",
                "sneha@skillbridge.com",
                "9988776655",
                "Referral",
                "Contacted",
                50000,
                str(today + timedelta(days=5)),
                "Needs a follow-up call."
            )
        ]

        conn.executemany("""
            INSERT INTO prospects
            (
                name,
                company,
                email,
                phone,
                source,
                status,
                value,
                next_followup,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            (
                name,
                company,
                email,
                phone,
                source,
                status,
                value,
                next_followup,
                notes,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            for (
                name,
                company,
                email,
                phone,
                source,
                status,
                value,
                next_followup,
                notes
            ) in demo
        ])

    conn.commit()
    conn.close()


# --------------------------------------------------
# IMPORTANT:
# INITIALIZE DATABASE WHEN APP STARTS
# --------------------------------------------------

init_db()


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/")
def dashboard():

    conn = db()

    total = conn.execute(
        "SELECT COUNT(*) FROM prospects"
    ).fetchone()[0]

    won = conn.execute(
        "SELECT COUNT(*) FROM prospects WHERE status='Won'"
    ).fetchone()[0]

    interested = conn.execute("""
        SELECT COUNT(*)
        FROM prospects
        WHERE status IN (
            'Interested',
            'Meeting Scheduled',
            'Proposal'
        )
    """).fetchone()[0]

    pipeline = conn.execute("""
        SELECT COALESCE(SUM(value), 0)
        FROM prospects
        WHERE status NOT IN ('Won', 'Lost')
    """).fetchone()[0]

    upcoming = conn.execute("""
        SELECT *
        FROM prospects
        WHERE next_followup IS NOT NULL
        AND next_followup >= ?
        ORDER BY next_followup
        LIMIT 5
    """, (
        str(date.today()),
    )).fetchall()

    recent = conn.execute("""
        SELECT *
        FROM prospects
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    source_rows = conn.execute("""
        SELECT source, COUNT(*) c
        FROM prospects
        GROUP BY source
    """).fetchall()

    status_rows = conn.execute("""
        SELECT status, COUNT(*) c
        FROM prospects
        GROUP BY status
    """).fetchall()

    conn.close()

    conversion = (
        round((won / total) * 100, 1)
        if total
        else 0
    )

    return render_template(
        "dashboard.html",
        total=total,
        won=won,
        interested=interested,
        pipeline=pipeline,
        conversion=conversion,
        upcoming=upcoming,
        recent=recent,
        source_rows=source_rows,
        status_rows=status_rows
    )


# --------------------------------------------------
# PROSPECTS LIST
# --------------------------------------------------

@app.route("/prospects")
def prospects():

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()

    conn = db()

    sql = """
        SELECT *
        FROM prospects
        WHERE 1=1
    """

    params = []

    if q:
        sql += """
            AND (
                name LIKE ?
                OR company LIKE ?
                OR email LIKE ?
            )
        """

        params += [
            f"%{q}%",
            f"%{q}%",
            f"%{q}%"
        ]

    if status:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY id DESC"

    rows = conn.execute(
        sql,
        params
    ).fetchall()

    conn.close()

    return render_template(
        "prospects.html",
        prospects=rows,
        statuses=STATUSES,
        q=q,
        selected_status=status
    )


# --------------------------------------------------
# ADD PROSPECT
# --------------------------------------------------

@app.route("/prospects/add", methods=["GET", "POST"])
def add_prospect():

    if request.method == "POST":

        data = request.form

        if not data.get("name") or not data.get("company"):

            flash(
                "Name and company are required.",
                "error"
            )

            return redirect(
                url_for("add_prospect")
            )

        conn = db()

        conn.execute("""
            INSERT INTO prospects
            (
                name,
                company,
                email,
                phone,
                source,
                status,
                value,
                next_followup,
                notes,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data["name"],
            data["company"],
            data["email"],
            data["phone"],
            data["source"],
            data["status"],
            float(data["value"] or 0),
            data["next_followup"] or None,
            data["notes"],
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        conn.commit()
        conn.close()

        flash(
            "Prospect added successfully.",
            "success"
        )

        return redirect(
            url_for("prospects")
        )

    return render_template(
        "add_prospect.html",
        statuses=STATUSES
    )


# --------------------------------------------------
# PROSPECT DETAILS / UPDATE
# --------------------------------------------------

@app.route(
    "/prospects/<int:pid>",
    methods=["GET", "POST"]
)
def prospect_detail(pid):

    conn = db()

    if request.method == "POST":

        data = request.form

        conn.execute("""
            UPDATE prospects
            SET
                name=?,
                company=?,
                email=?,
                phone=?,
                source=?,
                status=?,
                value=?,
                next_followup=?,
                notes=?
            WHERE id=?
        """, (
            data["name"],
            data["company"],
            data["email"],
            data["phone"],
            data["source"],
            data["status"],
            float(data["value"] or 0),
            data["next_followup"] or None,
            data["notes"],
            pid
        ))

        conn.commit()

        flash(
            "Prospect updated.",
            "success"
        )

    prospect = conn.execute("""
        SELECT *
        FROM prospects
        WHERE id=?
    """, (
        pid,
    )).fetchone()

    activities = conn.execute("""
        SELECT *
        FROM activities
        WHERE prospect_id=?
        ORDER BY activity_date DESC, id DESC
    """, (
        pid,
    )).fetchall()

    conn.close()

    if not prospect:
        return "Prospect not found", 404

    return render_template(
        "prospect_detail.html",
        prospect=prospect,
        activities=activities,
        statuses=STATUSES,
        activity_types=ACTIVITIES
    )


# --------------------------------------------------
# ADD ACTIVITY
# --------------------------------------------------

@app.route(
    "/prospects/<int:pid>/activity",
    methods=["POST"]
)
def add_activity(pid):

    data = request.form

    conn = db()

    conn.execute("""
        INSERT INTO activities
        (
            prospect_id,
            activity_type,
            activity_date,
            notes
        )
        VALUES (?, ?, ?, ?)
    """, (
        pid,
        data["activity_type"],
        data["activity_date"],
        data["notes"]
    ))

    conn.commit()
    conn.close()

    flash(
        "Activity recorded.",
        "success"
    )

    return redirect(
        url_for(
            "prospect_detail",
            pid=pid
        )
    )


# --------------------------------------------------
# DELETE PROSPECT
# --------------------------------------------------

@app.route(
    "/prospects/<int:pid>/delete",
    methods=["POST"]
)
def delete_prospect(pid):

    conn = db()

    # Delete related activities first
    conn.execute("""
        DELETE FROM activities
        WHERE prospect_id=?
    """, (
        pid,
    ))

    # Delete prospect
    conn.execute("""
        DELETE FROM prospects
        WHERE id=?
    """, (
        pid,
    ))

    conn.commit()
    conn.close()

    flash(
        "Prospect deleted.",
        "success"
    )

    return redirect(
        url_for("prospects")
    )


# --------------------------------------------------
# LOCAL DEVELOPMENT
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )