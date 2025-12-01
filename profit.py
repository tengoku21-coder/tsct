import streamlit as st
import numpy_financial as npf
import pandas as pd

def main():
    # --------------------------------------------------------------------------------
    # 1. 페이지 설정
    # --------------------------------------------------------------------------------
    st.set_page_config(page_title="EV 충전사업 정밀 분석기 (상환기간 가변형)", layout="wide")
    st.title("⚡ EV 충전사업 정밀 투자/수익성 분석기")
    st.markdown("""
    이 분석기는 **전체 운영 기간**과 **투자 상환 기간(1단계/2단계)**을 각각 독립적으로 설정할 수 있습니다.
    상환이 끝난 후 '무차입(Debt-Free) 기간'의 수익성 변화를 확인해 보세요.
    """)
    st.markdown("---")

    # --------------------------------------------------------------------------------
    # 2. 사이드바: 변수 입력
    # --------------------------------------------------------------------------------
    st.sidebar.header("📝 시뮬레이션 변수 설정")

    # [A] 초기 비용
    st.sidebar.subheader("1. 초기 투자 비용")
    infra_cost = st.sidebar.number_input("충전 인프라 투자비용 (원/1기)", value=2100000, step=100000)
    charger_cost = st.sidebar.number_input("충전기 비용 (원/1기)", value=600000, step=100000)
    subsidy = st.sidebar.number_input("보조금 (원/1기)", value=1800000, step=100000)

    # [B] 운영 기간 및 상환 스케줄 (핵심 수정 부분)
    st.sidebar.subheader("2. 기간 설정 (운영 vs 상환)")
    
    # B-1. 전체 사업 운영 기간
    operation_years = st.sidebar.number_input("전체 사업 운영 기간 (년)", value=6, min_value=1, max_value=20)
    total_op_months = operation_years * 12

    st.sidebar.markdown("**[투자자 상환 스케줄 설정]**")
    # B-2. 1단계 거치 기간
    phase1_months = st.sidebar.number_input("1단계: 거치(이자만) 기간 (개월)", value=24, min_value=0)
    
    # B-3. 2단계 상환 기간 (사용자 직접 입력)
    phase2_months = st.sidebar.number_input("2단계: 원리금 상환 기간 (개월)", value=36, min_value=1)
    
    # 상환 종료 시점 계산
    total_repay_months = phase1_months + phase2_months
    debt_free_months = total_op_months - total_repay_months

    # 기간 검증 메시지
    if debt_free_months > 0:
        st.sidebar.success(f"✅ 상환 완료 후 {debt_free_months}개월 간 100% 수익 구간이 있습니다.")
    elif debt_free_months == 0:
        st.sidebar.info("ℹ️ 운영 종료와 동시에 상환이 끝납니다.")
    else:
        st.sidebar.error(f"⚠️ 주의: 운영 기간보다 상환 기간이 {-debt_free_months}개월 더 깁니다. (상환 미완료)")

    # [C] 투자 수익률 조건
    st.sidebar.subheader("3. 투자자 수익률 조건")
    target_investor_roi = st.sidebar.number_input(f"투자자 목표 총 수익률 (원금 대비 %)", value=20.0, step=0.5, help="원금 1억, 20% 설정 시 -> 총 1억 2천만원 상환")
    phase1_rate = st.sidebar.number_input("1단계 적용 이자율 (연 %)", value=5.0, step=0.1)
    discount_rate = st.sidebar.slider("할인율 (NPV 계산용, %)", 0.0, 15.0, 5.0)

    # [D] 매출 및 운영 변수
    st.sidebar.subheader("4. 매출 및 운영 변수")
    
    # 프로모션
    use_promo = st.sidebar.checkbox("초기 프로모션 요금 적용", value=True)
    if use_promo:
        promo_months = st.sidebar.slider("프로모션 적용 기간 (개월)", 0, 36, 6)
        promo_fee = st.sidebar.number_input("프로모션 충전 요금 (원/kWh)", value=200.0, step=10.0)
    else:
        promo_months = 0
        promo_fee = 0.0
        
    # 기본 운영
    num_chargers = st.sidebar.number_input("충전기 대수 (기)", value=1, min_value=1)
    daily_avg_charge = st.sidebar.number_input("일일 평균 충전량 (kWh/1기)", value=15.0, step=0.1)
    normal_fee = st.sidebar.number_input("정상 충전 요금 (원/kWh)", value=300.0, step=10.0)
    elec_rate = st.sidebar.number_input("전력량 요금 (원/kWh, 원가)", value=150.0, step=10.0)
    monthly_maint = st.sidebar.number_input("월 관리비 (원/1기)", value=10000, step=1000)

    # 상수
    COMM_COST = 3000
    BASE_ELEC_COST = 2390 * 7

    # --------------------------------------------------------------------------------
    # 3. 계산 로직
    # --------------------------------------------------------------------------------

    # [Step 1] 투자 원금
    net_investment_per_unit = infra_cost + charger_cost - subsidy
    total_principal = net_investment_per_unit * num_chargers

    # [Step 2] 영업이익(Operating Profit) 계산 (금융비용 제외)
    monthly_fixed_op_cost_unit = BASE_ELEC_COST + COMM_COST + monthly_maint
    
    # 프로모션 마진
    margin_promo = daily_avg_charge * (promo_fee - elec_rate) * 30
    op_profit_promo = (margin_promo - monthly_fixed_op_cost_unit) * num_chargers

    # 정상 마진
    margin_normal = daily_avg_charge * (normal_fee - elec_rate) * 30
    op_profit_normal = (margin_normal - monthly_fixed_op_cost_unit) * num_chargers

    # [Step 3] 투자자 상환액 산출
    # 총 상환 목표액
    total_target_payout = total_principal * (1 + target_investor_roi / 100)
    
    # Phase 1: 이자 지급
    monthly_payout_phase1 = (total_principal * (phase1_rate / 100)) / 12
    total_paid_phase1 = monthly_payout_phase1 * phase1_months
    
    # Phase 2: 원리금 상환
    remaining_payout = total_target_payout - total_paid_phase1
    if phase2_months > 0:
        monthly_payout_phase2 = remaining_payout / phase2_months
    else:
        monthly_payout_phase2 = 0 # 2단계가 0개월인 경우

    # [Step 4] 월별 현금흐름 (Waterfall)
    cash_flow_log = []
    company_cash_flows = []
    cumulative_company_cash = 0
    
    # 실제 상환된 총액 추적 (운영기간이 상환기간보다 짧을 경우 대비)
    actual_paid_to_investor = 0 

    for m in range(1, total_op_months + 1):
        # (A) 매출/영업이익 계산
        if use_promo and m <= promo_months:
            current_op_profit = op_profit_promo
            period_type = "프로모션"
        else:
            current_op_profit = op_profit_normal
            period_type = "정상운영"
            
        # (B) 투자자 지급액 계산 (기간별 분기)
        if m <= phase1_months:
            current_investor_pay = monthly_payout_phase1
            pay_phase = "1단계(이자)"
        elif m <= (phase1_months + phase2_months):
            current_investor_pay = monthly_payout_phase2
            pay_phase = "2단계(상환)"
        else:
            current_investor_pay = 0
            pay_phase = "3단계(완료)"
            
        actual_paid_to_investor += current_investor_pay

        # (C) 회사 순수익
        company_net_profit = current_op_profit - current_investor_pay
        
        cumulative_company_cash += company_net_profit
        company_cash_flows.append(company_net_profit)
        
        cash_flow_log.append({
            "Month": m,
            "운영구분": period_type,
            "상환구분": pay_phase,
            "영업이익": int(current_op_profit),
            "투자자지급": int(-current_investor_pay),
            "회사순수익": int(company_net_profit),
            "회사누적수익": int(cumulative_company_cash)
        })

    # [Step 5] 지표 종합
    total_company_profit = sum(company_cash_flows)
    
    if total_principal > 0:
        company_roi = (total_company_profit / total_principal) * 100
    else:
        company_roi = 0

    monthly_discount_rate = (discount_rate / 100) / 12
    npv_stream = [0] + company_cash_flows 
    company_npv = npf.npv(monthly_discount_rate, npv_stream)

    # --------------------------------------------------------------------------------
    # 4. 결과 시각화
    # --------------------------------------------------------------------------------
    
    # [상단 메트릭]
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💼 투자자 실제 회수금", f"{int(actual_paid_to_investor):,} 원", 
                  help=f"목표액: {int(total_target_payout):,}원 (운영기간 짧으면 미달 가능)")
    with col2:
        st.metric(f"🏢 회사 {operation_years}년 누적수익", f"{int(total_company_profit):,} 원")
    with col3:
        st.metric("📈 회사 ROI (원금대비)", f"{company_roi:.1f} %")
    with col4:
        st.metric("💎 NPV (순현재가치)", f"{int(company_npv):,} 원", help=f"할인율 {discount_rate}% 적용")
        
    st.divider()

    # [메인 분석]
    left_col, right_col = st.columns([1, 1.3])

    with left_col:
        st.subheader("📊 구조화 금융 & 영업 요약")
        
        # 상환 테이블
        st.markdown("##### 1. 투자자 상환 계획")
        sch_data = {
            "구분": ["1단계 (거치)", "2단계 (상환)", "3단계 (종료)"],
            "기간": [f"{phase1_months}개월", f"{phase2_months}개월", f"{debt_free_months if debt_free_months>0 else 0}개월"],
            "월 지급액": [
                f"{int(monthly_payout_phase1):,} 원", 
                f"{int(monthly_payout_phase2):,} 원", 
                "0 원 (이익 100% 귀속)"
            ]
        }
        st.table(pd.DataFrame(sch_data))
        
        # 경고 메시지 (미상환 시)
        if debt_free_months < 0:
            st.error(f"⚠️ 경고: 운영 기간이 상환 완료 시점보다 {-debt_free_months}개월 짧습니다. 투자금을 다 갚지 못한 상태로 종료됩니다.")

        st.markdown("##### 2. 영업이익 (EBITDA)")
        op_data = pd.DataFrame({
            "구분": ["프로모션 기간", "정상 운영 기간"],
            "월 영업이익": [f"{int(op_profit_promo):,} 원", f"{int(op_profit_normal):,} 원"]
        })
        st.table(op_data)

    with right_col:
        st.subheader("📉 현금흐름 시뮬레이션")
        df_chart = pd.DataFrame(cash_flow_log)
        
        # 차트 커스텀: 상환 완료 시점 표시
        st.line_chart(df_chart, x="Month", y="회사누적수익", color="#2E86C1")
        
        if debt_free_months > 0:
            payback_finish_month = total_repay_months
            st.caption(f"🚀 {payback_finish_month}개월 차에 상환이 완료됩니다. 이후 그래프 기울기가 가파르게 상승합니다 (순수익 급증).")

    with st.expander("📑 월별 상세 데이터 (Excel용)"):
        st.dataframe(df_chart, use_container_width=True)

if __name__ == "__main__":
    main()