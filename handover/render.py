"""
Turning an alert into the actual words that get sent.

Each channel has a different shape, and the differences are not
cosmetic:

  SMS       hard length limit, and non-Latin scripts cost 70 characters
            per segment instead of 160 - a Gujarati message runs out of
            room in a third of the space. Trimmed to headline plus the
            two most important actions.

  WHATSAPP  no practical limit, supports formatting and line breaks, so
            the full advisory goes out with the reasoning included.

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


def render_whatsapp(alert):
    """Full advisory, with the reasoning, formatted for reading."""

    language = alert["language"]
    fallbacks = []

    headline, fell_back = lookup(alert["headline_key"], language)
    fallbacks.append(fell_back)

    lines = [f"*{headline}*", ""]

    for key in alert["action_keys"]:
        action, fell_back = lookup(key, language)
        fallbacks.append(fell_back)
        lines.append(f"• {action}")

    if alert.get("why_key"):
        why, fell_back = lookup(alert["why_key"], language)
        fallbacks.append(fell_back)
        lines.extend(["", f"_{why}_"])

    return {
        "channel": "whatsapp",
        "language": language,
        "body": "\n".join(lines),
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
