from datetime import date
import json
import pytest
import requests

from src.alerts.service import compose
from src.alerts.storage import Ledger
from src.alerts import dispatch, render
from src.alerts.advisories import CITIZEN_ADVISORIES
from scripts.dispatch_alerts import run

TODAY = date(2026, 9, 12)
PROFILE = dict(id="user-a", ward_id="1", age=70, preferred_language="gu",
               whatsapp_opt_in=True, phone="+919876543210")


@pytest.fixture(autouse=True)
def isolated_budget(tmp_path, monkeypatch):
    monkeypatch.setenv('ALERTS_DB_PATH', str(tmp_path / 'transport.sqlite'))
    monkeypatch.setenv('WHATSAPP_LIMITS_ENABLED', 'true')
    monkeypatch.setenv('WHATSAPP_DAILY_LIMIT', '3')
    monkeypatch.setenv('WHATSAPP_TOTAL_LIMIT', '10')
    monkeypatch.setenv('ALERTS_AUTOMATION_ENABLED', 'false')


def day(ward="1", when="2026-09-12", level="warning", ehf=5):
    return dict(ward_id=ward, date=when, ehf=ehf,
                group_levels=dict(elderly=level, general="watch", children="none", outdoor_workers="none"))


def alert(level="warning", **changes):
    return {**compose(PROFILE, [], [day(level=level)], TODAY)[0], **changes}


@pytest.mark.parametrize("language", ["en", "hi", "gu"])
def test_all_advisories_are_translated(language):
    for advisory in CITIZEN_ADVISORIES.values():
        for key in [advisory["headline"], *advisory["actions"], advisory["why"], advisory["voice"]]:
            if key:
                text, fallback = render.lookup(key, language)
                assert text and not fallback
    output = compose({**PROFILE, "preferred_language": language}, [], [day()], TODAY)[0]
    assert output["language"] == language
    assert not output["used_fallback_language"]
    if language != "en":
        assert any(ord(c) > 127 for c in output["body"])


def test_no_event_no_alert_and_missing_data_fails_loudly():
    assert compose(PROFILE, [], [day(ehf=0)], TODAY) == []
    with pytest.raises(ValueError):
        compose(PROFILE, [], [day(ehf=None)], TODAY)


def test_watch_dashboard_only_and_general_suppressed():
    result = compose(PROFILE, [], [day(level="watch")], TODAY)
    assert len(result) == 1
    assert result[0]["group"] == "elderly"
    assert result[0]["channels"] == ["dashboard"]


def test_dependent_receives_own_ward_advice():
    profile = {**PROFILE, "age": 30}
    family = [dict(profile_id=PROFILE["id"], age=80, ward_id="2", full_name="Grandmother")]
    result = compose(profile, family, [day(ehf=0), day(ward="2")], TODAY)
    assert len(result) == 1
    assert result[0]["ward_id"] == "2"
    assert result[0]["applies_to"] == ["Grandmother"]


def test_events_split_and_peak_selected():
    result = compose(PROFILE, [], [day(), day(when="2026-09-13", level="danger"),
        day(when="2026-09-14", ehf=0), day(when="2026-09-15")], TODAY)
    assert [a["level"] for a in result] == ["danger", "warning"]
    assert result[0]["lead_days"] == 1


def test_persisted_dedup_escalation_recovery_and_new_event(tmp_path):
    path = tmp_path / "alerts.sqlite"
    ledger = Ledger(path)
    first = ledger.reserve("a", PROFILE["phone"], alert())
    ledger.finish(first, {"status": "queued", "message_id": "SM1"})
    ledger.close()
    ledger = Ledger(path)
    assert ledger.reserve("a", PROFILE["phone"], alert()) is None
    high = ledger.reserve("a", PROFILE["phone"], alert("danger"))
    assert high
    assert ledger.reserve("a", PROFILE["phone"], alert()) is None
    assert ledger.reserve("b", PROFILE["phone"], alert())
    assert ledger.reserve("a", PROFILE["phone"], alert(event_start="2026-09-16", event_end="2026-09-18"))
    ledger.close()


