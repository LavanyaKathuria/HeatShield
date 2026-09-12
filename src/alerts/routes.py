import os
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
import requests

from . import accounts
from .dispatch import normalize_phone, opt_in_instructions, send_whatsapp
from .service import compose
from .storage import Ledger
from src.weather.forecast_cache import get_cached_or_compute

router = APIRouter(prefix="/alerts", tags=["alerts"])


def identity(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in to view alerts")
    token = authorization[7:]
    try:
        user = accounts.request("/auth/v1/user", token)
        return user["id"], token
    except requests.HTTPError as exc:
        raise HTTPException(401, "Session expired or invalid") from exc
    except (RuntimeError, requests.RequestException) as exc:
        raise HTTPException(503, "Account service unavailable") from exc


def owned_profile(auth):
    uid, token = auth
    try:
        rows = accounts.request("/rest/v1/profiles", token, params={"id": "eq." + uid})
    except (RuntimeError, requests.RequestException) as exc:
        raise HTTPException(503, "Account service unavailable") from exc
    if not rows:
        try:
            corporate = accounts.request('/rest/v1/corporate_accounts', token, params={'id': 'eq.' + uid})
            if corporate:
                return accounts.corporate_profile(corporate[0], accounts.request('/auth/v1/user', token))
        except (RuntimeError, requests.RequestException) as exc:
            raise HTTPException(503, 'Account service unavailable') from exc
        raise HTTPException(404, "Account profile not found")
    return rows[0]


@router.get('/status')
def alert_status(auth=Depends(identity)):
    from .automation import status
    from .budget import usage
    profile = owned_profile(auth)
    ledger = Ledger(os.getenv('ALERTS_DB_PATH', 'data/alerts.sqlite'))
    try:
        history = ledger.history(auth[0])
    finally:
        ledger.close()
    return dict(automation=status(), budget=usage(), history=history,
                opted_in=bool(profile.get('whatsapp_opt_in')), opt_in=opt_in_instructions(),
                preferences={key: profile.get(key) for key in ('phone', 'preferred_language', 'whatsapp_opt_in')})


class DemoRequest(BaseModel):
    send: bool = False


@router.post('/demo')
def demo(body: DemoRequest, auth=Depends(identity)):
    from src.risk.scenario import replay
    profile = owned_profile(auth)
    if os.getenv('WHATSAPP_MODE', 'sandbox') != 'sandbox':
        raise HTTPException(409, 'Historical demonstrations require sandbox mode')
    if not profile.get('ward_id') and profile.get('org_type') != 'city_admin':
        raise HTTPException(422, 'Save your ward before running the demonstration')
    try:
        family = accounts.request('/rest/v1/dependents', auth[1], params={'profile_id': 'eq.' + auth[0]})
        wards = {str(profile.get('ward_id') or 'citywide')} | {str(d['ward_id']) for d in family if d.get('ward_id')}
        history = replay('may_2024')
        records = [{**day, 'ward_id': ward} for ward in wards for day in history]
        alerts = compose(profile, family, records)
        candidates = [a for a in alerts if 'whatsapp' in a['channels']]
        if not candidates:
            return dict(status='no_qualifying_alerts', alert=None)
        from src.risk.levels import LEVEL_RANK
        alert = sorted(candidates, key=lambda a: (-LEVEL_RANK[a['level']], a['date'], a['group']))[0]
        if not body.send:
            return dict(status='preview', alert=alert, source='may_2024')
        if not profile.get('whatsapp_opt_in'):
            raise HTTPException(409, 'Enable and save WhatsApp consent first')
        phone = normalize_phone(profile.get('phone'))
        ledger = Ledger(os.getenv('ALERTS_DB_PATH', 'data/alerts.sqlite'))
        try:
            # Separate historical demo identities from live event deduplication.
            reserved_alert = {**alert, 'ward_id': 'demo:' + alert['language'] + ':' + alert['ward_id'], 'group': 'demo'}
            reservation = ledger.reserve(auth[0], phone, reserved_alert)
            if not reservation:
                return dict(status='suppressed', alert=alert, source='may_2024')
            record = send_whatsapp(phone, alert['body'], dry_run=False, alert=alert)
            ledger.finish(reservation, record)
            return dict(status=record['status'], id=reservation, alert=alert, source='may_2024')
        finally:
            ledger.close()
    except (RuntimeError, requests.RequestException) as exc:
        raise HTTPException(503, 'Demonstration service unavailable') from exc
    except ValueError as exc:
        raise HTTPException(422, 'Check your saved phone, language and ward') from exc


@router.post('/refresh-delivery')
def refresh_delivery(auth=Depends(identity)):
    # Reads provider status for this user's records only; never sends a message.
    from scripts.reconcile_alerts import reconcile
    owned_profile(auth)
    ledger = Ledger(os.getenv('ALERTS_DB_PATH', 'data/alerts.sqlite'))
    try:
        reconcile(ledger, recipient=auth[0])
    except (RuntimeError, requests.RequestException) as exc:
        raise HTTPException(503, 'Delivery status temporarily unavailable') from exc
    finally:
        ledger.close()
    return {'status': 'updated'}


@router.post('/replay')
def activate_dashboard_replay(auth=Depends(identity)):
    """A deliberate dashboard activation sends only this account's drill alerts."""
    from src.risk.historical_dashboard import historical_records
    profile = owned_profile(auth)
    if os.getenv('WHATSAPP_MODE', 'sandbox') != 'sandbox':
        raise HTTPException(409, 'Historical replay delivery requires sandbox mode')
    if not profile.get('whatsapp_opt_in'):
        return {'status': 'opted_out', 'results': []}
    try:
        phone = normalize_phone(profile.get('phone'))
        family = accounts.request('/rest/v1/dependents', auth[1], params={'profile_id': 'eq.' + auth[0]})
        alerts = compose(profile, family, historical_records())
        ledger = Ledger(os.getenv('ALERTS_DB_PATH', 'data/alerts.sqlite'))
        results = []
        try:
            for alert in alerts:
                if 'whatsapp' not in alert['channels']:
                    continue
                assert alert['is_replay']
                key = {**alert, 'ward_id': 'dashboard-replay:' + alert['language'] + ':' + alert['ward_id']}
                reservation = ledger.reserve(auth[0], phone, key, replay_cooldown_seconds=60)
                if not reservation:
                    results.append({'status': 'suppressed'})
                    continue
                record = send_whatsapp(phone, alert['body'], dry_run=False, alert=alert)
                ledger.finish(reservation, record)
                results.append({'status': record['status'], 'id': reservation})
        finally:
            ledger.close()
        return {'status': 'processed', 'results': results}
    except (RuntimeError, requests.RequestException) as exc:
        raise HTTPException(503, 'Replay alerts unavailable') from exc
    except ValueError as exc:
        raise HTTPException(422, 'Check your saved phone and ward') from exc


@router.get("/me")
def my_alerts(auth=Depends(identity), source: Literal['live', 'may_2024'] = 'live'):
    profile = owned_profile(auth)
    try:
        dependents = accounts.request("/rest/v1/dependents", auth[1], params={"profile_id": "eq." + auth[0]})
        if source == 'may_2024':
            from src.risk.historical_dashboard import get_historical_dashboard
            frame, *_ = get_historical_dashboard()
        else:
            frame, *_ = get_cached_or_compute(5)
        alerts = compose(profile, dependents, frame.astype(object).where(frame.notna(), None).to_dict("records"))
        ledger = Ledger(os.environ.get("ALERTS_DB_PATH", "data/alerts.sqlite"))
        try:
            history = ledger.history(auth[0])
        finally:
            ledger.close()
    except (RuntimeError, ValueError, requests.RequestException) as exc:
        raise HTTPException(503, "Alert forecast or account data unavailable") from exc
    return {"alerts": alerts, "history": history, "opt_in": opt_in_instructions(),
            "preferences": {key: profile.get(key) for key in
                ("phone", "preferred_language", "whatsapp_opt_in")}}


class Preferences(BaseModel):
    phone: str
    preferred_language: Literal["en", "hi", "gu"] = "en"
    whatsapp_opt_in: bool


@router.post("/preferences")
def save_preferences(body: Preferences, auth=Depends(identity)):
    profile = owned_profile(auth)
    try:
        phone = normalize_phone(body.phone) if body.phone.strip() else None
        if body.whatsapp_opt_in and not phone:
            raise ValueError("A WhatsApp phone number is required")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        if profile.get('_account_kind') == 'corporate':
            rows = accounts.request('/rest/v1/corporate_accounts', auth[1], method='PATCH',
                params={'id': 'eq.' + auth[0]}, payload={'contact_phone': phone})
            user = accounts.request('/auth/v1/user', auth[1], method='PUT', payload={'data': {
                'preferred_language': body.preferred_language, 'whatsapp_opt_in': body.whatsapp_opt_in}})
            return accounts.corporate_profile(rows[0], user)
        rows = accounts.request("/rest/v1/profiles", auth[1], method="PATCH",
            params={"id": "eq." + auth[0]}, payload={**body.model_dump(), "phone": phone})
    except (RuntimeError, requests.RequestException) as exc:
        raise HTTPException(503, "Could not save WhatsApp preferences") from exc
    return rows[0]
