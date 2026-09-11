"""
Refreshes the standing 3-5 day forecast cache (see
src/weather/forecast_cache.py). Run this on a schedule so the API and any
future SMS/WhatsApp alerting always have a current forecast ready without
recomputing it inline on every request.

Deployment options (pick whichever fits the host):
  - cron:                    */30 * * * * python scripts/refresh_forecast.py
  - Windows Task Scheduler:  run this script every 30-60 minutes
  - a simple always-on loop: see the __main__ block below

Cache freshness is enforced at read time too (see
forecast_cache.CACHE_MAX_AGE_HOURS) - this script just keeps it topped up
proactively so requests never hit a cold cache.
"""

import sys
import time

sys.path.insert(0, ".")

from src.weather.forecast_cache import save_forecast_cache


def refresh(forecast_days=5):

    cache = save_forecast_cache(forecast_days=forecast_days)

    print(
        f"Refreshed forecast cache: {forecast_days} days, "
        f"generated_at={cache['generated_at']}"
    )


if __name__ == "__main__":

    if "--loop" in sys.argv:

        REFRESH_INTERVAL_SECONDS = 30 * 60  # 30 minutes

        while True:
            refresh()
            time.sleep(REFRESH_INTERVAL_SECONDS)

    else:
        refresh()
