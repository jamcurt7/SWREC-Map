import streamlit as st
import pandas as pd
import pydeck as pdk
from math import radians, cos, sin, sqrt, atan2

st.title("SWREC School Travel Planner")

# ✅ Load dataset from repo
df = pd.read_csv("schools_with_coords_full.csv")
df.columns = df.columns.str.strip()

# Detect coordinate columns
lat_col = "Latitude" if "Latitude" in df.columns else "latitude"
lon_col = "Longitude" if "Longitude" in df.columns else "longitude"

df[lat_col] = pd.to_numeric(df[lat_col], errors="coerce")
df[lon_col] = pd.to_numeric(df[lon_col], errors="coerce")

# Remove missing coords
df_geo = df.dropna(subset=[lat_col, lon_col])

# Column names
level_col = "School Level (SY 2017-18 onward) [Public School] 2024-25"
name_col = "School Name [Public School] 2024-25"

# ✅ SIDEBAR FILTERS
st.sidebar.header("Filters")

grade_options = ["Elementary", "Middle", "High"]
selected_grades = st.sidebar.multiselect(
    "Select Grade Levels",
    grade_options,
    default=grade_options
)

df_filtered = df_geo[df_geo[level_col].isin(selected_grades)].copy()

# ✅ SCHOOL SELECTION
school_list = sorted(df_filtered[name_col].tolist())

selected_schools = st.sidebar.multiselect(
    "Select Schools for Route Planning",
    options=school_list
)

if selected_schools:
    df_selected = df_filtered[df_filtered[name_col].isin(selected_schools)].copy()
else:
    df_selected = df_filtered.copy()

# ✅ COLOR FUNCTION
def get_color(level):
    if level == "Elementary":
        return [0, 102, 204]
    elif level == "Middle":
        return [255, 140, 0]
    elif level == "High":
        return [200, 30, 30]
    return [150, 150, 150]

df_selected["color"] = df_selected[level_col].apply(get_color)

# ✅ DISTANCE FUNCTION (Haversine)
def distance(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c

# ✅ ROUTE OPTIMIZATION (nearest neighbor)
def optimize_route(df):
    df = df.reset_index(drop=True)
    visited = [df.iloc[0]]
    remaining = df.iloc[1:].copy()

    current = visited[0]

    while len(remaining) > 0:
        next_idx = remaining.apply(
            lambda row: distance(current[lat_col], current[lon_col], row[lat_col], row[lon_col]),
            axis=1
        ).idxmin()

        next_row = remaining.loc[next_idx]
        visited.append(next_row)

        current = next_row
        remaining = remaining.drop(next_idx)

    return pd.DataFrame(visited)

# ✅ APPLY ROUTE OPTIMIZATION
if len(df_selected) > 1:
    df_route = optimize_route(df_selected)
else:
    df_route = df_selected.copy()

st.subheader("Map")

# ✅ SCATTER POINTS
scatter_layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_route,
    get_position=[lon_col, lat_col],
    get_color="color",
    get_radius=6000,
    pickable=True,
)

# ✅ ROUTE LINE (Phase 2)
route_path = df_route[[lon_col, lat_col]].values.tolist()

line_layer = pdk.Layer(
    "LineLayer",
    data=[{"path": route_path}],
    get_path="path",
    get_color=[255, 255, 255],
    width_scale=4,
    width_min_pixels=2,
)

view_state = pdk.ViewState(latitude=32.5, longitude=-107.5, zoom=7)

st.pydeck_chart(pdk.Deck(
    layers=[scatter_layer, line_layer],
    initial_view_state=view_state,
    tooltip={"text": "{School Name [Public School] 2024-25}"}
))

# ✅ LEGEND
st.markdown("""
**Legend**
- 🔵 Elementary  
- 🟠 Middle  
- 🔴 High  
- ⚪ White line = travel route  
""")

# ✅ TRAVEL CALCULATION (Phase 3 improvement)
st.subheader("Travel Estimate")

if len(df_route) > 1:
    base_distance = 0

    for i in range(len(df_route) - 1):
        base_distance += distance(
            df_route.iloc[i][lat_col],
            df_route.iloc[i][lon_col],
            df_route.iloc[i+1][lat_col],
            df_route.iloc[i+1][lon_col]
        )

    # ✅ Adjust for real roads (more realistic)
    ROAD_MULTIPLIER = 1.6
    adjusted_distance = base_distance * ROAD_MULTIPLIER

    # ~50 mph avg rural speed
    avg_speed = 50
    travel_hours = adjusted_distance / avg_speed

    travel_days = travel_hours / 6

    st.write(f"Optimized route distance: {base_distance:.1f} miles (straight-line)")
    st.write(f"Estimated driving distance: {adjusted_distance:.1f} miles")
    st.write(f"Estimated travel time: {travel_hours:.1f} hours")
    st.write(f"Estimated travel days: {travel_days:.1f} days")

else:
    st.write("Select at least 2 schools to calculate travel.")
