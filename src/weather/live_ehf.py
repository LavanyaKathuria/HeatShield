"""
Excess Heat Factor for live forecast days.

THE PROBLEM THIS SOLVES
-----------------------
EHF needs 33 days of preceding weather: three days to form the short-term
mean, thirty before that to measure what the body has acclimatised to. A
forecast request only returns the days ahead, so the recent past has to
be fetched separately and stitched onto the front of the forecast.

CITY SCALE, NOT WARD SCALE
--------------------------
EHF is computed once for the city, not 48 times. A heatwave is a
synoptic-scale event - the wards of one city are all inside the same air
mass, and their day-to-day UTCI moves together. Pulling 33 days of hourly
history for every ward would multiply the request cost by 48 to recover
differences much smaller than the forecast's own error.

Ward-level detail is still preserved where it is real: each ward keeps
its own UTCI, its own anomaly against its own date-specific normal, and
therefore its own risk. Only the "is this an unusual event" judgement is
shared, which is the part that genuinely is city-wide.
"""

import numpy as np
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry

from src.weather.heat_stress import calculate_heat_stress
from src.weather.climatology import (
    compute_ehf_series,
    ACCLIMATISATION_WINDOW_DAYS,
    SHORT_WINDOW_DAYS,
)

CITY_LAT, CITY_LON = 23.0225, 72.5714

AFTERNOON_START_HOUR = 12
AFTERNOON_END_HOUR = 15

# Enough history for the acclimatisation window plus the short window,
# with a few days of slack for the archive's reporting lag.
LOOKBACK_DAYS = ACCLIMATISATION_WINDOW_DAYS + SHORT_WINDOW_DAYS + 7

# How far the reanalysis archive trails real time. Asking it for a date
# it does not have yet makes it reject the whole request rather than
# returning the days it does have, so the window stops short by this
# margin and the forecast model's own past covers the remainder.
ARCHIVE_LAG_DAYS = 7

# Must exceed ARCHIVE_LAG_DAYS so the two sources overlap.
FORECAST_PAST_DAYS = 14

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _client():
    session = retry(
        requests_cache.CachedSession(".cache_ehf", expire_after=6 * 3600),
        retries=5,
        backoff_factor=0.3,
    )
    return openmeteo_requests.Client(session=session)


def _afternoon_utci(response):
    """Daily afternoon UTCI series from one hourly response."""

    hourly = response.Hourly()

    times = pd.date_range(
        start=pd.Timestamp(hourly.Time(), unit="s"),
        periods=len(hourly.Variables(0).ValuesAsNumpy()),
        freq=pd.Timedelta(seconds=hourly.Interval()),
    ) + pd.Timedelta(seconds=response.UtcOffsetSeconds())

    frame = pd.DataFrame({
        "date": times.strftime("%Y-%m-%d"),
        "hour": times.hour,
        "temp": hourly.Variables(0).ValuesAsNumpy(),
        "humidity": hourly.Variables(1).ValuesAsNumpy(),
        # Served in km/h; every index here expects m/s.
        "wind": hourly.Variables(2).ValuesAsNumpy() / 3.6,
        "radiation": hourly.Variables(3).ValuesAsNumpy(),
    }).dropna()

    afternoon = frame[
        (frame["hour"] >= AFTERNOON_START_HOUR)
        & (frame["hour"] <= AFTERNOON_END_HOUR)
    ]

    daily = afternoon.groupby("date")[
        ["temp", "humidity", "wind", "radiation"]
    ].mean()

    return {
        date: calculate_heat_stress(
            temp_c=row["temp"],
            relative_humidity=row["humidity"],
            wind_speed_ms=row["wind"],
            solar_radiation_wm2=row["radiation"],
        )["utci_c"]
        for date, row in daily.iterrows()
    }


def recent_city_utci(end_date=None):
    """
    Afternoon UTCI for the LOOKBACK_DAYS days before today.

    Assembled from two sources because neither covers the whole window:
    the reanalysis archive is authoritative but lags real time, and the
    forecast model carries its own recent past. The archive is asked only
    for days it certainly has - requesting up to today makes it reject
    the ENTIRE request, not just the missing tail, which previously took
    the whole event detector down.
    """

    today = pd.Timestamp(end_date or pd.Timestamp.now().normalize())

    start = today - pd.Timedelta(days=LOOKBACK_DAYS)
    archive_end = today - pd.Timedelta(days=ARCHIVE_LAG_DAYS)

    hourly_vars = [
        "temperature_2m", "relative_humidity_2m",
        "wind_speed_10m", "shortwave_radiation",
    ]

    # The reanalysis archive lags real time by several days, so the tail
    # of the lookback window comes from the forecast model's own recent
    # past instead. Both are the same variables on the same grid.
    archive = _client().weather_api(ARCHIVE_URL, params={
        "latitude": CITY_LAT, "longitude": CITY_LON,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": archive_end.strftime("%Y-%m-%d"),
        "hourly": hourly_vars,
        "timezone": "Asia/Kolkata",
    })[0]

    series = _afternoon_utci(archive)

    # Covers the archive's lag and then some, so the two sources always
    # overlap rather than leaving a hole the EHF window would fall into.
    recent = _client().weather_api(FORECAST_URL, params={
        "latitude": CITY_LAT, "longitude": CITY_LON,
        "hourly": hourly_vars,
        "past_days": FORECAST_PAST_DAYS,
        "forecast_days": 1,
        "timezone": "Asia/Kolkata",
    })[0]

    # Forecast-model values win on overlapping dates: they are the more
    # recent analysis of the same days.
    series.update(_afternoon_utci(recent))

    return series


def ehf_for_forecast(forecast_utci_by_date, climatology, end_date=None):
    """
    EHF for each forecast day, using real recent history as the run-up.

    `forecast_utci_by_date` maps date string -> city afternoon UTCI for
    the days ahead. The significance threshold comes from the
    climatology per date, so the detector follows the season instead of
    being pinned to a May-derived annual figure. Returns date -> EHF,
    with None where the lookback is incomplete rather than a value
    computed from a short window.
    """

    history = recent_city_utci(end_date=end_date)

    combined = dict(history)
    combined.update(forecast_utci_by_date)

    dates = sorted(combined)
    values = np.array([combined[d] for d in dates], dtype=float)

    series = compute_ehf_series(
        values, climatology.significance_series(dates)
    )

    return {
        date: (None if np.isnan(value) else round(float(value), 2))
        for date, value in zip(dates, series)
        if date in forecast_utci_by_date
    }
