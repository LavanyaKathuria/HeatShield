"""
Keeps a standing 3-5 day forecast cached on disk, so the API (and later,
the alerting system) always has one ready instantly instead of recomputing
the full ward-weather + heat-stress + mortality pipeline on every request.

Design: `scripts/refresh_forecast.py` is meant to run on a schedule (cron /
Windows Task Scheduler / a simple loop - whatever the deployment allows)
and writes the cache via `save_forecast_cache`. API endpoints call
`get_cached_or_compute`, which serves the cache if it's fresh and matches
the requested forecast_days, and falls back to a live computation
(updating the cache for next time) if the cache is missing, stale, or
covers a different forecast_days.

Open-Meteo's own forecast updates roughly every few hours, so a stale
threshold of 3 hours keeps the cache meaningfully current without
recomputing (48 wards x hourly weather) on every single request.
"""

import json
import os
from datetime import datetime, timezone

import pandas as pd

from src.weather.weather_pipeline import get_ward_weather_mortality_risk


CACHE_PATH = "data/raw/weather/forecast_cache.json"
CACHE_MAX_AGE_HOURS = 3

# Bumped whenever the pipeline's output shape changes. Without this, a
# cache written by an older version stays "fresh" by age and is served
# with missing columns, which surfaces as an opaque 500 rather than as a
# stale cache - exactly what happened when the burden engine replaced the
# old mortality engine.
CACHE_SCHEMA_VERSION = 2


def _serialize(forecast_days, weather_df, ward_heat_risk, citywide_mortality, citywide_records):

    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecast_days": forecast_days,
        "weather_df": weather_df.to_dict(orient="records"),
        "ward_heat_risk": ward_heat_risk.to_dict(orient="records"),
        "citywide_mortality": citywide_mortality,
        "citywide_records": citywide_records,
    }


def save_forecast_cache(forecast_days=5):
    """
    Runs the full pipeline once and writes the result to disk. Call this
    from a scheduled job (see scripts/refresh_forecast.py), not per
    request.
    """

    (
        weather_df, ward_heat_risk, citywide_mortality, citywide_records
    ) = get_ward_weather_mortality_risk(forecast_days=forecast_days)

    payload = _serialize(
        forecast_days, weather_df, ward_heat_risk,
        citywide_mortality, citywide_records
    )

    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    return payload


def load_forecast_cache():

    if not os.path.exists(CACHE_PATH):
        return None

    with open(CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _cache_is_usable(cache, forecast_days):

    if cache is None:
        return False

    if cache.get("schema_version") != CACHE_SCHEMA_VERSION:
        return False

    if cache["forecast_days"] != forecast_days:
        return False

    generated_at = datetime.fromisoformat(cache["generated_at"])
    age_hours = (
        datetime.now(timezone.utc) - generated_at
    ).total_seconds() / 3600

    return age_hours <= CACHE_MAX_AGE_HOURS


def get_cache_generated_at():
    """
    When the currently-cached forecast was actually computed - for
    surfacing real data freshness in the UI ("as of HH:MM") instead of
    leaving it implicit.
    """

    cache = load_forecast_cache()

    return cache["generated_at"] if cache else None


def get_cached_or_compute(forecast_days=5):
    """
    Main entry point for API endpoints. Returns the same 4-tuple as
    get_ward_weather_mortality_risk - from the cache when it's fresh and
    matches forecast_days, otherwise computes live and refreshes the
    cache for next time.
    """

    cache = load_forecast_cache()

    if not _cache_is_usable(cache, forecast_days):
        cache = save_forecast_cache(forecast_days=forecast_days)

    weather_df = pd.DataFrame(cache["weather_df"])
    ward_heat_risk = pd.DataFrame(cache["ward_heat_risk"])

    return (
        weather_df,
        ward_heat_risk,
        cache["citywide_mortality"],
        cache["citywide_records"],
    )
