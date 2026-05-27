import streamlit as st
import pandas as pd
from math import radians, cos, sin, sqrt, atan2

st.title("SWREC School Travel Planner")

uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Clean column names
    df.columns = df.columns.str.strip()

    # Detect coordinate columns
    lat_col = "Latitude" if "Latitude" in df.columns else "latitude"
    lon_col = "Longitude" if "Longitude" in df.columns else "longitude"

    # Force numeric
    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")

    # Remove rows without coordinates (only for mapping + travel)
    df_geo = df.dropna(subset=[lat_col, lon_col])

    # Sidebar filters
    st.sidebar.header("Filters")

    grade_options = ["Elementary", "Middle", "High"]

    selected_grades = st.sidebar.multiselect(
        "Select Grade Levels",
        options=grade_options,
        default=grade_options
    )

    level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"

    df_filtered = df_geo[df_geo[level_col].isin(selected_grades)].reset_index(drop=True)

    # Summary stats
    st.write("### Total Schools (All):", len(df))
    st.write("### Schools with Coordinates:", len(df_geo))
    st.write("### Schools in Current View:", len(df_filtered))

    # ✅ MAP
    st.write("### Map View")

    map_df = df_filtered.rename(columns={lat_col: "lat", lon_col: "lon"})
    st.map(map_df[["lat", "lon"]])

    # Distance function
    def distance(lat1, lon1, lat2, lon2):
        R = 3958.8
