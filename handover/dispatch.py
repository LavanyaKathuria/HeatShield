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
WhatsApp is live, through the Twilio Sandbox: no WhatsApp Business
Account, no template approval, and recipients opt in by messaging a join
code to the sandbox number. That opt-in is doing real work - it means we
only ever message someone who asked us to.

SMS and voice are designed but not wired. SMS in India needs DLT
registration under the deploying organisation's own entity, which is
paperwork a prototype cannot honestly shortcut.
"""

import logging
import os
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

    A production WhatsApp Business sender has no join code: the phone
    number given at signup is enough. So this whole function disappears
    when the deployment stops being a prototype, and nothing else changes.

    Returns None when no join code is configured, which is also what a
    production sender looks like.
    """

    join_code = os.environ.get(ENV_JOIN_CODE)

    if not join_code:
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
    "en": "*TEST MESSAGE - NOT A REAL WARNING*\nThis is a demonstration "
          "using a real past heatwave (May 2024).",
    "hi": "*परीक्षण संदेश - यह वास्तविक चेतावनी नहीं है*\nयह मई 2024 की "
          "वास्तविक गर्मी की लहर का प्रदर्शन है।",
    "gu": "*પરીક્ષણ સંદેશ - આ વાસ્તવિક ચેતવણી નથી*\nઆ મે 2024 ના વાસ્તવિક "
          "ગરમીના મોજાનું નિદર્શન છે.",
}


class DispatchError(RuntimeError):
    pass


def is_configured():
    """True when Twilio credentials are present in the environment."""

    return bool(os.environ.get(ENV_ACCOUNT_SID)
                and os.environ.get(ENV_AUTH_TOKEN))


def _client():
    if not is_configured():
        raise DispatchError(
            f"set {ENV_ACCOUNT_SID} and {ENV_AUTH_TOKEN} in the environment"
        )

    from twilio.rest import Client

    return Client(os.environ[ENV_ACCOUNT_SID], os.environ[ENV_AUTH_TOKEN])


def _to_whatsapp(number):
    number = number.strip()
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


def build_message(alert, rendered, is_drill=False):
    """
    The exact text that will be sent, drill label included.

    Separated from sending so a preview and a real send can never differ
    - the dry run shows the identical string the recipient would get.
    """

    body = rendered["whatsapp"]["body"]

    if is_drill:
        notice = DRILL_NOTICE.get(alert["language"], DRILL_NOTICE["en"])
        body = f"{notice}\n\n{body}"

    return body


def send_whatsapp(to_number, body, dry_run=True):
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
        message = _client().messages.create(
            from_=os.environ.get(ENV_FROM, SANDBOX_FROM),
            to=_to_whatsapp(to_number),
            body=body,
        )
        record["status"] = message.status
        record["message_id"] = message.sid

    except Exception as error:
        # Never let one failed recipient stop the rest of a dispatch, and
        # never let it pass silently either.
        record["status"] = "failed"
        record["error"] = str(error)
        logger.error("WhatsApp send to %s failed: %s", to_number, error)

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

        record = send_whatsapp(phone, body, dry_run=dry_run)
        record.update({
            "group": alert["group"],
            "level": alert["level"],
            "language": alert["language"],
            "ward_id": alert.get("ward_id"),
            "is_drill": is_drill,
        })
        log.append(record)

    return log
