import requests
import json

url = (
    "https://livingatlas.esri.in/server1/rest/services/"
    "Health/IN_HealthcareFacility/MapServer/0/query"
)

params = {
    "where": "state='Gujarat' AND district LIKE '%Ahmad%'",
    "outFields": "*",
    "returnGeometry": "true",
    "outSR": "4326",
    "f": "geojson"
}

response = requests.get(url, params=params, timeout=60)
response.raise_for_status()

data = response.json()

print("Features downloaded:", len(data["features"]))

with open(
    "data/raw/facilities/ahmedabad_health_facilities.geojson",
    "w",
    encoding="utf-8"
) as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(
    "\nSaved: "
    "data/raw/facilities/ahmedabad_health_facilities.geojson"
)