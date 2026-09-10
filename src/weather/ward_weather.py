import geopandas as gpd
import pandas as pd
import openmeteo_requests
import requests_cache
from retry_requests import retry
from shapely.ops import transform


class WardWeatherFetcher:

    WARDS_FILE = "data/raw/wards/wards_ahmedabad.geojson"
    URL = "https://api.open-meteo.com/v1/forecast"

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

            for i in range(2, len(tmax)):

                date = start_time + pd.Timedelta(days=i)

                results.append({
                    "ward_id": ward.sourcewardcode,
                    "ward_name": ward.sourcewardname,
                    "date": date.strftime("%Y-%m-%d"),

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
                })

        return pd.DataFrame(results)


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