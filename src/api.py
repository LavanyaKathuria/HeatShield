import pandas as pd

from fastapi import FastAPI

from src.weather.weather_pipeline import (
    get_ward_weather_mortality_risk
)

from src.weather.ward_weather import (
    WardWeatherFetcher
)

from src.weather.heatwave_detector import (
    HeatwaveDetector
)

from src.vulnerability.ward_risk import (
    WardRiskModel
)

from src.mortality.mortality_engine import (
    MortalityRuleEngine
)


app = FastAPI(
    title="HEATSHIELD API",
    description=(
        "Ahmedabad heatwave risk and "
        "resource prioritization system"
    ),
    version="1.0"
)


AHMEDABAD_POPULATION = 9_432_449


# ==================================================
# ROOT
# ==================================================

@app.get("/")
def root():

    return {
        "project": "HEATSHIELD",
        "city": "Ahmedabad",
        "status": "running"
    }


# ==================================================
# WEATHER RISK
# ==================================================

@app.get("/weather-risk")
def weather_risk(
    forecast_days: int = 3
):

    (
        weather_df,
        ward_heat_risk,
        citywide_mortality
    ) = get_ward_weather_mortality_risk(
        forecast_days=forecast_days
    )

    return {

        "forecast_days":
            forecast_days,

        "wards":
            ward_heat_risk.to_dict(
                orient="records"
            ),

        "citywide_mortality": {

            "heatwave_duration_days":
                citywide_mortality[
                    "heatwave_duration_days"
                ],

            "total_excess_deaths":
                round(
                    citywide_mortality[
                        "total_excess_deaths"
                    ],
                    2
                )
        }
    }


# ==================================================
# WARD PRIORITY
# ==================================================

@app.get("/ward-priority")
def ward_priority():

    (
        weather_df,
        ward_heat_risk,
        citywide_mortality
    ) = get_ward_weather_mortality_risk(
        forecast_days=3
    )

    model = WardRiskModel()

    wards = model.predict_clusters()

    wards = model.calculate_priority_scores(
        ward_heat_risk
    )

    ranked = model.get_ranked_wards()

    return {

        "citywide_mortality": {

            "heatwave_duration_days":
                citywide_mortality[
                    "heatwave_duration_days"
                ],

            "estimated_total_excess_deaths":
                round(
                    citywide_mortality[
                        "total_excess_deaths"
                    ],
                    2
                )
        },

        "wards": ranked[
            [
                "ward_id",
                "ward_name",

                "final_priority_score",
                "final_priority_category",

                "healthcare_vulnerability",

                "hospital_count",
                "health_centre_count",
                "total_health_facilities",

                "healthcare_facilities_per_km2",

                "heat_risk",

                "city_demographic_vulnerability",

                "recommended_action"
            ]
        ].to_dict(
            orient="records"
        )
    }


# ==================================================
# HEATWAVE DETECTION
# ==================================================

@app.get("/heatwave-detection")
def heatwave_detection(
    forecast_days: int = 7
):

    fetcher = WardWeatherFetcher()

    weather = (
        fetcher.fetch_ward_forecast(
            forecast_days=forecast_days
        )
    )

    # Citywide daily average
    city_weather = (
        weather
        .groupby(
            "date",
            as_index=False
        )
        .agg({
            "tmax": "mean",
            "tmin": "mean"
        })
        .sort_values("date")
    )

    detector = HeatwaveDetector()

    events = detector.detect(
        city_weather.to_dict(
            orient="records"
        )
    )

    return {

        "forecast_days":
            forecast_days,

        "heatwave_detected":
            len(events) > 0,

        "events": events
    }


# ==================================================
# HEATWAVE PRIORITY
# ==================================================

