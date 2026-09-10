from datetime import datetime, timedelta

import openmeteo_requests
import requests_cache
from retry_requests import retry


class WeatherDataFetcher:

    AHMEDABAD_LAT = 23.0225
    AHMEDABAD_LON = 72.5714

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

    def fetch_forecast(self, forecast_days=3):

        url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": self.AHMEDABAD_LAT,
            "longitude": self.AHMEDABAD_LON,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min"
            ],
            "forecast_days": forecast_days,
            "past_days": 2,
            "timezone": "Asia/Kolkata",
        }

        responses = self.client.weather_api(
            url,
            params=params
        )

        response = responses[0]

        daily = response.Daily()

        tmax = daily.Variables(0).ValuesAsNumpy()
        tmin = daily.Variables(1).ValuesAsNumpy()

        start_time = datetime.fromtimestamp(
            daily.Time()
        )

        forecast = []

        for i in range(2, len(tmax)):

            date = start_time + timedelta(days=i)

            forecast.append({
                "date": date.strftime("%Y-%m-%d"),

                "tmax": float(tmax[i]),
                "tmin": float(tmin[i]),

                "previous_tmax": float(tmax[i - 1]),
                "previous_tmin": float(tmin[i - 1]),

                "two_days_ago_tmax": float(tmax[i - 2]),
                "two_days_ago_tmin": float(tmin[i - 2]),
            })

        return forecast