"""Backend-owned scheduler with a durable cross-process lease and audit status."""
import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from .storage import Ledger
from . import config  # Load root .env before reading scheduler settings.

logger = logging.getLogger(__name__)


def enabled():
    return os.getenv('ALERTS_AUTOMATION_ENABLED', 'false').lower() == 'true'


def state_db():
    ledger = Ledger(os.getenv('ALERTS_DB_PATH', 'data/alerts.sqlite'))
    ledger.db.execute('CREATE TABLE IF NOT EXISTS automation (id INTEGER PRIMARY KEY, lease_until REAL, owner TEXT, next_run REAL, result TEXT)')
    ledger.db.execute("INSERT OR IGNORE INTO automation VALUES (1,0,'',0,'{}')")
    ledger.db.commit()
    return ledger


def status():
    ledger = state_db()
    try:
        row = ledger.db.execute('SELECT * FROM automation WHERE id=1').fetchone()
        return dict(enabled=enabled(), next_run=row['next_run'], running=row['lease_until'] > time.time(),
                    last_run=json.loads(row['result']))
    finally:
        ledger.close()


def tick():
    if not enabled():
        return
    ledger = state_db()
    owner = str(uuid4())
    now = time.time()
    try:
        ledger.db.execute('BEGIN IMMEDIATE')
        row = ledger.db.execute('SELECT * FROM automation WHERE id=1').fetchone()
        if row['lease_until'] > now or row['next_run'] > now:
            ledger.db.rollback()
            return
        ledger.db.execute('UPDATE automation SET lease_until=?, owner=? WHERE id=1', (now+3600, owner))
        ledger.db.commit()
        result = dict(started_at=now, source='HeatShield automatic forecast', status='completed')
        try:
            from . import accounts
            from .budget import usage
            from scripts.dispatch_alerts import run
            from scripts.reconcile_alerts import reconcile
            from src.weather.forecast_cache import get_cached_or_compute
            reconcile(ledger)
            profiles = accounts.subscribers()
            result['subscribers'] = len(profiles)
            if not profiles:
                result['outcome'] = 'no_subscribers'
            elif usage()['remaining'] == 0:
                result['outcome'] = 'budget_blocked'
            else:
                dependents = accounts.all_rows('dependents')
                frame, *_ = get_cached_or_compute(5)
                records = frame.astype(object).where(frame.notna(), None).to_dict('records')
                outcomes = run(profiles, dependents, records, send=True)
                result['outcomes'] = [r['status'] for r in outcomes]
                result['outcome'] = 'processed' if outcomes else 'no_qualifying_alerts'
        except Exception as exc:
            logger.error('Automatic alerts failed (%s)', type(exc).__name__)
            result.update(status='error', error=type(exc).__name__)
        interval = max(60, int(os.getenv('ALERTS_INTERVAL_SECONDS', '60')))
        result['finished_at'] = time.time()
        ledger.db.execute('UPDATE automation SET lease_until=0,next_run=?,result=? WHERE id=1 AND owner=?',
                          (time.time()+interval, json.dumps(result), owner))
        ledger.db.commit()
    finally:
        ledger.close()


@asynccontextmanager
async def lifespan(app):
    stop = asyncio.Event()
    async def loop():
        while not stop.is_set():
            try:
                await asyncio.to_thread(tick)
            except Exception:
                logger.exception('Automatic alert scheduler error')
            try:
                await asyncio.wait_for(stop.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass
    task = asyncio.create_task(loop())
    yield
    stop.set()
    await task
