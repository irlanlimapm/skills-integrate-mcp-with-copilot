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


def init_db(seed_activities: Dict[str, Any] | None = None):
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
    conn.commit()

    # Seed if provided and table is empty
    cur.execute("SELECT COUNT(1) as c FROM activities")
    row = cur.fetchone()
    if seed_activities and row and row["c"] == 0:
        for name, data in seed_activities.items():
            cur.execute(
                "INSERT INTO activities (name, description, schedule, max_participants, participants) VALUES (?, ?, ?, ?, ?)",
                (name, data.get("description", ""), data.get("schedule", ""), data.get("max_participants", 0), json.dumps(data.get("participants", [])))
            )
        conn.commit()

    conn.close()


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
