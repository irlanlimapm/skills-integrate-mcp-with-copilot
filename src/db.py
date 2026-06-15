import sqlite3
import json
from pathlib import Path
from typing import Dict, Any


DB_PATH = Path(__file__).parent.parent / "data.db"


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(seed_activities: Dict[str, Any] | None = None, admin_password: str | None = None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            name TEXT PRIMARY KEY,
            description TEXT,
            schedule TEXT,
            max_participants INTEGER,
            participants TEXT
        )
        """
    )

    # Auth tables
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT,
            is_admin INTEGER DEFAULT 0
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            username TEXT,
            expires_at TEXT
        )
        """
    )

    conn.commit()

    # Seed activities if provided and table is empty
    cur.execute("SELECT COUNT(1) as c FROM activities")
    row = cur.fetchone()
    if seed_activities and row and row["c"] == 0:
        for name, data in seed_activities.items():
            cur.execute(
                "INSERT INTO activities (name, description, schedule, max_participants, participants) VALUES (?, ?, ?, ?, ?)",
                (name, data.get("description", ""), data.get("schedule", ""), data.get("max_participants", 0), json.dumps(data.get("participants", [])))
            )
        conn.commit()

    # Seed admin user if password provided and user doesn't exist
    if admin_password is not None:
        cur.execute("SELECT COUNT(1) as c FROM users WHERE username = ?", ("admin",))
        ur = cur.fetchone()
        if ur and ur["c"] == 0:
            import hashlib
+            # simple sha256 hash for prototype (replace with bcrypt in production)
+            pw_hash = hashlib.sha256(admin_password.encode("utf-8")).hexdigest()
+            cur.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, 1)", ("admin", pw_hash))
+            conn.commit()
+
+    conn.close()


def get_all_activities():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM activities ORDER BY name")
    rows = cur.fetchall()
    result = {}
    for r in rows:
        result[r["name"]] = {
            "description": r["description"],
            "schedule": r["schedule"],
            "max_participants": r["max_participants"],
            "participants": json.loads(r["participants"] or "[]"),
        }
    conn.close()
    return result


# ------------------- auth helpers -------------------
import hashlib
import uuid
from datetime import datetime, timedelta


def create_user_if_missing(username: str, password: str, is_admin: bool = False):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(1) as c FROM users WHERE username = ?", (username,))
    r = cur.fetchone()
    if r and r["c"] > 0:
        conn.close()
        return
    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    cur.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)", (username, pw_hash, 1 if is_admin else 0))
    conn.commit()
    conn.close()


def authenticate_and_create_token(username: str, password: str, days_valid: int = 7):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    r = cur.fetchone()
    if not r:
        conn.close()
        return None
    pw_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    if pw_hash != r["password_hash"]:
        conn.close()
        return None

    token = uuid.uuid4().hex
    expires = (datetime.utcnow() + timedelta(days=days_valid)).isoformat()
    cur.execute("INSERT INTO tokens (token, username, expires_at) VALUES (?, ?, ?)", (token, username, expires))
    conn.commit()
    conn.close()
    return token


def verify_token(token: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, expires_at FROM tokens WHERE token = ?", (token,))
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    expires = datetime.fromisoformat(r["expires_at"])
    if datetime.utcnow() > expires:
        return None
    return r["username"]


def get_activity(name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM activities WHERE name = ?", (name,))
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    return {
        "description": r["description"],
        "schedule": r["schedule"],
        "max_participants": r["max_participants"],
        "participants": json.loads(r["participants"] or "[]"),
    }


def save_activity(name: str, data: Dict[str, Any]):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO activities (name, description, schedule, max_participants, participants) VALUES (?, ?, ?, ?, ?)",
        (name, data.get("description", ""), data.get("schedule", ""), data.get("max_participants", 0), json.dumps(data.get("participants", [])))
    )
    conn.commit()
    conn.close()


def signup(name: str, email: str):
    activity = get_activity(name)
    if activity is None:
        raise KeyError("not_found")

    if email in activity["participants"]:
        raise KeyError("already_signed_up")

    if len(activity["participants"]) >= (activity.get("max_participants") or 0):
        raise KeyError("full")

    activity["participants"].append(email)
    save_activity(name, activity)


def unregister(name: str, email: str):
    activity = get_activity(name)
    if activity is None:
        raise KeyError("not_found")

    if email not in activity["participants"]:
        raise KeyError("not_signed_up")

    activity["participants"].remove(email)
    save_activity(name, activity)
