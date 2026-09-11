"""
Pulls 30 years of year-round hourly reanalysis weather for the city centre and
builds a day-of-year UTCI climatology.

This is the missing piece that makes anomaly-based heat detection possible: it
answers "what is normal for this date here", which is what separates a heatwave
from an ordinary hot season.

Output: data/cleaned/utci_climatology.csv  (one row per day-of-year)
        data/cleaned/utci_daily_history.csv (one row per historical day)

Run: python scripts/build_climatology.py
"""

import os
import sys

import numpy as np
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.weather.heat_stress import calculate_heat_stress  # noqa: E402

LAT, LON = 23.0225, 72.5714
START_YEAR, END_YEAR = 1995, 2024

AFTERNOON_START, AFTERNOON_END = 12, 15

# Overnight recovery window (22:00-06:00 local, wrapping midnight).
NIGHT_START, NIGHT_END = 22, 6

# Years counted as "recent" when computing the normal people are
# currently acclimatised to. May mean UTCI has risen about +1.5 C across
# this record, so a flat 30-year mean understates today's normal - and
# understates how unusual a past heatwave was.
RECENT_YEARS = 15

# Half-width of the calendar window used to pool days when computing the
# normal for a given day-of-year. +/-7 days across 30 years gives ~450
# samples per day-of-year - enough for a stable 95th percentile without
# smearing the seasonal cycle.
WINDOW_DAYS = 7

OUT_DIR = "data/cleaned"
HISTORY_FILE = f"{OUT_DIR}/utci_daily_history.csv"
CLIMATOLOGY_FILE = f"{OUT_DIR}/utci_climatology.csv"
TRAILING_FILE = f"{OUT_DIR}/utci_trailing_normals.csv"


def fetch_hourly(start_date, end_date):

    session = retry(
        requests_cache.CachedSession(".cache_archive", expire_after=-1),
        retries=5,
        backoff_factor=0.4,
    )
    client = openmeteo_requests.Client(session=session)

    responses = client.weather_api(
        "https://archive-api.open-meteo.com/v1/archive",
        params={
            "latitude": LAT,
            "longitude": LON,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": [
                "temperature_2m",
                "relative_humidity_2m",
                "wind_speed_10m",
                "shortwave_radiation",
            ],
            "timezone": "Asia/Kolkata",
        },
    )

    hourly = responses[0].Hourly()

    # Timestamps come back as UTC epochs with the local offset supplied
    # separately - it has to be added, or the afternoon window lands on
    # dusk. Wind arrives in km/h and every index here wants m/s.
    times = pd.date_range(
        start=pd.Timestamp(hourly.Time(), unit="s"),
        periods=len(hourly.Variables(0).ValuesAsNumpy()),
        freq=pd.Timedelta(seconds=hourly.Interval()),
    ) + pd.Timedelta(seconds=responses[0].UtcOffsetSeconds())

    return pd.DataFrame({
        "time": times,
        "temp": hourly.Variables(0).ValuesAsNumpy(),
        "humidity": hourly.Variables(1).ValuesAsNumpy(),
        "wind": hourly.Variables(2).ValuesAsNumpy() / 3.6,
        "radiation": hourly.Variables(3).ValuesAsNumpy(),
    })


def build_daily_history():

    chunks = []

    for year_start in range(START_YEAR, END_YEAR + 1, 5):
        year_end = min(year_start + 4, END_YEAR)
        print(f"  fetching {year_start}-{year_end} ...", flush=True)
        chunks.append(
            fetch_hourly(f"{year_start}-01-01", f"{year_end}-12-31")
        )

    hourly = pd.concat(chunks, ignore_index=True).dropna()

    hourly["date"] = hourly["time"].dt.strftime("%Y-%m-%d")
    hourly["hour"] = hourly["time"].dt.hour

    afternoon = hourly[
        (hourly["hour"] >= AFTERNOON_START)
        & (hourly["hour"] <= AFTERNOON_END)
    ]

    daily = (
        afternoon
        .groupby("date")[["temp", "humidity", "wind", "radiation"]]
        .mean()
        .reset_index()
    )

    # Daily maximum over the full 24 hours - needed to re-anchor the
    # dose-response curve, which is indexed by Tmax rather than by any
    # thermal index.
    daily = daily.merge(
        hourly.groupby("date")["temp"].max().rename("tmax").reset_index(),
        on="date",
    )

    # Overnight conditions. A hot night denies the body its recovery
    # window, and every operational heat-health system that predicts
    # mortality uses a night-time term alongside the daytime peak.
    night = hourly[(hourly["hour"] >= NIGHT_START) | (hourly["hour"] <= NIGHT_END)]
    daily = daily.merge(
        night.groupby("date")["temp"].agg(["min", "mean"])
        .rename(columns={"min": "tmin", "mean": "night_temp"})
        .reset_index(),
        on="date",
    )

    print(f"  computing UTCI for {len(daily):,} days ...", flush=True)

    stress = daily.apply(
        lambda r: calculate_heat_stress(
            temp_c=r["temp"],
            relative_humidity=r["humidity"],
            wind_speed_ms=r["wind"],
            solar_radiation_wm2=r["radiation"],
        )["utci_c"],
        axis=1,
    )

    daily["utci_c"] = stress
    daily["date"] = pd.to_datetime(daily["date"])
    daily["day_of_year"] = daily["date"].dt.dayofyear
    daily["year"] = daily["date"].dt.year

    return daily[
        ["date", "year", "day_of_year", "tmax", "tmin", "night_temp",
         "temp", "humidity", "wind", "radiation", "utci_c"]
    ]


