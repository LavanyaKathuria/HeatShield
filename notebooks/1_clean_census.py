import pandas as pd
from pathlib import Path

# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------

INPUT_FILE = Path(
    "data/raw/census/final.xlsx"
)

OUTPUT_FILE = Path(
    "data/cleaned/ahmedabad_census_2011.csv"
)

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# 1. READ CENSUS DATA
# --------------------------------------------------

print("Reading:", INPUT_FILE)

df = pd.read_excel(
    INPUT_FILE,
    sheet_name="Sheet1"
)

print("Original dataset:", df.shape)


# --------------------------------------------------
# 2. SELECT AHMEDABAD MUNICIPAL CORPORATION WARDS
# --------------------------------------------------

ahmedabad = df[
    (df["State"] == 24) &
    (df["District"] == 474) &
    (df["Subdistt"] == 3781) &
    (df["Town/Village"] == 802484) &
    (df["Level"] == "WARD")
].copy()


print("\nAhmedabad AMC wards found:", len(ahmedabad))


# --------------------------------------------------
# 3. KEEP ONLY USEFUL COLUMNS
# --------------------------------------------------

ahmedabad = ahmedabad[
    [
        "Ward",
        "Name",
        "No_HH",
        "TOT_P",
        "TOT_M",
        "TOT_F",
        "P_06",
        "P_SC",
        "P_ST",
        "P_LIT",
        "P_ILL",
        "TOT_WORK_P",
        "MAINWORK_P",
        "MARGWORK_P",
        "MAIN_AL_P",
        "MAIN_HH_P",
        "MAIN_OT_P",
        "NON_WORK_P"
    ]
].copy()


# --------------------------------------------------
# 4. RENAME COLUMNS
# --------------------------------------------------

ahmedabad.rename(
    columns={
        "Ward": "ward_id",
        "Name": "ward_name",
        "No_HH": "households",
        "TOT_P": "total_population",
        "TOT_M": "male_population",
        "TOT_F": "female_population",
        "P_06": "children_0_6",
        "P_SC": "sc_population",
        "P_ST": "st_population",
        "P_LIT": "literate_population",
        "P_ILL": "illiterate_population",
        "TOT_WORK_P": "total_workers",
        "MAINWORK_P": "main_workers",
        "MARGWORK_P": "marginal_workers",
        "MAIN_AL_P": "agricultural_workers",
        "MAIN_HH_P": "household_industry_workers",
        "MAIN_OT_P": "other_workers",
        "NON_WORK_P": "non_workers"
    },
    inplace=True
)


# --------------------------------------------------
# 5. FORMAT WARD ID
# --------------------------------------------------

# Census reads 0001 as integer 1.
# Convert it back to a 4-digit ward identifier.

ahmedabad["ward_id"] = (
    ahmedabad["ward_id"]
    .astype(int)
    .astype(str)
    .str.zfill(4)
)


# --------------------------------------------------
# 6. DERIVED DEMOGRAPHIC FEATURES
# --------------------------------------------------

ahmedabad["female_percentage"] = (
    ahmedabad["female_population"]
    / ahmedabad["total_population"]
    * 100
)

ahmedabad["children_percentage"] = (
    ahmedabad["children_0_6"]
    / ahmedabad["total_population"]
    * 100
)

ahmedabad["literacy_rate"] = (
    ahmedabad["literate_population"]
    /
    (
        ahmedabad["literate_population"]
        + ahmedabad["illiterate_population"]
    )
    * 100
)

ahmedabad["worker_percentage"] = (
    ahmedabad["total_workers"]
    / ahmedabad["total_population"]
    * 100
)

ahmedabad["non_worker_percentage"] = (
    ahmedabad["non_workers"]
    / ahmedabad["total_population"]
    * 100
)


# --------------------------------------------------
# 7. ADD DATA YEAR
# --------------------------------------------------

ahmedabad["data_year"] = 2011


# --------------------------------------------------
# 8. SORT BY WARD
# --------------------------------------------------

ahmedabad = ahmedabad.sort_values("ward_id")


# --------------------------------------------------
# 9. SAVE
# --------------------------------------------------

ahmedabad.to_csv(
    OUTPUT_FILE,
    index=False
)


# --------------------------------------------------
# 10. CHECK RESULT
# --------------------------------------------------

print("\nCleaned dataset shape:", ahmedabad.shape)

print("\nFirst 10 wards:")
print(
    ahmedabad[
        [
            "ward_id",
            "ward_name",
            "total_population",
            "male_population",
            "female_population",
            "children_0_6",
            "literacy_rate"
        ]
    ].head(10).to_string(index=False)
)

print("\nSaved to:")
print(OUTPUT_FILE)