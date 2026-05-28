import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import polyline

st.title("SWREC School Travel Planner (Optimized Routes)")

# ✅ LOAD DATA
df = pd.read_csv("schools_with_coords_FULL_COVERAGE.csv")
df.columns = df.columns.str.strip()

lat_col = "Latitude"
lon_col = "Longitude"
level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"
name_col = "School Name [Public School] 2024-25"

# ✅ SIDEBAR
st.sidebar.header("Filters")

# Grade filter
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
    "Select Schools",
    school_names
)

if selected_schools:
    df_selected = df_filtered[df_filtered[name_col].isin(selected_schools)].copy()
else:
    df_selected = df_filtered.copy()

# ✅ HUB OPTIONS
hubs = {
    "None": None,
    "Albuquerque": [35.0844, -106.6504],
    "El Paso": [31.7619, -106.4850],
    "Silver City": [32.7701, -108.2803],
    "Deming": [32.2687, -107.7586]
}

selected_hub = st.sidebar.selectbox("Starting Hub", list(hubs.keys()))

# ✅ Add hub as first point
if selected_hub != "None":
    hub_lat, hub_lon = hubs[selected_hub]
    hub_row = pd.DataFrame([{
        lat_col: hub_lat,
        lon_col: hub_lon,
        name_col: selected_hub,
        level_col: "Hub"
    }])
    df_selected = pd.concat([hub_row, df_selected]).reset_index(drop=True)

# ✅ BUILD COORDS
coords = [
    [row[lon_col], row[lat_col]]
    for _, row in df_selected.iterrows()
]

# ✅ API KEY
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjA0ODJmZGFkYmI2NzQxNzhiYTcyNWU5YjJmZTg0MDI4IiwiaCI6Im11cm11cjY0In0="

# ✅ ORS OPTIMIZATION (BEST ROUTE ORDER)
def optimize_route_ors(coords):
    url = "https://api.openrouteservice.org/v2/optimization"

    body = {
        "jobs": [
            {"id": i, "location": coord}
            for i, coord in enumerate(coords)
        ],
        "vehicles": [{
            "id": 1,
            "start": coords[0] if selected_hub != "None" else coords[0]
        }]
    }

    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=body, headers=headers)

    if response.status_code != 200:
        st.error("Optimization API error")
        return list(range(len(coords)))

    data = response.json()

    try:
        route = data["routes"][0]["steps"]
        ordered_indices = [step["job"] for step in route if "job" in step]
        return ordered_indices
    except:
        return list(range(len(coords)))

# ✅ APPLY TRUE OPTIMIZATION
if len(coords) > 1 and len(coords) <= 50:
    order = optimize_route_ors(coords)
    df_route = df_selected.iloc[order].reset_index(drop=True)
else:
    st.warning("Too many schools selected (max ~50 for optimization). Using simple order.")
    df_route = df_selected.copy()

df_route["order"] = range(1, len(df_route) + 1)

# ✅ BUILD ROUTE LINE
def get_route(coords):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"

    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }

    body = {"coordinates": coords}

    response = requests.post(url, json=body, headers=headers)

    if response.status_code != 200:
        st.error("Routing error")
        return None

    route = response.json()["routes"][0]
    geometry = route["geometry"]

    decoded = polyline.decode(geometry)
    return [[lon, lat] for lat, lon in decoded]

coords_optimized = [
    [row[lon_col], row[lat_col]]
    for _, row in df_route.iterrows()
]

route_path = get_route(coords_optimized)

# ✅ COLOR (start = green)
def get_color(i, level):
    if i == 0:
        return [0, 255, 0]
    if level == "Elementary":
        return [0, 102, 204]
    if level == "Middle":
        return [255, 140, 0]
    if level == "High":
        return [200, 30, 30]
    return [150, 150, 150]

df_route["color"] = [
    get_color(i, row[level_col])
    for i, row in df_route.iterrows()
]

# ✅ MAP
scatter = pdk.Layer(
    "ScatterplotLayer",
    data=df_route,
    get_position=[lon_col, lat_col],
    get_color="color",
    get_radius=5000,
    pickable=True
)

layers = [scatter]

if route_path:
    layers.append(
        pdk.Layer(
            "PathLayer",
            data=[{"path": route_path}],
            get_path="path",
            get_color=[255, 200, 0],
            width_scale=5,
            width_min_pixels=3
        )
    )

view_state = pdk.ViewState(
    latitude=df_route[lat_col].mean(),
    longitude=df_route[lon_col].mean(),
    zoom=6
)

deck = pdk.Deck(
    layers=layers,
    initial_view_state=view_state,
    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    tooltip={"text": "{order}. {School Name [Public School] 2024-25}"}
)

st.pydeck_chart(deck)

# ✅ ROUTE ORDER LIST
st.subheader("Route Order")

for i, row in df_route.iterrows():
    st.write(f"{i+1}. {row[name_col]}")