def build_climatology(daily):
    """
    For each day-of-year, pool every historical day falling within
    +/-WINDOW_DAYS on the calendar (wrapping at year end) and summarise
    the UTCI distribution.
    """

    rows = []

    for doy in range(1, 367):

        offsets = ((daily["day_of_year"] - doy + 182) % 365) - 182
        window = daily[offsets.abs() <= WINDOW_DAYS]

        if len(window) < 30:
            continue

        values = window["utci_c"].to_numpy()

        rows.append({
            "day_of_year": doy,
            "n_samples": len(values),
            "utci_mean": round(float(np.mean(values)), 2),
            "utci_p50": round(float(np.percentile(values, 50)), 2),
            "utci_p90": round(float(np.percentile(values, 90)), 2),
            "utci_p95": round(float(np.percentile(values, 95)), 2),
            "utci_p98": round(float(np.percentile(values, 98)), 2),
            "utci_sd": round(float(np.std(values)), 2),
            "night_temp_mean": round(
                float(np.mean(window["night_temp"].to_numpy())), 2
            ),
        })

    return pd.DataFrame(rows)


def build_trailing_normals(daily):
    """
    The normal "as of" each year: for year Y, the average of the
    RECENT_YEARS years before it.

    This matters twice, and for the same reason. People are acclimatised
    to the climate they have recently lived through, not to a 30-year
    average that a warming trend has pulled below present conditions -
    so a forecast issued today must be judged against recent years. And
    a past event must be judged against what was normal THEN: scoring
    the 2010 heatwave against a baseline that includes 2010-2024 makes
    it look ordinary, because the years since have caught up with it.

    One rule, applied consistently, gets both right.
    """

    rows = []

    for year in sorted(daily["year"].unique()):

        window = daily[
            (daily["year"] < year) & (daily["year"] >= year - RECENT_YEARS)
        ]

        # The earliest years have no history behind them; they borrow the
        # earliest window available rather than silently using the future.
        if window["year"].nunique() < 5:
            window = daily[daily["year"] < daily["year"].min() + RECENT_YEARS]

        for doy in range(1, 367):
            offsets = ((window["day_of_year"] - doy + 182) % 365) - 182
            near = window[offsets.abs() <= WINDOW_DAYS]

            if len(near) < 30:
                continue

            rows.append({
                "year": year,
                "day_of_year": doy,
                "utci_normal": round(float(near["utci_c"].mean()), 2),
                "night_temp_normal": round(
                    float(near["night_temp"].mean()), 2
                ),
            })

    return pd.DataFrame(rows)


if __name__ == "__main__":

    os.makedirs(OUT_DIR, exist_ok=True)

    print(f"Building {START_YEAR}-{END_YEAR} year-round UTCI climatology")

    daily = build_daily_history()
    daily.to_csv(HISTORY_FILE, index=False)
    print(f"  saved {len(daily):,} daily records -> {HISTORY_FILE}")

    climatology = build_climatology(daily)
    climatology.to_csv(CLIMATOLOGY_FILE, index=False)
    print(f"  saved {len(climatology)} day-of-year normals -> {CLIMATOLOGY_FILE}")

    trailing = build_trailing_normals(daily)
    trailing.to_csv(TRAILING_FILE, index=False)
    print(f"  saved {len(trailing):,} year-specific normals -> {TRAILING_FILE}")

    print("\nSample - the 15th of each month:")
    sample = climatology[
        climatology["day_of_year"].isin(
            pd.to_datetime(
                [f"2021-{m:02d}-15" for m in range(1, 13)]
            ).dayofyear
        )
    ]
    print(sample.to_string(index=False))
