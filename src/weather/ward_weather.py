import geopandas as gpd
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry
from shapely.ops import transform

from src.weather.heat_stress import calculate_heat_stress


class WardWeatherFetcher:

    WARDS_FILE = "data/raw/wards/wards_ahmedabad.geojson"
    URL = "https://api.open-meteo.com/v1/forecast"

    # Afternoon window (IST) used to represent peak daily heat stress.
    # Averaging daily humidity would dilute the actual danger window -
    # Ahmedabad's worst heat-health conditions occur in early-to-mid
    # afternoon, not as a 24h mean.
    AFTERNOON_START_HOUR = 12
    AFTERNOON_END_HOUR = 15

    # Overnight recovery window (wraps midnight).
    NIGHT_START_HOUR = 22
    NIGHT_END_HOUR = 6

    def __init__(self):

        cache_session = requests_cache.CachedSession(
            ".cache",
            expire_after=3600
        )

        retry_session = retry(
            cache_session,
            retries=5,
            backoff_factor=0.2
        )

        self.client = openmeteo_requests.Client(
            session=retry_session
        )

    def load_wards(self):

        wards = gpd.read_file(self.WARDS_FILE)

        wards = wards.to_crs(epsg=4326)

        # Fix reversed coordinates in the GeoJSON
        def swap_xy(x, y, z=None):
            return (y, x)

        wards["geometry"] = wards["geometry"].apply(
            lambda geom: transform(swap_xy, geom)
        )

        # Calculate centroid in projected CRS
        wards_projected = wards.to_crs(epsg=32643)

        centroids = wards_projected.geometry.centroid

        centroids = centroids.to_crs(epsg=4326)

        wards["latitude"] = centroids.y
        wards["longitude"] = centroids.x

        return wards

    def fetch_ward_forecast(self, forecast_days=3):

        wards = self.load_wards()

        latitudes = wards["latitude"].tolist()
        longitudes = wards["longitude"].tolist()

        params = {
            "latitude": latitudes,
            "longitude": longitudes,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min"
            ],
            "hourly": [
                "temperature_2m",
                "relative_humidity_2m",
                "wind_speed_10m",
                "shortwave_radiation"
            ],
            "forecast_days": forecast_days,
            "past_days": 2,
            "timezone": "Asia/Kolkata",
        }

        responses = self.client.weather_api(
            self.URL,
            params=params
        )

        results = []

        for ward, response in zip(
            wards.itertuples(),
            responses
        ):

            daily = response.Daily()

            tmax = daily.Variables(0).ValuesAsNumpy()
            tmin = daily.Variables(1).ValuesAsNumpy()

            start_time = pd.Timestamp(
                daily.Time(),
                unit="s"
            )

            dates = [
                (start_time + pd.Timedelta(days=i)).strftime(
                    "%Y-%m-%d"
                )
                for i in range(len(tmax))
            ]

            afternoon_heat_stress = (
                self._afternoon_heat_stress_by_date(response)
            )

            for i in range(2, len(tmax)):

                date = dates[i]

                row = {
                    "ward_id": ward.sourcewardcode,
                    "ward_name": ward.sourcewardname,
                    "date": date,

                    "tmax": round(float(tmax[i]), 2),
                    "tmin": round(float(tmin[i]), 2),

                    "previous_tmax": round(
                        float(tmax[i - 1]), 2
                    ),
                    "previous_tmin": round(
                        float(tmin[i - 1]), 2
                    ),

                    "two_days_ago_tmax": round(
                        float(tmax[i - 2]), 2
                    ),
                    "two_days_ago_tmin": round(
                        float(tmin[i - 2]), 2
                    ),
                }

                row.update(
                    afternoon_heat_stress.get(
                        date,
                        self._empty_heat_stress()
                    )
                )

                results.append(row)

        return pd.DataFrame(results)

    def _afternoon_heat_stress_by_date(self, response):
        """
        Average the afternoon (12:00-15:00 IST) temperature,
        humidity, wind, and solar radiation for one ward's hourly
        forecast, grouped by calendar date, and compute the
        corresponding heat-stress indices for each date.
        """

        hourly = response.Hourly()

        temp = hourly.Variables(0).ValuesAsNumpy()
        humidity = hourly.Variables(1).ValuesAsNumpy()
        wind = hourly.Variables(2).ValuesAsNumpy()
        radiation = hourly.Variables(3).ValuesAsNumpy()

        # The API returns UTC epoch timestamps even when a timezone is
        # requested - the offset comes back separately. Without adding it,
        # filtering on hours 12-15 selects 17:30-20:30 local time, i.e.
        # dusk, and the "peak afternoon" window silently became an
        # evening one: temperatures several degrees too low and solar
        # radiation near zero.
        times = pd.date_range(
            start=pd.Timestamp(hourly.Time(), unit="s"),
            periods=len(temp),
            freq=pd.Timedelta(seconds=hourly.Interval())
        ) + pd.Timedelta(seconds=response.UtcOffsetSeconds())

        hourly_df = pd.DataFrame({
            "date": times.strftime("%Y-%m-%d"),
            "hour": times.hour,
            "temp": temp,
            "humidity": humidity,
            # The API serves wind in km/h by default. UTCI and every
            # other index here expect m/s; feeding km/h straight in
            # overstates wind roughly 3.6x, which the UTCI polynomial
            # reads as heavy convective cooling.
            "wind": wind / 3.6,
            "radiation": radiation,
        })

        afternoon = hourly_df[
            (hourly_df["hour"] >= self.AFTERNOON_START_HOUR)
            & (hourly_df["hour"] <= self.AFTERNOON_END_HOUR)
        ]

        daily_means = (
            afternoon
            .groupby("date")[
                ["temp", "humidity", "wind", "radiation"]
            ]
            .mean()
        )

        # Overnight recovery temperature. The window and the grouping
        # must match scripts/build_climatology.py exactly, or the night
        # anomaly is measured against a differently-defined normal.
        night_means = (
            hourly_df[
                (hourly_df["hour"] >= self.NIGHT_START_HOUR)
                | (hourly_df["hour"] <= self.NIGHT_END_HOUR)
            ]
            .groupby("date")["temp"]
            .mean()
        )

        result = {}

        for date, row in daily_means.iterrows():

            heat_stress = calculate_heat_stress(
                temp_c=row["temp"],
                relative_humidity=row["humidity"],
                wind_speed_ms=row["wind"],
                solar_radiation_wm2=row["radiation"]
            )

            result[date] = {
                "afternoon_temp_c": round(row["temp"], 2),
                "afternoon_humidity_pct": round(
                    row["humidity"], 2
                ),
                "afternoon_wind_ms": round(row["wind"], 2),
                "afternoon_solar_wm2": round(
                    row["radiation"], 2
                ),
                "night_temp_c": (
                    round(float(night_means[date]), 2)
                    if date in night_means.index else None
                ),
                **heat_stress
            }

        return result

    @staticmethod
    def _empty_heat_stress():

        return {
            "afternoon_temp_c": None,
            "afternoon_humidity_pct": None,
            "afternoon_wind_ms": None,
            "afternoon_solar_wm2": None,
            "night_temp_c": None,
            "heat_index_c": None,
            "wbgt_shade_c": None,
            "mean_radiant_temp_c": None,
            "utci_c": None,
            "utci_stress_category": None,
            "utci_beyond_valid_input_range": None,
        }


if __name__ == "__main__":

    fetcher = WardWeatherFetcher()

    df = fetcher.fetch_ward_forecast(
        forecast_days=3
    )

    print(df.head(10))

    print("\nRows:", len(df))

    print("\nWards:", df["ward_id"].nunique())

    print(
        "\nTemperature range:"
        f" {df['tmin'].min():.1f}°C"
        f" - {df['tmax'].max():.1f}°C"
    )

    df.to_csv(
        "data/raw/weather/ward_weather_forecast.csv",
        index=False
    )

    print("\nSaved successfully.")