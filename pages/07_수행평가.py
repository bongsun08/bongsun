import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim

st.set_page_config(page_title="연도별 폐기물 배출 지도", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv("trash.csv", encoding="cp949")
    return df

@st.cache_data
def geocode_location(location):
    geolocator = Nominatim(user_agent="waste_map")
    try:
        geo = geolocator.geocode(location)
        if geo:
            return geo.latitude, geo.longitude
    except:
        pass
    return None, None

df = load_data()

st.title("🗺 연도별 폐기물 배출 지도 시각화 (Top 10)")

# --- Sidebar ---
years = sorted(df["배출연도"].unique())
selected_year = st.sidebar.selectbox("연도를 선택하세요", years)

st.subheader(f"📌 {selected_year}년 배출량 TOP 10 지역")

# --- 연도별 Top 10 데이터 추출 ---
df_year = df[df["배출연도"] == selected_year]
top10 = df_year.sort_values("배출량(톤)", ascending=False).head(10)

st.dataframe(top10)

# --- 지도 생성 ---
m = folium.Map(location=[36.5, 127.5], zoom_start=7)
marker_cluster = MarkerCluster().add_to(m)

# --- 위치 변환 + 지도 표시 ---
for _, row in top10.iterrows():
    loc_name = f"{row['광역시도']} {row['기초지자체']}"
    lat, lon = geocode_location(loc_name)
    if lat is not None and lon is not None:
        popup_text = f"{loc_name}<br>배출량: {row['배출량(톤)']:,} 톤"
        folium.Marker([lat, lon], popup=popup_text).add_to(marker_cluster)

st_folium(m, width=900, height=600)
