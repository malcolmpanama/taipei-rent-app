# app.py  –  Taipei District Rent Dashboard
import streamlit as st
import pandas as pd
import geopandas as gpd
import json, plotly.express as px

# ---------- page setup ----------
st.set_page_config("Taipei Rent Map", layout="wide", page_icon=":house:")

# ---------- load data ----------
DATA_DIR = "data/"
gdf = gpd.read_file(DATA_DIR + "taipei_districts_4326.geojson")
agg = pd.read_csv(DATA_DIR + "taipei_rent_district_metrics.csv")
gdf = gdf.merge(agg, left_on="TNAME", right_on="District", how="left")

# ---------- sidebar filters ----------
with st.sidebar:
    st.header("Filters")

    type_opts  = sorted(agg["type"].unique())
    room_opts  = sorted(agg["Rooms"].unique())

    sel_types  = st.multiselect("Building type", type_opts, type_opts)
    sel_rooms  = st.multiselect("Rooms (房)", room_opts, room_opts)

    metric = st.radio(
        "Colour metric",
        ("Median_Rent", "Median_Rent_per_ping", "Median_Rent_per_sqm"),
        format_func=lambda m: {
            "Median_Rent":"Median NT$ / month",
            "Median_Rent_per_ping":"Median NT$ / 坪",
            "Median_Rent_per_sqm":"Median NT$ / m²"}[m]
    )

# apply filters
mask = gdf["type"].isin(sel_types) & gdf["Rooms"].isin(sel_rooms)
gdf_f = gdf[mask]

# ---------- top‑10 table ----------
top10 = (gdf_f.sort_values(metric, ascending=False)
                [["District", metric]]
                .head(10)
                .reset_index(drop=True))

# ---------- plotly map ----------
fig = px.choropleth_mapbox(
    gdf_f,
    geojson=json.loads(gdf_f.to_json()),
    locations="TNAME",
    featureidkey="properties.TNAME",
    color=metric,
    hover_name="TNAME",
    hover_data={
        "Median_Rent":":,.0f NT$",
        "Mean_Rent":":,.0f NT$",
        "P25_Rent":":,.0f NT$",
        "P75_Rent":":,.0f NT$",
        "Listings":True
    },
    color_continuous_scale="YlOrRd",
    mapbox_style="carto-positron",
    center={"lat":25.04,"lon":121.55},
    zoom=9, opacity=0.85
)
fig.update_layout(margin=dict(l=0,r=0,t=0,b=0))

# ---------- layout ----------
col1, col2 = st.columns([1,3])

with col1:
    st.title("Taipei District Rent Explorer")
    st.markdown("Median rents by building type & room count.")
    st.subheader("Top 10 (current view)")
    st.table(top10.style.format({metric:":,.0f"}))
    st.markdown("---")
    st.markdown(
        "📺 **[My YouTube Channel](https://youtube.com/@YourChannel)** &nbsp;|&nbsp; "
        "💾 **[Full dataset on Gumroad](https://gumroad.com/l/taipei-rent-pack)**",
        unsafe_allow_html=True
    )

with col2:
    st.plotly_chart(fig, use_container_width=True)

# ---------- download button ----------
csv_bytes = gdf_f.to_csv(index=False).encode("utf-8-sig")
st.download_button("Download filtered CSV", csv_bytes,
                   file_name="taipei_rent_filtered.csv",
                   mime="text/csv")
