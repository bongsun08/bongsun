import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import matplotlib.colors as mcolors
import geopy
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# -----------------
# 1. 설정 및 데이터 로드
# -----------------
st.set_page_config(layout="wide", page_title="연간 화재 통계 분석")
st.title("🔥 연간 화재 통계 (재산피해 기준)")
st.caption("소방청_연간화재통계_20241231.csv 분석 결과")

@st.cache_data
def load_data(file_path):
    """CSV 파일을 로드하고 초기 데이터 처리를 수행합니다."""
    # 파일 경로가 사용자가 올린 파일의 contentFetchId에 해당함
    df = pd.read_csv(file_path, encoding='utf-8')
    # NaN은 '미상'으로 처리하여 문자열 결합에 문제가 없도록 합니다.
    df['시_군_구'] = df['시_군_구'].fillna('미상')
    # 지오코딩을 위한 주소 컬럼 생성
    df['full_address'] = df['시도'] + ' ' + df['시_군_구']
    # '인명피해(명)소계', '사망', '부상' 컬럼은 0으로 표기되어 있어 제외하거나 필요 시 활용
    
    # Folium 시각화를 위해 재산피해소계가 큰 순서로 정렬하고 상위 100개만 사용
    # *참고: 스트림릿 클라우드 환경에서 지오코딩은 API 호출 제한 및 실행 시간 문제로 전체 데이터 처리 시 비효율적입니다.
    # 따라서 재산피해 상위 100건만 시각화합니다.
    df_top = df.sort_values(by='재산피해소계', ascending=False).head(100).reset_index(drop=True)
    return df_top

# -----------------
# 2. 지오코딩 함수
# -----------------

@st.cache_data
def geocode_data(df):
    """주소 정보를 위도, 경도로 변환합니다."""
    # Nominatim geolocator 초기화
    geolocator = Nominatim(user_agent="fire_analysis_app")
    
    # RateLimiter를 사용하여 쿼리 간 지연시간 설정 (과도한 API 호출 방지)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.5, max_retries=3)
    
    st.info("⚠️ **지오코딩 진행 중**: 재산피해 상위 100건의 주소 정보를 위도/경도로 변환하는 중입니다. (약 2~3분 소요)")
    
    # 주소에 대한 위도/경도 정보를 새로운 컬럼에 저장
    location_data = df['full_address'].apply(geocode)
    
    df['Latitude'] = location_data.apply(lambda loc: loc.latitude if loc else None)
    df['Longitude'] = location_data.apply(lambda loc: loc.longitude if loc else None)
    
    # 유효한 좌표만 남기기
    df_geo = df.dropna(subset=['Latitude', 'Longitude'])
    st.success(f"지오코딩 완료: 유효한 위치 정보 {len(df_geo)}건")
    return df_geo

# -----------------
# 3. Folium 지도 생성 함수
# -----------------

def create_folium_map(df_geo):
    """Folium 지도를 생성하고 마커를 추가합니다."""
    
    # 지도 중심 설정 (대한민국 중앙 부근)
    map_center = [35.907757, 127.766922] 
    
    # Folium 지도 객체 생성
    m = folium.Map(location=map_center, zoom_start=7, tiles="cartodbdarkmatter")
    
    # MarkerCluster 플러그인 사용 (마커가 겹칠 때 그룹화)
    marker_cluster = MarkerCluster().add_to(m)
    
    # 재산피해소계의 최소/최대값으로 크기 및 색상 스케일 정의
    max_damage = df_geo['재산피해소계'].max()
    min_damage = df_geo['재산피해소계'].min()
    
    # 재산피해 규모에 따른 색상 스케일 (예: 노랑 -> 빨강)
    cmap = mcolors.LinearSegmentedColormap.from_list("damage_scale", ["#FFFF00", "#FF0000"])
    
    for _, row in df_geo.iterrows():
        lat = row['Latitude']
        lon = row['Longitude']
        damage = row['재산피해소계']
        
        # 재산피해에 비례하는 반지름 계산 (시각적 효과를 위해 로그 스케일 및 상수 곱 적용)
        # 1000만원 = 1, 10억원 = 1000
        radius_scale = 0.00001
        radius = (damage * radius_scale) ** 0.5 + 5  # 기본 크기 5 추가
        
        # 피해액에 따른 색상 결정 (정규화 후 색상 매핑)
        if max_damage > min_damage:
             normalized_damage = (damage - min_damage) / (max_damage - min_damage)
        else:
             normalized_damage = 1
             
        color_rgb = cmap(normalized_damage)
        color_hex = mcolors.rgb2hex(color_rgb)
        
        # 팝업 정보
        popup_html = f"""
        <b>장소:</b> {row['full_address']}<br>
        <b>피해액:</b> {damage:,.0f} 원<br>
        <b>발화요인:</b> {row['발화요인대분류']} / {row['발화요인소분류']}<br>
        <b>최초착화물:</b> {row['최초착화물소분류']}
        """

        # CircleMarker (원형 마커) 추가
        folium.CircleMarker(
            location=(lat, lon),
            radius=radius,
            color=color_hex,
            fill=True,
            fill_color=color_hex,
            fill_opacity=0.7,
            popup=popup_html
        ).add_to(marker_cluster)
        
    return m

# -----------------
# 4. Streamlit 실행 로직
# -----------------

if __name__ == "__main__":
    # 데이터 로드
    df_top = load_data("소방청_연간화재통계_20241231.csv")
    
    # 데이터 요약 정보 표시
    st.subheader("📊 재산피해 상위 100건 데이터 정보")
    st.write(f"최대 재산 피해액: **{df_top['재산피해소계'].max():,.0f}** 원")
    st.dataframe(df_top.head(5))

    # 지오코딩 및 지도 생성
    if st.button("🗺️ 지도 시각화 시작 (지오코딩 필요)"):
        df_geo = geocode_data(df_top)
        
        # 유효한 데이터가 있을 경우 지도 표시
        if not df_geo.empty:
            st.subheader("🌐 재산피해 규모별 Folium 지도")
            st.markdown("마커의 **크기**와 **색상(노랑 → 빨강)**은 **재산피해소계**에 비례하며, 마커를 클릭하면 상세 정보를 볼 수 있습니다.")
            
            folium_map = create_folium_map(df_geo)
            
            # Streamlit에 Folium 지도 표시
            from streamlit_folium import st_folium
            st_folium(folium_map, width=1000, height=700)
        else:
            st.error("지오코딩에 실패하여 지도에 표시할 유효한 위치 정보가 없습니다.")
