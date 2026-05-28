import streamlit as st
import pandas as pd
import pydeck as pdk
import requests
import polyline

st.set_page_config(layout="wide")

st.title("SWREC Travel Planner")

# ====================================
# LOAD DATA
# ====================================
df = pd.read_csv("schools_with_coords_FULL_COVERAGE.csv")
df.columns = df.columns.str.strip()

lat_col = "Latitude"
lon_col = "Longitude"
level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"
name_col = "School Name [Public School] 2024-25"

# ====================================
# SIDEBAR (STRUCTURED FLOW)
# ====================================
st.sidebar.header("1. School Selection")

grades = ["Elementary", "Middle", "High"]
selected_grades = st.sidebar.multiselect(
    "Grade Levels",
    grades,
    default=grades
)

df_filtered = df[df[level_col].isin(selected_grades)]

schools = sorted(df_filtered[name_col].tolist())

selected_schools = st.sidebar.multiselect(
    "Select Schools",
    schools
)

if selected_schools:
    df_selected = df_filtered[df_filtered[name_col].isin(selected_schools)].copy()
else:
    df_selected = df_filtered.copy()

# ====================================
# HUB
# ====================================
st.sidebar.header("2. Starting Location")

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
        name_col: selected_hub + " (START)",
        level_col: "Hub"
    }])
    df_selected = pd.concat([hub_row, df_selected]).reset_index(drop=True)

# ====================================
# COACHES
# ====================================
st.sidebar.header("3. Staffing Plan")

num_coaches = st.sidebar.slider("Number of Coaches", 1, 4, 1)

# ====================================
# BUILD COORDS
# ====================================
coords = [
    [row[lon_col], row[lat_col]]
    for _, row in df_selected.iterrows()
]

# ====================================
# API KEY
# ====================================
API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjA0ODJmZGFkYmI2NzQxNzhiYTcyNWU5YjJmZTg0MDI4IiwiaCI6Im11cm11cjY0In0="

# ====================================
# ORS OPTIMIZATION
# ====================================
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

    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }

    r = requests.post(url, json=body, headers=headers)

    if r.status_code != 200:
        st.error("Optimization failed")
        return list(range(len(coords)))

    steps = r.json()["routes"][0]["steps"]
    return [s["job"] for s in steps if "job" in s]

# ====================================
# APPLY OPTIMIZATION
# ====================================
if len(coords) <= 40:
    order = optimize(coords)
    df_route = df_selected.iloc[order].reset_index(drop=True)
else:
    st.warning("Too many locations (max ~40 for optimization)")
    df_route = df_selected.copy()

df_route["order"] = range(1, len(df_route) + 1)

# ====================================
# GET ROUTE PATH
# ====================================
def get_route(coords):
    url = "https://api.openrouteservice.org/v2/directions/driving-car"

    headers = {
        "Authorization": API_KEY,
        "Content-Type": "application/json"
    }

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

coords_final = [
    [row[lon_col], row[lat_col]]
    for _, row in df_route.iterrows()
]

route_path, total_dist, total_time = get_route(coords_final)

# ====================================
# COACH SPLITTING
# ====================================
schools_per_coach = max(1, len(df_route) // num_coaches)

coach_routes = []
colors = [
    [255, 200, 0],
    [0, 200, 255],
    [0, 255, 100],
    [255, 100, 200]
]

for i in range(num_coaches):
    start = i * schools_per_coach
    end = (i + 1) * schools_per_coach

    segment = df_route.iloc[start:end]

    if len(segment) < 2:
        continue

    coords_seg = [
        [row[lon_col], row[lat_col]]
        for _, row in segment.iterrows()
    ]

    path, dist, time = get_route(coords_seg)

    coach_routes.append({
        "coach": i + 1,
        "schools": segment[name_col].tolist(),
        "distance": dist,
        "time": time,
        "path": path,
        "color": colors[i]
    })

# ====================================
# COLORS FOR MAP POINTS
# ====================================
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

# ====================================
# LAYOUT
# ====================================
col1, col2 = st.columns([2, 1])

# ========== MAP ==========
with col1:
    st.subheader("Route Map")

    scatter = pdk.Layer(
        "ScatterplotLayer",
        data=df_route,
        get_position=[lon_col, lat_col],
        get_color="color",
        get_radius=7000,
        pickable=True
    )

    layers = [scatter]

    # draw each coach route
    for c in coach_routes:
        if c["path"]:
            layers.append(
                pdk.Layer(
                    "PathLayer",
                    data=[{"path": c["path"]}],
                    get_path="path",
                    get_color=c["color"],
                    width_min_pixels=6
                )
            )

    view = pdk.ViewState(
        latitude=df_route[lat_col].mean(),
        longitude=df_route[lon_col].mean(),
        zoom=6
    )

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view,
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        tooltip={"text": "{order}. {School Name [Public School] 2024-25}"}
    )

    st.pydeck_chart(deck)

# ========== SIDEPANEL DISPLAY ==========
with col2:

    st.subheader("Summary")

    st.metric("Total Distance", f"{total_dist:.0f} mi")
    st.metric("Total Time", f"{total_time:.1f} hrs")
    st.metric("Coaches", num_coaches)

    st.divider()

    st.subheader("Route Order")

    for i, row in df_route.iterrows():
        if i == 0:
            st.markdown(f"🟢 **START: {row[name_col]}**")
        else:
            st.write(f"{i+1}. {row[name_col]}")

    st.divider()

    st.subheader("Coach Plans")

    for c in coach_routes:
        with st.expander(f"Coach {c['coach']}"):

            st.write(f"Distance: {c['distance']:.1f} miles")
            st.write(f"Time: {c['time']:.1f} hours")
            st.write("Stops:")

            for s in c["schools"]:
                st.write(f"• {s}")
