# app.py
import streamlit as st
import pandas as pd
import json
import requests
import io
import folium
from folium.features import GeoJsonTooltip
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

st.set_page_config(page_title="행정구역 Choropleth (배출량)", layout="wide")

# --- 설정: 로컬 CSV 파일 경로 (업로드하신 파일) ---
CSV_PATH = "/mnt/data/trash.csv"   # <-- 이미 업로드된 파일 경로

# --- (추천) 공개 GeoJSON URL (시군구 레벨) ---
# 출처: southkorea / southkorea-maps (kostat 2018 예시). 필요시 다른 연도/파일로 바꿔도 됩니다.
GEOJSON_URL = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2018/json/skorea-municipalities-2018-geo.json"

# ---------------------------
# 유틸: 데이터 로드
# ---------------------------
@st.cache_data
def load_csv(path=CSV_PATH):
    # CSV는 cp949로 인코딩되어 있는 경우가 있으므로 시도해서 읽음
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            df = pd.read_csv(path, encoding=enc)
            return df
        except Exception:
            pass
    raise RuntimeError("CSV 파일을 읽을 수 없습니다. 인코딩 문제 또는 파일 경로 확인 필요.")

@st.cache_data
def load_geojson_from_url(url):
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        # 실패하면 None 반환 (앱에서 업로드 옵션 제공)
        return None

# ---------------------------
# Helper: GeoJSON property 이름 자동 탐색 (행정구역명 필드 찾기)
# ---------------------------
def detect_name_property(geojson):
    # 후보 필드 목록(다양한 repo/파일에서 쓰이는 이름)
    candidates = ["adm_nm", "ADM_NM", "name", "SIG_KOR_NM", "EMD_KOR_NM", "CTP_KOR_NM", "adm_nm_eng", "ADM_NM_2", "NAME"]
    features = geojson.get("features", [])
    if not features:
        return None
    props = features[0].get("properties", {})
    # 가장 먼저 일치하는 후보를 반환
    for c in candidates:
        if c in props:
            return c
    # fallback: 가장 길이(문자열) 값이 '한글'로 보이는 속성 선택
    for k, v in props.items():
        if isinstance(v, str) and any("\u3131" <= ch <= "\u3163" or "\uac00" <= ch <= "\ud7a3" for ch in v):
            return k
    # 없으면 첫번째 키 반환
    return next(iter(props.keys()), None)

# ---------------------------
# 데이터 준비
# ---------------------------
df = load_csv()
# 컬럼명 정리(공백 등)
df.columns = [c.strip() for c in df.columns]

# 타입 보정
df["배출연도"] = df["배출연도"].astype(int)
df["배출월"] = df["배출월"].astype(int)
df["배출량(톤)"] = pd.to_numeric(df["배출량(톤)"], errors="coerce").fillna(0)

st.title("🗺 행정구역별 Choropleth — 폐기물 배출량")
st.markdown("**행정구역(시군구) 단위 Choropleth + 상세 Tooltip** (GeoJSON: southkorea/southkorea-maps 권장).")

# ---------------------------
# Sidebar: 연도·월·옵션
# ---------------------------
st.sidebar.header("필터 & 옵션")
years = sorted(df["배출연도"].unique().tolist())
selected_year = st.sidebar.selectbox("연도", years, index=len(years)-1)
months = sorted(df["배출월"].unique().tolist())
selected_month = st.sidebar.selectbox("월", months, index=0)

# 툴팁에 보여줄 상위 n개(같은 광역시도 내 상위 기초지자체 등)
top_n_tooltip = st.sidebar.number_input("툴팁에 상위 N개 기초지자체 표시 (각 광역시도 내)", min_value=1, max_value=10, value=3, step=1)

st.sidebar.markdown("---")
st.sidebar.write("만약 자동으로 GeoJSON 로드가 실패하면, 로컬 GeoJSON 파일을 업로드하거나 다른 URL을 입력하세요.")

# ---------------------------
# GeoJSON 로드(기본: URL) + 업로드 폼
# ---------------------------
geojson = load_geojson_from_url(GEOJSON_URL)
if geojson is None:
    st.sidebar.warning("기본 GeoJSON을 자동으로 불러오지 못했습니다. 수동 업로드 또는 다른 URL 입력을 권장합니다.")
    uploaded = st.sidebar.file_uploader("GeoJSON 파일 업로드 (.geojson)", type=["geojson", "json"])
    if uploaded is not None:
        geojson = json.load(uploaded)
else:
    st.sidebar.success("기본 GeoJSON을 불러왔습니다. (southkorea/southkorea-maps 기준).")

# ---------------------------
# 데이터 집계: 선택된 연·월 기준 기초지자체별 합계
# ---------------------------
filtered = df[(df["배출연도"] == selected_year) & (df["배출월"] == selected_month)].copy()
agg = filtered.groupby(["광역시도", "기초지자체"], as_index=False)["배출량(톤)"].sum()
agg.rename(columns={"기초지자체": "name", "배출량(톤)": "value"}, inplace=True)

total_value = agg["value"].sum()
st.sidebar.write(f"선택된 기간 전체 배출량 합계: **{int(total_value):,} 톤**")

# ---------------------------
# GeoJSON과 매칭: feature 속성에서 지역명 필드 찾기
# ---------------------------
if geojson is None:
    st.error("GeoJSON 데이터가 없습니다. 사이드바에서 업로드하거나 인터넷 연결을 확인해주세요.")
    st.stop()

