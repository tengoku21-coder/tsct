import streamlit as st
import numpy_financial as npf
import pandas as pd

def main():
    # --------------------------------------------------------------------------------
    # 1. 페이지 설정
    # --------------------------------------------------------------------------------
    st.set_page_config(page_title="EV 충전사업 투자 정밀 분석기", layout="wide")
    st.title("⚡ EV 충전사업 투자 구조화 정밀 분석기 (투자금 설정형)")
    st.markdown("""
    이 분석기는 **총 사업비**와 **투자자 유치 금액**을 구분하여 분석합니다.
    투자자가 낸 금액에 대해서만 1단계 이자와 2단계 목표 수익률을 적용하여 정확한 배당 스케줄을 산출합니다.
    """)
    st.markdown("---")

    # --------------------------------------------------------------------------------
    # 2. 사이드바: 변수 입력
    # --------------------------------------------------------------------------------
    st.sidebar.header("📝 시뮬레이션 변수 설정")

    # [Sec A] 사업 비용 구조
    st.sidebar.subheader("1. 사업 비용 구조 (Cost)")
    infra_cost = st.sidebar.number_input("충전 인프라 투자비용 (원/1기)", value=2100000, step=100000)
    charger_cost = st.sidebar.number_input("충전기 비용 (원/1기)", value=600000, step=100000)
    subsidy = st.sidebar.number_input("보조금 (원/1기)", value=1800000, step=100000)
    num_chargers = st.sidebar.number_input("충전기 대수 (기)", value=1, min_value=1)

    # 총 필요 자금 계산
    project_cost_per_unit = infra_cost + charger_cost - subsidy
    total_project_cost = project_cost_per_unit * num_chargers
    
    st.sidebar.info(f"💰 총 필요 사업 자금: {int(total_project_cost):,} 원")

    # [Sec B] 투자자 조건 설정 (핵심 수정 사항)
    st.sidebar.subheader("2. 투자자 자금 및 회수 조건")
    
    # B-1. 투자금 설정
    investor_principal = st.sidebar.number_input(
        "투자자 실제 투자 금액 (원)", 
        value=int(total_project_cost), 
        step=1000000, 
        help="투자자로부터 실제로 조달한 금액입니다. 총 사업비와 다를 수 있습니다."
    )

    # B-2. 1단계 (이자 지급 구간)
    st.sidebar.markdown("**[1단계: 이자 지급 구간]**")
    phase1_months = st.sidebar.number_input("1단계 기간 (개월)", value=24, min_value=0)
    phase1_rate = st.sidebar.number_input("1단계 적용 연이자율 (%)", value=5.0, step=0.1, help="투자 원금에 대한 연 이자율입니다.")

    # B-3. 2단계 (원금+수익 상환 구간)
    st.sidebar.markdown("**[2단계: 원금 및 수익 상환 구간]**")
    phase2_months = st.sidebar.number_input("2단계 기간 (개월)", value=36, min_value=1)
    
    # B-4. 최종 목표 수익률
    target_return_pct = st.sidebar.number_input(
        "투자자 목표 총 수익률 (%)", 
        value=20.0, 
        step=0.5, 
        help="투자 종료 시점까지 투자자가 가져갈 총 금액(이자 포함)이 '투자 원금' 대비 몇 %가 되어야 하는지 설정합니다. (예: 20% -> 원금의 120% 회수)"
    )

    # [Sec C] 운영 기간 및 매출 변수
    st.sidebar.subheader("3. 운영 및 매출 설정")
    operation_years = st.sidebar.number_input("전체 사업 운영 기간 (년)", value=6, min_value=1, max_value=20)
    total_op_months = operation_years * 12
    
    # 기간 검증
    total_repay_months = phase1_months + phase2_months
    debt_free_months = total_op_months - total_repay_months
    
    if debt_free_months > 0:
        st.sidebar.success(f"✅ 상환 종료 후 {debt_free_months}개월 간 무차입(100% 회사수익) 구간 발생")
    elif debt_free_months < 0:
        st.sidebar.error(f"⚠️ 경고: 상환 기간이 운영 기간보다 {-debt_free_months}개월 더 깁니다.")

    # 프로모션 설정
    use_promo = st.sidebar.checkbox("초기 프로모션 요금 적용", value=True)
    if use_promo:
        promo_months = st.sidebar.slider("프로모션 기간 (개월)", 0, 36, 6)
        promo_fee = st.sidebar.number_input("프로모션 요금 (원/kWh)", value=200.0, step=10.0)
    else:
        promo_months = 0
        promo_fee = 0.0

    # 일반 운영 변수
    daily_avg_charge = st.sidebar.number_input("일일 평균 충전량 (kWh/1기)", value=15.0, step=0.1)
    normal_fee = st.sidebar.number_input("정상 충전 요금 (원/kWh)", value=300.0, step=10.0)
    elec_rate = st.sidebar.number_input("전력량 요금 (원/kWh, 원가)", value=150.0, step=10.0)
    monthly_maint = st.sidebar.number_input("월 관리비 (원/1기)", value=10000, step=1000)
    discount_rate = st.sidebar.slider("NPV 할인율 (%)", 0.0, 15.0, 5.0)

    # 상수
    COMM_COST = 3000
    BASE_ELEC_COST = 2390 * 7

    # --------------------------------------------------------------------------------
    # 3. 계산 로직 (Core Calculation)
    # --------------------------------------------------------------------------------

    # [A] 월간 영업이익(Operating Profit) 계산 (금융비용 제외 순수 영업단)
    monthly_fixed_cost_unit = BASE_ELEC_COST + COMM_COST + monthly_maint
    
    # 프로모션 기간 월 이익
    margin_promo = daily_avg_charge * (promo_fee - elec_rate) * 30
    op_profit_promo = (margin_promo - monthly_fixed_cost_unit) * num_chargers

    # 정상 기간 월 이익
    margin_normal = daily_avg_charge * (normal_fee - elec_rate) * 30
    op_profit_normal = (margin_normal - monthly_fixed_cost_unit) * num_chargers

    # [B] 투자자 상환 스케줄 계산 (Payout Schedule)
    # 1. 목표 총 지급액 (Target Total Payout)
    target_total_payout = investor_principal * (1 + target_return_pct / 100)
    
    # 2. Phase 1: 이자 지급액 계산
    # 월 이자 = 투자원금 * 연이율 / 12
    monthly_interest_phase1 = (investor_principal * (phase1_rate / 100)) / 12
    total_paid_phase1 = monthly_interest_phase1 * phase1_months
    
    # 3. Phase 2: 원금 + 잔여수익 상환액 계산
    # 남은 지급해야 할 돈 = 목표 총액 - 1단계에서 이미 준 돈
    remaining_payout = target_total_payout - total_paid_phase1
    
    # 월 상환액 (2단계 기간으로 나눔)
    if phase2_months > 0:
        monthly_payout_phase2 = remaining_payout / phase2_months
    else:
        monthly_payout_phase2 = 0

    # [C] 현금흐름 시뮬레이션 (Waterfall)
    cash_flow_log = []
    company_cash_flows = [] # NPV용
    cumulative_company_cash = 0
    actual_investor_received = 0

    for m in range(1, total_op_months + 1):
        # 1. 영업 수익 발생
        if use_promo and m <= promo_months:
            current_op = op_profit_promo
            op_status = "프로모션"
        else:
            current_op = op_profit_normal
            op_status = "정상운영"
            
        # 2. 투자자 지급 (비용 발생)
        if m <= phase1_months:
            current_payout = monthly_interest_phase1
            pay_status = "1단계(이자)"
        elif m <= total_repay_months:
            current_payout = monthly_payout_phase2
            pay_status = "2단계(상환)"
        else:
            current_payout = 0
            pay_status = "3단계(완료)"
            
        actual_investor_received += current_payout

        # 3. 회사 순수익 (Net)
        net_profit = current_op - current_payout
        
        # 누적
        cumulative_company_cash += net_profit
        company_cash_flows.append(net_profit)
        
        cash_flow_log.append({
            "Month": m,
            "영업상태": op_status,
            "상환상태": pay_status,
            "영업이익": int(current_op),
            "투자자지급": int(-current_payout),
            "회사순수익": int(net_profit),
            "회사누적수익": int(cumulative_company_cash)
        })

    # [D] 최종 지표
    total_company_profit = sum(company_cash_flows)
    
    # 회사 ROI (자기자본이 0원일 수도 있으므로, 총 사업비 대비 회사 수익 비율로 참조)
    if total_project_cost > 0:
        company_roi = (total_company_profit / total_project_cost) * 100
    else:
        company_roi = 0

    # NPV
    monthly_discount = (discount_rate / 100) / 12
    # 0개월차: 투자금은 투자자가 냈으므로 회사 현금흐름엔 영향 X (Project Financing 관점)
    # 다만 회수 기간 분석을 위해 초기 마이너스를 넣기도 하지만, 여기선 '운영 수익' 중심 분석
    npv_stream = [0] + company_cash_flows
    company_npv = npf.npv(monthly_discount, npv_stream)

    # --------------------------------------------------------------------------------
    # 4. 결과 시각화
    # --------------------------------------------------------------------------------
    
    # [Top Metric]
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 투자자 총 회수금", f"{int(actual_investor_received):,} 원", 
                  help=f"목표: {int(target_total_payout):,}원 / 투자원금: {int(investor_principal):,}원")
    with col2:
        st.metric(f"🏢 회사 {operation_years}년 누적수익", f"{int(total_company_profit):,} 원")
    with col3:
        st.metric("📈 회사 ROI (사업비대비)", f"{company_roi:.1f} %")
    with col4:
        st.metric("💎 NPV (순현재가치)", f"{int(company_npv):,} 원", help=f"할인율 {discount_rate}% 적용")
    
    st.divider()

    # [2단 레이아웃]
    left_col, right_col = st.columns([1, 1.3])

    with left_col:
        st.subheader("📊 투자 상환 상세 스케줄")
        
        # 요약 테이블 데이터 생성
        sch_data = [
            ["투자자 투자 원금", f"{int(investor_principal):,} 원", "-"],
            ["목표 총 수익률", f"{target_return_pct} %", f"총 {int(target_total_payout):,} 원 지급 목표"],
            ["1단계 (이자 구간)", f"{phase1_months} 개월", f"월 {int(monthly_interest_phase1):,} 원 (연 {phase1_rate}%)"],
            ["2단계 (상환 구간)", f"{phase2_months} 개월", f"월 {int(monthly_payout_phase2):,} 원"],
            ["3단계 (종료 후)", f"{debt_free_months} 개월", "투자자 지급액 0원"]
        ]
        df_sch = pd.DataFrame(sch_data, columns=["구분", "값", "비고"])
        st.table(df_sch)
        
        if debt_free_months < 0:
             st.error(f"⚠️ 경고: 운영 기간 종료 시까지 투자금을 다 갚지 못합니다. ({-debt_free_months}개월 부족)")

    with right_col:
        st.subheader("📉 월별 현금흐름 (회사 수익)")
        df_chart = pd.DataFrame(cash_flow_log)
        
        st.line_chart(df_chart, x="Month", y="회사누적수익", color="#E74C3C")
        
        if len(df_chart) > 0:
            last_profit = df_chart.iloc[-1]['회사누적수익']
            if last_profit > 0:
                st.success("✅ 최종적으로 흑자 사업입니다.")
            else:
                st.error("❌ 최종적으로 적자 사업입니다. 수익 구조 개선이 필요합니다.")

    with st.expander("📑 월별 상세 데이터 (Excel 다운로드 용도)"):
        st.dataframe(df_chart, use_container_width=True)

if __name__ == "__main__":
    main()