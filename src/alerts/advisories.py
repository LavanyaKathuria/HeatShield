"""
Advisory catalogue: what each audience is actually told.

DESIGN RULES
------------
1. Every advisory names a SPECIFIC ACTION with a TIME or a NUMBER.
   "Stay hydrated" is not advice; "one glass every 30 minutes, even if
   you are not thirsty" is. Vague advisories get ignored, and ignored
   advisories are worse than none because they teach people to skip the
   next one.

2. Advisories carry the REASON where the reason changes behaviour.
   Older people are told their thirst signal is unreliable, because that
   single fact is what makes the drinking schedule make sense.

3. Content is stored as KEYS, never as English strings. The translated
   text lives with the rest of the interface translations, so an alert
   and the dashboard always speak the same language, and a new language
   is a translation file rather than a code change.

4. Voice scripts are written SEPARATELY from text. A spoken message
   cannot use bullet points, cannot be re-read, and must lead with the
   action. They are shorter, use simpler words, and repeat the single
   most important instruction at the end.

5. Institutional advisories are checklists with owners and lead times,
   not warnings. A hospital does not need to be told it is hot; it needs
   to know what to stock and when.
"""

# ----------------------------------------------------------------------
# CITIZEN ADVISORIES  -  keyed by (audience, level)
# ----------------------------------------------------------------------
# `headline` is the SMS/push first line and the voice call's opening.
# `actions` are the specific instructions.
# `why` appears only where the reason drives compliance.
# `voice` is the spoken script - written, not derived.

CITIZEN_ADVISORIES = {

    # -- ELDERLY --------------------------------------------------------
    ("elderly", "watch"): {
        "headline": "advisory.elderly.watch.headline",
        "actions": [
            "advisory.elderly.watch.action.drink_schedule",
            "advisory.elderly.watch.action.stay_in_midday",
            "advisory.elderly.watch.action.daily_checkin",
        ],
        "why": "advisory.elderly.why.thirst_unreliable",
        "voice": "voice.elderly.watch",
    },
    ("elderly", "warning"): {
        "headline": "advisory.elderly.warning.headline",
        "actions": [
            "advisory.elderly.warning.action.drink_schedule",
            "advisory.elderly.warning.action.coolest_room",
            "advisory.elderly.warning.action.damp_cloth",
            "advisory.elderly.warning.action.medication_check",
            "advisory.elderly.warning.action.twice_daily_checkin",
        ],
        "why": "advisory.elderly.why.medication",
        "voice": "voice.elderly.warning",
    },
    ("elderly", "danger"): {
        "headline": "advisory.elderly.danger.headline",
        "actions": [
            "advisory.elderly.danger.action.do_not_go_out",
            "advisory.elderly.danger.action.cool_shower",
            "advisory.elderly.danger.action.someone_present",
            "advisory.elderly.danger.action.warning_signs",
            "advisory.elderly.danger.action.call_108",
        ],
        "why": "advisory.elderly.why.confusion_is_emergency",
        "voice": "voice.elderly.danger",
    },

    # -- OUTDOOR WORKERS ------------------------------------------------
    ("outdoor_workers", "watch"): {
        "headline": "advisory.worker.watch.headline",
        "actions": [
            "advisory.worker.watch.action.water_every_20",
            "advisory.worker.watch.action.shade_breaks",
            "advisory.worker.watch.action.shift_heavy_work",
        ],
        "why": "advisory.worker.why.urine_colour",
        "voice": "voice.worker.watch",
    },
    ("outdoor_workers", "warning"): {
        "headline": "advisory.worker.warning.headline",
        "actions": [
            "advisory.worker.warning.action.rest_half_hour",
            "advisory.worker.warning.action.avoid_peak_hours",
            "advisory.worker.warning.action.buddy_system",
            "advisory.worker.warning.action.ors",
            "advisory.worker.warning.action.new_workers",
        ],
        "why": "advisory.worker.why.acclimatisation",
        "voice": "voice.worker.warning",
    },
    ("outdoor_workers", "danger"): {
        "headline": "advisory.worker.danger.headline",
        "actions": [
            "advisory.worker.danger.action.stop_heavy_work",
            "advisory.worker.danger.action.reschedule",
            "advisory.worker.danger.action.warning_signs",
            "advisory.worker.danger.action.cool_first_transport_second",
        ],
        "why": "advisory.worker.why.cooling_first",
        "voice": "voice.worker.danger",
    },

    # -- CHILDREN (addressed to the parent or carer) --------------------
    ("children", "watch"): {
        "headline": "advisory.child.watch.headline",
        "actions": [
            "advisory.child.watch.action.no_midday_play",
            "advisory.child.watch.action.water_bottle",
            "advisory.child.watch.action.never_leave_in_vehicle",
        ],
        "why": "advisory.child.why.vehicle",
        "voice": "voice.child.watch",
    },
    ("children", "warning"): {
        "headline": "advisory.child.warning.headline",
        "actions": [
            "advisory.child.warning.action.indoor_only_midday",
            "advisory.child.warning.action.extra_feeds",
            "advisory.child.warning.action.watch_nappies",
            "advisory.child.warning.action.light_clothing",
        ],
        "why": "advisory.child.why.infants_cannot_tell_you",
        "voice": "voice.child.warning",
    },
    ("children", "danger"): {
        "headline": "advisory.child.danger.headline",
        "actions": [
            "advisory.child.danger.action.keep_indoors",
            "advisory.child.danger.action.cool_sponge",
            "advisory.child.danger.action.warning_signs",
            "advisory.child.danger.action.seek_care",
        ],
        "why": "advisory.child.why.rapid_deterioration",
        "voice": "voice.child.danger",
    },

    # -- GENERAL PUBLIC -------------------------------------------------
    ("general", "watch"): {
        "headline": "advisory.general.watch.headline",
        "actions": [
            "advisory.general.watch.action.plan_around_midday",
            "advisory.general.watch.action.carry_water",
            "advisory.general.watch.action.check_on_neighbours",
        ],
        "why": None,
        "voice": "voice.general.watch",
    },
    ("general", "warning"): {
        "headline": "advisory.general.warning.headline",
        "actions": [
            "advisory.general.warning.action.avoid_midday",
            "advisory.general.warning.action.hydrate",
            "advisory.general.warning.action.check_on_vulnerable",
            "advisory.general.warning.action.cooling_centres",
        ],
        "why": None,
        "voice": "voice.general.warning",
    },
    ("general", "danger"): {
        "headline": "advisory.general.danger.headline",
        "actions": [
            "advisory.general.danger.action.stay_indoors",
            "advisory.general.danger.action.no_outdoor_work",
            "advisory.general.danger.action.check_twice_daily",
            "advisory.general.danger.action.emergency_signs",
        ],
        "why": "advisory.general.why.heatstroke_is_emergency",
        "voice": "voice.general.danger",
    },
}