def test_failed_can_retry_unknown_cannot(tmp_path, monkeypatch):
    monkeypatch.setenv('WHATSAPP_FAILURE_RETRY_SECONDS', '0')
    ledger = Ledger(tmp_path / "alerts.sqlite")
    ident = ledger.reserve("a", PROFILE["phone"], alert())
    ledger.finish(ident, {"status": "failed"})
    ident = ledger.reserve("a", PROFILE["phone"], alert())
    assert ident
    ledger.finish(ident, {"status": "unknown"})
    assert ledger.reserve("a", PROFILE["phone"], alert()) is None
    ledger.close()


def test_dry_run_and_opt_out_never_touch_provider(tmp_path, monkeypatch):
    monkeypatch.setattr("src.alerts.service.local_today", lambda: TODAY)
    def forbidden(*args, **kwargs):
        pytest.fail("Network call in preview")
    monkeypatch.setattr(dispatch.requests, "post", forbidden)
    path = tmp_path / "alerts.sqlite"
    assert run([PROFILE], [], [day()], db_path=path)[0]["status"] == "preview"
    assert not path.exists()
    assert run([{**PROFILE, "whatsapp_opt_in": False}], [], [day()]) == []


@pytest.mark.parametrize("language", ["en", "hi", "gu"])
def test_historical_label_replaces_test_notice(language):
    item = {**alert(), "language": language, "is_replay": True}
    body = dispatch.build_message(item, {"whatsapp": {"body": "advisory"}}, is_drill=False)
    assert body.startswith(dispatch.REPLAY_NOTICE[language])
    assert dispatch.DRILL_NOTICE[language] not in body
    test_body = dispatch.build_message({**item, 'is_replay': False}, {'whatsapp': {'body': 'advisory'}}, is_drill=True)
    assert test_body.startswith(dispatch.DRILL_NOTICE[language])


@pytest.mark.parametrize('language', ['en', 'hi', 'gu'])
@pytest.mark.parametrize('group', ['elderly', 'children', 'outdoor_workers', 'general'])
@pytest.mark.parametrize('level', ['watch', 'warning', 'danger'])
def test_individual_messages_are_compact_with_full_advisory_available(language, group, level):
    from src.alerts.advisories import citizen_advisory
    advisory = citizen_advisory(group, level)
    item = dict(language=language, group=group, level=level, date='2024-05-23', ward_id='38',
                headline_key=advisory['headline'], action_keys=advisory['actions'], why_key=advisory['why'])
    short = render.render_whatsapp(item)['body']
    full = render.render_whatsapp(item, compact=False)['body']
    assert len(short) < len(full)
    assert sum(line.startswith('• ') for line in short.splitlines()) == 2
    assert '2024-05-23' in short and '38' in short
    for key in advisory['actions']:
        assert render.lookup(key, language)[0] in full
        if key.endswith('.call_108'):
            assert render.lookup(key, language)[0] in short


