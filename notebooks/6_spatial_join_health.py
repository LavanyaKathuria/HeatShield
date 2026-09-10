import pandas as pd
import geopandas as gpd
from shapely.ops import transform

# --------------------------------------------------
# 1. Load health facilities
# --------------------------------------------------

health = gpd.read_file(
    "data/raw/facilities/ahmedabad_health_facilities.geojson"
)

print("Health facilities loaded:", len(health))
print("Health facility types:")
print(health["facilitytype"].value_counts().to_string())


# --------------------------------------------------
# 2. Load current 48 AMC wards
# --------------------------------------------------

wards = gpd.read_file(
    "data/raw/wards/wards_ahmedabad.geojson"
)

print("\nWards loaded:", len(wards))
print("Original CRS:", wards.crs)


# --------------------------------------------------
# 3. Correct ward geometry
# --------------------------------------------------
# The source GeoJSON has latitude/longitude axes swapped.

def swap_xy(x, y, z=None):
    return (y, x)

wards["geometry"] = wards["geometry"].apply(
    lambda geom: transform(swap_xy, geom)
)

wards = wards[
    [
        "ward_lgd_code",
        "ward_lgd_name",
        "sourcewardname",
        "sourcewardcode",
        "geometry"
    ]
].copy()

wards = wards.set_crs(
    "EPSG:4326",
    allow_override=True
)


# --------------------------------------------------
# 4. Make sure health facilities use EPSG:4326
# --------------------------------------------------

health = health.to_crs("EPSG:4326")

print("\nWard CRS:", wards.crs)
print("Health CRS:", health.crs)


# --------------------------------------------------
# 5. Spatial join
# --------------------------------------------------

health_with_wards = gpd.sjoin(
    health,
    wards,
    how="left",
    predicate="within"
)


# --------------------------------------------------
# 6. Check unmatched facilities
# --------------------------------------------------

unmatched = health_with_wards[
    health_with_wards["sourcewardcode"].isna()
]

print(
    "\nUnmatched health facilities:",
    len(unmatched),
    "/",
    len(health_with_wards)
)


# --------------------------------------------------
# 7. Show sample
# --------------------------------------------------

print("\nSample joined facilities:")

print(
    health_with_wards[
        [
            "facilityname",
            "facilitytype",
            "locality",
            "sourcewardcode",
            "sourcewardname"
        ]
    ].head(15).to_string(index=False)
)


# --------------------------------------------------
# 8. Count facilities by ward + original type
# --------------------------------------------------

ward_health_type = (
    health_with_wards
    .dropna(subset=["sourcewardcode"])
    .groupby(
        [
            "sourcewardcode",
            "sourcewardname",
            "facilitytype"
        ]
    )
    .size()
    .reset_index(name="facility_count")
)

print("\nHealth facilities by ward and type:")

print(
    ward_health_type
    .sort_values(
        ["sourcewardcode", "facilitytype"]
    )
    .to_string(index=False)
)


# --------------------------------------------------
# 9. Save joined data
# --------------------------------------------------

health_with_wards.to_csv(
    "data/cleaned/health_facilities_with_wards.csv",
    index=False
)

ward_health_type.to_csv(
    "data/cleaned/ward_health_type_counts.csv",
    index=False
)

print("\nSaved:")
print("data/cleaned/health_facilities_with_wards.csv")
print("data/cleaned/ward_health_type_counts.csv")