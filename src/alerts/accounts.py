"""Supabase REST access; browser requests retain the caller's RLS identity."""
import os
import requests
from . import config


def request(path, token=None, method="GET", payload=None, params=None, privileged=False):
    url = os.environ.get("SUPABASE_URL", "").rstrip("/").removesuffix("/rest/v1")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY" if privileged else "SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Backend Supabase configuration is missing")
    response = requests.request(method, url + path, headers={"apikey": key,
        "Authorization": "Bearer " + (key if privileged else token or key),
        "Prefer": "return=representation"}, json=payload, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def all_rows(table, privileged=True, params=None):
    rows, offset = [], 0
    while True:
        page = request("/rest/v1/" + table, privileged=privileged,
                       params={**(params or {}), "order": "id", "limit": 500, "offset": offset})
        rows.extend(page)
        if len(page) < 500:
            return rows
        offset += len(page)


def corporate_profile(row, user):
    """Corporate alert preferences live in the account's existing Auth metadata."""
    meta = user.get('user_metadata') or {}
    return {**row, '_account_kind': 'corporate', 'full_name': row['org_name'],
            'phone': row.get('contact_phone'),
            'preferred_language': meta.get('preferred_language') if meta.get('preferred_language') in ('en','hi','gu') else 'en',
            'whatsapp_opt_in': meta.get('whatsapp_opt_in') is True}


def subscribers():
    profiles = all_rows('profiles', params={'whatsapp_opt_in': 'eq.true'})
    for row in all_rows('corporate_accounts'):
        user = request('/auth/v1/admin/users/' + row['id'], privileged=True)
        profile = corporate_profile(row, user)
        if profile['whatsapp_opt_in']:
            profiles.append(profile)
    return profiles
