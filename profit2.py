import streamlit as st
import numpy_financial as npf
import pandas as pd

def main():
    # --------------------------------------------------------------------------------
    # 1. 페이지 설정
    # --------------------------------------------------------------------------------
    st.set_page_config(page_title="EV 충전 투자 분석기 (자금 조달형)", layout="wide")
    st.title("⚡ EV 충전 투자 분석기 (초과 자금 조달형)")
    st.markdown("""
    이 모델은 **실제 사업 비용**보다 **더 많은 투자금**을 유치하는 경우를 시뮬레이션합니다.
    초과 확보된 자금(잉여 현금)은 초기 이자 지급이나 운영 자금으로 활용되어 안정성을 높여줍니다.
    """)
    st.markdown("---")

    # --------------------------------------------------------------------------------
    # 2. 사이드바: 변수 입력
    # --------------------------------------------------------------------------------
    st.sidebar.header("📝 시뮬레이션 변수 설정")

    # [Sec A] 사업 비용 (실제 지출되는 돈)
    st.sidebar.subheader("1. 사업 비용 (Project Cost)")
    infra_cost = st.sidebar.number_input("충전 인프라 투자비용 (원/1기)", value=2100000, step=100000)
    charger_cost = st.sidebar.number_input("충전기 비용 (원/1기)", value=600000, step=100000)
    subsidy = st.sidebar.number_input("보조금 (원/1기)", value=1800000, step=100000)
    num_chargers = st.sidebar.number_input("충전기 대수 (기)", value=1, min_value=1)

    # 사업비 계산
    cost_per_unit = infra_cost + charger_cost - subsidy
    total_project_cost = cost_per_unit * num_chargers
    
    st.sidebar.info(f"🛠️ 실제 필요 사업비: {int(total_project_cost):,} 원")

    # [Sec B] 투자자 자금 유치 (Funding) - 핵심 수정
    st.sidebar.subheader("2. 자금 유치 (Funding)")
    
    investor_amount = st.sidebar.number_input(
        "투자자 실제 유치 금액 (원)", 
        value=int(total_project_cost * 1.1), # 기본값을 사업비의 110%로 설정해봄
        step=1000000,
        help="투자자로부터 실제로 받은 총 금액입니다. 사업비보다 많으면 그 차액은 회사의 초기 잉여 현금이 됩니다."
    )

    # 잉여금 계산
    initial_surplus_cash = investor_amount - total_project_cost
    
    if initial_surplus_cash > 0:
        st.sidebar.success(f"💰 잉여 자금 확보: {int(initial_surplus_cash):,} 원 (초기 운영비로 활용)")
    elif initial_surplus_cash < 0:
        st.sidebar.error(f"⚠️ 자금 부족: {int(-initial_surplus_cash):,} 원이 부족합니다.")
    else:
        st.sidebar.warning("사업비와 투자금이 정확히 일치합니다 (여유 자금 없음).")

    # [Sec C] 투자 상환 조건
    st.sidebar.subheader("3. 투자자 상환 조건 (유치금액 기준)")
    
    st.sidebar.markdown("**[1단계: 이자 지급]**")
    phase1_months = st.sidebar.number_input("1단계 기간 (개월)", value=24, min_value=0)
    phase1_rate = st.sidebar.number_input("1단계 연 이자율 (%)", value=5.0, step=0.1, help="유치한 투자금 전체에 대한 이자율입니다.")

    st.sidebar.markdown("**[2단계: 원금+수익 상환]**")
    phase2_months = st.sidebar.number_input("2단계 기간 (개월)", value=36, min_value=1)
    phase2_return_pct = st.sidebar.number_input("2단계 추가 수익률 (%)", value=10.0, step=0.5, help="유치한 투자금 원금에 얹어줄 추가 수익률입니다.")

    # [Sec D] 운영 기간 및 매출
    st.sidebar.subheader("4. 운영 및 매출 설정")
    operation_years = st.sidebar.number_input("전체 사업 운영 기간 (년)", value=6, min_value=1, max_value=20)
    total_op_months = operation_years * 12

    # 기간 검증
    total_repay_months = phase1_months + phase2_months
    debt_free_months = total_op_months - total_repay_months

    # 프로모션 및 운영 변수
    use_promo = st.sidebar.checkbox("초기 프로모션 요금 적용", value=True)
    if use_promo:
        promo_months = st.sidebar.slider("프로모션 기간 (개월)", 0, 36, 6)
        promo_fee = st.sidebar.number_input("프로모션 요금 (원/kWh)", value=200.0, step=10.0)
    else:
        promo_months = 0
        promo_fee = 0.0

    daily_avg_charge = st.sidebar.number_input("일일 평균 충전량 (kWh/1기)", value=15.0, step=0.1)
    normal_fee = st.sidebar.number_input("정상 충전 요금 (원/kWh)", value=300.0, step=10.0)
    elec_rate = st.sidebar.number_input("전력량 요금 (원/kWh, 원가)", value=150.0, step=10.0)
    monthly_maint = st.sidebar.number_input("월 관리비 (원/1기)", value=10000, step=1000)
    discount_rate = st.sidebar.slider("NPV 할인율 (%)", 0.0, 15.0, 5.0)

    # 상수
    COMM_COST = 3000
    BASE_ELEC_COST = 2390 * 7

    # --------------------------------------------------------------------------------
    # 3. 계산 로직
    # --------------------------------------------------------------------------------

    # [A] 월간 영업이익 계산
    monthly_fixed_cost_unit = BASE_ELEC_COST + COMM_COST + monthly_maint
    
    margin_promo = daily_avg_charge * (promo_fee - elec_rate) * 30
    op_profit_promo = (margin_promo - monthly_fixed_cost_unit) * num_chargers

    margin_normal = daily_avg_charge * (normal_fee - elec_rate) * 30
    op_profit_normal = (margin_normal - monthly_fixed_cost_unit) * num_chargers

    # [B] 투자자 상환액 계산 (기준: investor_amount)
    
    # 1. Phase 1 (이자)
    monthly_pay_phase1 = int((investor_amount * (phase1_rate / 100)) / 12)
    total_pay_phase1 = monthly_pay_phase1 * phase1_months
    
    # 2. Phase 2 (원금 + 추가수익)
    # 총 2단계 상환 목표액 = 유치금액 * (1 + 추가수익률)
    total_target_phase2 = investor_amount * (1 + phase2_return_pct / 100)
    monthly_pay_phase2 = int(total_target_phase2 / phase2_months) if phase2_months > 0 else 0
    total_pay_phase2 = monthly_pay_phase2 * phase2_months

    # 3. 총 회수금
    grand_total_payout = total_pay_phase1 + total_pay_phase2
    
    # 최종 수익률
    if investor_amount > 0:
        final_investor_roi = ((grand_total_payout - investor_amount) / investor_amount) * 100
    else:
        final_investor_roi = 0

    # [C] 현금흐름 시뮬레이션
    cash_flow_log = []
    company_cash_flows = [] 
    
    # ★핵심 수정: 회사의 시작 현금은 0원이 아니라 '잉여 자금'에서 시작함
    cumulative_company_cash = initial_surplus_cash 
    
    actual_investor_received = 0

    for m in range(1, total_op_months + 1):
        # 1. 영업 수익
        if use_promo and m <= promo_months:
            current_op = op_profit_promo
            op_status = "프로모션"
        else:
            current_op = op_profit_normal
            op_status = "정상운영"
            
        # 2. 투자자 지급
        if m <= phase1_months:
            current_payout = monthly_pay_phase1
            pay_status = "1단계(이자)"
        elif m <= total_repay_months:
            current_payout = monthly_pay_phase2
            pay_status = "2단계(상환)"
        else:
            current_payout = 0
            pay_status = "3단계(완료)"
            
        actual_investor_received += current_payout

        # 3. 회사 순현금흐름 (Net Cash Flow)
        # 이번 달 번 돈 - 이번 달 나간 돈
        net_flow = current_op - current_payout
        
        # 4. 누적 현금 (Cumulative Cash)
        # 전월 잔고 + 이번 달 순현금흐름
        cumulative_company_cash += net_flow
        
        company_cash_flows.append(net_flow)
        
        cash_flow_log.append({
            "Month": m,
            "영업상태": op_status,
            "상환상태": pay_status,
            "영업이익": int(current_op),
            "투자자지급": int(-current_payout),
            "월순현금": int(net_flow),
            "회사누적잔고": int(cumulative_company_cash)
        })

    # [D] 지표 종합
    # 회사 총 수익 (운영 종료 후 잔고 - 초기 잉여금 = 순수 벌어들인 돈? 아니면 최종 잔고?)
    # 여기서는 '최종적으로 회사 통장에 남은 돈'을 표시하는 게 가장 직관적임
    final_balance = cumulative_company_cash
    
    # NPV (운영 현금흐름에 대한 가치 + 초기 잉여금도 현재가치로 봐야 하나? 보통은 미래 흐름만 할인)
    monthly_discount = (discount_rate / 100) / 12
    # 초기 잉여금은 현재 시점(0)의 현금이므로 할인하지 않고 더함
    npv_stream = company_cash_flows
    op_npv = npf.npv(monthly_discount, npv_stream)
    total_npv = initial_surplus_cash + op_npv

    # --------------------------------------------------------------------------------
    # 4. 결과 시각화
    # --------------------------------------------------------------------------------
    
    # [Top Metric]
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 1. 잉여 자금 (Start)", f"{int(initial_surplus_cash):,} 원", 
                  help="투자금 - 사업비 = 초기 확보 현금")
    with col2:
        st.metric(f"🏦 2. 최종 회사 잔고 ({operation_years}년후)", f"{int(final_balance):,} 원",
                  help="잉여금 + 누적 영업이익 - 투자자 상환금")
    with col3:
        st.metric("🤝 3. 투자자 총 회수금", f"{int(grand_total_payout):,} 원", 
                  delta=f"수익률 {final_investor_roi:.1f}%")
    with col4:
        st.metric("💎 4. 프로젝트 NPV", f"{int(total_npv):,} 원")
    
    st.divider()

    # [2단 레이아웃]
    left_col, right_col = st.columns([1, 1.3])

    with left_col:
        st.subheader("📊 자금 구조 및 상환 계획")
        
        # 자금 조달 요약
        st.info(f"""
        **[자금 조달 요약]**
        * 필요 사업비: {int(total_project_cost):,} 원
        * 유치 투자금: {int(investor_amount):,} 원
        * **초기 잉여금: {int(initial_surplus_cash):,} 원** (이 돈으로 초기 이자를 방어합니다)
        """)
        
        # 상환 스케줄
        st.markdown("##### 📅 투자자 상환 스케줄")
        df_sch = pd.DataFrame([
            ["1단계 (이자)", f"{phase1_months}개월", f"월 {monthly_pay_phase1:,}원", f"총 {total_pay_phase1:,}원"],
            ["2단계 (원금+수익)", f"{phase2_months}개월", f"월 {monthly_pay_phase2:,}원", f"총 {total_pay_phase2:,}원"],
            ["합계", f"{total_repay_months}개월", "-", f"총 {grand_total_payout:,}원"]
        ], columns=["구분", "기간", "월 지급액", "총 지급액"])
        st.table(df_sch)

    with right_col:
        st.subheader("📉 월별 현금흐름 (회사 잔고)")
        df_chart = pd.DataFrame(cash_flow_log)
        
        # 그래프 설명
        st.line_chart(df_chart, x="Month", y="회사누적잔고", color="#27AE60")
        
        # 잔고 분석
        min_balance = df_chart['회사누적잔고'].min()
        if min_balance < 0:
            st.error(f"⚠️ 경고: 운영 도중 잔고가 마이너스({int(min_balance):,}원)로 떨어지는 구간이 발생합니다! (흑자 도산 위험)")
        else:
            st.success("✅ 운영 전 구간에서 현금 잔고가 플러스(+)를 유지합니다. 안정적인 현금 흐름입니다.")

    with st.expander("📑 월별 상세 데이터 (Excel 다운로드 용도)"):
        st.dataframe(df_chart, use_container_width=True)

if __name__ == "__main__":
    main()