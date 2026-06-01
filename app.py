import streamlit as st
import numpy as np
import time

# 1. 웹페이지 기본 설정
st.set_page_config(page_title="FAB Web Automation", layout="wide")

# 고화질 픽셀 렌더링 유지 CSS
st.markdown("""
    <style>
    img {
        image-rendering: pixelated !important;
        image-rendering: crisp-edges !important;
    }
    </style>
""", unsafe_allow_html=True)

def generate_new_wafer():
    size = 20
    center = (size - 1) / 2
    radius = size / 2
    y, x = np.ogrid[:size, :size]
    dist = np.sqrt((x - center)**2 + (y - center)**2)
    
    wafer = np.zeros((size, size), dtype=int)
    wafer[dist > radius] = -2  # 원 밖 영역 (-2)
    
    # 전공정 불량(EDS Reject) 사전 마킹 (약 5%)
    valid_spots = np.where(wafer == 0)
    valid_coords = list(zip(valid_spots[0], valid_spots[1]))
    reject_indices = np.random.choice(len(valid_coords), int(len(valid_coords)*0.05), replace=False)
    for idx in reject_indices:
        wafer[valid_coords[idx]] = -1  # 전공정 불량 (-1)
    return wafer, valid_coords

# 2. 세션 상태(장비 메모리) 초기화
if "wafer_num" not in st.session_state:
    st.session_state.wafer_num = 1
    st.session_state.scan_idx = 0
    st.session_state.is_running = False
    st.session_state.interlock = False
    st.session_state.current_fault = None
    
    wafer, valid_coords = generate_new_wafer()
    st.session_state.wafer_data = wafer
    st.session_state.valid_coords = valid_coords

# 3. 사이드바 컨트롤 패널 구성
st.sidebar.title("🏭 CHIP ATTACH WEB LINE")
st.sidebar.markdown(f"### **Current Wafer:** {st.session_state.wafer_num} / 25")

# 수율 및 진행률 실시간 계산
total_valid = np.sum(st.session_state.wafer_data >= -1)
good_chips = np.sum(st.session_state.wafer_data == 1)
current_yield = (good_chips / total_valid) * 100 if total_valid > 0 else 0.0
progress = (st.session_state.scan_idx / len(st.session_state.valid_coords)) * 100

st.sidebar.metric(label="Real-time Yield (수율)", value=f"{current_yield:.1f} %")
st.sidebar.progress(int(progress))
st.sidebar.caption(f"Wafer Progress: {progress:.1f}%")

# 제어 버튼
col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("▶ Auto Start", disabled=st.session_state.is_running or st.session_state.interlock, use_container_width=True):
        st.session_state.is_running = True
        st.rerun()
with col2:
    if st.button("🔄 Reset Line", use_container_width=True):
        st.session_state.wafer_num = 1
        st.session_state.scan_idx = 0
        st.session_state.is_running = False
        st.session_state.interlock = False
        st.session_state.current_fault = None
        wafer, valid_coords = generate_new_wafer()
        st.session_state.wafer_data = wafer
        st.session_state.valid_coords = valid_coords
        st.rerun()

# 4. 메인 대시보드 타이틀
st.title("🖥️ Inline Web-MES Packaging Control Dashboard")

# 🚨 인터록(불량 발생) 활성화 시 처리 창
if st.session_state.interlock:
    r, c = st.session_state.current_fault
    st.error(f"⚠️ **EQUIPMENT INTERLOCK ACTIVATED:** [{r}행, {c}열] 칩 어태치 조립 불량 검출!")
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🔧 Execute Rework (리웍 후 양품 전환)", type="primary", use_container_width=True):
            st.session_state.wafer_data[r, c] = 1
            st.session_state.interlock = False
            st.session_state.is_running = True
            st.session_state.scan_idx += 1
            st.rerun()
            
    with col_btn2:
        if st.button("❌ Confirm Reject (리젝 확정 및 패스)", use_container_width=True):
            st.session_state.wafer_data[r, c] = -1
            st.session_state.interlock = False
            st.session_state.is_running = True
            st.session_state.scan_idx += 1
            st.rerun()

# 🎨 5. 고해상도 칩 테두리(Grid) 매핑 프로세스
# 각 칩을 1x1 픽셀로 그리지 않고, 24x24 픽셀 영역으로 확대해 경계선을 만듭니다.
cell_size = 24
grid_color = [30, 41, 59]  # 칩 사이를 나눌 딥네이비 테두리 선 색상

color_map = {
    -2: [15, 23, 42],    # 다크 네이비 배경
    -1: [239, 68, 68],   # 불량 (빨강)
     0: [100, 116, 139], # 대기 (회색)
     1: [16, 185, 129]   # 성공 (초록)
}

# 20x20 배열을 테두리 포함 크기(480x480)의 고해상도 이미지로 빌드
img_data = np.zeros((20 * cell_size, 20 * cell_size, 3), dtype=np.uint8)

for r in range(20):
    for c in range(20):
        val = st.session_state.wafer_data[r, c]
        color = color_map[val]
        
        # 칩 내부 영역 색상 채우기
        r_start, r_end = r * cell_size, (r + 1) * cell_size
        c_start, c_end = c * cell_size, (c + 1) * cell_size
        img_data[r_start:r_end, c_start:c_end] = color
        
        # 원 밖 영역(-2)이 아닐 때만 칩 가장자리에 깔끔하게 테두리 선 긋기
        if val != -2:
            img_data[r_start:r_end, c_end-1] = grid_color  # 우측 테두리
            img_data[r_end-1, c_start:c_end] = grid_color  # 하단 테두리

# 화면에 선명한 고해상도 격자형 웨이퍼 출력
st.image(img_data, width=500, use_container_width=False)

# 6. 자동화 공정 실시간 백엔드 연산 제어 루프
if st.session_state.is_running and not st.session_state.interlock:
    if st.session_state.scan_idx < len(st.session_state.valid_coords):
        r, c = st.session_state.valid_coords[st.session_state.scan_idx]
        current_state = st.session_state.wafer_data[r, c]
        
        if current_state == -1:
            st.session_state.scan_idx += 1
            st.rerun()
        elif current_state == 0:
            time.sleep(0.04)
            
            if np.random.rand() > 0.02:
                st.session_state.wafer_data[r, c] = 1
                st.session_state.scan_idx += 1
                st.rerun()
            else:
                st.session_state.wafer_data[r, c] = -1
                st.session_state.interlock = True
                st.session_state.is_running = False
                st.session_state.current_fault = (r, c)
                st.rerun()
    else:
        st.session_state.is_running = False
        if st.session_state.wafer_num < 25:
            st.session_state.wafer_num += 1
            st.session_state.scan_idx = 0
            wafer, valid_coords = generate_new_wafer()
            st.session_state.wafer_data = wafer
            st.session_state.valid_coords = valid_coords
            st.session_state.is_running = True
            st.rerun()
        else:
            st.balloons()
            st.success("🏆 1개 LOT (25장) 최종 패키징 공정 마감 완료!")