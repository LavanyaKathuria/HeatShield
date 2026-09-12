"""
Who gets alerted, about what, in which language, down which channel.

THE RULE THAT SHAPES EVERYTHING
-------------------------------
A person is alerted about the groups THEY belong to, or that someone in
their household belongs to - nothing else.

If a forecast crosses only the elderly threshold, then only households
containing an older person receive the elderly advisory. Everyone else
receives the general heatwave notice, or nothing at all if the general
threshold was not crossed either. A construction worker with no elderly
relatives gets the worker advisory when WBGT crosses, and silence when it
does not.

This is the difference between a warning system and a broadcast. Sending
everyone everything is how people learn to ignore all of it.

FORECAST AND NOWCAST ARE BOTH ALERTABLE
---------------------------------------
Alerts fire when a heat event is FORECAST within the next few days, and
again while one is UNDERWAY. The two read differently: a forecast says
what to do before it arrives and carries a lead time; a live alert says
what to do now. Both are produced here.

DEDUPLICATION
-------------
A five-day forecast would otherwise generate five near-identical messages
per person. Each recipient receives one message per group per event, at
the highest level that event reaches, and is only re-alerted if the event
escalates.
"""

from . import advisories
from src.risk import levels as triggers

# Channel selection. A channel is only useful if the person can act on
# what arrives through it.
CHANNEL_VOICE = "voice"
CHANNEL_WHATSAPP = "whatsapp"
CHANNEL_SMS = "sms"
CHANNEL_DASHBOARD = "dashboard"

# Age boundaries for group membership, matching the risk model's bands.
CHILD_MAX_AGE = 14
ELDERLY_MIN_AGE = 65


def groups_for_person(age=None, is_outdoor_worker=False):
    """Which risk groups a single person belongs to."""

    groups = set()

    if age is not None:
        if age <= CHILD_MAX_AGE:
            groups.add("children")
        elif age >= ELDERLY_MIN_AGE:
            groups.add("elderly")

    if is_outdoor_worker:
        groups.add("outdoor_workers")

    return groups


def groups_for_household(profile, dependents=()):
    """
    Every risk group present in a household, and who puts it there.

    A person is alerted for a group their dependent belongs to even when
    they do not belong to it themselves - the whole reason the family
    feature exists is that the person at risk often is not the person
    holding the phone.
    """

    present = {}

    own = groups_for_person(
        age=profile.get("age"),
        is_outdoor_worker=profile.get("is_outdoor_worker", False),
    )
    for group in own:
        present.setdefault(group, []).append("self")

    for dependent in dependents:
        for group in groups_for_person(
            age=dependent.get("age"),
            is_outdoor_worker=dependent.get("is_outdoor_worker", False),
        ):
            present.setdefault(group, []).append(
                dependent.get("full_name") or "family"
            )

    return present


def choose_channels(profile, level, is_vulnerable_group):
    """
    Which channels to use for one recipient.

    Voice is not a fallback for people without smartphones - it is the
    primary channel for anyone who may not read a written alert, which is
    the population this system exists to reach. It is used whenever the
    recipient is flagged low-literacy, whenever the household's alert is
    about an older person, and always at danger level.
    """

    if level == "watch":
        return [CHANNEL_DASHBOARD]
    channels = []

    wants_voice = (
        profile.get("prefers_voice")
        or profile.get("low_literacy")
        or is_vulnerable_group
        or triggers.LEVEL_RANK[level] >= triggers.LEVEL_RANK["danger"]
    )

    if wants_voice and profile.get("phone"):
        channels.append(CHANNEL_VOICE)

    if profile.get("phone"):
        channels.append(
            CHANNEL_WHATSAPP if profile.get("has_whatsapp", True)
            else CHANNEL_SMS
        )

    channels.append(CHANNEL_DASHBOARD)

    return channels


