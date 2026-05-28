import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import polyline

st.title("SWREC Travel Planner (Multi-Day + Coaches)")

# =========================
# LOAD DATA
# =========================
df = pd.read_csv("schools_with_coords_FULL_COVERAGE.csv")
df.columns = df.columns.str.strip()

lat_col = "Latitude"
lon_col = "Longitude"
level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"
name_col = "School Name [Public School] 2024-25"

# =========================
# FILTERS
# =========================
st.sidebar.header("Filters")

grades = ["Elementary", "Middle", "High"]
selected_grades = st.sidebar.multiselect(
    "Select Grade Levels", grades, default=grades
)

df_filtered = df[df[level_col].isin(selected_grades)]

schools = sorted(df_filtered[name_col].tolist())

selected_schools = st.sidebar.multiselect("Select Schools", schools)

if selected_schools:
    df_selected = df_filtered[df_filtered[name_col].isin(selected_schools)].copy()
else:
    df_selected = df_filtered.copy()

# =========================
# HUB
# =========================
hubs = {
    "None": None,
    "Albuquerque": [35.0844, -106.6504],
    "El Paso": [31.7619, -106.4850],
    "Silver City": [32.7701, -108.2803],
    "Deming": [32.2687, -107.7586]
}

selected_hub = st.sidebar.selectbox("Starting Hub", list(hubs.keys()))

if selected_hub != "None":
    lat, lon = hubs[selected_hub]
    hub_row = pd.DataFrame([{
        lat_col: lat,
        lon_col: lon,
        name_col: selected_hub + " (Start)",
        level_col: "Hub"
    }])
    df_selected = pd.concat([hub_row, df_selected]).reset_index(drop=True)

# =========================
# COACHES
# =========================
num_coaches = st.sidebar.slider("Number of Coaches", 1, 4, 1)

# =========================
# COORDS
# =========================
coords = [[row[lon_col], row[lat_col]] for _, row in df_selected.iterrows()]

# =========================
# API KEY
# =========================
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjA0ODJmZGFkYmI2NzQxNzhiYTcyNWU5YjJmZTg0MDI4IiwiaCI6Im11cm11cjY0In0="

# =========================
# OPTIMIZATION
# =========================
def optimize(coords):
    url = "https://api.openrouteservice.org/optimization"

    jobs = [{"id": i, "location": c} for i, c in enumerate(coords)]

    body = {
        "jobs": jobs,
        "vehicles": [{
            "id": 1,
            "start": coords[0],
            "end": coords[0]
        }]
    }

    headers = {"Authorization": API_KEY, "Content-Type": "application/json"}

    r = requests.post(url, json=body, headers=headers)

    if r.status_code != 200:
        st.error("Optimization failed")
        return list(range(len(coords)))

    steps = r.json()["routes"][0]["steps"]
    return [s["job"] for s in steps if "job" in s]

# =========================
# ROUTE ORDER
# =========================
if len(coords) <= 40:
    order = optimize(coords)
    df_route = df_selected.iloc[order].reset_index(drop=True)
else:
    st.warning("Too many locations (max ~40)")
    df_route = df_selected.copy()

df_route["order"] = range(1, len(df_route) + 1)

# =========================
# GET ROAD PATH
# =========================
def get_route(coords):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"

    headers = {"Authorization": API_KEY, "Content-Type": "application/json"}

    body = {"coordinates": coords}

    r = requests.post(url, json=body, headers=headers)

    if r.status_code != 200:
        return None, 0, 0

    route = r.json()["routes"][0]

    dist = route["summary"]["distance"] / 1609
    dur = route["summary"]["duration"] / 3600

    decoded = polyline.decode(route["geometry"])
    path = [[lon, lat] for lat, lon in decoded]

    return path, dist, dur

coords_final = [[row[lon_col], row[lat_col]] for _, row in df_route.iterrows()]
route_path, total_dist, total_time = get_route(coords_final)

# =========================
# MULTI-DAY + COACH SPLIT
# =========================
st.subheader("Planning Breakdown")

schools_per_coach = max(1, len(df_route) // num_coaches)

coach_routes = []
for i in range(num_coaches):
    start = i * schools_per_coach
    end = (i + 1) * schools_per_coach
    segment = df_route.iloc[start:end]

    if len(segment) < 2:
        continue

    coords_seg = [[row[lon_col], row[lat_col]] for _, row in segment.iterrows()]
    _, dist, time = get_route(coords_seg)

    coach_routes.append({
        "coach": i + 1,
        "schools": segment[name_col].tolist(),
        "distance": dist,
        "time": time
    })

# =========================
# MAP COLORS
# =========================
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
    get_color(i, row[level_col]) for i, row in df_route.iterrows()
]

# =========================
# MAP
# =========================
scatter = pdk.Layer(
    "ScatterplotLayer",
    data=df_route,
    get_position=[lon_col, lat_col],
    get_color="color",
    get_radius=5000,
    pickable=True,
)

layers = [scatter]

if route_path:
    layers.append(
        pdk.Layer(
            "PathLayer",
            data=[{"path": route_path}],
            get_path="path",
            get_color=[255, 200, 0],
            width_min_pixels=3
        )
    )

view = pdk.ViewState(
    latitude=df_route[lat_col].mean(),
    longitude=df_route[lon_col].mean(),
    zoom=6
)

st.pydeck_chart(pdk.Deck(
    layers=layers,
    initial_view_state=view,
    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    tooltip={"text": "{order}. {School Name [Public School] 2024-25}"}
))

# =========================
# OUTPUT
# =========================
st.subheader("Full Route")
for i, row in df_route.iterrows():
    st.write(f"{i+1}. {row[name_col]}")

st.subheader("Total Travel")
st.write(f"Distance: {total_dist:.1f} miles")
st.write(f"Time: {total_time:.1f} hours")

st.subheader("Coach Breakdown")

for c in coach_routes:
    st.write(f"--- Coach {c['coach']} ---")
    st.write(f"Stops: {len(c['schools'])}")
    st.write(f"Distance: {c['distance']:.1f} mi")
    st.write(f"Time: {c['time']:.1f} hrs")
    for s in c["schools"]:
        st.write(f"• {s}")
