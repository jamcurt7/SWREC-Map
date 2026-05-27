!pip install geopy pandas openpyxl

import pandas as pd
from geopy.geocoders import Nominatim
import time

# Load original Excel
df = pd.read_excel("New Mexico SWREC RFP Research.xlsx", sheet_name="School-Level Data")
df.columns = df.columns.str.strip()

geolocator = Nominatim(user_agent="swrec_full")

latitudes = []
longitudes = []

def geocode_with_fallback(row):
    try:
        # ✅ attempt 1: school + city
        address = f"{row['School Name [Public School] 2024-25']}, {row['Location City [Public School] 2024-25']}, NM"
        location = geolocator.geocode(address, timeout=10)

        # ✅ attempt 2: city only
        if not location:
            city = row['Location City [Public School] 2024-25']
            location = geolocator.geocode(f"{city}, NM", timeout=10)

        if location:
            return location.latitude, location.longitude
        else:
            return None, None

    except:
        return None, None

# Run geocoding
for _, row in df.iterrows():
    lat, lon = geocode_with_fallback(row)
    latitudes.append(lat)
    longitudes.append(lon)
    time.sleep(1)

df["Latitude"] = latitudes
df["Longitude"] = longitudes

# ✅ FINAL STEP: fill any remaining NULLS with city centroid
df["Latitude"] = df.groupby("Location City [Public School] 2024-25")["Latitude"].transform(lambda x: x.fillna(x.mean()))
df["Longitude"] = df.groupby("Location City [Public School] 2024-25")["Longitude"].transform(lambda x: x.fillna(x.mean()))

# Save
df.to_csv("schools_with_coords_FULL_COVERAGE.csv", index=False)

from google.colab import files
files.download("schools_with_coords_FULL_COVERAGE.csv")