def test_production_requires_template_and_uses_content_sid(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test")
    monkeypatch.setenv("WHATSAPP_MODE", "production")
    monkeypatch.setenv("WHATSAPP_TEMPLATES", json.dumps({"gu.elderly.warning": "HXtest"}))
    def post(url, **kwargs):
        assert kwargs["data"]["ContentSid"] == "HXtest"
        assert "Body" not in kwargs["data"]
        response = requests.Response()
        response.status_code = 201
        response._content = b'{"sid":"SMtest", "status":"queued"}'
        return response
    monkeypatch.setattr(dispatch.requests, "post", post)
    result = dispatch.send_whatsapp(PROFILE["phone"], alert()["body"], False, alert())
    assert result["status"] == "queued"
    monkeypatch.setenv("WHATSAPP_TEMPLATES", "{}")
    assert dispatch.send_whatsapp(PROFILE["phone"], "body", False, alert())["status"] == "failed"


def test_phone_validation():
    assert dispatch.normalize_phone("98765 43210") == "+919876543210"
    with pytest.raises(ValueError):
        dispatch.normalize_phone("123")


def test_missing_auth_rejected():
    from src.alerts.routes import identity
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        identity("")
    assert error.value.status_code == 401


def test_preferences_use_verified_identity_and_user_token(monkeypatch):
    from src.alerts.routes import save_preferences, Preferences
    calls = []
    def request(path, token, **kwargs):
        calls.append((path, token, kwargs))
        return [PROFILE]
    monkeypatch.setattr("src.alerts.accounts.request", request)
    save_preferences(Preferences(phone="9876543210", preferred_language="hi", whatsapp_opt_in=True),
                     auth=("verified-user", "user-token"))
    path, token, kwargs = calls[-1]
    assert token == "user-token"
    assert kwargs["params"] == {"id": "eq.verified-user"}
    assert kwargs["payload"]["phone"] == "+919876543210"
    assert "privileged" not in kwargs


def test_templates_match_rendered_preview():
    from scripts.export_whatsapp_templates import templates
    from src.alerts.render import timing_label
    for language in ("en", "hi", "gu"):
        item = compose({**PROFILE, "preferred_language": language}, [], [day()], TODAY)[0]
        body = templates()[f"{language}.elderly.warning"]
        body = body.replace("{{1}}", item["ward_id"]).replace("{{2}}", item["date"]).replace("{{3}}", timing_label(item))
        assert body == item["body"]


def test_reconciliation_uses_actual_provider_status(tmp_path, monkeypatch):
    from scripts.reconcile_alerts import reconcile
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test")
    ledger = Ledger(tmp_path / "alerts.sqlite")
    ident = ledger.reserve("a", PROFILE["phone"], alert())
    ledger.finish(ident, {"status": "queued", "message_id": "SMtest"})
    def get(*args, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"status":"delivered"}'
        return response
    monkeypatch.setattr(requests, "get", get)
    assert reconcile(ledger) == 1
    assert ledger.history("a")[0]["status"] == "delivered"
    ledger.close()


def test_budget_atomic_and_total_never_resets(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from src.alerts.budget import reserve_attempt, usage
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: reserve_attempt(), range(10)))
    assert sum(results) == 3
    assert usage()['remaining'] == 0
    monkeypatch.setenv('WHATSAPP_DAILY_LIMIT', '100')
    assert sum(reserve_attempt() for _ in range(20)) == 7
    assert usage()['total_attempts'] == 10


def test_exhausted_budget_never_calls_provider(monkeypatch):
    monkeypatch.setenv('WHATSAPP_DAILY_LIMIT', '0')
    monkeypatch.setenv('WHATSAPP_MODE', 'sandbox')
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'test')
    def forbidden(*args, **kwargs):
        pytest.fail('Provider called beyond budget')
    monkeypatch.setattr(requests, 'post', forbidden)
    assert dispatch.send_whatsapp(PROFILE['phone'], 'TEST', False)['status'] == 'budget_blocked'


def test_demo_preview_send_and_repeat(monkeypatch):
    from src.alerts import routes
    from src.alerts.budget import usage
    monkeypatch.setenv('WHATSAPP_MODE', 'sandbox')
    monkeypatch.setattr(routes, 'owned_profile', lambda auth: PROFILE)
    monkeypatch.setattr(routes.accounts, 'request', lambda *args, **kwargs: [])
    sends = []
    def send(phone, body, **kwargs):
        assert phone == PROFILE['phone']
        assert body.startswith(dispatch.REPLAY_NOTICE['gu'])
        sends.append(body)
        return dict(status='queued', message_id='SMdemo')
    monkeypatch.setattr(routes, 'send_whatsapp', send)
    auth = (PROFILE['id'], 'token')
    assert routes.demo(routes.DemoRequest(), auth)['status'] == 'preview'
    assert not sends
    assert usage()['total_attempts'] == 0
    assert routes.demo(routes.DemoRequest(send=True), auth)['status'] == 'queued'
    assert routes.demo(routes.DemoRequest(send=True), auth)['status'] == 'suppressed'
    assert len(sends) == 1


def test_demo_requires_consent(monkeypatch):
    from fastapi import HTTPException
    from src.alerts import routes
    monkeypatch.setenv('WHATSAPP_MODE', 'sandbox')
    monkeypatch.setattr(routes, 'owned_profile', lambda auth: {**PROFILE, 'whatsapp_opt_in': False})
    monkeypatch.setattr(routes.accounts, 'request', lambda *args, **kwargs: [])
    with pytest.raises(HTTPException) as error:
        routes.demo(routes.DemoRequest(send=True), (PROFILE['id'], 'token'))
    assert error.value.status_code == 409


