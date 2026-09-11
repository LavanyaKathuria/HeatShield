"""
Smoke-check every API endpoint against a running server.

Start the server first:  python -m uvicorn src.api:app --port 8000
Then:                    python scripts/check_api.py
"""

import sys

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


failures = 0


def check(label, method, path, **kwargs):
    global failures
    try:
        response = requests.request(
            method, f"{BASE}{path}", timeout=180, **kwargs
        )
        response.raise_for_status()
        return response.json()
    except Exception as error:
        failures += 1
        print(f"  FAIL  {label}: {error}")
        return None


print(f"Checking {BASE}\n")

data = check("GET /ward-priority", "GET", "/ward-priority")
if data:
    print(f"  ok  GET  /ward-priority           wards={len(data['wards'])} "
          f"peak={data['citywide']['peak_alert_level']} "
          f"excess={data['citywide']['estimated_total_excess_deaths']}")

data = check("GET /ward-forecast-timeline", "GET", "/ward-forecast-timeline")
if data:
    print(f"  ok  GET  /ward-forecast-timeline  days={len(data['days'])} "
          f"dates={len(data['dates'])}")

data = check("GET /heat-event", "GET", "/heat-event")
if data:
    print(f"  ok  GET  /heat-event              "
          f"detected={data['heatwave_detected']} "
          f"severity={data['event_severity']}")

data = check("GET /risk-levels", "GET", "/risk-levels")
if data:
    print(f"  ok  GET  /risk-levels             "
          f"groups={len(data['groups'])} "
          f"levels={len(data['levels'])}")

print(f"\n{'all endpoints ok' if not failures else f'{failures} FAILED'}")
sys.exit(1 if failures else 0)

