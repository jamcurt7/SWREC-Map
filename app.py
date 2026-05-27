import streamlit as st
import pandas as pd
import pydeck as pdk
from math import radians, cos, sin, sqrt, atan2

st.title("SWREC School Travel Planner")

# Load data
df = pd.read_csv("schools_with_coords_full.csv")
df.columns = df.columns.str.strip()

# Column detection
lat_col = "Latitude" if "Latitude" in df.columns else "latitude"
lon_col = "Longitude" if "Longitude" in df.columns else "longitude"

df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")

df = df.dropna(subset=[lat_col, lon_col])

level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"
name_col = "School Name [Public School] 2024-25"

# Sidebar filters
st.sidebar.header("Filters")
grades = ["Elementary", "Middle", "High"]

selected_grades = st.sidebar.multiselect(
    "Grade Levels",
    grades,
    default=grades
)

df = df[df[level_col].isin(selected_grades)].copy()

# School selection
school_names = sorted(df[name_col].tolist())

selected_schools = st.sidebar.multiselect(
    "Select Schools",
    school_names
)

if selected_schools:
    df = df[df[name_col].isin(selected_schools)]

# Color mapping
def get_color(level):
    if level == "Elementary":
        return [0, 102, 204]
    elif level == "Middle":
        return [255, 140, 0]
    elif level == "High":
        return [200, 30, 30]
    return [150, 150, 150]

df["color"] = df[level_col].apply(get_color)

# Distance function
def distance(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

# Route optimization
def optimize_route(df):
    df = df.reset_index(drop=True)
    if len(df) <= 1:
        return df

    ordered = [df.iloc[0]]
    remaining = df.iloc[1:].copy()
    current = ordered[0]

    while not remaining.empty:
        distances = remaining.apply(
            lambda row: distance(current[lat_col], current[lon_col], row[lat_col], row[lon_col]),
            axis=1
        )
        next_idx = distances.idxmin()
        next_row = remaining.loc[next_idx]

        ordered.append(next_row)
        current = next_row
        remaining = remaining.drop(next_idx)

    return pd.DataFrame(ordered)

# Apply routing
df_route = optimize_route(df)

# Build route lines
line_data = []
for i in range(len(df_route) - 1):
    line_data.append({
        "start": [df_route.iloc[i][lon_col], df_route.iloc[i][lat_col]],
        "end": [df_route.iloc[i+1][lon_col], df_route.iloc[i+1][lat_col]],
    })

# Map
scatter_layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_route,
    get_position=[lon_col, lat_col],
    get_color="color",
    get_radius=4000,
    pickable=True,
)

line_layer = pdk.Layer(
    "LineLayer",
    data=line_data,
    get_source_position="start",
    get_target_position="end",
    get_color=[255, 215, 0],
    get_width=5,
)

view_state = pdk.ViewState(
    latitude=df_route[lat_col].mean() if not df_route.empty else 32.5,
    longitude=df_route[lon_col].mean() if not df_route.empty else -107.5,
    zoom=7,
)

st.subheader("Map")

st.pydeck_chart(pdk.Deck(
    layers=[line_layer, scatter_layer],
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/light-v9",
    tooltip={"text": "{School Name [Public School] 2024-25}"}
))

# Legend
st.markdown("""
**Legend**
- 🔵 Elementary  
- 🟠 Middle  
- 🔴 High  
- 🟡 Yellow line = travel route  
""")

# Travel estimate
st.subheader("Travel Estimate")

if len(df_route) > 1:
    base_distance = 0

    for i in range(len(df_route) - 1):
        base_distance += distance(
            df_route.iloc[i][lat_col],
            df_route.iloc[i][lon_col],
            df_route.iloc[i+1][lat_col],
            df_route.iloc[i+1][lon_col],
        )

    road_factor = 1.6
    driving_distance = base_distance * road_factor

    avg_speed = 50
    hours = driving_distance / avg_speed
    days = hours / 6

    st.write(f"Optimized route distance: {base_distance:.1f} miles")
    st.write(f"Estimated driving distance: {driving_distance:.1f} miles")
    st.write(f"Estimated travel time: {hours:.1f} hours")
    st.write(f"Estimated travel days: {days:.1f} days")

else:
    st.write("Select at least 2 schools.")
