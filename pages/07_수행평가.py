import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# 데이터 불러오기
df = pd.read_csv("trash.csv", encoding="cp949")

st.title("📍 연도·월별 폐기물 배출량 TOP10 시각화")
st.write("배출량이 많을수록 색이 진하게 표시됩니다.")

# -----------------------------
# 🔍 사이드바 필터
# -----------------------------
years = sorted(df["배출연도"].unique())
months = sorted(df["배출월"].unique())

year = st.sidebar.selectbox("연도 선택", years)
month = st.sidebar.selectbox("월 선택", months)
search_keyword = st.sidebar.text_input("지역 검색 (기초지자체 이름 입력)")

# -----------------------------
# 🔍 데이터 필터링
# -----------------------------
filtered = df[(df["배출연도"] == year) & (df["배출월"] == month)]

if search_keyword:
    filtered = filtered[filtered["기초지자체"].str.contains(search_keyword, case=False)]

# 상위 10개
top10 = filtered.sort_values("배출량(톤)", ascending=False).head(10)
top10 = top10.reset_index(drop=True)

st.subheader(f"📊 {year}년 {month}월 Top 10 배출 지역")
st.dataframe(top10)

# -----------------------------
# 🎨 색상 그라데이션 설정
# -----------------------------
colors = [
    "#ff0066", "#ff1a75", "#ff3385", "#ff4d94", "#ff66a3",
    "#ff80b3", "#ff99c2", "#ffb3d1", "#ffcce0", "#ffe6f0"
]

# -----------------------------
# 🗺 지도 표시
# -----------------------------
m = folium.Map(location=[36.5, 127.8], zoom_start=7)

coord_map = {
    "서울특별시": [37.5665, 126.9780],
    "부산광역시": [35.1796, 129.0756],
    "대구광역시": [35.8714, 128.6014],
    "인천광역시": [37.4563, 126.7052],
    "광주광역시": [35.1595, 126.8526],
    "대전광역시": [36.3504, 127.3845],
    "울산광역시": [35.5384, 129.3114],
    "세종특별자치시": [36.4800, 127.2880],
    "경기도": [37.2751, 127.0090],
    "강원도": [37.8228, 128.1555],
    "충청북도": [36.8000, 127.7000],
    "충청남도": [36.5184, 126.8000],
    "전라북도": [35.7175, 127.1530],
    "전라남도": [34.8679, 126.9910],
    "경상북도": [36.4919, 128.8889],
    "경상남도": [35.4606, 128.2132],
    "제주특별자치도": [33.4996, 126.5312]
}

for idx, row in top10.iterrows():
    city = row["광역시도"]
    gu = row["기초지자체"]
    emission = row["배출량(톤)"]

    lat, lon = coord_map.get(city, [36.5, 127.8])
    color = colors[idx]  # 순위 기반 색상 선택

    folium.CircleMarker(
        location=[lat, lon],
        radius=12,  # 크기 일정하게 유지
        popup=f"{city} {gu}<br>배출량: {emission:,} 톤",
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.85
    ).add_to(m)

st.subheader("🗺 지도 시각화 (색상 = 배출량 순위)")
st_folium(m, width=700, height=500)