@app.get("/heatwave-priority")
def heatwave_priority(
    forecast_days: int = 7
):

    # --------------------------------------------------
    # 1. FETCH WARD WEATHER
    # --------------------------------------------------

    fetcher = WardWeatherFetcher()

    weather = (
        fetcher.fetch_ward_forecast(
            forecast_days=forecast_days
        )
    )

    # --------------------------------------------------
    # 2. CITY WEATHER
    # --------------------------------------------------

    city_weather = (
        weather
        .groupby(
            "date",
            as_index=False
        )
        .agg({
            "tmax": "mean",
            "tmin": "mean"
        })
        .sort_values("date")
    )

    # --------------------------------------------------
    # 3. DETECT HEATWAVE
    # --------------------------------------------------

    detector = HeatwaveDetector()

    heatwave_events = detector.detect(
        city_weather.to_dict(
            orient="records"
        )
    )

    # --------------------------------------------------
    # NO HEATWAVE
    # --------------------------------------------------

    if not heatwave_events:

        return {

            "heatwave_detected":
                False,

            "message":
                "No heatwave detected in forecast.",

            "forecast_days":
                forecast_days,

            "wards": []
        }

    # --------------------------------------------------
    # 4. SELECT LONGEST EVENT
    # --------------------------------------------------

    heatwave = max(
        heatwave_events,
        key=len
    )

    heatwave_dates = {
        day["date"]
        for day in heatwave
    }

    # --------------------------------------------------
    # 5. MORTALITY ENGINE
    # --------------------------------------------------

    mortality = MortalityRuleEngine(
        AHMEDABAD_POPULATION
    )

    citywide_records = (
        city_weather[
            city_weather["date"].isin(
                heatwave_dates
            )
        ]
        .copy()
    )

    # Add lag values
    full_city_weather = (
        city_weather
        .sort_values("date")
        .reset_index(drop=True)
    )

    selected_records = []

    for date in heatwave_dates:

        matches = full_city_weather[
            full_city_weather["date"] == date
        ]

        if matches.empty:
            continue

        idx = matches.index[0]

        current = (
            full_city_weather
            .iloc[idx]
        )

        previous = (
            full_city_weather
            .iloc[idx - 1]
            if idx >= 1
            else current
        )

        two_days = (
            full_city_weather
            .iloc[idx - 2]
            if idx >= 2
            else current
        )

        selected_records.append({

            "date": date,

            "tmax":
                float(current["tmax"]),

            "tmin":
                float(current["tmin"]),

            "previous_tmax":
                float(previous["tmax"]),

            "previous_tmin":
                float(previous["tmin"]),

            "two_days_ago_tmax":
                float(two_days["tmax"]),

            "two_days_ago_tmin":
                float(two_days["tmin"])
        })

    selected_records = sorted(
        selected_records,
        key=lambda x: x["date"]
    )

    citywide_mortality = (
        mortality.calculate_heatwave_excess_deaths(
            selected_records
        )
    )

    # --------------------------------------------------
    # 6. WARD HEAT RISK
    # --------------------------------------------------

    ward_results = []

    for ward_id, group in weather.groupby(
        "ward_id"
    ):

        ward_name = (
            group["ward_name"].iloc[0]
        )

        ward_group = (
            group[
                group["date"].isin(
                    heatwave_dates
                )
            ]
            .sort_values("date")
        )

        if ward_group.empty:
            continue

        max_risk = 0.0

        for _, row in ward_group.iterrows():

            result = (
                mortality.calculate_relative_risk(
                    tmax=row["tmax"],
                    tmin=row["tmin"],
                    previous_tmax=
                        row["previous_tmax"],
                    previous_tmin=
                        row["previous_tmin"],
                    two_days_ago_tmax=
                        row["two_days_ago_tmax"],
                    two_days_ago_tmin=
                        row["two_days_ago_tmin"]
                )
            )

            risk = (
                result - 1
            ) * 100

            max_risk = max(
                max_risk,
                risk
            )

        ward_results.append({

            "ward_id":
                ward_id,

            "ward_name":
                ward_name,

            "risk_increase_percent":
                max_risk
        })

    ward_heat = pd.DataFrame(
        ward_results
    )

    # --------------------------------------------------
    # 7. NORMALIZE HEAT RISK
    # --------------------------------------------------

    max_risk = (
        ward_heat[
            "risk_increase_percent"
        ].max()
    )

    if max_risk > 0:

        ward_heat["heat_risk"] = (
            ward_heat[
                "risk_increase_percent"
            ] / max_risk
        )

    else:

        ward_heat["heat_risk"] = 0.0

    # --------------------------------------------------
    # 8. WARD MODEL
    # --------------------------------------------------

    model = WardRiskModel()

    wards = model.predict_clusters()

    wards = model.calculate_priority_scores(
        ward_heat
    )

    # --------------------------------------------------
    # 9. RECOMMENDATIONS
    # --------------------------------------------------

    def recommendation(row):

        score = (
            row["final_priority_score"]
        )

        if score >= 0.75:

            return (
                "Deploy mobile medical unit, "
                "ambulance support, temporary "
                "cooling centre and emergency "
                "water supply"
            )

        if score >= 0.60:

            return (
                "Increase ambulance coverage "
                "and establish temporary cooling "
                "and hydration support"
            )

        if score >= 0.40:

            return (
                "Increase heatwave monitoring "
                "and prepare ambulance and "
                "cooling support"
            )

        return (
            "Routine heatwave monitoring "
            "and preparedness"
        )

    wards["recommended_action"] = (
        wards.apply(
            recommendation,
            axis=1
        )
    )

    # --------------------------------------------------
    # 10. RANK
    # --------------------------------------------------

    wards = (
        wards
        .sort_values(
            "final_priority_score",
            ascending=False
        )
    )

    # --------------------------------------------------
    # 11. RESPONSE
    # --------------------------------------------------

    return {

        "heatwave_detected":
            True,

        "heatwave_start":
            min(heatwave_dates),

        "heatwave_end":
            max(heatwave_dates),

        "heatwave_duration_days":
            len(heatwave),

        "citywide_mortality": {

            "estimated_total_excess_deaths":
                round(
                    citywide_mortality[
                        "total_excess_deaths"
                    ],
                    2
                ),

            "daily_results":
                citywide_mortality[
                    "daily_results"
                ]
        },

        "wards": wards[
            [
                "ward_id",
                "ward_name",

                "final_priority_score",
                "final_priority_category",

                "healthcare_vulnerability",

                "hospital_count",
                "health_centre_count",
                "total_health_facilities",

                "healthcare_facilities_per_km2",

                "heat_risk",
                "risk_increase_percent",

                "city_demographic_vulnerability",

                "recommended_action"
            ]
        ].to_dict(
            orient="records"
        )
    }