def test_two_users_demo_goes_to_each_saved_number_and_language(monkeypatch):
    from src.alerts import routes
    monkeypatch.setenv('WHATSAPP_MODE', 'sandbox')
    profiles = {
        'first': {**PROFILE, 'id': 'first', 'phone': '+919111111111', 'preferred_language': 'hi'},
        'second': {**PROFILE, 'id': 'second', 'phone': '+919222222222', 'preferred_language': None},
    }
    monkeypatch.setattr(routes, 'owned_profile', lambda auth: profiles[auth[0]])
    monkeypatch.setattr(routes.accounts, 'request', lambda *args, **kwargs: [])
    sends = []
    def send(phone, body, **kwargs):
        sends.append((phone, kwargs['alert']['language']))
        return {'status': 'queued', 'message_id': 'SMtest'}
    monkeypatch.setattr(routes, 'send_whatsapp', send)
    for uid in profiles:
        assert routes.demo(routes.DemoRequest(send=True), (uid, 'token'))['status'] == 'queued'
    assert sends == [('+919111111111', 'hi'), ('+919222222222', 'en')]
    assert set(routes.DemoRequest.model_fields) == {'send'}  # Caller cannot choose someone else's number.


def test_worker_uses_each_profile_phone_language_and_updated_preferences(monkeypatch):
    monkeypatch.setattr('src.alerts.service.local_today', lambda: TODAY)
    monkeypatch.setattr('scripts.dispatch_alerts.is_configured', lambda: True)
    sends = []
    def send(phone, body, **kwargs):
        sends.append((phone, kwargs['alert']['language']))
        return {'status': 'queued', 'message_id': 'SMtest'}
    monkeypatch.setattr('scripts.dispatch_alerts.send_whatsapp', send)
    profiles = [{**PROFILE, 'id': 'one', 'phone': '+919111111111', 'preferred_language': 'gu'},
                {**PROFILE, 'id': 'two', 'phone': '+919222222222', 'preferred_language': None}]
    run(profiles, [], [day()], send=True)
    assert sends == [('+919111111111', 'gu'), ('+919222222222', 'en')]
    profiles[0].update(phone='+919333333333', preferred_language='hi')
    run(profiles, [], [day()], send=True)
    assert sends[-1] == ('+919333333333', 'hi')


def test_disabled_caps_still_count_attempts(monkeypatch):
    from src.alerts.budget import reserve_attempt, usage
    monkeypatch.setenv('WHATSAPP_LIMITS_ENABLED', 'false')
    monkeypatch.setenv('WHATSAPP_DAILY_LIMIT', '0')
    assert reserve_attempt()
    assert usage()['remaining'] is None
    assert usage()['total_attempts'] == 1


def test_scheduler_records_run_and_does_not_repeat(monkeypatch):
    from src.alerts import automation, accounts
    monkeypatch.setenv('ALERTS_AUTOMATION_ENABLED', 'true')
    calls = []
    monkeypatch.setattr('scripts.reconcile_alerts.reconcile', lambda ledger: 0)
    def rows(*args, **kwargs):
        calls.append(1)
        return []
    monkeypatch.setattr(accounts, 'subscribers', rows)
    automation.tick()
    automation.tick()
    assert len(calls) == 1
    assert automation.status()['last_run']['outcome'] == 'no_subscribers'


def test_scheduler_uses_forecast_and_dispatch(monkeypatch):
    import pandas as pd
    from src.alerts import automation, accounts
    monkeypatch.setenv('ALERTS_AUTOMATION_ENABLED', 'true')
    monkeypatch.setattr('scripts.reconcile_alerts.reconcile', lambda ledger: 0)
    monkeypatch.setattr(accounts, 'all_rows', lambda table, **kwargs: [PROFILE] if table == 'profiles' else [])
    monkeypatch.setattr(accounts, 'subscribers', lambda: [PROFILE])
    monkeypatch.setattr('src.weather.forecast_cache.get_cached_or_compute', lambda _: (pd.DataFrame([day()]),))
    calls = []
    def dispatch_run(profiles, family, records, send):
        assert send and records[0]['ehf'] == 5
        calls.append(1)
        return [{'status': 'queued'}]
    monkeypatch.setattr('scripts.dispatch_alerts.run', dispatch_run)
    automation.tick()
    assert calls == [1]
    assert automation.status()['last_run']['outcomes'] == ['queued']


