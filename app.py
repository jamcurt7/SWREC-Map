import streamlit as st
import pandas as pd
import pydeck as pdk
from math import radians, cos, sin, sqrt, atan2

st.title("SWREC School Travel Planner")

uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()

    lat_col = "Latitude" if "Latitude" in df.columns else "latitude"
    lon_col = "Longitude" if "Longitude" in df.columns else "longitude"

    df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
    df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")

    df_geo = df.dropna(subset=[lat_col, lon_col])

    level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"
    name_col = "School Name [Public School] 2024-25"

    # ✅ Sidebar filters
    st.sidebar.header("Filters")

    grade_options = ["Elementary", "Middle", "High"]
    selected_grades = st.sidebar.multiselect(
        "Select Grade Levels",
        grade_options,
        default=grade_options
    )

    df_filtered = df_geo[df_geo[level_col].isin(selected_grades)].copy()

    # ✅ NEW: SCHOOL SELECTOR
    school_list = df_filtered[name_col].tolist()

    selected_schools = st.sidebar.multiselect(
        "Select Specific Schools (for route planning)",
        options=school_list
    )

    # ✅ If user selects schools, use those
    if selected_schools:
        df_selected = df_filtered[df_filtered[name_col].isin(selected_schools)].copy()
    else:
        df_selected = df_filtered.copy()

    # ✅ Color coding
    def get_color(level):
        if level == "Elementary":
            return [0, 102, 204]
        elif level == "Middle":
            return [255, 140, 0]
        elif level == "High":
            return [200, 30, 30]
        else:
            return [150, 150, 150]

    df_selected["color"] = df_selected[level_col].apply(get_color)

    st.write("### Schools shown:", len(df_selected))

    # ✅ MAP
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_selected,
        get_position=[lon_col, lat_col],
        get_color="color",
        get_radius=6000,
        pickable=True
    )

    view_state = pdk.ViewState(
        latitude=32.5,
        longitude=-107.5,
        zoom=7
    )

    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip={"text": "{School Name [Public School] 2024-25}"}
    ))

    # ✅ DISTANCE FUNCTION
    def distance(lat1, lon1, lat2, lon2):
        R = 3958.8
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)

        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    # ✅ TRAVEL CALC FOR SELECTED
    st.write("### Travel Estimate")

    if len(df_selected) > 1:
        total_distance = 0

        for i in range(len(df_selected) - 1):
            lat1 = df_selected.iloc[i][lat_col]
            lon1 = df_selected.iloc[i][lon_col]
            lat2 = df_selected.iloc[i+1][lat_col]
            lon2 = df_selected.iloc[i+1][lon_col]

            total_distance += distance(lat1, lon1, lat2, lon2)

        travel_hours = (total_distance * 1.4) / 60

        st.write(f"Estimated distance: {total_distance:.1f} miles")
        st.write(f"Estimated travel time: {travel_hours:.1f} hours")
    else:
        st.write("Select at least 2 schools to calculate travel.")
