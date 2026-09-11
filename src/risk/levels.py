"""
What fires an alert, and for whom.

ONE GATE
--------
Every alert level in this module is gated on the heat event. If the day
is not unusual for the place and date, nothing fires - no exceptions.

An earlier version left the occupational and child triggers ungated, on
the reasoning that a work/rest cycle matters on any hot day. That was
wrong, and it produced exactly the failure it deserved: on an ordinary
September afternoon the event test said "no event", the burden said
"zero deaths", and the map still painted 45 of 48 wards amber because an
ungated WBGT threshold sat in the middle of a 0.6C spread. Four parts of
the system, three different answers.

Work/rest guidance is still produced every day - see
`work_rest_guidance` below - but it is GUIDANCE, not an alert. The
distinction matters: guidance is a standing fact about the climate,
while an alert is a claim that today is different.

DIFFERENT GROUPS, DIFFERENT MEASURES
------------------------------------
Every group's mortality risk is the same attributable fraction times its
own baseline, so a single shared threshold would activate all of them at
once or none of them. Each group is therefore triggered on the measure
that governs the action we actually want taken:

  ELDERLY          excess mortality risk per 100,000. The endpoint
                   really is death, and it arrives first for them.
  OUTDOOR WORKERS  WBGT, the occupational heat-exposure standard.
  CHILDREN         thermal stress, which governs safe outdoor activity.
  GENERAL PUBLIC   event severity itself.
"""

# ----------------------------------------------------------------------
# ELDERLY - excess deaths per 100,000 per day
# ----------------------------------------------------------------------
# Set from the distribution of elderly risk ON EVENT DAYS across this
# city's 30-year record (241 event days): the lower quartile, the median,
# and the top decile. So the three levels read as "milder than most
# events here", "a typical event", and "worse than nine events in ten".
#
# These are RESPONSE TIERS calibrated on the local event distribution,
# not clinical thresholds - there is no death rate at which medicine says
# a different treatment begins. Saying so is the point; the previous
# version quietly chose numbers that produced a comfortable alert
# frequency and presented them as if they meant something.
#
# Firing rates: 5.9, 4.0 and 0.8 days per year. The three worst events in
# the record - May 2010, May 2024 and May 2016 - all reach `danger`.
#
# NOTE: these depend on the baseline death rate. If CITY_POPULATION or
# BASELINE_DEATHS_PER_LAKH_PER_DAY changes, re-derive them; they were
# silently left behind once already when the baseline was corrected.
ELDERLY_RISK_PER_100K = {
    "watch": 1.7,
    "warning": 4.1,
    "danger": 11.1,
}

# ----------------------------------------------------------------------
# OUTDOOR WORKERS - WBGT, degrees C
# ----------------------------------------------------------------------
# ISO 7243 / NIOSH work-rest limits for acclimatised workers at moderate
# workload. Real published occupational limits, not local percentiles.
#
# The previous values (34/35/36) were this city's 90th/95th/99th WBGT
# percentiles, chosen because the textbook numbers "fired too often".
# That was backwards: the textbook numbers fire on more than half the
# year here because outdoor work in this climate genuinely does exceed
# international heat limits for more than half the year. Moving the
# threshold to hide that was changing the answer because we disliked it.
WBGT_WORK_REST = {
    "continuous": 28.0,     # below this, normal work
    "75_25": 29.4,          # 45 min work / 15 min rest per hour
    "50_50": 31.1,          # 30 / 30
    "25_75": 32.2,          # 15 / 45 - essential work only
}

# Alert bands for outdoor workers, used only once an event is underway.
OUTDOOR_WBGT_C = {
    "watch": WBGT_WORK_REST["75_25"],
    "warning": WBGT_WORK_REST["50_50"],
    "danger": WBGT_WORK_REST["25_75"],
}

# ----------------------------------------------------------------------
# CHILDREN - thermal stress, degrees C
# ----------------------------------------------------------------------
# The official UTCI heat-stress category boundaries (Brode et al. 2012):
# strong / very strong / extreme heat stress. Published category edges
# rather than local percentiles, for the same reason as above.
CHILDREN_UTCI_C = {
    "watch": 38.0,
    "warning": 46.0,
    "danger": 50.0,
}

# ----------------------------------------------------------------------
# GENERAL PUBLIC - event severity
# ----------------------------------------------------------------------
# Multiples of the local 85th-percentile positive Excess Heat Factor,
# which is the yardstick the heatwave detector already uses.
GENERAL_EHF_MULTIPLE = {
    "watch": 0.0,
    "warning": 1.0,
    "danger": 3.0,
}

LEVELS = ["none", "watch", "warning", "danger", "extreme"]
LEVEL_RANK = {level: i for i, level in enumerate(LEVELS)}


def _level_from(value, thresholds):
    """Highest band whose threshold this value clears."""

    if value is None:
        return "none"

    level = "none"
    for band in ("watch", "warning", "danger"):
        if value >= thresholds[band]:
            level = band

    return level


def work_rest_guidance(wbgt_c):
    """
    Recommended work/rest split for outdoor work at this WBGT.

    Produced EVERY day, event or not, because it is a fact about the
    conditions rather than a claim that today is unusual. In this climate
    it will recommend rest breaks for a large part of the year - that is
    the honest answer, not a calibration failure.

    Returns a key for translation, never rendered text.
    """

    if wbgt_c is None:
        return None

    if wbgt_c >= WBGT_WORK_REST["25_75"]:
        return "work_rest.25_75"
    if wbgt_c >= WBGT_WORK_REST["50_50"]:
        return "work_rest.50_50"
    if wbgt_c >= WBGT_WORK_REST["75_25"]:
        return "work_rest.75_25"
    if wbgt_c >= WBGT_WORK_REST["continuous"]:
        return "work_rest.caution"

    return "work_rest.normal"


def group_levels(elderly_risk_per_100k, wbgt_c, utci_c, ehf,
                 ehf_reference, is_heat_event):
    """
    The alert level for each group on one day in one place.

    `is_heat_event` gates everything. A day that is not unusual for this
    place and date produces no alerts at all, however hot it is in
    absolute terms - because in this climate "hot" is most of the year,
    and a warning that fires most of the year is not a warning.
    """

    if not is_heat_event:
        return {group: "none" for group in
                ("elderly", "outdoor_workers", "children", "general")}

    ratio = (ehf / ehf_reference) if (ehf and ehf_reference) else 0.0

    return {
        "elderly": _level_from(elderly_risk_per_100k, ELDERLY_RISK_PER_100K),
        "outdoor_workers": _level_from(wbgt_c, OUTDOOR_WBGT_C),
        "children": _level_from(utci_c, CHILDREN_UTCI_C),
        "general": _level_from(ratio, GENERAL_EHF_MULTIPLE),
    }


def overall_level(levels):
    """The headline level: the worst any group is facing."""

    return max(levels.values(), key=lambda level: LEVEL_RANK[level])


def activated_groups(levels):
    """Groups at or above watch, worst first."""

    active = [group for group, level in levels.items() if level != "none"]

    return sorted(active, key=lambda group: -LEVEL_RANK[levels[group]])
