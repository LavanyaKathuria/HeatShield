"""Scheduled WhatsApp worker. Preview by default; --send enables delivery."""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.alerts import accounts
from src.alerts.dispatch import normalize_phone, send_whatsapp, is_configured
from src.alerts.service import compose
from src.alerts.storage import Ledger
from src.weather.forecast_cache import get_cached_or_compute


def run(profiles, dependents, records, send=False, db_path=None):
    if send and not is_configured():
        raise RuntimeError("Twilio credentials are missing")
    ledger = Ledger(db_path or os.environ.get("ALERTS_DB_PATH", "data/alerts.sqlite")) if send else None
    results = []
    try:
        for profile in profiles:
            if not profile.get("whatsapp_opt_in"):
                continue
            try:
                phone = normalize_phone(profile.get("phone"))
                family = [d for d in dependents if d["profile_id"] == profile["id"]]
                alerts = compose(profile, family, records)
                for alert in alerts:
                    if "whatsapp" not in alert["channels"]:
                        continue
                    if send and alert.get("is_replay"):
                        raise ValueError("Historical replay is preview-only in the scheduled worker")
                    if ledger:
                        reservation = ledger.reserve(profile["id"], phone, alert)
                        if not reservation:
                            results.append({"status": "suppressed"})
                            continue
                        record = send_whatsapp(phone, alert["body"], dry_run=False, alert=alert)
                        ledger.finish(reservation, record)
                        results.append({"status": record["status"], "id": reservation})
                    else:
                        results.append({"status": "preview", "language": alert["language"], "body": alert["body"]})
            except ValueError as exc:
                results.append({"status": "failed", "error": str(exc)})
    finally:
        if ledger:
            ledger.close()
    return results


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--scenario", choices=["may_2024", "may_2010", "may_2016"])
    parser.add_argument("--language", choices=["en", "hi", "gu"], default="en")
    args = parser.parse_args()
    if args.scenario:
        if args.send:
            parser.error("Historical scenarios are preview-only")
        from src.risk.scenario import replay
        records = [{**day, "ward_id": "1"} for day in replay(args.scenario)]
        profiles = [dict(id="demo", ward_id="1", age=70, is_outdoor_worker=True,
                         preferred_language=args.language, phone="+919876543210", whatsapp_opt_in=True)]
        dependents = []
    else:
        profiles = accounts.subscribers()
        dependents = accounts.all_rows("dependents")
        frame, *_ = get_cached_or_compute(5)
        records = frame.astype(object).where(frame.notna(), None).to_dict("records")
    results = run(profiles, dependents, records, args.send)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return int(any(r["status"] in ("failed", "unknown") for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