def test_shared_phone_preserves_each_household_and_worker_targeting(monkeypatch):
    monkeypatch.setattr('src.alerts.service.local_today', lambda: TODAY)
    monkeypatch.setattr('scripts.dispatch_alerts.is_configured', lambda: True)
    captured = []
    def send(phone, body, **kwargs):
        captured.append((phone, body, kwargs['alert']['group']))
        return {'status': 'queued', 'message_id': 'SMtest'}
    monkeypatch.setattr('scripts.dispatch_alerts.send_whatsapp', send)
    profiles = [
        {**PROFILE, 'id': 'elder', 'full_name': 'Senior profile', 'age': 70},
        {**PROFILE, 'id': 'worker', 'full_name': 'Worker profile', 'age': 30, 'is_outdoor_worker': True},
        {**PROFILE, 'id': 'carer', 'full_name': 'Family profile', 'age': 30},
    ]
    family = [dict(profile_id='carer', full_name='Grandmother', age=80),
              dict(profile_id='carer', full_name='Child', age=7)]
    weather = day()
    weather['group_levels'].update(children='warning', outdoor_workers='warning', general='warning')
    run(profiles, family, [weather], send=True)
    assert len(captured) == 4
    assert {p for p, _, _ in captured} == {PROFILE['phone']}
    assert 'Senior profile' in captured[0][1] and captured[0][2] == 'elderly'
    assert 'Worker profile' in captured[1][1] and captured[1][2] == 'outdoor_workers'
    assert any('Grandmother' in b and g == 'elderly' for _, b, g in captured)
    assert any('Child' in b and g == 'children' for _, b, g in captured)
    run(profiles, family, [weather], send=True)
    assert len(captured) == 4


@pytest.mark.parametrize('language', ['en', 'hi', 'gu'])
@pytest.mark.parametrize('org', ['hospital', 'school', 'primary_health_centre', 'city_admin'])
def test_institutional_checklists_fully_translated_and_bounded(language, org):
    profile = {**PROFILE, '_account_kind': 'corporate', 'org_name': 'Demo Institution',
               'org_type': org, 'preferred_language': language}
    weather = day(level='danger')
    weather['group_levels']['children'] = 'danger'
    alerts = compose(profile, [], [weather], TODAY)
    assert alerts
    assert all(a['group'].startswith(org + ':') for a in alerts)
    assert all('Demo Institution' in a['body'] for a in alerts)
    assert all(not a['used_fallback_language'] and len(a['body']) < 1500 for a in alerts)
    assert all('whatsapp' in a['channels'] for a in alerts)


def test_city_admin_gets_one_city_checklist_not_48_broadcasts():
    profile = {**PROFILE, '_account_kind': 'corporate', 'org_name': 'City', 'org_type': 'city_admin', 'ward_id': None}
    alerts = compose(profile, [], [day(ward=str(i)) for i in range(1,49)], TODAY)
    assert 1 <= len(alerts) <= 4
    assert all(a['ward_id'] == 'citywide' for a in alerts)


def test_school_uses_children_threshold():
    profile = {**PROFILE, '_account_kind': 'corporate', 'org_name': 'School', 'org_type': 'school'}
    assert compose(profile, [], [day(level='danger')], TODAY) == []


def test_corporate_subscriptions_load_saved_metadata(monkeypatch):
    from src.alerts import accounts
    row = dict(id='corp', org_name='Hospital', contact_phone=PROFILE['phone'], ward_id='1', org_type='hospital')
    monkeypatch.setattr(accounts, 'all_rows', lambda table, **kwargs: [row] if table == 'corporate_accounts' else [PROFILE])
    monkeypatch.setattr(accounts, 'request', lambda *args, **kwargs: {'user_metadata': {'preferred_language':'hi', 'whatsapp_opt_in':True}})
    profiles = accounts.subscribers()
    assert len(profiles) == 2
    assert profiles[1]['phone'] == PROFILE['phone']
    assert profiles[1]['preferred_language'] == 'hi'
    assert profiles[1]['_account_kind'] == 'corporate'


def test_corporate_preferences_only_update_owned_account(monkeypatch):
    from src.alerts import routes
    row = dict(id='corp', org_name='Hospital', contact_phone=PROFILE['phone'], ward_id='1', org_type='hospital')
    monkeypatch.setattr(routes, 'owned_profile', lambda auth: {**row, '_account_kind':'corporate'})
    calls = []
    def request(path, token, **kwargs):
        calls.append((path, token, kwargs))
        return [row] if path.endswith('corporate_accounts') else {'user_metadata': kwargs['payload']['data']}
    monkeypatch.setattr(routes.accounts, 'request', request)
    result = routes.save_preferences(routes.Preferences(phone=PROFILE['phone'], preferred_language='gu', whatsapp_opt_in=True), ('corp','token'))
    assert result['preferred_language'] == 'gu'
    assert calls[0][2]['params'] == {'id':'eq.corp'}
    assert all(call[1] == 'token' and not call[2].get('privileged') for call in calls)