def build_citizen_alerts(profile, dependents, ward_forecast):
    """
    Every alert one citizen should receive for one ward forecast.

    `ward_forecast` is a list of per-day dicts, each carrying the group
    levels already computed by `triggers.group_levels`, plus the date and
    whether that day is a forecast or already underway.
    """

    household = groups_for_household(profile, dependents)
    language = profile.get("preferred_language") or profile.get("language") or "en"

    # Highest level each group reaches anywhere in the window, and the
    # first day it does - that day is the lead time.
    peak = {}
    for day in sorted(ward_forecast, key=lambda d: d["date"]):
        if not day.get("ehf") or not day["ehf"] > 0:
            continue
        for group, level in day["group_levels"].items():
            if level == "none":
                continue
            rank = triggers.LEVEL_RANK[level]
            if group not in peak or rank > triggers.LEVEL_RANK[peak[group]["level"]]:
                peak[group] = {
                    "level": level,
                    "date": day["date"],
                    "is_current": day.get("is_current", False),
                    "lead_days": day.get("lead_days", 0),
                }

    alerts = []

    for group, info in peak.items():

        # A group only reaches this person if their household contains it.
        # `general` is the exception - it is for everyone, by definition.
        if group != "general" and group not in household:
            continue

        advisory = advisories.citizen_advisory(group, info["level"])
        if advisory is None:
            continue

        is_vulnerable = group in ("elderly", "children")

        alerts.append({
            "group": group,
            "level": info["level"],
            "date": info["date"],
            "is_current": info["is_current"],
            "lead_days": info["lead_days"],
            "applies_to": household.get(group, ["self"]),
            "profile_name": profile.get('full_name'),
            "language": language,
            "headline_key": advisory["headline"],
            "action_keys": advisory["actions"],
            "why_key": advisory["why"],
            "voice_script_key": advisory["voice"],
            "channels": choose_channels(profile, info["level"], is_vulnerable),
            "ward_id": profile.get("ward_id"),
            "is_replay": any(day.get("is_replay", False) for day in ward_forecast),
        })

    # If a specific group already alerted this person, the general notice
    # is redundant noise on top of more precise advice.
    specific = [a for a in alerts if a["group"] != "general"]
    if specific:
        alerts = specific

    return sorted(
        alerts,
        key=lambda a: -triggers.LEVEL_RANK[a["level"]],
    )


def build_institution_alert(org_profile, ward_forecast):
    """
    The action checklist for one institution.

    Institutions are not filtered by group membership: a hospital
    prepares for whoever is coming through the door, and a school acts on
    the child trigger regardless of who else is affected. They receive
    the overall level and the full checklist for it.
    """

    peak_level = "none"
    peak_date = None
    lead_days = 0

    for day in sorted(ward_forecast, key=lambda d: d['date']):
        if not day.get('ehf') or day['ehf'] <= 0:
            continue
        level = day['group_levels'].get('children', 'none') if org_profile.get('org_type') == 'school' else triggers.overall_level(day["group_levels"])
        if triggers.LEVEL_RANK[level] > triggers.LEVEL_RANK[peak_level]:
            peak_level = level
            peak_date = day["date"]
            lead_days = day.get("lead_days", 0)

    if peak_level == "none":
        return None

    org_type = org_profile.get("org_type")
    checklist = advisories.institution_checklist(org_type, peak_level)

    if not checklist:
        return None

    return {
        "org_type": org_type,
        "level": peak_level,
        "date": peak_date,
        "lead_days": lead_days,
        "language": org_profile.get('preferred_language') or org_profile.get("language") or "en",
        "checklist": checklist,
        "channels": [CHANNEL_DASHBOARD] if peak_level == 'watch' else [CHANNEL_DASHBOARD, CHANNEL_WHATSAPP],
        "ward_id": org_profile.get("ward_id"),
        "group": org_type,
        "profile_name": org_profile.get('org_name'),
        "is_replay": any(d.get('is_replay') for d in ward_forecast),
    }


def alert_fingerprint(alert):
    """
    Identity of an alert for deduplication.

    Ward, group and level - deliberately not the date, so that the same
    event forecast on five consecutive days produces one message rather
    than five. An escalation changes the level and therefore does send
    again, which is the one repeat worth making.
    """

    return (
        alert.get("ward_id"),
        alert.get("group") or alert.get("org_type"),
        alert["level"],
    )


def suppress_already_sent(alerts, already_sent):
    """Drop alerts whose fingerprint has already gone out."""

    return [
        alert for alert in alerts
        if alert_fingerprint(alert) not in already_sent
    ]
