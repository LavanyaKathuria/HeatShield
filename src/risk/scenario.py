"""
Replaying a real historical heat event, for demonstration and testing.

WHY REPLAY INSTEAD OF SYNTHESISE
--------------------------------
Demonstrating the alerting path requires a heatwave, and there usually
is not one on the day of the demo. The tempting shortcut is to invent
weather until the thresholds trip, which proves nothing: a system can be
made to alert on numbers chosen to make it alert.

So this replays days that actually happened. The May 2024 event is the
event containing the highest UTCI in the stored 1995–2024 record; May 2010 is the
one with independently measured mortality. Both run through exactly the
same climatology, burden engine and triggers as a live forecast - the
only substitution is where the weather comes from.

Anything produced here is labelled as a replay, at every layer, so a
demonstration can never be mistaken for a live warning.
"""

import pandas as pd

from src.weather.climatology import Climatology
from src.weather.heat_stress import calculate_wbgt_shade
from src.mortality.heat_burden import HeatBurdenEngine
from src.mortality.age_structure import CITY_POPULATION
from src.risk import levels

# Real events in the historical record, by peak date.
SCENARIOS = {
    # Contains the highest UTCI in the stored 1995–2024 record.
    "may_2024": ("2024-05-21", "2024-05-25"),
    # The catastrophic event, with independently measured excess deaths.
    "may_2010": ("2010-05-19", "2010-05-23"),
    # The all-time record temperature day.
    "may_2016": ("2016-05-17", "2016-05-21"),
}

DEFAULT_SCENARIO = "may_2024"


def replay(scenario=DEFAULT_SCENARIO):
    """
    Per-day group levels for a real past heat event.

    Returns the same shape the alert engine consumes from a live
    forecast, so nothing downstream needs a demo-specific code path.
    """

    if scenario not in SCENARIOS:
        raise ValueError(
            f"unknown scenario {scenario!r}; expected one of "
            f"{sorted(SCENARIOS)}"
        )

    start, end = SCENARIOS[scenario]

    climatology = Climatology()
    engine = HeatBurdenEngine(CITY_POPULATION)

    history = climatology.history
    window = history[
        (history["date"] >= pd.Timestamp(start))
        & (history["date"] <= pd.Timestamp(end))
    ].sort_values("date")

    if window.empty:
        raise ValueError(f"no historical record for {scenario}")

    # EHF needs its full run-up, so it is computed on the record as a
    # whole and then read off for the replayed days.
    from src.weather.climatology import compute_ehf_series

    ordered = history.sort_values("date").reset_index(drop=True)
    ehf_series = compute_ehf_series(
        ordered["utci_c"].to_numpy(),
        climatology.significance_series(ordered["date"]),
    )
    ehf_by_date = dict(zip(
        ordered["date"].dt.strftime("%Y-%m-%d"), ehf_series
    ))

    days = []

    for index, (_, row) in enumerate(window.iterrows()):

        date = row["date"].strftime("%Y-%m-%d")
        normal = climatology.normal_for(row["date"])
        ehf = ehf_by_date.get(date)
        ehf = None if ehf is None or pd.isna(ehf) else float(ehf)

        burden = engine.daily_burden(
            utci_c=row["utci_c"],
            utci_normal_c=normal["utci_normal"],
            ehf=ehf,
            night_temp_c=row["night_temp"],
            night_normal_c=climatology.night_normal_for(row["date"]),
        )

        wbgt = calculate_wbgt_shade(row["temp"], row["humidity"])

        group_levels = levels.group_levels(
            elderly_risk_per_100k=(
                burden["indirect_all_cause"]["by_age"]
                ["elderly"]["excess_per_100k"]
            ),
            wbgt_c=wbgt,
            utci_c=row["utci_c"],
            ehf=ehf,
            ehf_reference=climatology.ehf_reference,
            is_heat_event=bool(ehf and ehf > 0),
        )

        days.append({
            "date": date,
            "lead_days": index,
            "is_current": index == 0,
            "group_levels": group_levels,
            "is_replay": True,
            "utci_c": row["utci_c"],
            "utci_normal_c": normal["utci_normal"],
            "wbgt_c": round(wbgt, 1),
            "ehf": None if ehf is None else round(ehf, 1),
            "event_severity": climatology.severity(ehf),
            "excess_deaths": burden["indirect_all_cause"]["total"],
            "highest_risk_group": burden["highest_risk_group"],
        })

    return days