name_prop = detect_name_property(geojson)
if name_prop is None:
    st.error("GeoJSON에서 지역명 속성을 자동으로 찾을 수 없습니다. 업로드하신 GeoJSON의 properties를 확인해주세요.")
    st.stop()

# Build a mapping dict {지역명(데이터): value}
value_map = dict(zip(agg["name"].astype(str).str.strip(), agg["value"]))

# Because 이름 표기 차이가 있을 수 있어, 작은 전처리 맵을 준비 (예: '서울특별시 종로구' vs '종로구' 등)
# 우리는 GeoJSON의 각 feature에서 name_prop 값을 읽고, 아래 규칙으로 매칭 시도:
# 1) 동일 문자열 매칭
# 2) feature_name이 '광역시도 + 기초지자체' 형태면 앞뒤 결합으로 매칭
# 3) feature_name의 공백/특수문자 제거해서 매칭
def find_value_for_feature(feature_name):
    fn = feature_name.strip()
    # 직접 매칭
    if fn in value_map:
        return value_map[fn]
    # 공백 제거 버전
    k = fn.replace(" ", "")
    for dkey in value_map.keys():
        if dkey.replace(" ", "") == k:
            return value_map[dkey]
    # 기초지자체만 포함하면(예: '종로구'만 있으면) 마지막 토큰으로 매칭 시도
    if " " in fn:
        last = fn.split()[-1]
        if last in value_map:
            return value_map[last]
        if last.replace(" ", "") in value_map:
            return value_map[last.replace(" ", "")]
    # 실패하면 0
    return 0

# Prepare a dictionary mapping feature id -> value (and store in feature properties for tooltip)
for feat in geojson.get("features", []):
    props = feat.setdefault("properties", {})
    feature_name = str(props.get(name_prop, "")).strip()
    v = find_value_for_feature(feature_name)
    props["_value"] = v
    props["_display_name"] = feature_name

# ---------------------------
# Folium 지도 생성 및 Choropleth
# ---------------------------
m = folium.Map(location=[36.5, 127.8], zoom_start=7)

# Choropleth — value가 0인 곳도 채우도록 na_fill_color 지정
choropleth = folium.Choropleth(
    geo_data=geojson,
    name="choropleth",
    data=pd.DataFrame([(f["properties"].get("_display_name",""), f["properties"].get("_value",0)) for f in geojson["features"]], columns=["name","value"]),
    columns=["name","value"],
    key_on=f"feature.properties._display_name",
    fill_color="YlOrRd",
    nan_fill_color="white",
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name=f"{selected_year}-{selected_month} 배출량 (톤)",
    highlight=True
).add_to(m)

# Tooltip: 이름, 값, 비율, (해당 광역시도 내 상위 N개 예시)
# To compute additional info (like % of total), we can use properties already set
def make_tooltip_html(props):
    name = props.get("_display_name", "Unknown")
    value = int(props.get("_value", 0))
    pct = (value / total_value * 100) if total_value > 0 else 0.0
    html = f"<div style='font-size:14px'><b>{name}</b><br>"
    html += f"배출량: <b>{value:,}</b> 톤<br>"
    html += f"전체 대비: <b>{pct:.2f}%</b><br>"
    html += "</div>"
    return html

# Add GeoJson layer with tooltip (so hover shows tooltip)
gj = folium.GeoJson(
    geojson,
    name="행정구역",
    tooltip=folium.GeoJsonTooltip(
        fields=["_display_name", "_value"],
        aliases=["지역명", "배출량(톤)"],
        localize=True,
        labels=True,
        sticky=True
    ),
    highlight_function=lambda x: {"weight":3, "color":"blue"},
).add_to(m)

# Customize tooltips with more info (popup-like on hover/click)
for feat in gj.data["features"]:
    props = feat["properties"]
    tooltip_html = make_tooltip_html(props)
    folium.Popup(tooltip_html, max_width=300).add_to(folium.GeoJson(feat))

# ---------------------------
# Top10 마커(기존) — MarkerCluster
# ---------------------------
marker_cluster = MarkerCluster(name="Top10 위치(geocoding 필요)").add_to(m)

# 지오코딩 없이 간단하게: top10 표 보여주기 + (선택적으로) 사용자가 지도 중앙으로 이동시키는 버튼 제공
top10_df = agg.sort_values("value", ascending=False).head(10).reset_index(drop=True)
st.subheader(f"{selected_year}년 {selected_month}월 — 기초지자체별 상위 10")
st.dataframe(top10_df.style.format({"value":"{:,}"}))

st.info("※ Top10 지점은 현재 좌표(위경도) 정보가 파일에 없어 자동 마커 위치를 찍지 않습니다. "
        "원하면 geopy Nominatim 등을 사용해 '광역시도 기초지자체'로 geocoding하여 마커를 추가할 수 있습니다.")

# ---------------------------
# 레이어 컨트롤 & 출력
# ---------------------------
folium.LayerControl().add_to(m)
st_folium(m, width=1000, height=700)

# ---------------------------
# 데이터 다운로드 (선택)
# ---------------------------
st.markdown("---")
st.subheader("데이터 다운로드")
csv_bytes = agg.to_csv(index=False).encode("utf-8-sig")
st.download_button("기초지자체별 집계 CSV 다운로드", csv_bytes, file_name=f"aggregated_{selected_year}_{selected_month}.csv", mime="text/csv")
