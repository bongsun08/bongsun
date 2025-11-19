import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from geopy.geocoders import GoogleV3
import os
import time

# --- 1. 데이터 로드 함수 (Streamlit Caching) ---
@st.cache_data
def load_data(file_path):
    """CSV 파일을 로드하고 초기 데이터 처리를 수행합니다."""
    try:
        df = pd.read_csv(file_path, encoding='utf-8')
        # 필요한 열만 선택하고, 결측값 처리 (이 데이터에서는 결측값 없음)
        df = df[['시도', '시_군_구', '재산피해소계', '장소대분류']]
        return df
    except Exception as e:
        st.error(f"데이터 로딩 중 오류 발생: {e}")
        return pd.DataFrame()

# --- 2. Google Maps API를 사용한 지오코딩 함수 ---
@st.cache_data
def geocode_location(address):
    """주소(시도 + 시_군_구)를 위도 및 경도로 변환합니다."""
    # Streamlit Secrets 또는 환경 변수에서 API 키 로드
    api_key = os.getenv("GOOGLE_MAPS_API_KEY") or st.secrets.get("GOOGLE_MAPS_API_KEY")
    
    if not api_key:
        st.warning("Google Maps API 키를 설정해주세요 (`Maps_API_KEY`). 지도 기능이 작동하지 않습니다.")
        return None, None
    
    try:
        geolocator = GoogleV3(api_key=api_key)
        location = geolocator.geocode(address, timeout=10)
        
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
            
    except Exception as e:
        # API 사용량 제한, 시간 초과 등 예외 처리
        # st.error(f"지오코딩 오류: {e}")
        return None, None

# --- 3. Streamlit 앱 메인 함수 ---
def app():
    st.set_page_config(layout="wide", page_title="화재 재산피해 시각화")
    st.title("🔥 전국 화재 재산피해 시각화")
    st.markdown("재산피해 규모가 큰 상위 화재를 지도에 표시합니다. (데이터는 상위 500건 사용)")
    
    # --- 데이터 로드 및 전처리 ---
    file_path = "fire.csv"  # Streamlit Cloud에서 파일 이름
    df = load_data(file_path)

    if df.empty:
        return

    # 재산피해소계를 기준으로 내림차순 정렬 및 상위 500개만 선택
    df_top = df.sort_values(by='재산피해소계', ascending=False).head(500).reset_index(drop=True)
    
    # '주소' 열 생성
    df_top['주소'] = df_top['시도'] + ' ' + df_top['시_군_구']
    
    # 지오코딩 수행 (시간이 많이 소요될 수 있습니다)
    with st.spinner("지오코딩 진행 중... (Google Maps API 호출)"):
        # 캐싱된 함수 호출로 중복 API 호출 방지
        df_top[['위도', '경도']] = df_top['주소'].apply(
            lambda x: pd.Series(geocode_location(x))
        )
        # API 호출 간 딜레이 (Rate Limit 방지)
        # time.sleep(0.1) 
    
    # 유효한 좌표만 필터링
    df_map = df_top.dropna(subset=['위도', '경도'])

    if df_map.empty:
        st.warning("유효한 좌표를 찾을 수 없습니다. API 키와 데이터 주소를 확인해주세요.")
        return

    # --- 4. Folium 지도 시각화 ---
    
    # 재산 피해 규모를 마크 크기로 변환하기 위한 정규화 (최솟값 5, 최댓값 30)
    min_val = df_map['재산피해소계'].min()
    max_val = df_map['재산피해소계'].max()

    def get_radius(value):
        """재산피해소계 값에 비례하는 마크 크기 반환"""
        if max_val == min_val:
            return 10
        # Min-Max Normalization 후 범위 조정: (5 ~ 30)
        normalized = (value - min_val) / (max_val - min_val)
        return 5 + normalized * 25 # 최소 5, 최대 30

    # 지도 초기화 (평균 위도/경도 사용)
    m = folium.Map(
        location=[df_map['위도'].mean(), df_map['경도'].mean()], 
        zoom_start=7
    )
    
    marker_cluster = MarkerCluster().add_to(m)

    # 각 화재 위치에 마크 추가
    for idx, row in df_map.iterrows():
        radius = get_radius(row['재산피해소계'])
        
        # 팝업 텍스트 포맷팅 (원 단위로 변환)
        popup_text = f"""
            **주소:** {row['시도']} {row['시_군_구']}<br>
            **장소:** {row['장소대분류']}<br>
            **재산피해:** {row['재산피해소계']:,}원
        """
        
        folium.CircleMarker(
            location=[row['위도'], row['경도']],
            radius=radius,
            color='red',
            fill=True,
            fill_color='red',
            fill_opacity=0.6,
            popup=popup_text
        ).add_to(marker_cluster)

    # Streamlit에 지도 표시
    st.subheader("재산피해 규모별 화재 위치 지도")
    st.markdown("*마크의 크기는 재산피해소계 값에 비례합니다.*")
    st.folium_static(m, width=1200, height=700)
    
    # --- 데이터 프레임 미리보기 ---
    st.subheader("상위 500개 화재 데이터 미리보기")
    st.dataframe(df_map[['시도', '시_군_구', '재산피해소계', '장소대분류', '위도', '경도']])

if __name__ == "__main__":
    app()
