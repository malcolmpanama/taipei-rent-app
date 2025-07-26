# app.py — Taipei District Rent Explorer
# ───────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import json
from pathlib import Path

# 1 ▸ Page setup
st.set_page_config("Taipei Rent Map", layout="wide", page_icon=":house:")

# 2 ▸ Data paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

RAW_CSV = DATA_DIR / "taipei_rent_listings.csv"
GEOJSON = DATA_DIR / "taipei_districts_4326.geojson"

# 3 ▸ Load data
df_raw   = pd.read_csv(RAW_CSV)
gdf_base = gpd.read_file(GEOJSON)

if "Price_per_ping" not in df_raw.columns:
    df_raw["Price_per_ping"] = df_raw["Price_NT"] / df_raw["Ping"]

# 4 ▸ Sidebar filters
with st.sidebar:
    st.header("Filters")

    type_opts = sorted(df_raw["type"].dropna().unique())
    room_opts = sorted(df_raw["Rooms"].dropna().astype(int).unique())

    sel_types = st.multiselect("Building type", type_opts, type_opts)
    sel_rooms = st.multiselect("Rooms (房)", room_opts, room_opts)

    metric = st.radio(
        "Colour metric",
        ("Median_Rent", "Median_Rent_per_ping"),
        format_func=lambda m: {
            "Median_Rent": "Median NT$ / month",
            "Median_Rent_per_ping": "Median NT$ / 坪"
        }[m]
    )

# 5 ▸ Filter listings
mask = df_raw["type"].isin(sel_types) & df_raw["Rooms"].isin(sel_rooms)
df_f = df_raw[mask]

if df_f.empty:
    st.error("No listings match the current filters.")
    st.stop()

# 6 ▸ Aggregate per district
agg = (
    df_f.groupby("District")
        .agg(
            Median_Rent=("Price_NT", "median"),
            Mean_Rent  =("Price_NT", "mean"),
            P25_Rent   =("Price_NT", lambda s: s.quantile(.25)),
            P75_Rent   =("Price_NT", lambda s: s.quantile(.75)),
            Median_Rent_per_ping=("Price_per_ping", "median"),
            Listings   =("Price_NT", "size")
        )
        .round(0)
        .reset_index()
)

# 7 ▸ Merge with geometry
gdf = gdf_base.merge(agg, left_on="TNAME", right_on="District", how="left")

# 8 ▸ Top‑10 table
top10 = (
    agg.sort_values(metric, ascending=False)
       .loc[:, ["District", metric]]
       .head(10)
       .reset_index(drop=True)
)

top10_table = (
    top10.style
         .hide(axis="index")
         .format({metric: "{:,.0f}"})
         .set_table_styles(
             [{"selector": "tbody tr:nth-child(even)",
               "props": [("background-color", "#f5f5f5")]}]
         )
)

# 9 ▸ Plotly map - Back to choropleth_mapbox with correct bounds
fig = px.choropleth_mapbox(
    gdf,
    geojson=json.loads(gdf.to_json()),
    locations="TNAME",
    featureidkey="properties.TNAME",
    color=metric,
    hover_name="TNAME",
    hover_data={
        "Median_Rent": ":,.0f NT$",
        "Mean_Rent":   ":,.0f NT$",
        "P25_Rent":    ":,.0f NT$",
        "P75_Rent":    ":,.0f NT$",
        "Listings":    True
    },
    color_continuous_scale="YlOrRd",
    mapbox_style="carto-positron",
    opacity=0.85
)

# Calculate bounds from the GeoDataFrame with much more padding
bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
padding_horizontal = 0.05  # Horizontal padding
padding_vertical = 0.15    # Much much more vertical padding

fig.update_layout(
    mapbox=dict(
        bounds=dict(
            west=bounds[0] - padding_horizontal,
            east=bounds[2] + padding_horizontal, 
            south=bounds[1] - padding_vertical,
            north=bounds[3] + padding_vertical
        )
    ),
    margin=dict(l=0, r=0, t=0, b=0),
    height=700  # Keep the increased height
)

# 10 ▸ Layout
col1, col2 = st.columns([1, 3])

with col1:
    st.title("Taipei District Rent Explorer")
    st.markdown("Filter by **building type** and **room count** to see current medians.")
    st.subheader("Top 10 (current view)")
    st.write(top10_table)        # ← only one table now
    st.markdown("---")
    st.markdown(
        """
        📺 **[My YouTube Channel](https://www.youtube.com/@malcolmtalks)**  
        💾 **[Taipei Neighborhood & Apartment Guide](https://malcolmproducts.gumroad.com/l/kambt)**
        """,
        unsafe_allow_html=True
    )

with col2:
    st.plotly_chart(fig, use_container_width=True)

# 11 ▸ Download button
csv_bytes = df_f.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Download filtered listings",
    csv_bytes,
    file_name="taipei_rent_filtered_listings.csv",
    mime="text/csv"
)