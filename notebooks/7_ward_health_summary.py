import pandas as pd

# --------------------------------------------------
# 1. Load spatially joined health facilities
# --------------------------------------------------

health = pd.read_csv(
    "data/cleaned/health_facilities_with_wards.csv"
)

print("Health facilities loaded:", len(health))


# --------------------------------------------------
# 2. Load all 48 wards
# --------------------------------------------------

wards = pd.read_csv(
    "data/cleaned/ward_facility_summary.csv"
)[
    ["ward_code", "ward_name"]
].copy()

print("Wards loaded:", len(wards))


# --------------------------------------------------
# 3. Keep only facilities inside current AMC wards
# --------------------------------------------------

health = health.dropna(
    subset=["sourcewardcode"]
).copy()

health["ward_code"] = (
    health["sourcewardcode"]
    .astype(int)
)

health["ward_name"] = health["sourcewardname"]


# --------------------------------------------------
# 4. Map source facility types into broad categories
# --------------------------------------------------

hospital_types = {
    "District Hospital",
    "STH"
}

clinic_types = {
    "Clinic"
}

health_centre_types = {
    "Primary Health Centre",
    "Community Health Centre",
    "Urban Health Centre",
    "Sub Centre",
    "HSC",
    "Urban Health Posts",
    "Dispensary",
    "Post Partum Unit",
    "M & CW Centre"
}


def classify_facility(facility_type):

    if facility_type in hospital_types:
        return "hospital"

    elif facility_type in clinic_types:
        return "clinic"

    elif facility_type in health_centre_types:
        return "health_centre"

    else:
        return "other"


health["health_category"] = (
    health["facilitytype"]
    .apply(classify_facility)
)


# --------------------------------------------------
# 5. Show anything not classified
# --------------------------------------------------

print("\nFacility types classified as OTHER:")

print(
    health[
        health["health_category"] == "other"
    ]["facilitytype"]
    .value_counts()
    .to_string()
)


# --------------------------------------------------
# 6. Aggregate by ward + broad category
# --------------------------------------------------

counts = (
    health
    .groupby(
        ["ward_code", "health_category"]
    )
    .size()
    .unstack(fill_value=0)
    .reset_index()
)


# --------------------------------------------------
# 7. Make sure all categories exist
# --------------------------------------------------

for column in [
    "hospital",
    "clinic",
    "health_centre"
]:
    if column not in counts.columns:
        counts[column] = 0


# --------------------------------------------------
# 8. Merge with all 48 wards
# --------------------------------------------------

summary = wards.merge(
    counts,
    on="ward_code",
    how="left"
)

summary[
    [
        "hospital",
        "clinic",
        "health_centre"
    ]
] = summary[
    [
        "hospital",
        "clinic",
        "health_centre"
    ]
].fillna(0)


# --------------------------------------------------
# 9. Rename columns
# --------------------------------------------------

summary = summary.rename(
    columns={
        "hospital": "hospital_count",
        "clinic": "clinic_count",
        "health_centre": "health_centre_count"
    }
)

summary["hospital_count"] = (
    summary["hospital_count"].astype(int)
)

summary["clinic_count"] = (
    summary["clinic_count"].astype(int)
)

summary["health_centre_count"] = (
    summary["health_centre_count"].astype(int)
)

summary["total_health_facilities"] = (
    summary["hospital_count"]
    + summary["clinic_count"]
    + summary["health_centre_count"]
)


# --------------------------------------------------
# 10. Sort by ward
# --------------------------------------------------

summary = summary.sort_values(
    "ward_code"
)


# --------------------------------------------------
# 11. Print result
# --------------------------------------------------

print("\nFINAL HEALTH SUMMARY:")

print(
    summary.to_string(index=False)
)

print("\nTotal health facilities:", 
      summary["total_health_facilities"].sum())

print(
    "Wards with health facilities:",
    (summary["total_health_facilities"] > 0).sum()
)

print(
    "Wards with zero health facilities:",
    (summary["total_health_facilities"] == 0).sum()
)


# --------------------------------------------------
# 12. Save
# --------------------------------------------------

summary.to_csv(
    "data/cleaned/ward_health_summary.csv",
    index=False
)

print(
    "\nSaved: "
    "data/cleaned/ward_health_summary.csv"
)