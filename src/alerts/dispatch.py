"""
Actually sending the alerts.

SAFETY FIRST, BECAUSE THIS ONE CAN DO HARM
------------------------------------------
Every other module in this project produces numbers. This one puts a
message on a stranger's phone saying people may die. Two consequences
follow, and both are enforced here rather than left to discipline:

1. NOTHING SENDS UNLESS ASKED. `dry_run` defaults to True. A caller has
   to pass dry_run=False explicitly, and credentials have to be present
   in the environment. Forgetting either produces a preview, not a
   message.

2. A DRILL IS ALWAYS LABELLED AS A DRILL. Replayed events and tests are
   prefixed with a notice in the recipient's own language, at the top of
   the message where it cannot be missed. A realistic emergency warning
   that is not real is not a harmless demo - people act on these.

CHANNELS
--------
WhatsApp uses Twilio REST: sandbox free-form text during the reply window,
or approved language-specific templates for production notifications.
The scheduled worker requires saved opt-in before reserving any message.

SMS and voice are designed but not wired. SMS in India needs DLT
registration under the deploying organisation's own entity, which is
paperwork a prototype cannot honestly shortcut.
"""

import logging
import os
import re
import json
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Credentials come from a .env file at the project root (gitignored) so
# they survive between shells and never reach the repository. Shell
# environment variables still win, which is what a deployment wants.
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:  # pragma: no cover - dotenv is optional
    pass

CHANNEL_WHATSAPP = "whatsapp"

# Twilio's shared sandbox sender. Only numbers that have joined this
# sandbox can receive from it, which is exactly the property we want.
SANDBOX_FROM = "whatsapp:+14155238886"

ENV_ACCOUNT_SID = "TWILIO_ACCOUNT_SID"
ENV_AUTH_TOKEN = "TWILIO_AUTH_TOKEN"
ENV_FROM = "TWILIO_WHATSAPP_FROM"
ENV_JOIN_CODE = "TWILIO_SANDBOX_JOIN_CODE"


def opt_in_instructions():
    """
    What a user must do before they can receive anything.

    This exists because of a SANDBOX limitation, not a product decision.
    On the sandbox, Twilio can only message numbers that have sent it a
    join phrase - which is why a real citizen signing up in the app still
    has to do this one manual step.

    A production sender needs explicit opt-in and approved templates for
    business-initiated notifications. It does not need a sandbox join code.

    Returns None when no join code is configured, which is also what a
    production sender looks like.
    """

    join_code = os.environ.get(ENV_JOIN_CODE)

    if not join_code or os.environ.get("WHATSAPP_MODE", "sandbox") != "sandbox":
        return None

    return {
        "send_to": os.environ.get(ENV_FROM, SANDBOX_FROM).replace(
            "whatsapp:", ""
        ),
        "message": join_code,
        # Opens WhatsApp with the join message already typed, so the user
        # only has to press send. Works from a QR code or a link.
        "deep_link": (
            "https://wa.me/"
            + os.environ.get(ENV_FROM, SANDBOX_FROM)
            .replace("whatsapp:", "").replace("+", "")
            + "?text=" + join_code.replace(" ", "%20")
        ),
        "is_sandbox": True,
    }

# Shown at the top of any message that is not a live warning. Kept here
# rather than in the translation files because it must never be possible
# to ship a drill whose label failed to resolve.
DRILL_NOTICE = {
    "en": "*TEST MESSAGE - NOT A REAL WARNING*\nHistorical heatwave demonstration.",
    "hi": "*परीक्षण संदेश - यह वास्तविक चेतावनी नहीं है*\nपुरानी गर्मी की लहर का प्रदर्शन।",
    "gu": "*પરીક્ષણ સંદેશ - આ વાસ્તવિક ચેતવણી નથી*\nભૂતકાળના ગરમીના મોજાનું નિદર્શન.",
}

REPLAY_NOTICE = {
    "en": "Historical heatwave replay",
    "hi": "ऐतिहासिक हीटवेव रीप्ले",
    "gu": "ઐતિહાસિક હીટવેવ રીપ્લે",
}


class DispatchError(RuntimeError):
    pass


def is_configured():
    """True when Twilio credentials are present in the environment."""

    return bool(os.environ.get(ENV_ACCOUNT_SID)
                and os.environ.get(ENV_AUTH_TOKEN))


def _to_whatsapp(number):
    return "whatsapp:" + normalize_phone(number)


