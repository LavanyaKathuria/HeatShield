"""Forecast targeting shared by authenticated previews and the scheduled worker."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import math

from .engine import build_citizen_alerts, build_institution_alert
from .render import render
from .dispatch import build_message


def local_today():
    return datetime.now(ZoneInfo("Asia/Kolkata")).date()


def compose(profile, dependents, records, today=None):
    today = today or local_today()
    wards = {str(profile["ward_id"])} if profile.get("ward_id") else set()
    wards.update(str(d["ward_id"]) for d in dependents if d.get("ward_id"))
    if profile.get('_account_kind') == 'corporate' and not wards:
        if profile.get('org_type') == 'city_admin':
            from src.risk.levels import LEVEL_RANK
            aggregate = []
            for when in sorted({r['date'] for r in records}):
                days = [r for r in records if r['date'] == when]
                if any(d.get('ehf') is None or not math.isfinite(d['ehf']) for d in days):
                    raise ValueError('City event data unavailable')
                groups = {g for d in days for g in d['group_levels']}
                aggregate.append(dict(ward_id='citywide', date=when, ehf=max(d['ehf'] for d in days),
                    group_levels={g: max((d['group_levels'].get(g, 'none') for d in days), key=LEVEL_RANK.get) for g in groups},
                    is_replay=any(d.get('is_replay') for d in days)))
            records = aggregate
            wards = {'citywide'}
        else:
            raise ValueError('An institutional ward must be selected')
    result = []
    for ward in sorted(wards):
        people = [d for d in dependents if str(d.get("ward_id") or profile.get("ward_id")) == ward]
        scoped = {**profile, "ward_id": ward}
        if str(profile.get("ward_id")) != ward:
            scoped.update(age=None, is_outdoor_worker=False)
        days = sorted([dict(r) for r in records if str(r["ward_id"]) == ward], key=lambda r: r["date"])
        if not days:
            raise ValueError(f"Forecast unavailable for ward {ward}")
        if any(r.get("ehf") is None or not math.isfinite(r["ehf"]) for r in days):
            raise ValueError(f"Heat event data unavailable for ward {ward}")
        if not any(r.get("is_replay") or date.fromisoformat(str(r["date"])[:10]) >= today for r in days):
            raise ValueError(f"Forecast is expired for ward {ward}")
        # Separate events across quiet days, including within one forecast window.
        events, current = [], []
        for day in days:
            day["date"] = str(day["date"])[:10]
            day_date = date.fromisoformat(day["date"])
            if day_date < today and not day.get("is_replay"):
                continue
            day.update(is_current=day_date == today, lead_days=max(0, (day_date - today).days))
            active = day["ehf"] > 0
            if current and (not active or day_date > date.fromisoformat(current[-1]["date"]) + timedelta(days=1)):
                events.append(current)
                current = []
            if active:
                current.append(day)
        if current:
            events.append(current)
        for event in events:
            if profile.get('_account_kind') == 'corporate':
                from .render import render_institution_whatsapp
                alert = build_institution_alert(scoped, event)
                if alert:
                    alert.update(event_start=event[0]['date'], event_end=event[-1]['date'])
                    bodies, fallback = render_institution_whatsapp(alert)
                    for index, body in enumerate(bodies):
                        part = {**alert, 'group': f"{alert['group']}:{index+1}"}
                        result.append({**part, 'body': build_message(part, {'whatsapp': {'body': body}}),
                                       'used_fallback_language': fallback})
                continue
            for alert in build_citizen_alerts(scoped, people, event):
                alert.update(event_start=event[0]["date"], event_end=event[-1]["date"])
                rendered = render(alert)
                # Watch is dashboard-only but can still be previewed as text.
                from .render import render_whatsapp
                rendered["whatsapp"] = render_whatsapp(alert)
                full_advisory = build_message(alert, {"whatsapp": render_whatsapp(alert, compact=False)})
                result.append({**alert, "body": build_message(alert, rendered), "advisory_body": full_advisory,
                               "used_fallback_language": rendered["whatsapp"]["used_fallback_language"]})
    return result
