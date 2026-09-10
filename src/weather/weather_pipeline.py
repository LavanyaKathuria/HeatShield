import pandas as pd

from src.weather.ward_weather import WardWeatherFetcher
from src.weather.heatwave_detector import HeatwaveDetector
from src.mortality.mortality_engine import MortalityRuleEngine


AHMEDABAD_POPULATION = 9_432_449


def get_ward_weather_mortality_risk(forecast_days=3):

    # --------------------------------------------------
    # 1. FETCH WARD WEATHER
    # --------------------------------------------------

    weather_fetcher = WardWeatherFetcher()

    weather = weather_fetcher.fetch_ward_forecast(
        forecast_days=forecast_days
    )

    mortality = MortalityRuleEngine(
        AHMEDABAD_POPULATION
    )

    results = []

    # --------------------------------------------------
    # 2. CALCULATE DAILY MORTALITY RISK
    # --------------------------------------------------

    for _, row in weather.iterrows():

        mortality_result = (
            mortality.calculate_excess_deaths(
                tmax=row["tmax"],
                tmin=row["tmin"],
                previous_tmax=row["previous_tmax"],
                previous_tmin=row["previous_tmin"],
                two_days_ago_tmax=row["two_days_ago_tmax"],
                two_days_ago_tmin=row["two_days_ago_tmin"]
            )
        )

        results.append({
            "ward_id": row["ward_id"],
            "ward_name": row["ward_name"],
            "date": row["date"],

            "tmax": row["tmax"],
            "tmin": row["tmin"],

            "previous_tmax": row["previous_tmax"],
            "previous_tmin": row["previous_tmin"],

            "two_days_ago_tmax":
                row["two_days_ago_tmax"],

            "two_days_ago_tmin":
                row["two_days_ago_tmin"],

            "risk_increase_percent":
                mortality_result[
                    "risk_increase_percent"
                ]
        })

    df = pd.DataFrame(results)

    # --------------------------------------------------
    # 3. WARD HEAT RISK
    # --------------------------------------------------

    ward_heat_risk = (
        df.groupby(
            ["ward_id", "ward_name"],
            as_index=False
        )["risk_increase_percent"]
        .max()
    )

    max_risk = (
        ward_heat_risk[
            "risk_increase_percent"
        ].max()
    )

    if max_risk > 0:

        ward_heat_risk["heat_risk"] = (
            ward_heat_risk[
                "risk_increase_percent"
            ] / max_risk
        )

    else:

        ward_heat_risk["heat_risk"] = 0.0

    # --------------------------------------------------
    # 4. CITYWIDE DAILY WEATHER
    # --------------------------------------------------

    citywide_weather = (
        df.groupby(
            "date",
            as_index=False
        )
        .agg({
            "tmax": "mean",
            "tmin": "mean",
            "previous_tmax": "mean",
            "previous_tmin": "mean",
            "two_days_ago_tmax": "mean",
            "two_days_ago_tmin": "mean"
        })
        .sort_values("date")
        .reset_index(drop=True)
    )

    citywide_records = (
        citywide_weather.to_dict(
            orient="records"
        )
    )

    # --------------------------------------------------
    # 5. AUTOMATIC HEATWAVE DETECTION
    # --------------------------------------------------

    detector = HeatwaveDetector()

    heatwave = detector.get_longest_heatwave(
        citywide_records
    )

    # --------------------------------------------------
    # 6. NO HEATWAVE
    # --------------------------------------------------

    if not heatwave:

        citywide_mortality = {
            "heatwave_duration_days": 0,
            "daily_results": [],
            "total_excess_deaths": 0.0
        }

    # --------------------------------------------------
    # 7. HEATWAVE FOUND
    # --------------------------------------------------

    else:

        # Make sure the selected heatwave days have
        # the required lag temperatures.

        full_weather = citywide_weather.copy()

        heatwave_dates = {
            day["date"]
            for day in heatwave
        }

        selected_records = []

        for idx, row in full_weather.iterrows():

            if row["date"] not in heatwave_dates:
                continue

            # Previous day
            if idx >= 1:
                previous = full_weather.iloc[idx - 1]
            else:
                previous = row

            # Two days ago
            if idx >= 2:
                two_days_ago = full_weather.iloc[idx - 2]
            else:
                two_days_ago = row

            selected_records.append({
                "date": row["date"],

                "tmax": float(row["tmax"]),
                "tmin": float(row["tmin"]),

                "previous_tmax":
                    float(previous["tmax"]),

                "previous_tmin":
                    float(previous["tmin"]),

                "two_days_ago_tmax":
                    float(two_days_ago["tmax"]),

                "two_days_ago_tmin":
                    float(two_days_ago["tmin"])
            })

        citywide_mortality = (
            mortality.calculate_heatwave_excess_deaths(
                selected_records
            )
        )

    # --------------------------------------------------
    # 8. RETURN
    # --------------------------------------------------

    return (
        df,
        ward_heat_risk,
        citywide_mortality
    )


# ======================================================
# RUN DIRECTLY
# ======================================================

if __name__ == "__main__":

    (
        weather_df,
        ward_heat_risk,
        citywide_mortality
    ) = get_ward_weather_mortality_risk(
        forecast_days=3
    )

    # --------------------------------------------------
    # WEATHER
    # --------------------------------------------------

    print(
        weather_df.head(10).to_string(
            index=False
        )
    )

    print(
        "\nRows:",
        len(weather_df)
    )

    print(
        "\nWards:",
        weather_df[
            "ward_id"
        ].nunique()
    )

    # --------------------------------------------------
    # RISK
    # --------------------------------------------------

    print(
        "\nAverage heat mortality risk:",
        round(
            weather_df[
                "risk_increase_percent"
            ].mean(),
            2
        ),
        "%"
    )

    print("\nWard heat risk:")

    print(
        ward_heat_risk
        .sort_values(
            "heat_risk",
            ascending=False
        )
        .head(10)
        .to_string(index=False)
    )

    # --------------------------------------------------
    # MORTALITY
    # --------------------------------------------------

    print("\nCITYWIDE MORTALITY")

    print(
        "Duration:",
        citywide_mortality[
            "heatwave_duration_days"
        ]
    )

    print(
        "Total estimated excess deaths:",
        round(
            citywide_mortality[
                "total_excess_deaths"
            ],
            2
        )
    )

    # --------------------------------------------------
    # SAVE
    # --------------------------------------------------

    weather_df.to_csv(
        "data/raw/weather/ward_weather_mortality.csv",
        index=False
    )

    ward_heat_risk.to_csv(
        "data/final/ward_heat_risk.csv",
        index=False
    )

    print("\nSaved successfully.")