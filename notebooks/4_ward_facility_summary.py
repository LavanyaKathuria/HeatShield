import pandas as pd

# Load spatially joined facilities
df = pd.read_csv("data/cleaned/facilities_with_wards.csv")

print("Facilities loaded:", len(df))

# Create one row per ward
ward_summary = (
    df.groupby(
        ["sourcewardcode", "sourcewardname"]
    )
    .agg(
        total_facilities=("facility_id", "count"),
        ward_offices=("kml_category", lambda x: (x == "Ward Office").sum()),
        libraries=("kml_category", lambda x: (x == "library").sum()),
        municipal_gyms=("kml_category", lambda x: (x == "Municipal Gym").sum()),
        swimming_pools=("kml_category", lambda x: (x == "Swimming Pools").sum()),
        zonal_offices=("kml_category", lambda x: (x == "Zonal Office").sum()),
    )
    .reset_index()
)

# Rename columns
ward_summary = ward_summary.rename(
    columns={
        "sourcewardcode": "ward_code",
        "sourcewardname": "ward_name"
    }
)

# Sort wards numerically
ward_summary = ward_summary.sort_values("ward_code")

# Save
ward_summary.to_csv(
    "data/cleaned/ward_facility_summary.csv",
    index=False
)

print("\nWard facility summary:")
print(ward_summary.to_string(index=False))

print("\nNumber of wards:", len(ward_summary))
print("Total facilities:", ward_summary["total_facilities"].sum())

print("\nSaved:")
print("data/cleaned/ward_facility_summary.csv")