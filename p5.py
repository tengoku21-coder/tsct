import streamlit as st
import numpy_financial as npf
import pandas as pd

def main():
    # --------------------------------------------------------------------------------
    # 1. 페이지 설정
    # --------------------------------------------------------------------------------
    st.set_page_config(page_title="EV 충전 투자 분석기 (3단계 조립형)", layout="wide")
    st.title("⚡ EV 충전 투자 분석기 (3단계 기간 조립형)")
    st.markdown("""
    이 모델은 **각 단계(Phase)의 기간을 독립적으로 설정**하여 전체 사업 기간을 구성합니다.
    * **Phase 1:** 이자 지급 + 원금 상환
    * **Phase 2:** 수익 배분 (Profit Share)
    * **Phase 3:** 회사 독점 (100% 수익)
    """)
    st.markdown("---")

    # --------------------------------------------------------------------------------
    # 2. 사이드바: 변수 입력
    # --------------------------------------------------------------------------------
    st.sidebar.header("📝 시뮬레이션 변수 설정")

    # [Sec A] 자금 조달
    st.sidebar.subheader("1. 자금 조달 및 비용")
    infra_cost = st.sidebar.number_input("충전 인프라 투자비용 (원/1기)", value=2100000, step=100000)
    charger_cost = st.sidebar.number_input("충전기 비용 (원/1기)", value=600000, step=100000)
    subsidy = st.sidebar.number_input("보조금 (원/1기)", value=1800000, step=100000)
    num_chargers = st.sidebar.number_input("충전기 대수 (기)", value=1, min_value=1)

    project_cost = (infra_cost + charger_cost - subsidy) * num_chargers
    st.sidebar.info(f"🛠️ 총 사업 비용: {int(project_cost):,} 원")

    investor_amount = st.sidebar.number_input(
        "투자자 유치 금액 (원)", 
        value=int(project_cost * 1.2), 
        step=1000000,
        help="초기 잉여금을 확보하려면 사업비보다 높게 설정하세요."
    )
    initial_surplus = investor_amount - project_cost

    # [Sec B] 단계별 기간 및 조건 (핵심 변경)
    st.sidebar.subheader("2. 단계별 기간 설정 (Total 기간 자동합산)")
    
    # Phase 1
    st.sidebar.markdown("---")
    st.sidebar.markdown("**[Phase 1: 원금 회수 구간]**")
    p1_years = st.sidebar.number_input("1단계 기간 (년)", value=2, min_value=1, key="p1y")
    p1_rate = st.sidebar.number_input("1단계 연 이자율 (%)", value=5.0, step=0.1, key="p1r")

    # Phase 2
    st.sidebar.markdown("**[Phase 2: 수익 배분 구간]**")
    p2_years = st.sidebar.number_input("2단계 기간 (년)", value=3, min_value=0, key="p2y")
    p2_share_pct = st.sidebar.slider("2단계 배분율 (이익의 %)", 0, 100, 50, key="p2s")

    # Phase 3
    st.sidebar.markdown("**[Phase 3: 회사 독점 구간]**")
    p3_years = st.sidebar.number_input("3단계 기간 (년)", value=5, min_value=0, key="p3y", help="투자자와의 관계가 끝난 후, 회사가 수익을 독차지하는 기간입니다.")
    
    # 전체 기간 자동 계산
    total_years = p1_years + p2_years + p3_years
    total_months = total_years * 12
    
    st.sidebar.success(f"🗓️ 총 사업 기간: {total_years}년 ({total_months}개월)")

    # [Sec C] 운영 변수
    st.sidebar.subheader("3. 매출 및 운영")
    use_promo = st.sidebar.checkbox("초기 프로모션 적용", value=True)
    if use_promo:
        promo_months = st.sidebar.slider("프로모션 기간 (개월)", 0, 24, 6)
        promo_fee = st.sidebar.number_input("프로모션 요금", value=200.0)
    else:
        promo_months = 0
        promo_fee = 0.0

    daily_avg_charge = st.sidebar.number_input("일일 평균 충전량 (kWh/1기)", value=20.0)
    normal_fee = st.sidebar.number_input("정상 요금", value=300.0)
    elec_rate = st.sidebar.number_input("전력 원가", value=150.0)
    monthly_maint = st.sidebar.number_input("월 관리비 (1기당)", value=10000)
    discount_rate = st.sidebar.slider("할인율 (%)", 0.0, 15.0, 5.0)

    # 상수
    COMM_COST = 3000
    BASE_ELEC_COST = 2390 * 7

    # --------------------------------------------------------------------------------
    # 3. 계산 로직
    # --------------------------------------------------------------------------------

    fixed_cost_unit = BASE_ELEC_COST + COMM_COST + monthly_maint
    
    # 월별 영업이익 계산
    op_promo = ((daily_avg_charge * (promo_fee - elec_rate) * 30) - fixed_cost_unit) * num_chargers
    op_normal = ((daily_avg_charge * (normal_fee - elec_rate) * 30) - fixed_cost_unit) * num_chargers

    # 시뮬레이션
    cash_flow_log = []
    company_flows = []
    cumulative_cash = initial_surplus
    total_investor_paid = 0

    # Phase 구분용 월수 계산
    p1_months = p1_years * 12
    p2_months = p2_years * 12
    # p3_months = p3_years * 12 (루프에서 자동 처리)

    end_p1 = p1_months
    end_p2 = p1_months + p2_months

    for m in range(1, total_months + 1):
        # 1. 영업이익 산출
        if use_promo and m <= promo_months:
            op = op_promo
            op_str = "프로모션"
        else:
            op = op_normal
            op_str = "정상"

        # 2. 투자자 지급액 산출
        payout = 0
        phase_str = ""
        note = ""

        # [Phase 1]
        if m <= end_p1:
            # 이자 지급
            interest = int((investor_amount * (p1_rate / 100)) / 12)
            payout += interest
            phase_str = "1단계 (이자)"
            
            # 마지막 달 원금 상환 (Event)
            if m == end_p1:
                payout += investor_amount
                note = "💰 원금 상환"
                phase_str = "1단계 (상환)"

        # [Phase 2]
        elif m <= end_p2:
            # 수익 배분
            if op > 0:
                share = int(op * (p2_share_pct / 100))
                payout += share
            else:
                payout = 0
            phase_str = f"2단계 ({p2_share_pct}%)"

        # [Phase 3]
        else:
            # 회사 독점
            payout = 0
            phase_str = "3단계 (독점)"
            
            # Phase 3 시작 첫 달에 메시지 표시
            if m == end_p2 + 1:
                note = "🚀 독점 시작"

        # 3. 현금흐름 집계
        total_investor_paid += payout
        net_flow = op - payout
        cumulative_cash += net_flow
        company_flows.append(net_flow)

        cash_flow_log.append({
            "Month": m,
            "영업": op_str,
            "단계": phase_str,
            "영업이익": int(op),
            "투자자지급": int(-payout),
            "회사순수익": int(net_flow),
            "회사누적잔고": int(cumulative_cash),
            "비고": note
        })

    # 결과 지표
    if investor_amount > 0:
        roi = ((total_investor_paid - investor_amount) / investor_amount) * 100
    else:
        roi = 0

    monthly_discount = (discount_rate / 100) / 12
    npv = initial_surplus + npf.npv(monthly_discount, company_flows)

    # --------------------------------------------------------------------------------
    # 4. 결과 시각화
    # --------------------------------------------------------------------------------
    
    # [Metrics]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 1. 초기 잉여금", f"{int(initial_surplus):,} 원")
    with c2:
        st.metric("🤝 2. 투자자 총 수령", f"{int(total_investor_paid):,} 원", delta=f"ROI {roi:.1f}%")
    with c3:
        st.metric(f"🏦 3. 최종 회사 잔고 ({total_years}년)", f"{int(cumulative_cash):,} 원")
    with c4:
        st.metric("💎 4. NPV", f"{int(npv):,} 원")

    st.divider()

    left, right = st.columns([1, 1.3])

    with left:
        st.subheader("📊 단계별 기간 구조")
        
        # 단계별 요약표
        phase_data = pd.DataFrame([
            ["Phase 1 (이자+상환)", f"{p1_years}년 ({p1_months}개월)", f"이자 지급 후 원금 전액 상환"],
            ["Phase 2 (수익배분)", f"{p2_years}년 ({p2_months}개월)", f"영업이익의 {p2_share_pct}% 투자자에게 지급"],
            ["Phase 3 (회사독점)", f"{p3_years}년 ({p3_years*12}개월)", f"수익 100% 회사 귀속"]
        ], columns=["단계", "기간", "내용"])
        st.table(phase_data)
        
        st.info(f"🗓️ 총 사업 기간: {total_years}년")

        # Cash Cliff 체크
        df = pd.DataFrame(cash_flow_log)
        min_bal = df['회사누적잔고'].min()
        if min_bal < 0:
            st.error(f"🚨 **자금 경고:** 원금 상환 시점에 잔고가 {int(min_bal):,}원 부족합니다. 초기 투자금을 늘리거나 1단계 기간을 늘리세요.")
        else:
            st.success(f"✅ **안정적:** 최저 잔고가 {int(min_bal):,}원으로, 원금 상환 위기를 잘 넘겼습니다.")

    with right:
        st.subheader("📉 기간별 회사 누적 수익 추이")
        st.line_chart(df, x="Month", y="회사누적잔고", color="#2980B9")
        st.caption("그래프가 급락(원금상환) 후 다시 상승하는지 확인하세요. Phase 3에서 기울기가 가장 가파릅니다.")

    with st.expander("📑 상세 데이터 (Excel 다운로드)"):
        st.dataframe(df, use_container_width=True)

if __name__ == "__main__":
    main()