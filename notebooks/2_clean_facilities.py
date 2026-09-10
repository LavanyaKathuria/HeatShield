import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path


# ==================================================
# FILE PATHS
# ==================================================

FACILITY_DIR = Path("data/raw/facilities")
OUTPUT_FILE = Path("data/cleaned/facilities.csv")

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


# ==================================================
# FIND KML
# ==================================================

kml_files = list(FACILITY_DIR.glob("*.kml"))

if not kml_files:
    raise FileNotFoundError(
        "No KML file found in data/raw/facilities/"
    )

KML_FILE = kml_files[0]

print("Reading:", KML_FILE)


# ==================================================
# PARSE XML
# ==================================================

tree = ET.parse(KML_FILE)
root = tree.getroot()

NS = {
    "kml": "http://www.opengis.net/kml/2.2"
}


# ==================================================
# HELPER
# ==================================================

def get_text(element, tag):
    child = element.find(f"kml:{tag}", NS)

    if child is not None and child.text:
        return child.text.strip()

    return None


# ==================================================
# RECURSIVELY EXTRACT FACILITIES
# ==================================================

records = []


def process_folder(folder, parent_categories=None):

    if parent_categories is None:
        parent_categories = []

    folder_name = get_text(folder, "name")

    categories = parent_categories.copy()

    if folder_name:
        categories.append(folder_name)

    # ----------------------------------------------
    # Facilities directly inside this folder
    # ----------------------------------------------

    for placemark in folder.findall("kml:Placemark", NS):

        name = get_text(placemark, "name")
        description = get_text(placemark, "description")

        coordinates_element = placemark.find(
            ".//kml:Point/kml:coordinates",
            NS
        )

        if coordinates_element is None:
            continue

        coordinates = coordinates_element.text.strip()
        parts = coordinates.split(",")

        if len(parts) < 2:
            continue

        try:
            longitude = float(parts[0])
            latitude = float(parts[1])
        except ValueError:
            continue

        records.append({
            "facility_name": name,
            "description": description,
            "latitude": latitude,
            "longitude": longitude,
            "kml_category": " > ".join(categories)
        })

    # ----------------------------------------------
    # Process nested folders
    # ----------------------------------------------

    for subfolder in folder.findall("kml:Folder", NS):
        process_folder(
            subfolder,
            categories
        )


# ==================================================
# START FROM ROOT FOLDERS
# ==================================================

for folder in root.findall(".//kml:Folder", NS):

    # Only process top-level folders
    parent = None

    # ElementTree doesn't directly expose parents,
    # so we'll process all folders through recursion
    # only when they are direct children of Document.

    document = root.find("kml:Document", NS)

    if document is not None:
        for folder in document.findall("kml:Folder", NS):
            process_folder(folder)


    break


# ==================================================
# DATAFRAME
# ==================================================

facilities = pd.DataFrame(records)


# ==================================================
# REMOVE DUPLICATES
# ==================================================

facilities = facilities.drop_duplicates(
    subset=[
        "facility_name",
        "latitude",
        "longitude"
    ]
).reset_index(drop=True)


# ==================================================
# VALIDATE COORDINATES
# ==================================================

facilities = facilities[
    facilities["latitude"].between(20, 25)
    &
    facilities["longitude"].between(70, 75)
].copy()


# ==================================================
# FACILITY ID
# ==================================================

facilities.insert(
    0,
    "facility_id",
    range(1, len(facilities) + 1)
)


# ==================================================
# SAVE
# ==================================================

facilities.to_csv(
    OUTPUT_FILE,
    index=False
)


# ==================================================
# CHECK
# ==================================================

print("\nFacilities extracted:", len(facilities))

print("\nKML categories:")
print(
    facilities["kml_category"]
    .value_counts()
    .to_string()
)

print("\nSample:")
print(
    facilities[
        [
            "facility_id",
            "facility_name",
            "kml_category",
            "latitude",
            "longitude"
        ]
    ].head(20).to_string(index=False)
)

print("\nSaved to:")
print(OUTPUT_FILE)