# ----------------------------------------------------------------------
# INSTITUTIONAL ADVISORIES  -  checklists, with lead times
# ----------------------------------------------------------------------
# `lead_time_days` says when the item should be actioned relative to the
# forecast day, so a 3-5 day forecast becomes a schedule rather than a
# warning.

INSTITUTION_ADVISORIES = {

    ("hospital", "watch"): [
        ("hospital.watch.brief_triage", 2),
        ("hospital.watch.check_ors_iv_stock", 2),
        ("hospital.watch.identify_cooling_area", 2),
    ],
    ("hospital", "warning"): [
        ("hospital.warning.surge_roster", 3),
        ("hospital.warning.cooling_area_ready", 1),
        ("hospital.warning.ice_packs_fans", 1),
        ("hospital.warning.brief_heatstroke_protocol", 1),
        ("hospital.warning.flag_dialysis_cardiac", 2),
    ],
    ("hospital", "danger"): [
        ("hospital.danger.activate_surge", 0),
        ("hospital.danger.triage_fast_track", 0),
        ("hospital.danger.extra_ambulance", 0),
        ("hospital.danger.daily_reporting", 0),
    ],

    ("school", "watch"): [
        ("school.watch.move_assembly_early", 1),
        ("school.watch.water_points", 1),
        ("school.watch.inform_parents", 1),
    ],
    ("school", "warning"): [
        ("school.warning.no_outdoor_sport", 0),
        ("school.warning.shift_timings", 2),
        ("school.warning.shaded_transport_wait", 0),
        ("school.warning.identify_at_risk_students", 1),
    ],
    ("school", "danger"): [
        ("school.danger.consider_closure", 1),
        ("school.danger.all_activity_indoors", 0),
        ("school.danger.first_aid_ready", 0),
        ("school.danger.notify_parents_pickup", 1),
    ],

    ("primary_health_centre", "watch"): [
        ("phc.watch.prepare_outreach_list", 2),
        ("phc.watch.ors_stock", 2),
    ],
    ("primary_health_centre", "warning"): [
        ("phc.warning.call_elderly_list", 1),
        ("phc.warning.brief_asha_workers", 2),
        ("phc.warning.ors_distribution", 1),
        ("phc.warning.pregnant_and_chronic", 1),
    ],
    ("primary_health_centre", "danger"): [
        ("phc.danger.door_to_door_elderly", 0),
        ("phc.danger.mobile_ors_points", 0),
        ("phc.danger.refer_early", 0),
    ],

    ("city_admin", "watch"): [
        ("city.watch.confirm_cooling_centres", 3),
        ("city.watch.water_tanker_readiness", 3),
        ("city.watch.brief_ward_officers", 2),
    ],
    ("city_admin", "warning"): [
        ("city.warning.open_cooling_centres", 1),
        ("city.warning.extend_park_hours", 1),
        ("city.warning.shift_municipal_outdoor_work", 2),
        ("city.warning.water_tankers_to_wards", 1),
        ("city.warning.public_announcement", 1),
        ("city.warning.power_grid_readiness", 2),
    ],
    ("city_admin", "danger"): [
        ("city.danger.activate_heat_action_plan", 0),
        ("city.danger.all_cooling_centres_24h", 0),
        ("city.danger.halt_outdoor_municipal_work", 0),
        ("city.danger.pre_position_ambulances", 0),
        ("city.danger.coordinate_with_hospitals", 0),
    ],
}


def citizen_advisory(audience, level):
    """The advisory for one audience at one level, or None."""

    if level in ("none", None):
        return None

    # "extreme" reuses the danger content; the level label carries the
    # escalation, and inventing a fifth register of urgency for a rare
    # case produces worse copy, not better.
    lookup = "danger" if level == "extreme" else level

    return CITIZEN_ADVISORIES.get((audience, lookup))


def institution_checklist(org_type, level):
    """Checklist items for an institution, cumulative across levels."""

    if level in ("none", None):
        return []

    lookup = "danger" if level == "extreme" else level

    order = ["watch", "warning", "danger"]
    items = []

    for band in order[: order.index(lookup) + 1]:
        items.extend(INSTITUTION_ADVISORIES.get((org_type, band), []))

    return [
        {"key": key, "lead_time_days": lead}
        for key, lead in items
    ]
