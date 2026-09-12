"""Atomic limits on ALL provider send attempts, including failed/uncertain ones."""
import os
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timezone
from . import config  # Load root .env for standalone usage as well as the API.


def limits():
    return max(0, int(os.getenv('WHATSAPP_DAILY_LIMIT', '3'))), max(0, int(os.getenv('WHATSAPP_TOTAL_LIMIT', '10')))


def enabled():
    return os.getenv('WHATSAPP_LIMITS_ENABLED', 'true').lower() == 'true'


def connect():
    path = os.getenv('ALERTS_DB_PATH', 'data/alerts.sqlite')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.execute('CREATE TABLE IF NOT EXISTS send_budget (id INTEGER PRIMARY KEY, day TEXT NOT NULL)')
    return db


def usage():
    daily, total = limits()
    with connect() as db:
        used = db.execute('SELECT COUNT(*) FROM send_budget').fetchone()[0]
        today = db.execute('SELECT COUNT(*) FROM send_budget WHERE day=?', (datetime.now(timezone.utc).date().isoformat(),)).fetchone()[0]
    db.close()
    return dict(enabled=enabled(), daily_limit=daily, total_limit=total, today_attempts=today, total_attempts=used,
                remaining=max(0, min(daily-today, total-used)) if enabled() else None)


def reserve_attempt():
    daily, total = limits()
    db = connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        day = datetime.now(timezone.utc).date().isoformat()
        used = db.execute('SELECT COUNT(*) FROM send_budget').fetchone()[0]
        today = db.execute('SELECT COUNT(*) FROM send_budget WHERE day=?', (day,)).fetchone()[0]
        if enabled() and (used >= total or today >= daily):
            db.rollback()
            return False
        db.execute('INSERT INTO send_budget(day) VALUES (?)', (day,))
        db.commit()
        return True
    finally:
        db.close()


def pace_sandbox():
    """Share the sandbox's send spacing across API and worker processes."""
    db = connect()
    try:
        db.execute('CREATE TABLE IF NOT EXISTS send_clock (id INTEGER PRIMARY KEY, next_at REAL)')
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT next_at FROM send_clock WHERE id=1').fetchone()
        slot = max(time.time(), row[0] if row else 0)
        db.execute('INSERT OR REPLACE INTO send_clock VALUES (1,?)', (slot+3.1,))
        db.commit()
    finally:
        db.close()
    time.sleep(max(0, slot-time.time()))
