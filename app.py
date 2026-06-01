import streamlit as st
import numpy as np
import pandas as pd
import time

# 1. 웹페이지 기본 설정 (한 번만 실행)
st.set_page_config(page_title="FAB Web Automation Pro", layout="wide")

# UI 가시성 및 수율 글자 색상/크기 극대화 CSS
st.markdown("""
    <style>
    img {
        image-rendering: pixelated !important;
        image-rendering: crisp-edges !important;
    }
    [data-testid="stMetricValue"] {
        color: #00ff66 !important;
        font-weight: bold !important;
        font-size: 2.5rem !important;
        text-shadow: 1px 1px 10px rgba(0,255,102,0.3);
    }
    [data-testid="stMetricLabel"] {
        color: #ffffff !important;
    }
    .stProgress > div > div > div > div {
        background-color: #00ff66 !important;
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
    
    # 전공정 불량(EDS Reject) 사전 마킹 (약 6%)
    valid_spots = np.where(wafer == 0)
    valid_coords = list(zip(valid_spots[0], valid_spots[1]))
    reject_indices = np.random.choice(len(valid_coords), int(len(valid_coords)*0.06), replace=False)
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
    
    st.session_state.total_processed_chips = 0  
    st.session_state.total_good_chips = 0       
    st.session_state.rework_count = 0           
    st.session_state.reject_count = 0           
    st.session_state.wafer_history = []         
    
    st.session_state.maintenance_required = False 
    st.session_state.pm_done_signal = False       

    wafer, valid_coords = generate_new_wafer()
    st.session_state.wafer_data = wafer
    st.session_state.valid_coords = valid_coords

# 3. 사이드바 컨트롤 패널 구성
st.sidebar.title("🏭 MES PACKAGING LINE")
sidebar_title_holder = st.sidebar.empty()
sidebar_title_holder.markdown(f"### **현재 웨이퍼 런:** {st.session_state.wafer_num} / 25 장")

# LOT 누적 수율 계산 함수
def get_lot_yield():
    if st.session_state.total_processed_chips == 0:
        return 100.0
    return (st.session_state.total_good_chips / st.session_state.total_processed_chips) * 100

# 사이드바 실시간 데이터 홀더 지정 (깜빡임 방지용)
yield_metric_holder = st.sidebar.empty()
progress_bar_holder = st.sidebar.empty()
progress_text_holder = st.sidebar.empty()

# 사이드바 초기 렌더링
lot_yield = get_lot_yield()
progress = (st.session_state.scan_idx / len(st.session_state.valid_coords)) * 100 if len(st.session_state.valid_coords) > 0 else 0
yield_metric_holder.metric(label="📊 LOT 누적 공정 수율 (Yield)", value=f"{lot_yield:.2f} %")
progress_bar_holder.progress(min(int(progress), 100))
progress_text_holder.caption(f"웨이퍼 공정 진행률: {progress:.1f}% (조립 완료: {st.session_state.total_processed_chips} EA)")

st.sidebar.markdown("---")
st.sidebar.markdown("⏱️ **공정 시뮬레이션 속도 제어**")
speed_mode = st.sidebar.radio(
    "발표/시연 모드 선택",
    ["일반 실시간 모드 (눈으로 확인용)", "1 LOT 종합 시뮬레이션 모드 (즉시 결과 출력)"],
    index=0
)

st.sidebar.markdown("---")
col1, col2 = st.sidebar.columns(2)
with col1:
    if st.button("▶ Auto Start", disabled=st.session_state.is_running or st.session_state.interlock or st.session_state.maintenance_required, use_container_width=True):
        if speed_mode == "1 LOT 종합 시뮬레이션 모드 (즉시 결과 출력)":
            start_num = st.session_state.wafer_num
            for w_idx in range(start_num, 26):
                w_data, v_coords = generate_new_wafer()
                wafer_reject_count = 0
                for r, c in v_coords:
                    if w_data[r, c] == 0:
                        st.session_state.total_processed_chips += 1
                        fail_rate = 0.012 if st.session_state.pm_done_signal else 0.048
                        if np.random.rand() > fail_rate:
                            w_data[r, c] = 1
                            st.session_state.total_good_chips += 1
                        else:
                            w_data[r, c] = -1
                            st.session_state.reject_count += 1
                            wafer_reject_count += 1
                current_lot_yield = (st.session_state.total_good_chips / st.session_state.total_processed_chips) * 100
                st.session_state.wafer_history.append({
                    "Wafer": f"#{w_idx:02d}",
                    "수율(%)": round(current_lot_yield, 2),
                    "불량수(EA)": wafer_reject_count
                })
            st.session_state.wafer_num = 25
            st.session_state.scan_idx = len(v_coords)
            st.session_state.is_running = False
            st.rerun()
        else:
            st.session_state.is_running = True
            st.rerun()
            
with col2:
    if st.button("🔄 Reset Line", use_container_width=True):
        st.session_state.wafer_num = 1
        st.session_state.scan_idx = 0
        st.session_state.is_running = False
        st.session_state.interlock = False
        st.session_state.current_fault = None
        st.session_state.total_processed_chips = 0
        st.session_state.total_good_chips = 0
        st.session_state.rework_count = 0
        st.session_state.reject_count = 0
        st.session_state.wafer_history = []
        st.session_state.maintenance_required = False
        st.session_state.pm_done_signal = False
        wafer, valid_coords = generate_new_wafer()
        st.session_state.wafer_data = wafer
        st.session_state.valid_coords = valid_coords
        st.rerun()

# 4. 메인 화면 프레임 레이아웃 배치 (고정 영역)
st.title("🖥️ Inline Web-MES Packaging Control Dashboard")

maintenance_holder = st.empty()
if st.session_state.maintenance_required:
    with maintenance_holder.container():
        st.warning("⚠️ **[FDC 설비진단 알림]** 라인 내 누적 패키징 불량(Reject) 5회 검출! 어태치 툴 흡착 압력 노즐 오염 및 파라미터 이탈이 의심됩니다.")
        maintenance_action = st.radio(
            "🛠️ **장비 엔지니어 메인터넌스 스텝 선택**",
            ["선택 안함 (대기)", "본더 흡착 헤드 클리닝 및 압력 파라미터 보정 조치", "어태치 칼날 노즐 팁 소모품 즉시 교체"],
            index=0
        )
        if maintenance_action != "선택 안함 (대기)":
            if st.button("🔧 정비 조치 승인 및 장비 알림 초기화", type="primary"):
                st.session_state.maintenance_required = False
                st.session_state.pm_done_signal = True 
                st.session_state.is_running = True 
                st.session_state.reject_count = 0  
                st.rerun()

if st.session_state.pm_done_signal and not st.session_state.maintenance_required:
    st.info("💡 [장비 상태 알림] 엔지니어 PM 조치 완료 - 현재 최적 압력 구동 중 (불량 발생률 최소화)")

# 메인 레이아웃 분할
main_col1, main_col2 = st.columns([1.1, 1.0])

with main_col1:
    st.subheader("🔮 Real-time Wafer Map")
    interlock_holder = st.empty()
    map_holder = st.empty() # 이미지 알맹이만 바꿀 전용 바구니 고정

    if st.session_state.interlock:
        with interlock_holder.container():
            r, c = st.session_state.current_fault
            st.error(f"⚠️ **EQUIPMENT INTERLOCK ACTIVATED:** [X: {c}, Y: {r}] 패키징 불량 검출!")
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("🔧 Execute Rework (리웍 구제)", type="primary", use_container_width=True):
                    st.session_state.wafer_data[r, c] = 1
                    st.session_state.total_good_chips += 1
                    st.session_state.rework_count += 1
                    st.session_state.interlock = False
                    st.session_state.is_running = True
                    st.session_state.scan_idx += 1
                    st.rerun()
            with btn_col2:
                if st.button("❌ Confirm Reject (폐기 확정)", use_container_width=True):
                    st.session_state.wafer_data[r, c] = -1
                    st.session_state.reject_count += 1
                    st.session_state.interlock = False
                    st.session_state.is_running = True
                    st.session_state.scan_idx += 1
                    st.rerun()

    # 이미지 갱신을 렌더링 병목 없이 주입하는 함수
    def update_map_display():
        cell_size = 24
        grid_color = [30, 41, 59]
        color_map = {-2: [15, 23, 42], -1: [239, 68, 68], 0: [100, 116, 139], 1: [16, 185, 129]}
        img_data = np.zeros((20 * cell_size, 20 * cell_size, 3), dtype=np.uint8)
        for r_idx in range(20):
            for c_idx in range(20):
                val = st.session_state.wafer_data[r_idx, c_idx]
                r_start, r_end = r_idx * cell_size, (r_idx + 1) * cell_size
                c_start, c_end = c_idx * cell_size, (c_idx + 1) * cell_size
                img_data[r_start:r_end, c_start:c_end] = color_map[val]
                if val != -2:
                    img_data[r_start:r_end, c_end-1] = grid_color
                    img_data[r_end-1, c_start:c_end] = grid_color
        map_holder.image(img_data, width=460, use_container_width=False)

    update_map_display()

with main_col2:
    st.subheader("📊 LOT 제조 품질 분석 통계 트렌드")
    chart_holder = st.empty()
    
    def draw_charts():
        if st.session_state.wafer_history:
            chart_df = pd.DataFrame(st.session_state.wafer_history)
            with chart_holder.container():
                tab1, tab2 = st.tabs(["📉 누적 수율 변동 추이 (%)", "🚨 웨이퍼별 불량 발생 수량 (EA)"])
                with tab1:
                    st.line_chart(chart_df.set_index("Wafer")["수율(%)"])
                with tab2:
                    st.bar_chart(chart_df.set_index("Wafer")["불량수(EA)"])
                st.markdown("**🔍 LOT 실시간 생산 이력 요약 데이터 표**")
                st.dataframe(chart_df, use_container_width=True, hide_index=True)
        else:
            chart_holder.info("💡 공정이 가동되면 여기에 LOT 단위 통계 공정 제어(SPC) 수율 정보가 표시됩니다.")

    draw_charts()
    
    report_holder = st.empty()
    if st.session_state.wafer_num >= 25 and st.session_state.scan_idx >= len(st.session_state.valid_coords):
        with report_holder.container():
            st.balloons()
            st.success("🏆 1 LOT (25 Wafers) RUN COMPLETED!")
            st.subheader("📋 Final Manufacturing Output Summary")
            report_col1, report_col2, report_col3 = st.columns(3)
            report_col1.metric("종합 양품 수율", f"{get_lot_yield():.2f} %")
            report_col2.metric("총 폐기 칩(Reject)", f"{st.session_state.reject_count} EA")
            report_col3.metric("엔지니어 구제(Rework) 건수", f"{st.session_state.rework_count} 건")


# 🌟 5. [버그 완전 해결] 깜빡임 원천 차단형 인라인 드로잉 엔진
if st.session_state.is_running and not st.session_state.interlock and not st.session_state.maintenance_required:
    if speed_mode == "일반 실시간 모드 (눈으로 확인용)":
        
        # 전체 화면 새로고침(st.rerun) 없이 내부 While 루프 안에서 지정된 placeholder 슬롯의 정보만 실시간 스왑
        while st.session_state.scan_idx < len(st.session_state.valid_coords):
            
            # 장비 오염도(5회 불량) 도달 시 즉시 인터럽트 걸고 전체 리런
            if st.session_state.reject_count >= 5:
                st.session_state.maintenance_required = True
                st.session_state.is_running = False
                st.rerun()

            r, c = st.session_state.valid_coords[st.session_state.scan_idx]
            current_state = st.session_state.wafer_data[r, c]
            
            if current_state == -1:
                # 이미 불량 처리된 칩은 딜레이 없이 순간 통과
                st.session_state.scan_idx += 1
                continue
                
            elif current_state == 0:
                st.session_state.total_processed_chips += 1
                fail_rate = 0.012 if st.session_state.pm_done_signal else 0.048
                
                if np.random.rand() > fail_rate:
                    st.session_state.wafer_data[r, c] = 1
                    st.session_state.total_good_chips += 1
                    st.session_state.scan_idx += 1
                    
                    # 🔥 핵심: st.rerun()을 쓰지 않고 오직 타겟 요소만 데이터 변조 적용 (깜빡임 완벽 제거의 비밀)
                    update_map_display()
                    
                    # 사이드바 텍스트 및 게이지도 새로고침 없이 부드럽게 제자리 스왑
                    cur_yield = get_lot_yield()
                    yield_metric_holder.metric(label="📊 LOT 누적 공정 수율 (Yield)", value=f"{cur_yield:.2f} %")
                    prog = (st.session_state.scan_idx / len(st.session_state.valid_coords)) * 100
                    progress_bar_holder.progress(min(int(prog), 100))
                    progress_text_holder.caption(f"웨이퍼 공정 진행률: {prog:.1f}% (조립 완료: {st.session_state.total_processed_chips} EA)")
                    
                    # 점이 찍히는 시각적 속도 제어 틱 타임 (원하는 스피드로 조절 가능)
                    time.sleep(0.02)
                else:
                    st.session_state.wafer_data[r, c] = -1
                    st.session_state.interlock = True
                    st.session_state.is_running = False
                    st.session_state.current_fault = (r, c)
                    st.rerun() # 불량 인터록 팝업을 안전하게 노출하기 위해서만 리런 사용
        else:
            # 한 장 마감 후 자동 다음 장 교체 시스템 마감
            unique, counts = np.unique(st.session_state.wafer_data, return_counts=True)
            counts_dict = dict(zip(unique, counts))
            w_rejects = counts_dict.get(-1, 0)
            
            st.session_state.wafer_history.append({
                "Wafer": f"#{st.session_state.wafer_num:02d}",
                "수율(%)": round(get_lot_yield(), 2),
                "불량수(EA)": w_rejects
            })
            
            if st.session_state.wafer_num < 25:
                st.session_state.wafer_num += 1
                st.session_state.scan_idx = 0
                wafer, valid_coords = generate_new_wafer()
                st.session_state.wafer_data = wafer
                st.session_state.valid_coords = valid_coords
                st.rerun()
            else:
                st.session_state.is_running = False
                st.rerun()
