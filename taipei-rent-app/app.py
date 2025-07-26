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

st.markdown(
    """
    <style>
    /* shrink any table inside the left column to its intrinsic width */
    .block-container .element-container:has(.dataframe)           {width: fit-content;}
    .block-container .element-container:has(.dataframe) > div     {width: fit-content;}
    .block-container .element-container:has(.dataframe)           {margin: 0 auto;}
    </style>
    """,
    unsafe_allow_html=True
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

# ── mapping Chinese → English for districts
zh2en_dist = {
    "信義區": "Xinyi District",
    "中正區": "Zhongzheng District",
    "南港區": "Nangang District",
    "大安區": "Da'an District",
    "大同區": "Datong District",
    "中山區": "Zhongshan District",
    "松山區": "Songshan District",
    "內湖區": "Neihu District",
    "萬華區": "Wanhua District",
    "北投區": "Beitou District",
    "士林區": "Shilin District",
    "文山區": "Wenshan District"
}
gdf_base["District_EN"] = gdf_base["TNAME"].map(zh2en_dist)

# ── mapping Chinese → English for building type
type_zh2en = {
    "電梯大樓": "Elevator Building",
    "無電梯公寓": "Walk‑up Apartment"
}
type_en2zh = {en: zh for zh, en in type_zh2en.items()}

# 4 ▸ sidebar filters (multi‑select dropdowns)
with st.sidebar:
    st.header("Filters")

    type_opts_en = [type_zh2en.get(zh, zh)
                    for zh in sorted(df_raw["type"].dropna().unique())]
    room_opts    = sorted(df_raw["Rooms"].dropna().astype(int).unique())

    sel_types_en = st.multiselect("Building type", type_opts_en, type_opts_en)
    sel_rooms    = st.multiselect("Rooms (房)", room_opts, room_opts)

    # user‑friendly metric names
    metric_labels = {
        "Median Rent":            "Median_Rent",
        "Median Rent per 坪":     "Median_Rent_per_ping"
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
            Listings=("Price_NT", "size")
        )
        .round(0)
        .reset_index()
)

# rename columns to nice display names
agg.rename(columns={
    "Median_Rent": "Median Rent",
    "Mean_Rent":   "Mean Rent",
    "P25_Rent":    "25th Percentile",
    "P75_Rent":    "75th Percentile",
    "Median_Rent_per_ping": "Median Rent per 坪"
}, inplace=True)

# 7 ▸ merge with geometry
gdf = gdf_base.merge(agg, left_on="TNAME", right_on="District", how="left")

# 8 ▸ top‑10 table
top10_table = (
    agg.assign(District=agg["District"].map(zh2en_dist))
       .sort_values(metric_label, ascending=False)
       .loc[:, ["District", metric_label]]
       .head(10)
       .reset_index(drop=True)
       .style
       .hide(axis="index")
       .format({metric_label: "{:,.0f}"})
)

# 9 ▸ plotly map (fixed zoom)
fig = px.choropleth_mapbox(
    gdf,
    geojson=json.loads(gdf.to_json()),
    locations="TNAME",
    featureidkey="properties.TNAME",
    color=metric_label,
    hover_name="District_EN",
    hover_data={
        "Chinese Name": gdf["TNAME"],
        "Median Rent": ":,.0f NT$",
        "Mean Rent": ":,.0f NT$",
        "25th Percentile": ":,.0f NT$",
        "75th Percentile": ":,.0f NT$",
        "Listings": True,
        "TNAME": False           # hide raw key
    },
    color_continuous_scale="YlOrRd",
    mapbox_style="carto-positron",
    center={"lat": 25.04, "lon": 121.55},
    zoom=10.3,
    opacity=0.85
)
fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=750)

# 10 ▸ layout
col1, col2 = st.columns([1, 1])

with col1:
    st.title("Taipei District Rent Explorer")
    st.markdown(
        """
    **How this works**

    * Select one or more **building types** (elevator vs. walk-up)  
      and **room counts** from the sidebar.  
    * The map colors each Taipei district based on your selected metric  
      (default: **Median Rent per 坪**).  
    * Hover over a district for detailed rent stats.

    **Glossary**

    | Term | Meaning |
    |------|---------|
    | **Median Rent** | Middle monthly rent of all filtered listings. |
    | **Mean Rent** | Average rent across listings. |
    | **25th / 75th Percentile** | Ranges covering the cheaper and pricier ends of the market. |
    | **Median Rent per 坪** | Median rent divided by interior area (1 坪 ≈ 3.3 m²). |

    ---

    💡 **Moving to Taipei?**  
    Want a deeper, no-fluff breakdown on where to live — including vibes, commute times, rent ranges, and local tips?  
    👉 [Click here](https://malcolmproducts.gumroad.com/l/kambt)
    """,
    unsafe_allow_html=True
)
    st.subheader("Top 10 (current view)")
    st.write(top10_table)
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
