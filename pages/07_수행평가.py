import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim

# 페이지 설정
st.set_page_config(page_title="연도·월별 폐기물 배출 지도", layout="wide")

# 데이터 로드
@st.cache_data
def load_data():
    df = pd.read_csv("trash.csv", encoding="cp949")
    return df

# 지오코딩(위경도 변환)
@st.cache_data
def geocode_location(location):
    geolocator = Nominatim(user_agent="waste_map_app")
    try:
        geo = geolocator.geocode(location)
        if geo:
            return geo.latitude, geo.longitude
    except:
        pass
    return None, None

df = load_data()

st.title("🗺 연도·월별 폐기물 배출량 지도 시각화 (Top 10)")

# ---------------------
# 🔍 Sidebar 영역
# ---------------------
years = sorted(df["배출연도"].unique())
months = sorted(df["배출월"].unique())

selected_year = st.sidebar.selectbox("📆 연도를 선택하세요", years)
selected_month = st.sidebar.selectbox("🗓 월을 선택하세요", months)

search_text = st.sidebar.text_input("🔍 지역 검색 (예: 서울특별시 종로구)")

st.sidebar.markdown("---")
st.sidebar.write("검색을 입력하면 해당 지역이 지도에 표시됩니다.")

# ---------------------
# 📌 선택된 연도/월 데이터 필터링
# ---------------------
filtered = df[(df["배출연도"] == selected_year) & (df["배출월"] == selected_month)]

st.subheader(f"📌 {selected_year}년 {selected_month}월 배출량 TOP 10 지역")

# Top 10 가져오기
top10 = filtered.sort_values("배출량(톤)", ascending=False).head(10)
st.dataframe(top10)

# ---------------------
# 🗺 지도 생성
# ---------------------
m = folium.Map(location=[36.5, 127.5], zoom_start=7)
marker_cluster = MarkerCluster().add_to(m)

# ---------------------
# 📍 TOP10 마커 추가 (핑크색)
# ---------------------
for _, row in top10.iterrows():
    loc_name = f"{row['광역시도']} {row['기초지자체']}"
    lat, lon = geocode_location(loc_name)

    if lat is not None:
        popup_text = f"<b>{loc_name}</b><br>배출량: {row['배출량(톤)']:,} 톤"
        folium.Marker(
            [lat, lon],
            popup=popup_text,
            icon=folium.Icon(color="pink", icon="info-sign")
        ).add_to(marker_cluster)

# ---------------------
# 🔍 지역 검색 기능
# ---------------------
if search_text.strip() != "":
    lat, lon = geocode_location(search_text)

    if lat is not None:
        folium.Marker(
            [lat, lon],
            popup=f"<b>{search_text}</b>",
            icon=folium.Icon(color="pink", icon="star")
        ).add_to(m)

        # 검색 지역으로 지도 이동
        m.location = [lat, lon]
        m.zoom_start = 12
    else:
        st.warning("⚠ 검색한 지역을 찾을 수 없습니다. (정확한 행정구역명을 입력해주세요)")

# ---------------------
# 지도 출력
# ---------------------
st_folium(m, width=1000, height=600)
