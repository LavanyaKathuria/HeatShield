"""Single-host durable dispatch ledger. Reservations commit BEFORE network I/O.

An interrupted/uncertain send stays reserved for manual reconciliation; blindly
retrying it could duplicate an emergency alert. Deploy workers on one durable DB.
"""
import sqlite3
import os
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from src.risk.levels import LEVEL_RANK


class Ledger:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, ward TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS deliveries (
            id TEXT PRIMARY KEY, recipient TEXT NOT NULL, phone TEXT NOT NULL,
            event TEXT NOT NULL, audience TEXT NOT NULL, rank INTEGER NOT NULL,
            language TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL,
            message_id TEXT, error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
          );
        """)

    def close(self):
        self.db.close()

    def reserve(self, recipient, phone, alert, replay_cooldown_seconds=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            # Overlapping/adjacent forecast windows refer to the same event.
            lo = (date.fromisoformat(alert["event_start"]) - timedelta(days=1)).isoformat()
            hi = (date.fromisoformat(alert["event_end"]) + timedelta(days=1)).isoformat()
            rows = self.db.execute("SELECT * FROM events WHERE ward=? AND start<=? AND end>=?",
                                   (alert["ward_id"], hi, lo)).fetchall()
            event_id = rows[0]["id"] if rows else str(uuid4())
            start = min([alert["event_start"]] + [r["start"] for r in rows])
            end = max([alert["event_end"]] + [r["end"] for r in rows])
            for row in rows[1:]:
                self.db.execute("UPDATE deliveries SET event=? WHERE event=?", (event_id, row["id"]))
                self.db.execute("DELETE FROM events WHERE id=?", (row["id"],))
            self.db.execute("INSERT OR REPLACE INTO events VALUES (?,?,?,?)", (event_id, alert["ward_id"], start, end))
            # Closed sandbox windows / provider failures must not be retried every
            # minute just because profile polling is frequent.
            cooldown = max(0, int(os.getenv('WHATSAPP_FAILURE_RETRY_SECONDS', '10800')))
            recent_failure = self.db.execute("""SELECT 1 FROM deliveries WHERE recipient=? AND phone=?
                AND event=? AND audience=? AND status IN ('failed','undelivered')
                AND created_at > datetime('now', ?) LIMIT 1""",
                (recipient, phone, event_id, alert['group'], f'-{cooldown} seconds')).fetchone()
            if recent_failure:
                self.db.commit()
                return None
            prior_query = """SELECT MAX(rank) FROM deliveries WHERE recipient=? AND phone=?
                AND event=? AND audience=? AND status NOT IN ('failed','undelivered','budget_blocked')"""
            prior_params = [recipient, phone, event_id, alert['group']]
            if replay_cooldown_seconds is not None:
                if not alert.get('is_replay'):
                    raise ValueError('Repeat delivery is only available for historical replay')
                # Never retry an uncertain/in-flight delivery automatically.
                prior_query += " AND (status IN ('reserved','unknown','accepted','scheduled','queued','sending') OR created_at > datetime('now', ?))"
                prior_params.append(f'-{max(60, replay_cooldown_seconds)} seconds')
            prior = self.db.execute(prior_query, prior_params).fetchone()[0]
            rank = LEVEL_RANK[alert["level"]]
            if prior is not None and prior >= rank:
                self.db.commit()
                return None
            delivery_id = str(uuid4())
            self.db.execute("""INSERT INTO deliveries
                (id,recipient,phone,event,audience,rank,language,body,status)
                VALUES (?,?,?,?,?,?,?,?, 'reserved')""", (delivery_id, recipient, phone, event_id,
                alert["group"], rank, alert["language"], alert["body"]))
            self.db.commit()
            return delivery_id
        except Exception:
            self.db.rollback()
            raise

    def finish(self, delivery_id, record):
        self.db.execute("UPDATE deliveries SET status=?,message_id=?,error=? WHERE id=?",
                        (record["status"], record.get("message_id"), record.get("error"), delivery_id))
        self.db.commit()

    def history(self, recipient):
        return [dict(r) for r in self.db.execute("""SELECT id,audience,language,body,status,created_at
            FROM deliveries WHERE recipient=? ORDER BY created_at DESC LIMIT 30""", (recipient,))]
