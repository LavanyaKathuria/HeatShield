"""
The live pipeline: forecast weather in, ward risk and alert levels out.

WHAT CHANGED FROM THE PREVIOUS VERSION
--------------------------------------
The old pipeline scored every day against a fixed minimum-mortality
temperature and reported excess deaths on 292 days a year, including
ordinary hot-season afternoons. It also ranked wards on a relative scale
where the worst ward was always 1.0, so a mild day and a lethal one
looked identical on the map.

This version:
  - measures each ward-day against the trailing normal for that calendar
    date, so an ordinary day returns zero;
  - adds the overnight anomaly, because a hot night denies the body its
    recovery window;
  - uses the Excess Heat Factor to decide whether an event is actually
    unusual, rather than an absolute threshold that sits below the May
    average;
  - splits burden by age and by occupation on two independent axes;
  - emits per-group alert levels, so the alert engine can target people
    by the groups they actually belong to.
"""

import logging

import pandas as pd

from src.weather.ward_weather import WardWeatherFetcher
from src.weather.climatology import Climatology
from src.weather.live_ehf import ehf_for_forecast
from src.weather.heat_stress import calculate_heat_stress
from src.mortality.heat_burden import HeatBurdenEngine
from src.mortality.age_structure import CITY_POPULATION
from src.risk import levels

logger = logging.getLogger(__name__)


def get_ward_weather_mortality_risk(forecast_days=3):

    # ------------------------------------------------------------------
    # 1. WARD WEATHER  (UTCI/WBGT/HI already computed per ward-day)
    # ------------------------------------------------------------------

    weather = WardWeatherFetcher().fetch_ward_forecast(
        forecast_days=forecast_days
    )

    climatology = Climatology()
    # ------------------------------------------------------------------
    # 2. EVENT DETECTION  (city scale - see live_ehf.py for why)
    # ------------------------------------------------------------------

    city_utci_by_date = (
        weather.groupby("date")["utci_c"].mean().round(1).to_dict()
    )

    try:
        ehf_by_date = ehf_for_forecast(city_utci_by_date, climatology)
        event_detection_failed = False
    except Exception as error:
        # A failed history fetch must not take the whole forecast down -
        # but it must not pass unnoticed either. Swallowing this silently
        # is how the event detector ran as None in production for days:
        # the archive was being asked for a date it did not have yet and
        # rejected the entire request, so every EHF was None, every
        # event-gated group stayed quiet, and the map was left being
        # coloured by the one trigger that is not gated.
        logger.error(
            "event detection unavailable, falling back to anomaly only: %s",
            error,
        )
        ehf_by_date = {date: None for date in city_utci_by_date}
        event_detection_failed = True

    return evaluate_weather(weather, climatology, ehf_by_date, event_detection_failed)