def test_provider_failures_are_not_retried_every_minute(tmp_path):
    ledger = Ledger(tmp_path / 'failed.sqlite')
    ident = ledger.reserve('a', PROFILE['phone'], alert())
    ledger.finish(ident, {'status':'failed'})
    assert ledger.reserve('a', PROFILE['phone'], alert()) is None
    ledger.close()


@pytest.mark.parametrize('language', ['en', 'hi', 'gu'])
@pytest.mark.parametrize('corporate', [False, True])
def test_dashboard_replay_uses_owned_profile_and_suppresses_repeat(monkeypatch, language, corporate):
    from src.alerts import routes
    profile = {**PROFILE, 'ward_id': '38', 'preferred_language': language, 'full_name': 'Demo senior'}
    if corporate:
        profile.update(_account_kind='corporate', org_type='city_admin', org_name='Demo City', ward_id=None)
    monkeypatch.setenv('WHATSAPP_MODE', 'sandbox')
    monkeypatch.setattr(routes, 'owned_profile', lambda auth: profile)
    def family(path, token, **kwargs):
        assert token == 'own-token' and kwargs['params'] == {'profile_id': 'eq.user-a'}
        return [] if corporate else [dict(full_name='Demo child', age=7), dict(full_name='Demo worker', age=30, is_outdoor_worker=True)]
    monkeypatch.setattr(routes.accounts, 'request', family)
    calls = []
    def send(phone, body, **kwargs):
        assert phone == PROFILE['phone']
        assert kwargs['alert']['is_replay'] and kwargs['alert']['language'] == language
        assert dispatch.REPLAY_NOTICE[language] in body
        calls.append(kwargs['alert'])
        return {'status': 'queued', 'message_id': 'SMmock'}
    monkeypatch.setattr(routes, 'send_whatsapp', send)
    result = routes.activate_dashboard_replay(('user-a', 'own-token'))
    assert result['results'] and all(r['status'] == 'queued' for r in result['results'])
    if not corporate:
        assert {'elderly', 'children', 'outdoor_workers'} <= {a['group'] for a in calls}
    count = len(calls)
    result = routes.activate_dashboard_replay(('user-a', 'own-token'))
    assert all(r['status'] == 'suppressed' for r in result['results'])
    assert len(calls) == count


def test_dashboard_replay_respects_opt_out(monkeypatch):
    from src.alerts import routes
    monkeypatch.setenv('WHATSAPP_MODE', 'sandbox')
    monkeypatch.setattr(routes, 'owned_profile', lambda auth: {**PROFILE, 'whatsapp_opt_in': False})
    def forbidden(*args, **kwargs):
        raise AssertionError('Opted out account must not send')
    monkeypatch.setattr(routes, 'send_whatsapp', forbidden)
    assert routes.activate_dashboard_replay(('user-a', 'token'))['status'] == 'opted_out'


def test_replay_can_repeat_after_cooldown_but_live_cannot(tmp_path):
    ledger = Ledger(tmp_path / 'replay.sqlite')
    replay = {**alert(), 'is_replay': True}
    first = ledger.reserve('a', PROFILE['phone'], replay, replay_cooldown_seconds=60)
    ledger.finish(first, {'status': 'read'})
    assert ledger.reserve('a', PROFILE['phone'], replay, replay_cooldown_seconds=60) is None
    ledger.db.execute("UPDATE deliveries SET created_at=datetime('now','-2 minutes')")
    ledger.db.commit()
    assert ledger.reserve('a', PROFILE['phone'], replay) is None
    second = ledger.reserve('a', PROFILE['phone'], replay, replay_cooldown_seconds=60)
    assert second
    ledger.db.execute("UPDATE deliveries SET created_at=datetime('now','-2 minutes')")
    ledger.db.commit()
    assert ledger.reserve('a', PROFILE['phone'], replay, replay_cooldown_seconds=60) is None
    ledger.close()
