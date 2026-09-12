"""
Turning an alert into the actual words that get sent.

Each channel has a different shape, and the differences are not
cosmetic:

  SMS       hard length limit, and non-Latin scripts cost 70 characters
            per segment instead of 160 - a Gujarati message runs out of
            room in a third of the space. Trimmed to headline plus the
            two most important actions.

  WHATSAPP  compact headline and two priority actions. The dashboard
            retains the full advisory and reasoning.

  VOICE     a separate hand-written script, never a text message read
            aloud. A listener cannot re-read a sentence, so the script
            leads with the action, avoids lists, and repeats the single
            most important instruction at the end.

  DASHBOARD structured, so the interface can lay it out.

Language falls back to English only if a translation is genuinely
missing, and the fallback is reported rather than hidden - a silently
English alert reaching someone who reads only Gujarati is a failure the
system should be able to see.
"""

import json
import os

CONTENT_DIR = os.path.join(os.path.dirname(__file__), "content")

SUPPORTED_LANGUAGES = ("en", "hi", "gu")
FALLBACK_LANGUAGE = "en"

# Single-segment SMS length. Latin-script GSM-7 gets 160 characters;
# anything needing UCS-2 - Devanagari and Gujarati included - gets 70.
SMS_LIMIT_LATIN = 160
SMS_LIMIT_UNICODE = 70
SMS_MAX_SEGMENTS = 3

_cache = {}


def load_content(language):
    """Load and cache one language's advisory text."""

    if language not in SUPPORTED_LANGUAGES:
        language = FALLBACK_LANGUAGE

    if language not in _cache:
        path = os.path.join(CONTENT_DIR, f"{language}.json")
        with open(path, encoding="utf-8") as handle:
            _cache[language] = json.load(handle)

    return _cache[language]


def lookup(key, language):
    """
    Resolve a dotted key. Returns (text, used_fallback).

    A missing translation returns the English text and says so, rather
    than returning the raw key - a person receiving "advisory.elderly.
    watch.headline" as an SMS is worse than receiving English.
    """

    def walk(content):
        node = content
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node if isinstance(node, str) else None

    text = walk(load_content(language))
    if text is not None:
        return text, False

    fallback = walk(load_content(FALLBACK_LANGUAGE))
    return (fallback if fallback is not None else key), True


def _sms_limit(text):
    """SMS capacity depends on whether the text fits the GSM-7 alphabet."""

    is_latin = all(ord(ch) < 128 for ch in text)
    per_segment = SMS_LIMIT_LATIN if is_latin else SMS_LIMIT_UNICODE

    return per_segment * SMS_MAX_SEGMENTS


def render_sms(alert):
    """Headline plus as many actions as fit the segment budget."""

    language = alert["language"]
    fallbacks = []

    headline, fell_back = lookup(alert["headline_key"], language)
    fallbacks.append(fell_back)

    parts = [headline]
    limit = _sms_limit(headline)

    for key in alert["action_keys"]:
        action, fell_back = lookup(key, language)
        fallbacks.append(fell_back)
        candidate = " ".join(parts + [action])
        if len(candidate) > limit:
            break
        parts.append(action)

    body = " ".join(parts)

    return {
        "channel": "sms",
        "language": language,
        "body": body,
        "characters": len(body),
        "segments": -(-len(body) // (
            SMS_LIMIT_LATIN if all(ord(c) < 128 for c in body)
            else SMS_LIMIT_UNICODE
        )),
        "used_fallback_language": any(fallbacks),
    }


def timing_label(alert):
    labels = {"en": ("Forecast for", "Today"), "hi": ("पूर्वानुमान", "आज"), "gu": ("આગાહી", "આજે")}
    return labels[alert["language"]][bool(alert.get("is_current"))]


def render_whatsapp(alert, compact=True):
    """Short citizen warning; full advisory remains available in the dashboard."""

    language = alert["language"]
    fallbacks = []

    headline, fell_back = lookup(alert["headline_key"], language)
    fallbacks.append(fell_back)

    labels = {
        "en": ("Ward", "Forecast for", "Today", {"watch": "Watch", "warning": "Warning", "danger": "Danger", "extreme": "Extreme"}),
        "hi": ("वार्ड", "पूर्वानुमान", "आज", {"watch": "निगरानी", "warning": "चेतावनी", "danger": "खतरा", "extreme": "अत्यधिक खतरा"}),
        "gu": ("વોર્ડ", "આગાહી", "આજે", {"watch": "દેખરેખ", "warning": "ચેતવણી", "danger": "જોખમ", "extreme": "અત્યંત જોખમ"}),
    }
    ward_label, forecast_label, today_label, tiers = labels[language]
    timing = today_label if alert.get("is_current") else forecast_label
    lines = [f"*HeatShield — {tiers[alert['level']]}*",
             f"{ward_label} {alert.get('ward_id', '')} | {timing}: {alert['date']}",
             "", f"*{headline}*", ""]

    action_keys = alert["action_keys"]
    if compact:
        # Keep an emergency action when the advisory includes one, rather
        # than letting a brevity change remove the instruction to get help.
        emergency = next((key for key in action_keys if key.endswith('.call_108')), None)
        action_keys = action_keys[:2]
        if emergency and emergency not in action_keys:
            action_keys = [action_keys[0], emergency]
    for key in action_keys:
        action, fell_back = lookup(key, language)
        fallbacks.append(fell_back)
        lines.append(f"• {action}")

    if not compact and alert.get("why_key"):
        why, fell_back = lookup(alert["why_key"], language)
        fallbacks.append(fell_back)
        lines.extend(["", f"_{why}_"])

    if alert.get('profile_name') or any(p != 'self' for p in alert.get('applies_to', [])):
        labels = {'en': ('Profile', 'Advice for', 'you'), 'hi': ('प्रोफ़ाइल', 'सलाह इनके लिए', 'आप'), 'gu': ('પ્રોફાઇલ', 'સલાહ માટે', 'તમે')}
        account_label, for_label, self_label = labels[language]
        clean = lambda value: ' '.join(str(value).split())[:80]
        context = []
        if alert.get('profile_name'):
            context.append(f"{account_label}: {clean(alert['profile_name'])}")
        people = [self_label if p == 'self' else clean(p) for p in alert.get('applies_to', [])]
        if people:
            context.append(f"{for_label}: {', '.join(people)}")
        lines[2:2] = context
    return {
        "channel": "whatsapp",
        "language": language,
        "body": "\n".join(line for line in lines if line) if compact else "\n".join(lines),
        "used_fallback_language": any(fallbacks),
    }


