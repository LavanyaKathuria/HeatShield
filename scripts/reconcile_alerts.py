"""Poll Twilio for actual delivery status; never sends messages."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import requests
from src.alerts.dispatch import ENV_ACCOUNT_SID, ENV_AUTH_TOKEN, is_configured
from src.alerts.storage import Ledger


def reconcile(ledger, recipient=None):
    if not is_configured():
        raise RuntimeError("Twilio credentials are missing")
    rows = ledger.db.execute("""SELECT id,message_id FROM deliveries WHERE message_id IS NOT NULL
        AND status NOT IN ('read','failed','undelivered','canceled')
        AND (? IS NULL OR recipient=?) ORDER BY created_at DESC LIMIT 50""", (recipient, recipient)).fetchall()
    for row in rows:
        response = requests.get(
            f"https://api.twilio.com/2010-04-01/Accounts/{os.environ[ENV_ACCOUNT_SID]}/Messages/{row['message_id']}.json",
            auth=(os.environ[ENV_ACCOUNT_SID], os.environ[ENV_AUTH_TOKEN]), timeout=20)
        response.raise_for_status()
        message = response.json()
        ledger.finish(row["id"], {"status": message["status"], "message_id": row["message_id"],
                                 "error": str(message["error_code"]) if message.get("error_code") else None})
    return len(rows)


if __name__ == "__main__":
    ledger = Ledger(os.environ.get("ALERTS_DB_PATH", "data/alerts.sqlite"))
    try:
        print(f"Checked {reconcile(ledger)} provider records")
    finally:
        ledger.close()
