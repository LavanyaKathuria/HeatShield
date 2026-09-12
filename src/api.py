from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Literal

from src.weather.forecast_cache import (
    get_cached_or_compute,
    get_cache_generated_at,
)
from src.risk import levels
from src.alerts.routes import router as alerts_router
from src.alerts.automation import lifespan

app = FastAPI(
    lifespan=lifespan,
    title="HEATSHIELD API",
    description="Localized heat risk, mortality risk and personalised alerting",
    version="2.0",
)
app.include_router(alerts_router)

# Frontend dev server runs on a different origin. Kept to specific dev
# ports rather than "*" - widen when a real deployment domain exists.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# The problem statement asks for forecasts "3 to 5 days in advance" -
# enforced as a hard bound on every endpoint, not just a default.
MIN_FORECAST_DAYS = 3
MAX_FORECAST_DAYS = 5
DEFAULT_FORECAST_DAYS = 5


def forecast_days_param(default=DEFAULT_FORECAST_DAYS):
    return Query(
        default=default,
        ge=MIN_FORECAST_DAYS,
        le=MAX_FORECAST_DAYS,
        description="Forecast horizon in days (3-5, per the problem statement).",
    )


# Response text is never rendered here. Endpoints return stable keys and
# the caller supplies the language, so the API cannot ship English-only
# copy no matter which interface calls it.
def recommended_action(peak_utci_stress_category):

    if peak_utci_stress_category in (
        "very strong heat stress", "extreme heat stress"
    ):
        return "deploy_mobile_unit"

    if peak_utci_stress_category == "strong heat stress":
        return "increase_ambulance_cooling"

    if peak_utci_stress_category == "moderate heat stress":
        return "increase_monitoring"

    return "routine_monitoring"


WARD_FIELDS = [
    "ward_id", "ward_name", "peak_date",
    "peak_utci_c", "peak_utci_stress_category",
    "utci_normal_c", "utci_anomaly_c",
    "wbgt_shade_c", "heat_index_c",
    "ehf", "event_severity",
    "citywide_equivalent_excess_deaths",
    "elderly_per_100k", "highest_risk_group",
    "alert_level", "group_levels",
    "work_rest_key",
    "is_beyond_observed_range",
    "recommended_action_key",
]

TIMELINE_FIELDS = [
    "ward_id", "ward_name", "date",
    "utci_c", "utci_stress_category",
    "utci_normal_c", "utci_anomaly_c", "night_anomaly_c",
    "tmax", "tmin",
    "afternoon_humidity_pct", "afternoon_wind_ms", "afternoon_solar_wm2",
    "wbgt_shade_c", "heat_index_c",
    "ehf", "event_severity",
    "elderly_per_100k", "highest_risk_group",
    "alert_level", "group_levels",
    "work_rest_key",
    "recommended_action_key",
]


def _records(frame, columns):
    """
    DataFrame rows as JSON-safe dicts.

    pandas turns a Python None into NaN, and NaN is not valid JSON - it
    serialises as a bare `NaN` token that strict parsers reject, which
    surfaces as an opaque 500. Legitimately-absent values (no
    highest-risk group on a quiet day, no EHF before the lookback fills)
    are converted back to null here.
    """

    payload = frame[columns].astype(object).where(frame[columns].notna(), None)

    return payload.to_dict(orient="records")


def citywide_summary(citywide_burden):
    """
    The citywide picture.

    Mortality is reported CITYWIDE only. Ward-level death counts do not
    exist in any data source and are never produced here - wards carry
    thermal stress, anomaly and relative risk, which genuinely are
    ward-resolved.
    """

    return {
        "heatwave_detected": citywide_burden["heatwave_detected"],
        "heatwave_duration_days": citywide_burden["heatwave_duration_days"],
        "event_severity": citywide_burden["event_severity"],
        "peak_alert_level": citywide_burden["peak_alert_level"],
        "estimated_total_excess_deaths":
            citywide_burden["total_excess_deaths"],
        "estimated_total_excess_deaths_low":
            citywide_burden["total_excess_deaths_low"],
        "estimated_total_excess_deaths_high":
            citywide_burden["total_excess_deaths_high"],
        "daily": citywide_burden["daily"],
        "scope": "citywide",
        "forecast_generated_at": None if citywide_burden.get('is_replay') else get_cache_generated_at(),
    }


def _wards_payload(ward_summary):

    wards = ward_summary.copy()

    wards["recommended_action_key"] = (
        wards["peak_utci_stress_category"].apply(recommended_action)
    )

    ranked = wards.sort_values(
        "citywide_equivalent_excess_deaths", ascending=False
    )

    return _records(ranked, WARD_FIELDS)


