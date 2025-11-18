import streamlit as st
st.title('나의 첫 웹 서비스 만들기!')
a=st.text_input('이름이 머누')
b=st.selectbox('좋아하는 음식을 골라바',['마라탕', '떡볶이', '김치찌개'])
if st.button('인사말 생성'):
  st.info(a+'님, 하이! 반가와')
st.warning(b+'를 조아하는 구나')
st.error('반가워')
st.balloons()
