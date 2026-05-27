import streamlit as st
import pandas as pd
import pydeck as pdk
from math import radians, cos, sin, sqrt, atan2

st.title("SWREC School Travel Planner")

uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()

    # Detect coordinate columns
    lat_col = "Latitude" if "Latitude" in df.columns else "latitude"
    lon_col = "Longitude" if "Longitude" in df.columns else "longitude"

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")

    # Filter out missing coords
    df_geo = df.dropna(subset=[lat_col, lon_col])

    # Sidebar filters
    st.sidebar.header("Filters")

    grade_options = ["Elementary", "Middle", "High"]
    selected_grades = st.sidebar.multiselect(
        "Select Grade Levels",
        grade_options,
        default=grade_options
    )

    level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"

    df_filtered = df_geo[df_geo[level_col].isin(selected_grades)].copy()

    # ✅ COLOR CODING
    def get_color(level):
        if level == "Elementary":
            return [0, 102, 204]  # blue
        elif level == "Middle":
            return [255, 140, 0]  # orange
        elif level == "High":
            return [200, 30, 30]  # red
        else:
            return [120, 120, 120]

    df_filtered["color"] = df_filtered[level_col].apply(get_color)

    st.write("### Schools in view:", len(df_filtered))

    # ✅ MAP (UPGRADED)
    st.write("### Interactive Map")

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_filtered,
        get_position=[lon_col, lat_col],
        get_color="color",
        get_radius=6000,
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=32.5,
        longitude=-107.5,
        zoom=7,
    )

    r = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "{School Name [Public School] 2024-25}\n{School Level (SY 2017-18 onward) [Public School] 2024-25}"}
    )

    st.pydeck_chart(r)

    # ✅ LEGEND
    st.markdown("""
    **Legend**
    - 🔵 Blue = Elementary  
    - 🟠 Orange = Middle  
    - 🔴 Red = High  
    """)

    # ✅ DISTANCE FUNCTION
    def distance(lat1, lon1, lat2, lon2):
        R = 3958.8
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)

        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    # ✅ TRAVEL ESTIMATE
    st.write("### Travel Estimate")

    if len(df_filtered) > 1:
        total_distance = 0

        for i in range(len(df_filtered) - 1):
            lat1 = df_filtered.iloc[i][lat_col]
            lon1 = df_filtered.iloc[i][lon_col]
            lat2 = df_filtered.iloc[i+1][lat_col]
            lon2 = df_filtered.iloc[i+1][lon_col]

            total_distance += distance(lat1, lon1, lat2, lon2)

        travel_hours = (total_distance * 1.4) / 60

        st.write(f"Estimated distance: {total_distance:.1f} miles")
        st.write(f"Estimated travel time: {travel_hours:.1f} hours")
    else:
        st.write("Select more schools to calculate travel.")

    def distance(lat1, lon1, lat2, lon2):
        R = 3958.8
