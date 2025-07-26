# app.py — Taipei District Rent Explorer
# ───────────────────────────────────────────────────────────────
import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import json
from pathlib import Path

# 1 ▸ page setup
st.set_page_config("Taipei Rent Map", layout="wide", page_icon=":house:")

# optional: tighten left / right padding and auto‑size tables
st.markdown(
    """
    <style>
      .block-container {padding-left:1rem; padding-right:1rem;}
      /* shrink any pandas Styler table */
      .element-container:has(.dataframe) {width:fit-content; margin-left:0;}
    </style>
    """,
    unsafe_allow_html=True,
)

# 2 ▸ paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_CSV = DATA_DIR / "taipei_rent_listings.csv"
GEOJSON = DATA_DIR / "taipei_districts_4326.geojson"

# 3 ▸ load data
df_raw   = pd.read_csv(RAW_CSV)
gdf_base = gpd.read_file(GEOJSON)

if "Price_per_ping" not in df_raw.columns:
    df_raw["Price_per_ping"] = df_raw["Price_NT"] / df_raw["Ping"]

# ── district Chinese → English
zh2en_dist = {
    "信義區": "Xinyi District",      "中正區": "Zhongzheng District",
    "南港區": "Nangang District",   "大安區": "Da'an District",
    "大同區": "Datong District",     "中山區": "Zhongshan District",
    "松山區": "Songshan District",   "內湖區": "Neihu District",
    "萬華區": "Wanhua District",     "北投區": "Beitou District",
    "士林區": "Shilin District",     "文山區": "Wenshan District",
}
gdf_base["District_EN"] = gdf_base["TNAME"].map(zh2en_dist)

# ── building‑type Chinese → English
type_zh2en = {
    "電梯大樓": "Elevator Building",
    "無電梯公寓": "Walk‑up Apartment",
}
type_en2zh = {en: zh for zh, en in type_zh2en.items()}

# 4 ▸ sidebar filters
with st.sidebar:
    st.header("Filters")

    type_opts_en = [type_zh2en.get(zh, zh)
                    for zh in sorted(df_raw["type"].dropna().unique())]
    room_opts = sorted(df_raw["Rooms"].dropna().astype(int).unique())

    sel_types_en = st.multiselect("Building type", type_opts_en, type_opts_en)
    sel_rooms    = st.multiselect("Rooms (房)", room_opts, room_opts)

    metric_labels = {          # user‑friendly radio
        "Median Rent per 坪": "Median Rent per 坪",
        "Median Rent":        "Median Rent",
    }
    metric_label = st.radio("Colour metric", list(metric_labels.keys()))
    metric = metric_labels[metric_label]

# 5 ▸ filter listings
sel_types_zh = [type_en2zh[en] for en in sel_types_en] if sel_types_en else []
mask  = df_raw["type"].isin(sel_types_zh) if sel_types_zh else True
mask &= df_raw["Rooms"].isin(sel_rooms)   if sel_rooms   else True
df_f = df_raw[mask]

if df_f.empty:
    st.error("No listings match the current filters.")
    st.stop()

# 6 ▸ aggregate per district
agg = (
    df_f.groupby("District")
        .agg(
            Median_Rent=("Price_NT", "median"),
            Mean_Rent=("Price_NT", "mean"),
            P25_Rent=("Price_NT", lambda s: s.quantile(.25)),
            P75_Rent=("Price_NT", lambda s: s.quantile(.75)),
            Median_Rent_per_ping=("Price_per_ping", "median"),
            Listings=("Price_NT", "size"),
        )
        .round(0)
        .reset_index()
)

# nicer labels
agg.rename(
    columns={
        "Median_Rent": "Median Rent",
        "Mean_Rent": "Mean Rent",
        "P25_Rent": "25th Percentile",
        "P75_Rent": "75th Percentile",
        "Median_Rent_per_ping": "Median Rent per 坪",
    },
    inplace=True,
)

# 7 ▸ merge with geometry
gdf = gdf_base.merge(agg, left_on="TNAME", right_on="District", how="left")
gdf["Rooms_sel"] = ", ".join(map(str, sel_rooms))  # for hover

# 8 ▸ top‑10 table
top10_table = (
    agg.assign(District=agg["District"].map(zh2en_dist))
    .sort_values(metric_label, ascending=False)
    .loc[:, ["District", metric_label]]
    .head(10)
    .reset_index(drop=True)
    .style.hide(axis="index")
    .format({metric_label: "{:,.0f}"})
)

# 9 ▸ plotly map (Viridis + white borders + tight bounds)
fig = px.choropleth_mapbox(
    gdf,
    geojson=json.loads(gdf.to_json()),
    locations="TNAME",
    featureidkey="properties.TNAME",
    color=metric_label,
    hover_name="District_EN",
    hover_data={
        "Chinese Name": gdf["TNAME"],
        "Rooms": gdf["Rooms_sel"],
        "Median Rent": ":,.0f NT$",
        "Mean Rent": ":,.0f NT$",
        "25th Percentile": ":,.0f NT$",
        "75th Percentile": ":,.0f NT$",
        "Listings": True,
        "TNAME": False,
    },
    color_continuous_scale="Viridis",
    mapbox_style="carto-positron",
    line_color="white",
    line_width=0.5,
    opacity=0.85,
)

minx, miny, maxx, maxy = gdf.total_bounds
pad_x = (maxx - minx) * 0.02
pad_y = (maxy - miny) * 0.02
fig.update_layout(
    mapbox=dict(
        bounds=dict(
            west=minx - pad_x,
            east=maxx + pad_x,
            south=miny - pad_y,
            north=maxy + pad_y,
        )
    ),
    margin=dict(l=0, r=0, t=0, b=0),
)
fig.update_coloraxes(colorbar_title=metric_label)

# 10 ▸ layout (wider map column)
col1, col2 = st.columns([1, 5])

with col1:
    st.title("Taipei District Rent Explorer")
    st.markdown(
        """
**How this works**

* Select one or many **building types** (elevator vs. walk‑up) and **room counts** in the sidebar.  
* The map colours each district by the metric you pick (default: **Median Rent per 坪**).  
* Hover over a district to see detailed stats.

**Glossary**

| Term | Meaning |
|------|---------|
| **Median Rent** | Middle monthly rent of filtered listings |
| **Mean Rent** | Simple average of rents |
| **25th / 75th Percentile** | One‑quarter of listings are below / above these values |
| **Median Rent per 坪** | Median rent divided by interior area in 坪 (1 坪 ≈ 3.3 m²) |
""",
        unsafe_allow_html=True,
    )

    st.subheader("Top 10 (current view)")
    st.write(top10_table)
    st.markdown(
        """
📺 **[My YouTube Channel](https://www.youtube.com/@malcolmtalks)**  
💾 **[Taipei Neighborhood & Apartment Guide](https://malcolmproducts.gumroad.com/l/kambt)**
""",
        unsafe_allow_html=True,
    )

with col2:
    st.plotly_chart(fig, use_container_width=True)
