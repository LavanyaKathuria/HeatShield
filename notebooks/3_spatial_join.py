import pandas as pd
import geopandas as gpd
from shapely.ops import transform


# ============================================================
# 1. LOAD FACILITIES
# ============================================================

facilities = pd.read_csv(
    "data/cleaned/facilities.csv"
)

print("Facilities loaded:", len(facilities))

facility_gdf = gpd.GeoDataFrame(
    facilities,
    geometry=gpd.points_from_xy(
        facilities["longitude"],
        facilities["latitude"]
    ),
    crs="EPSG:4326"
)


# ============================================================
# 2. LOAD AHMEDABAD WARD BOUNDARIES
# ============================================================

wards = gpd.read_file(
    "data/raw/wards/wards_ahmedabad.geojson"
)

print("Wards loaded:", len(wards))
print("Original CRS:", wards.crs)


# ============================================================
# 3. FIX SWAPPED LATITUDE/LONGITUDE IN WARD GEOMETRIES
# ============================================================

def swap_xy(x, y, z=None):
    return (y, x)


wards["geometry"] = wards["geometry"].apply(
    lambda geom: transform(swap_xy, geom)
)

print("Ward coordinates corrected.")


# ============================================================
# 4. KEEP ONLY REQUIRED WARD COLUMNS
# ============================================================

wards = wards[
    [
        "ward_lgd_code",
        "ward_lgd_name",
        "sourcewardname",
        "sourcewardcode",
        "geometry"
    ]
].copy()


# ============================================================
# 5. CHECK CRS
# ============================================================

wards = wards.set_crs(
    "EPSG:4326",
    allow_override=True
)

print("Ward CRS:", wards.crs)
print("Facility CRS:", facility_gdf.crs)


# ============================================================
# 6. SPATIAL JOIN
# ============================================================

facilities_with_wards = gpd.sjoin(
    facility_gdf,
    wards,
    how="left",
    predicate="within"
)


# ============================================================
# 7. CHECK JOIN RESULTS
# ============================================================

unmatched = facilities_with_wards[
    facilities_with_wards["sourcewardcode"].isna()
]

print(
    "\nUnmatched facilities:",
    len(unmatched),
    "/",
    len(facilities_with_wards)
)

print("\nSample joined facilities:")

print(
    facilities_with_wards[
        [
            "facility_id",
            "facility_name",
            "kml_category",
            "sourcewardcode",
            "sourcewardname"
        ]
    ]
    .head(10)
    .to_string(index=False)
)


# ============================================================
# 8. FACILITY COUNTS BY WARD AND CATEGORY
# ============================================================

ward_facility_counts = (
    facilities_with_wards
    .dropna(subset=["sourcewardcode"])
    .groupby(
        [
            "sourcewardcode",
            "sourcewardname",
            "kml_category"
        ]
    )
    .size()
    .reset_index(name="facility_count")
)


# ============================================================
# 9. PRINT FACILITY COUNTS
# ============================================================

print("\nFacility counts by ward and category:")

print(
    ward_facility_counts
    .sort_values(
        ["sourcewardcode", "kml_category"]
    )
    .to_string(index=False)
)


# ============================================================
# 10. SAVE FACILITIES WITH WARD INFORMATION
# ============================================================

facilities_with_wards.to_csv(
    "data/cleaned/facilities_with_wards.csv",
    index=False
)


# ============================================================
# 11. SAVE WARD-LEVEL FACILITY COUNTS
# ============================================================

ward_facility_counts.to_csv(
    "data/cleaned/ward_facility_counts.csv",
    index=False
)


# ============================================================
# 12. FINAL MESSAGE
# ============================================================

print("\nSaved:")
print("data/cleaned/facilities_with_wards.csv")
print("data/cleaned/ward_facility_counts.csv")