# ==================================================
# ROOT
# ==================================================

@app.get("/")
def root():
    return {"project": "HEATSHIELD", "status": "running", "version": "2.0"}


# ==================================================
# WARD PRIORITY
# ==================================================

def risk_data(forecast_days, source):
    if source == 'may_2024':
        from src.risk.historical_dashboard import get_historical_dashboard
        return get_historical_dashboard()
    return get_cached_or_compute(forecast_days=forecast_days)


def source_metadata(source):
    if source == 'may_2024':
        from src.risk.historical_dashboard import METADATA
        return METADATA
    return {'source': 'live', 'is_replay': False}


@app.get("/ward-priority")
def ward_priority(forecast_days: int = forecast_days_param(), source: Literal['live', 'may_2024'] = 'live'):

    _, ward_summary, citywide_burden, _ = risk_data(forecast_days, source)

    return {
        "forecast_days": 5 if source == "may_2024" else forecast_days,
        "citywide": citywide_summary(citywide_burden),
        "wards": _wards_payload(ward_summary),
        "metadata": source_metadata(source),
    }


# ==================================================
# WARD FORECAST TIMELINE  (per ward, per day)
# ==================================================

@app.get("/ward-forecast-timeline")
def ward_forecast_timeline(forecast_days: int = forecast_days_param(), source: Literal['live', 'may_2024'] = 'live'):

    weather_df, _, _, _ = risk_data(forecast_days, source)

    days = weather_df.copy()
    days["recommended_action_key"] = (
        days["utci_stress_category"].apply(recommended_action)
    )

    return {
        "forecast_days": 5 if source == "may_2024" else forecast_days,
        "dates": sorted(days["date"].unique().tolist()),
        "days": _records(days, TIMELINE_FIELDS),
        "metadata": source_metadata(source),
    }


# ==================================================
# HEAT EVENT
# ==================================================

@app.get("/heat-event")
def heat_event(forecast_days: int = forecast_days_param(), source: Literal['live', 'may_2024'] = 'live'):
    """
    Whether an unusual heat event is forecast, and how severe.

    "Unusual" is measured against this city's own 30-year record, not an
    absolute temperature - which is why an ordinary hot-season afternoon
    does not register as an event.
    """

    _, ward_summary, citywide_burden, citywide_records = risk_data(forecast_days, source)

    event_days = [
        {
            "date": record["date"],
            "utci_c": record["utci_c"],
            "ehf": record["ehf"],
            "severity": record["event_severity"],
        }
        for record in citywide_records
        if record["ehf"] and record["ehf"] > 0
    ]

    return {
        "forecast_days": 5 if source == "may_2024" else forecast_days,
        "heatwave_detected": len(event_days) > 0,
        "metadata": source_metadata(source),
        "event_severity": citywide_burden["event_severity"],
        "days": event_days,
        "citywide": citywide_summary(citywide_burden),
        "wards_affected": [
            ward["ward_id"]
            for ward in _wards_payload(ward_summary)
            if ward["alert_level"] != "none"
        ],
    }


# ==================================================
# RISK LEVEL DEFINITIONS
# ==================================================

@app.get("/risk-levels")
def risk_levels():
    """
    The thresholds behind every level this API reports, published rather
    than hidden.

    A risk system that will not say what made it fire cannot be audited
    by the health department relying on it. Each group is scored on the
    measure that governs its own response - mortality is the wrong
    endpoint for most of them.
    """

    return {
        "levels": levels.LEVELS,
        "groups": {
            "elderly": {
                "metric": "excess_deaths_per_100k_per_day",
                "thresholds": levels.ELDERLY_RISK_PER_100K,
                "basis": "local event-day distribution, 30-year record",
            },
            "outdoor_workers": {
                "metric": "wbgt_c",
                "thresholds": levels.OUTDOOR_WBGT_C,
                "basis": "ISO 7243 / NIOSH work-rest limits",
            },
            "children": {
                "metric": "utci_c",
                "thresholds": levels.CHILDREN_UTCI_C,
                "basis": "official UTCI heat-stress categories",
            },
            "general": {
                "metric": "ehf_multiple_of_local_severe",
                "thresholds": levels.GENERAL_EHF_MULTIPLE,
                "basis": "Excess Heat Factor vs local 85th percentile",
            },
        },
        # Standing occupational guidance, which applies every day rather
        # than only during an event.
        "work_rest_wbgt": levels.WBGT_WORK_REST,
        "gated_on_heat_event": True,
    }





