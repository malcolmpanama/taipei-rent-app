# app.py — Taipei District Rent Explorer
import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import json
from pathlib import Path

# ─────────────────────────────────────────────
# 1 ▸ PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Taipei Rent Map",
    layout="wide",
    page_icon=":house:"
)

# ─────────────────────────────────────────────
# 2 ▸ LOAD DATA (paths are now robust)
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent     # folder where app.py lives
DATA_DIR = BASE_DIR / "data"

gdf = gpd.read_file(DATA_DIR / "taipei_districts_4326.geojson")
agg = pd.read_csv(DATA_DIR / "taipei_rent_district_metrics.csv")

gdf = gdf.merge(agg, left_on="TNAME", right_on="District", how="left")

# ─────────────────────────────────────────────
# 3 ▸ SIDEBAR  •  filters
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")

    type_opts = sorted(gdf["type"].dropna().unique())
    room_opts = sorted(gdf["Rooms"].dropna().unique())

    sel_types = st.multiselect("Building type", type_opts, type_opts)
    sel_rooms = st.multiselect("Rooms (房)", room_opts, room_opts)

    metric = st.radio(
        "Colour metric",
        ("Median_Rent", "Median_Rent_per_ping", "Median_Rent_per_sqm"),
        format_func=lambda m: {
            "Median_Rent": "Median NT$ / month",
            "Median_Rent_per_ping": "Median NT$ / 坪",
            "Median_Rent_per_sqm": "Median NT$ / m²"
        }[m]
    )

# apply filters
mask = gdf["type"].isin(sel_types) & gdf["Rooms"].isin(sel_rooms)
gdf_f = gdf[mask]

# ─────────────────────────────────────────────
# 4 ▸ TOP‑10 TABLE
# ─────────────────────────────────────────────
top10 = (
    gdf_f.sort_values(metric, ascending=False)
         .loc[:, ["District", metric]]
         .head(10)
         .reset_index(drop=True)
)

# ─────────────────────────────────────────────
# 5 ▸ PLOTLY MAP
# ─────────────────────────────────────────────
fig = px.choropleth_mapbox(
    gdf_f,
    geojson=json.loads(gdf_f.to_json()),
    locations="TNAME",
    featureidkey="properties.TNAME",
    color=metric,
    hover_name="TNAME",
    hover_data={
        "Median_Rent": ":,.0f NT$",
        "Mean_Rent": ":,.0f NT$",
        "P25_Rent": ":,.0f NT$",
        "P75_Rent": ":,.0f NT$",
        "Listings": True
    },
    color_continuous_scale="YlOrRd",
    mapbox_style="carto-positron",
    center={"lat": 25.04, "lon": 121.55},
    zoom=9,
    opacity=0.85
)
fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))

# ─────────────────────────────────────────────
# 6 ▸ LAYOUT
# ─────────────────────────────────────────────
col1, col2 = st.columns([1, 3])

with col1:
    st.title("Taipei District Rent Explorer")
    st.markdown("Median rents by **building type** and **room count**.")

    st.subheader("Top 10 (current view)")
    st.table(top10.style.format({metric: ":,.0f"}))

    st.markdown("---")
    st.markdown(
        """
        📺 **[My YouTube Channel](https://youtube.com/@YourChannel)**  
        💾 **[Full dataset on Gumroad](https://gumroad.com/l/taipei-rent-pack)**
        """,
        unsafe_allow_html=True
    )

with col2:
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────────────────────────
# 7 ▸ DOWNLOAD BUTTON
# ─────────────────────────────────────────────
csv_bytes = gdf_f.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "Download filtered CSV",
    csv_bytes,
    file_name="taipei_rent_filtered.csv",
    mime="text/csv"
)
