import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import polyline
from math import radians, cos, sin, sqrt, atan2

st.title("SWREC School Travel Planner (Real Routes)")

# ✅ LOAD DATA
df = pd.read_csv("schools_with_coords_FULL_COVERAGE.csv")
df.columns = df.columns.str.strip()

lat_col = "Latitude"
lon_col = "Longitude"
level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"
name_col = "School Name [Public School] 2024-25"

# ✅ SIDEBAR
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

# ✅ LIMIT ROUTE SIZE (prevents messy routes)
max_stops = st.sidebar.slider(
    "Max Schools in Route",
    min_value=2,
    max_value=15,
    value=6
)

df_selected = df_selected.head(max_stops)

# ✅ DISTANCE FUNCTION (for optimizer)
def distance(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c

# ✅ ROUTE OPTIMIZATION (simple nearest neighbor)
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
                current[lat_col],
                current[lon_col],
                row[lat_col],
                row[lon_col]
            ),
            axis=1
        )

        next_idx = distances.idxmin()
        next_row = remaining.loc[next_idx]

        ordered.append(next_row)
        current = next_row
        remaining = remaining.drop(next_idx)

    return pd.DataFrame(ordered)

# ✅ APPLY ROUTE ORDER
df_route = optimize_route(df_selected).reset_index(drop=True)

# ✅ ADD ORDER COLUMN
df_route["order"] = range(1, len(df_route) + 1)

# ✅ COLOR (start = green)
def get_color(index, level):
    if index == 0:
        return [0, 255, 0]  # START = GREEN
    if level == "Elementary":
        return [0, 102, 204]
    elif level == "Middle":
        return [255, 140, 0]
    elif level == "High":
        return [200, 30, 30]
    return [150, 150, 150]

df_route["color"] = [
    get_color(i, row[level_col])
    for i, row in df_route.iterrows()
]

# ✅ BUILD COORDS FOR API
coords = [
    [row[lon_col], row[lat_col]]
    for _, row in df_route.iterrows()
]

# ✅ ADD YOUR API KEY HERE
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjA0ODJmZGFkYmI2NzQxNzhiYTcyNWU5YjJmZTg0MDI4IiwiaCI6Im11cm11cjY0In0="

# ✅ ROUTING FUNCTION
def get_route(coords):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"

    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }

    body = {"coordinates": coords}

    response = requests.post(url, json=body, headers=headers)

    if response.status_code != 200:
        st.error(f"Routing error: {response.status_code}")
        return None, None, None

    data = response.json()
    route = data["routes"][0]

    distance_miles = route["summary"]["distance"] / 1609.34
    duration_hours = route["summary"]["duration"] / 3600
    geometry = route["geometry"]

    return distance_miles, duration_hours, geometry

# ✅ GET ROUTE
route_path = []
distance_miles = None
duration_hours = None

if len(coords) > 1:
    distance_miles, duration_hours, geometry = get_route(coords)

    if geometry:
        decoded = polyline.decode(geometry)
        route_path = [[lon, lat] for lat, lon in decoded]

# ✅ MAP LAYERS
layers = []

scatter_layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_route,
    get_position=[lon_col, lat_col],
    get_color="color",
    get_radius=5000,
    pickable=True
)

layers.append(scatter_layer)

if route_path:
    route_layer = pdk.Layer(
        "PathLayer",
        data=[{"path": route_path}],
        get_path="path",
        get_color=[255, 200, 0],
        width_scale=5,
        width_min_pixels=3
    )
    layers.append(route_layer)

# ✅ VIEW STATE
center_lat = df_route[lat_col].mean()
center_lon = df_route[lon_col].mean()

view_state = pdk.ViewState(
    latitude=center_lat,
    longitude=center_lon,
    zoom=7
)

st.subheader("Map")

deck = pdk.Deck(
    layers=layers,
    initial_view_state=view_state,
    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    tooltip={"text": "{order}. {School Name [Public School] 2024-25}"}
)

st.pydeck_chart(deck)

# ✅ ROUTE LIST (CRITICAL FOR USABILITY)
st.subheader("Route Order")

for i, row in df_route.iterrows():
    st.write(f"{i+1}. {row[name_col]}")

# ✅ TRAVEL SUMMARY
st.subheader("Travel Summary")

if distance_miles:
    st.write(f"Driving distance: {distance_miles:.1f} miles")
    st.write(f"Driving time: {duration_hours:.1f} hours")
    st.write(f"Estimated days (6hr/day): {duration_hours/6:.1f}")
else:
    st.write("Select at least 2 schools.")