def evaluate_weather(weather, climatology, ehf_by_date, event_detection_failed=False):
    """Shared risk computation for live weather and labelled historical replay."""
    engine = HeatBurdenEngine(CITY_POPULATION)

    # ------------------------------------------------------------------
    # 3. PER WARD-DAY RISK
    # ------------------------------------------------------------------

    rows = []

    for _, row in weather.iterrows():

        date = row["date"]
        normal = climatology.normal_for(date)
        night_normal = climatology.night_normal_for(date)

        burden = engine.daily_burden(
            utci_c=row["utci_c"],
            utci_normal_c=normal["utci_normal"],
            ehf=ehf_by_date.get(date),
            night_temp_c=row.get("night_temp_c"),
            night_normal_c=night_normal,
        )

        indirect = burden["indirect_all_cause"]
        ehf = ehf_by_date.get(date)

        group_levels = levels.group_levels(
            elderly_risk_per_100k=(
                indirect["by_age"]["elderly"]["excess_per_100k"]
            ),
            wbgt_c=row["wbgt_shade_c"],
            utci_c=row["utci_c"],
            ehf=ehf,
            ehf_reference=climatology.ehf_reference,
            is_heat_event=bool(ehf and ehf > 0),
        )

        rows.append({
            "ward_id": row["ward_id"],
            "ward_name": row["ward_name"],
            "date": date,

            "tmax": row["tmax"],
            "tmin": row["tmin"],
            "afternoon_temp_c": row["afternoon_temp_c"],
            "afternoon_humidity_pct": row["afternoon_humidity_pct"],
            "afternoon_wind_ms": row["afternoon_wind_ms"],
            "afternoon_solar_wm2": row["afternoon_solar_wm2"],
            "night_temp_c": row.get("night_temp_c"),

            "heat_index_c": row["heat_index_c"],
            "wbgt_shade_c": row["wbgt_shade_c"],
            "utci_c": row["utci_c"],
            "utci_stress_category": row["utci_stress_category"],

            "utci_normal_c": burden["utci_normal_c"],
            "utci_anomaly_c": burden["utci_anomaly_c"],
            "night_anomaly_c": burden["night_anomaly_c"],
            "effective_utci_c": burden["effective_utci_c"],

            "ehf": ehf,
            "event_severity": climatology.severity(ehf),

            # City-scale burden evaluated at THIS ward's conditions.
            # It ranks wards against each other; it is not this ward's
            # death count and must never be summed across wards.
            "citywide_equivalent_excess_deaths": indirect["total"],
            "citywide_equivalent_excess_deaths_low": indirect["total_low"],
            "citywide_equivalent_excess_deaths_high": indirect["total_high"],
            "elderly_per_100k": (
                indirect["by_age"]["elderly"]["excess_per_100k"]
            ),
            "highest_risk_group": burden["highest_risk_group"],

            "alert_level": levels.overall_level(group_levels),
            "group_levels": group_levels,

            # Standing occupational guidance, produced every day whether
            # or not an event is underway - it describes the conditions
            # rather than claiming today is unusual.
            "work_rest_key": levels.work_rest_guidance(row["wbgt_shade_c"]),

            # True when the thermal index is past the highest point the
            # dose-response curve was actually fitted on. Roughly one day
            # a year. The burden is still computed - capping it would
            # understate exactly the days that kill most - but it is a
            # lower bound, not a point estimate, and must be shown as one.
            "is_beyond_observed_range": indirect["is_beyond_observed_range"],
        })

    df = pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # 4. WARD SUMMARY - each ward's worst day in the window
    # ------------------------------------------------------------------
    # One idxmax, so every peak-day field comes from the SAME day rather
    # than from independently maximised columns that could disagree.

    # Which day represents the ward must be decided by something that
    # still varies when the burden is zero. Ranking on burden alone made
    # idxmax fall back to the first row on every quiet day, so the panel
    # showed day one instead of the ward's worst day. Level first, then
    # burden, then the anomaly - which is never flat.
    ordered = df.assign(
        _rank=df["alert_level"].map(levels.LEVEL_RANK)
    ).sort_values(
        ["_rank", "citywide_equivalent_excess_deaths", "utci_anomaly_c"],
        ascending=False,
    )

    peak_idx = ordered.groupby(["ward_id", "ward_name"], sort=False).head(1).index

    ward_summary = df.loc[
        peak_idx,
        [
            "ward_id", "ward_name", "date",
            "utci_c", "utci_stress_category",
            "utci_normal_c", "utci_anomaly_c",
            "wbgt_shade_c", "heat_index_c",
            "ehf", "event_severity",
            "citywide_equivalent_excess_deaths",
            "elderly_per_100k", "highest_risk_group",
            "work_rest_key",
            "alert_level", "group_levels",
            "is_beyond_observed_range",
        ],
    ].rename(columns={
        "date": "peak_date",
        "utci_c": "peak_utci_c",
        "utci_stress_category": "peak_utci_stress_category",
    }).reset_index(drop=True)

    # ------------------------------------------------------------------
    # 5. CITYWIDE DAILY SERIES
    # ------------------------------------------------------------------

    citywide = (
        df.groupby("date", as_index=False)
        .agg({
            "tmax": "mean", "tmin": "mean",
            "afternoon_temp_c": "mean",
            "afternoon_humidity_pct": "mean",
            "afternoon_wind_ms": "mean",
            "afternoon_solar_wm2": "mean",
            "night_temp_c": "mean",
        })
        .sort_values("date")
        .reset_index(drop=True)
    )

    city_stress = citywide.apply(
        lambda r: calculate_heat_stress(
            temp_c=r["afternoon_temp_c"],
            relative_humidity=r["afternoon_humidity_pct"],
            wind_speed_ms=r["afternoon_wind_ms"],
            solar_radiation_wm2=r["afternoon_solar_wm2"],
        ),
        axis=1,
        result_type="expand",
    )

    citywide = pd.concat([citywide, city_stress], axis=1)
    citywide["ehf"] = citywide["date"].map(ehf_by_date)
    citywide["event_severity"] = citywide["ehf"].apply(climatology.severity)

    # ------------------------------------------------------------------
    # 6. CITYWIDE BURDEN
    # ------------------------------------------------------------------
    # Computed ONCE PER DAY from the city-average conditions, never by
    # summing the per-ward figures. Every ward row already carries a
    # citywide-scale burden evaluated at that ward's conditions - it
    # exists to rank wards against each other, and adding 48 of them
    # together would multiply the city's death toll by 48.

    daily_burden = []

    for record in citywide.to_dict(orient="records"):
        normal = climatology.normal_for(record["date"])
        burden = engine.daily_burden(
            utci_c=record["utci_c"],
            utci_normal_c=normal["utci_normal"],
            ehf=record["ehf"],
            night_temp_c=record.get("night_temp_c"),
            night_normal_c=climatology.night_normal_for(record["date"]),
        )
        indirect = burden["indirect_all_cause"]

        record["excess_deaths"] = indirect["total"]
        record["excess_deaths_low"] = indirect["total_low"]
        record["excess_deaths_high"] = indirect["total_high"]
        record["by_age"] = indirect["by_age"]
        record["by_occupation"] = indirect["by_occupation"]
        record["direct_heat_illness"] = burden["direct_heat_illness"]
        record["highest_risk_group"] = burden["highest_risk_group"]

        daily_burden.append(record)

    citywide_records = daily_burden

    event_days = [
        record for record in citywide_records
        if record["ehf"] and record["ehf"] > 0
    ]

    severity_order = ["none", "low_intensity", "severe", "extreme"]

    citywide_burden = {
        "heatwave_detected": len(event_days) > 0,
        "heatwave_duration_days": len(event_days),
        "event_severity": max(
            (record["event_severity"] for record in citywide_records),
            key=severity_order.index,
            default="none",
        ),
        "total_excess_deaths": round(
            sum(record["excess_deaths"] for record in citywide_records), 1
        ),
        "total_excess_deaths_low": round(
            sum(record["excess_deaths_low"] for record in citywide_records), 1
        ),
        "total_excess_deaths_high": round(
            sum(record["excess_deaths_high"] for record in citywide_records), 1
        ),
        "event_detection_failed": event_detection_failed,
        "peak_alert_level": max(
            df["alert_level"],
            key=lambda level: levels.LEVEL_RANK[level],
        ),
        "daily": [
            {
                "date": record["date"],
                "utci_c": record["utci_c"],
                "ehf": record["ehf"],
                "event_severity": record["event_severity"],
                "excess_deaths": record["excess_deaths"],
                "excess_deaths_low": record["excess_deaths_low"],
                "excess_deaths_high": record["excess_deaths_high"],
                "highest_risk_group": record["highest_risk_group"],
            }
            for record in citywide_records
        ],
    }

    return df, ward_summary, citywide_burden, citywide_records


if __name__ == "__main__":

    df, wards, burden, records = get_ward_weather_mortality_risk(
        forecast_days=5
    )

    print(df.head(8).to_string(index=False))
    print("\nwards:", df["ward_id"].nunique(), " rows:", len(df))
    print("\ncitywide:", burden)








