import streamlit as st
import pandas as pd
import pydeck as pdk
from math import radians, cos, sin, sqrt, atan2
import requests
import polyline

st.title("SWREC School Travel Planner")

# ✅ LOAD DATA
df = pd.read_csv("schools_with_coords_FULL_COVERAGE.csv")
df.columns = df.columns.str.strip()

# ✅ COLUMN DETECTION
lat_col = "Latitude" if "Latitude" in df.columns else "latitude"
lon_col = "Longitude" if "Longitude" in df.columns else "longitude"

df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")

# ✅ REQUIRED COLUMN NAMES
level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"
name_col = "School Name [Public School] 2024-25"

# ✅ SIDEBAR FILTER
st.sidebar.header("Filters")

grades = ["Elementary", "Middle", "High"]
selected_grades = st.sidebar.multiselect(
    "Select Grade Levels",
    grades,
    default=grades
)

df_filtered = df[df[level_col].isin(selected_grades)].copy()

# ✅ SCHOOL SELECTION
school_names = sorted(df_filtered[name_col].tolist())

selected_schools = st.sidebar.multiselect(
    "Select Schools for Route Planning",
    school_names
)

if selected_schools:
    df_selected = df_filtered[df_filtered[name_col].isin(selected_schools)].copy()
else:
    df_selected = df_filtered.copy()

# ✅ COLOR CODING
def get_color(level):
    if level == "Elementary":
        return [0, 102, 204]   # blue
    elif level == "Middle":
        return [255, 140, 0]   # orange
    elif level == "High":
        return [200, 30, 30]   # red
    return [150, 150, 150]

df_selected["color"] = df_selected[level_col].apply(get_color)

# ✅ DISTANCE FUNCTION
def distance(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c

# ✅ ROUTE OPTIMIZATION
def optimize_route(df):
    df = df.reset_index(drop=True)

    if len(df) <= 1:
        return df

    ordered = [df.iloc[0]]
    remaining = df.iloc[1:].copy()
    current = ordered[0]

    while not remaining.empty:
        distances = remaining.apply(
            lambda row: distance(
                current[lat_col], current[lon_col],
                row[lat_col], row[lon_col]
            ),
            axis=1
        )

        next_idx = distances.idxmin()
        next_row = remaining.loc[next_idx]

        ordered.append(next_row)
        current = next_row
        remaining = remaining.drop(next_idx)

    return pd.DataFrame(ordered)

# ✅ APPLY ROUTE
df_route = optimize_route(df_selected)

# ✅ BUILD COORDINATES FOR API
coords = [
    [row[lon_col], row[lat_col]]
    for _, row in df_route.iterrows()
]

# ✅ YOUR API KEY (PASTE HERE)
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjA0ODJmZGFkYmI2NzQxNzhiYTcyNWU5YjJmZTg0MDI4IiwiaCI6Im11cm11cjY0In0="

# ✅ FUNCTION TO CALL OPENROUTESERVICE
def get_route(coords):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"

    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "coordinates": coords
    }

    response = requests.post(url, json=body, headers=headers)

    if response.status_code != 200:
        st.error("Routing API error")
        return None, None, None

    data = response.json()
    route = data["routes"][0]

    distance_miles = route["summary"]["distance"] / 1609.34
    duration_hours = route["summary"]["duration"] / 3600
    geometry = route["geometry"]

    return distance_miles, duration_hours, geometry

# ✅ CALL API
distance_miles = None
duration_hours = None
route_path = []

if len(coords) > 1:
    distance_miles, duration_hours, geometry = get_route(coords)

    if geometry:
        decoded = polyline.decode(geometry)
        route_path = [[lon, lat] for lat, lon in decoded]

# ✅ USE REAL ROUTE FROM API
layers = []

scatter_layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_route,
    get_position=[lon_col, lat_col],
    get_color="color",
    get_radius=4000,
    pickable=True,
)

layers.append(scatter_layer)

if route_path:
    route_layer = pdk.Layer(
        "PathLayer",
        data=[{"path": route_path}],
        get_path="path",
        get_color=[255, 200, 0],
        width_scale=5,
        width_min_pixels=3,
    )
    layers.append(route_layer)
# ✅ MAP LAYERS
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
    get_source_position="source",
    get_target_position="target",
    get_color=[255, 200, 0],  # bright yellow
    get_width=8,
)

# ✅ DYNAMIC CENTER
center_lat = df_route[lat_col].mean() if not df_route.empty else 32.5
center_lon = df_route[lon_col].mean() if not df_route.empty else -107.5

view_state = pdk.ViewState(
    latitude=center_lat,
    longitude=center_lon,
    zoom=7
)

st.subheader("Map")

# ✅ ✅ FIXED BASEMAP (THIS SOLVES YOUR BLACK MAP ISSUE)
deck = pdk.Deck(
    layers=layers,
    initial_view_state=view_state,
    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    tooltip={"text": "{School Name [Public School] 2024-25}"}
)

st.pydeck_chart(deck)

# ✅ LEGEND
st.markdown("""
**Legend**
- 🔵 Elementary  
- 🟠 Middle  
- 🔴 High  
- 🟡 Yellow line = optimized travel route  
""")

# ✅ TRAVEL CALCULATION
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

    # ✅ ROAD ADJUSTMENT
    ROAD_FACTOR = 1.6
    driving_distance = base_distance * ROAD_FACTOR

    avg_speed = 50
    travel_hours = driving_distance / avg_speed
    travel_days = travel_hours / 6

    st.write(f"Optimized route distance: {base_distance:.1f} miles")
    st.write(f"Estimated driving distance: {driving_distance:.1f} miles")
    st.write(f"Estimated travel time: {travel_hours:.1f} hours")
    st.write(f"Estimated travel days: {travel_days:.1f} days")

else:
    st.write("Select at least 2 schools to calculate travel.")