def normalize_phone(number):
    number = re.sub(r"[\s()\-]", "", (number or "").removeprefix("whatsapp:"))
    if re.fullmatch(r"[6-9]\d{9}", number):
        number = "+91" + number
    if not re.fullmatch(r"\+[1-9]\d{7,14}", number):
        raise ValueError("Use an international phone number, e.g. +919876543210")
    return number


def build_message(alert, rendered, is_drill=False):
    """
    The exact text that will be sent, drill label included.

    Separated from sending so a preview and a real send can never differ
    - the dry run shows the identical string the recipient would get.
    """

    body = rendered["whatsapp"]["body"]

    if alert.get("is_replay"):
        notice = REPLAY_NOTICE.get(alert["language"], REPLAY_NOTICE["en"])
        body = f"{notice}\n{body}"
    elif is_drill:
        notice = DRILL_NOTICE.get(alert["language"], DRILL_NOTICE["en"])
        body = f"{notice}\n\n{body}"

    return body


def send_whatsapp(to_number, body, dry_run=True, alert=None):
    """
    Send one WhatsApp message through the sandbox.

    Returns a record of what happened - including for a dry run, so the
    caller's logging path is the same either way.
    """

    record = {
        "channel": CHANNEL_WHATSAPP,
        "to": to_number,
        "characters": len(body),
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "status": None,
        "message_id": None,
        "error": None,
    }

    if dry_run:
        record["status"] = "preview"
        return record

    try:
        if not is_configured():
            raise DispatchError("Twilio credentials are not configured")
        data = dict(From=os.environ.get(ENV_FROM, SANDBOX_FROM), To=_to_whatsapp(to_number))
        mode = os.environ.get("WHATSAPP_MODE", "sandbox")
        if mode not in ("sandbox", "production"):
            raise DispatchError("WHATSAPP_MODE must be sandbox or production")
        if mode == "sandbox":
            data["Body"] = body
        else:
            if not alert or alert.get("is_replay"):
                raise DispatchError("Production templates require a live advisory")
            templates = json.loads(os.environ.get("WHATSAPP_TEMPLATES", "{}"))
            key = f"{alert['language']}.{alert['group']}.{alert['level']}"
            if key not in templates:
                raise DispatchError(f"Missing approved template: {key}")
            data["ContentSid"] = templates[key]
            from .render import timing_label
            data["ContentVariables"] = json.dumps({"1": str(alert["ward_id"]), "2": alert["date"],
                                                    "3": timing_label(alert)}, ensure_ascii=False)
        from .budget import reserve_attempt
        if not reserve_attempt():
            record["status"] = "budget_blocked"
            record["error"] = "HeatShield message cap reached; no provider request made"
            return record
        if mode == 'sandbox':
            from .budget import pace_sandbox
            pace_sandbox()
        response = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{os.environ[ENV_ACCOUNT_SID]}/Messages.json",
            auth=(os.environ[ENV_ACCOUNT_SID], os.environ[ENV_AUTH_TOKEN]),
            data=data, timeout=30,
        )
        if response.status_code >= 500:
            record["status"] = "unknown"
            record["error"] = "Provider response uncertain; reconcile before retrying"
            return record
        response.raise_for_status()
        message = response.json()
        record["status"] = message["status"]
        record["message_id"] = message["sid"]

    except (requests.Timeout, requests.ConnectionError):
        record["status"] = "unknown"
        record["error"] = "Provider response uncertain; reconcile before retrying"
    except Exception as error:
        # Never let one failed recipient stop the rest of a dispatch, and
        # never let it pass silently either.
        record["status"] = "failed"
        record["error"] = str(error) if isinstance(error, DispatchError) else "WhatsApp request failed; check configuration and provider logs"
        logger.error("WhatsApp request failed (%s)", type(error).__name__)

    return record


def dispatch(alerts_by_recipient, dry_run=True, is_drill=False):
    """
    Send a batch.

    `alerts_by_recipient` is a list of (phone, alert, rendered) triples.
    Returns one record per message, which is the delivery log: what was
    sent, to whom, when, and whether it worked.
    """

    if not dry_run and not is_configured():
        raise DispatchError(
            "refusing to send: Twilio credentials are not configured"
        )

    log = []

    for phone, alert, rendered in alerts_by_recipient:

        if CHANNEL_WHATSAPP not in alert["channels"]:
            continue

        body = build_message(alert, rendered, is_drill=is_drill)

        record = send_whatsapp(phone, body, dry_run=dry_run,
                               alert={**alert, "is_replay": is_drill or alert.get("is_replay", False)})
        record.update({
            "group": alert["group"],
            "level": alert["level"],
            "language": alert["language"],
            "ward_id": alert.get("ward_id"),
            "is_drill": is_drill,
        })
        log.append(record)

    return log