def render_voice(alert):
    """
    The spoken script, plus the metadata a telephony gateway needs.

    `repeat_on_no_input` matters: an older person may not reach the phone
    before the message starts. The script is repeated once if nobody
    acknowledges, then the call ends rather than ringing back endlessly.
    """

    language = alert["language"]
    script, fell_back = lookup(alert["voice_script_key"], language)

    words = len(script.split())

    return {
        "channel": "voice",
        "language": language,
        "script": script,
        # Roughly 130 words per minute for clear, slow delivery in an
        # advisory call - deliberately slower than conversational speech.
        "estimated_seconds": round(words / 130 * 60),
        "repeat_on_no_input": True,
        "max_attempts": 2,
        "used_fallback_language": fell_back,
    }


def render_dashboard(alert):
    """Structured content for the interface to lay out itself."""

    language = alert["language"]

    headline, _ = lookup(alert["headline_key"], language)
    actions = [lookup(key, language)[0] for key in alert["action_keys"]]
    why = lookup(alert["why_key"], language)[0] if alert.get("why_key") else None

    return {
        "channel": "dashboard",
        "language": language,
        "headline": headline,
        "actions": actions,
        "why": why,
    }


_RENDERERS = {
    "sms": render_sms,
    "whatsapp": render_whatsapp,
    "voice": render_voice,
    "dashboard": render_dashboard,
}


def render(alert):
    """Render one alert for every channel it is going out on."""

    return {
        channel: _RENDERERS[channel](alert)
        for channel in alert["channels"]
        if channel in _RENDERERS
    }


def render_institution(alert):
    """An institutional checklist, ordered by when it must be actioned."""

    language = alert["language"]

    items = []
    for item in alert["checklist"]:
        text, fell_back = lookup(f"institution.{item['key']}", language)
        items.append({
            "text": text,
            "lead_time_days": item["lead_time_days"],
            "used_fallback_language": fell_back,
        })

    return {
        "language": language,
        "level": alert["level"],
        "date": alert["date"],
        "items": sorted(items, key=lambda i: -i["lead_time_days"]),
    }


def render_institution_whatsapp(alert):
    """Full role-specific checklist, split at action boundaries into small messages."""
    from datetime import date, timedelta
    labels = {
        'en': ('Institution', 'Ward', 'Heat action checklist', 'Due by'),
        'hi': ('संस्था', 'वार्ड', 'गर्मी कार्य सूची', 'इस तारीख तक'),
        'gu': ('સંસ્થા', 'વોર્ડ', 'ગરમીની કાર્ય સૂચિ', 'આ તારીખ સુધી'),
    }
    institution, ward, title, due = labels[alert['language']]
    tiers = {'en': {'watch':'Watch','warning':'Warning','danger':'Danger','extreme':'Extreme'},
             'hi': {'watch':'निगरानी','warning':'चेतावनी','danger':'खतरा','extreme':'अत्यधिक खतरा'},
             'gu': {'watch':'દેખરેખ','warning':'ચેતવણી','danger':'જોખમ','extreme':'અત્યંત જોખમ'}}
    name = ' '.join(str(alert.get('profile_name') or '').split())[:80]
    place = {'en':'Ahmedabad city', 'hi':'अहमदाबाद शहर', 'gu':'અમદાવાદ શહેર'}[alert['language']] if alert['ward_id'] == 'citywide' else f"{ward} {alert['ward_id']}"
    header = f"*HeatShield — {tiers[alert['language']][alert['level']]}*\n{institution}: {name}\n{place} | {alert['date']}\n{title}\n"
    rendered = render_institution(alert)
    bodies, body = [], header
    for item in rendered['items']:
        deadline = (date.fromisoformat(alert['date']) - timedelta(days=item['lead_time_days'])).isoformat()
        line = f"\n• {item['text']} ({due}: {deadline})\n"
        if len(body + line) > 1250 and body != header:
            bodies.append(body)
            body = header
        body += line
    bodies.append(body)
    return bodies, any(item['used_fallback_language'] for item in rendered['items'])
