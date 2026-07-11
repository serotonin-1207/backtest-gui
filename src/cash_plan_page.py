# -*- coding: utf-8 -*-
"""적립식 현금관리 계산기 — Streamlit 페이지 (세로토닌 백테스트 2번째 모드).

가격 백테스트와 달리, 대기자금 RP운용·후순위 조달이자·이체/환전/매수 수수료의
'순효과'만 계산한다. 순수 계산은 cash_plan.py, 여기선 화면·차트·다운로드만 담당.
"""
from __future__ import annotations

import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .cash_plan import CashPlanError, compare_scenarios, run_scenario
from .currency import korean_money

_LAYOUT = dict(
    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(20,24,35,1)",
    font=dict(family="Malgun Gothic, sans-serif", size=13),
    margin=dict(l=40, r=20, t=50, b=40), hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
)
ACCENT = "#4FC3F7"

RP_PRESETS = {
    "CMA RP형 (2.05%)": 0.0205,
    "발행어음형 CMA (2.35%)": 0.0235,
    "한국투자 외화RP (3.25%)": 0.0325,
    "키움 USD RP 수시형 (4.00%)": 0.0400,
    "직접 입력": None,
}

DISCLAIMERS = [
    "이 계산기는 수수료·RP 수익·이자비용·이체비용을 비교하기 위한 시뮬레이터이며, "
    "실제 투자수익률은 QLD/TQQQ 가격 변동에 따라 크게 달라질 수 있습니다.",
    "RP 수익률, 키움 수수료 무료 여부, QLD/TQQQ 주식더모으기 가능 여부, 환전수수료, "
    "외화이체 자동화 가능 여부는 실제 증권사 앱에서 최종 확인해야 합니다.",
    "외화 RP를 쓰면서 매일 원화로 바꿔 키움에 이체하고 다시 키움 원화주문으로 환전하는 구조는 "
    "환전이 중복될 수 있으므로 비추천입니다.",
]


def _bignum(v: float) -> str:
    return f"{v:,.0f}원"


def render_cash_plan():
    st.title("💵 적립식 현금관리 계산기")
    st.caption("해외주식 자동 적립매수 시 — 대기자금 RP운용 · 후순위 조달이자 · 이체/환전/매수 수수료의 순효과 비교. "
               "제작 serotonin(이은호)")
    st.info("ℹ️ " + DISCLAIMERS[0])

    # ================= 사이드바 입력
    with st.sidebar:
        st.header("💵 계산기 설정")
        total = st.number_input("총 투자금(원)", 1_000_000.0, value=300_000_000.0,
                                step=10_000_000.0, format="%.0f")
        st.caption(f"= {korean_money(total, 'KRW')}")
        pre_amount = st.number_input("선투입 대기자금(원)", 0.0, value=200_000_000.0,
                                     step=10_000_000.0, format="%.0f")
        financed = max(total - pre_amount, 0.0)
        st.caption(f"후순위 조달금 = 총투자금 − 선투입 = **{korean_money(financed, 'KRW')}**")

        period_sel = st.radio("투자기간", ["1년 (252거래일)", "2년 (504거래일)", "직접 입력"], index=0)
        year_days = st.number_input("연간 거래일 수", 100, 366, 252)
        if period_sel.startswith("1년"):
            days = year_days
        elif period_sel.startswith("2년"):
            days = year_days * 2
        else:
            days = st.number_input("총 거래일 수", 1, 5000, 252)

        cal_basis = st.toggle("기간 환산: 달력일(/365) 기준", value=False,
                              help="OFF(기본)=거래일 기준(÷연간거래일수). 검증값과 일치하는 기준입니다.")

        sub_mode = st.radio("후순위 조달 방식", ["매일 필요한 만큼 조달", "한 번에 조달"], index=0,
                            help="매일 조달: 평균 사용액 후순위/2, RP 대기 없음(일반적으로 가장 효율적). "
                                 "한 번에: 소진 시점에 전액 조달 → RP 운용되지만 이자도 전액.")
        sub_mode_k = "매일" if sub_mode.startswith("매일") else "한번에"

        st.divider()
        rp_kind = st.selectbox("RP 종류", list(RP_PRESETS), index=0)
        default_rp = RP_PRESETS[rp_kind]
        rp_yield = st.number_input("RP 세전 연수익률(%)",
                                   0.0, 20.0, (default_rp * 100 if default_rp else 2.05), 0.05) / 100
        tax_rate = st.number_input("이자소득세율(%)", 0.0, 50.0, 15.4, 0.1) / 100
        debt_rate = st.number_input("후순위 조달 이자율(연 %)", 0.0, 30.0, 4.5, 0.1) / 100

        st.divider()
        buy_fee_rate = st.number_input("매수수수료율(%)", 0.0, 5.0, 0.0, 0.05,
                                       help="키움 주식더모으기 무료=0. 비교용 일반 수수료 0.25%.") / 100
        won_transfer = st.selectbox("원화 이체수수료(/일)", [0, 500], index=0)

        use_fx = st.toggle("외화 RP 구조 사용", value=False)
        fx_transfer = 0
        fx_cost_rate = 0.0
        fx_structure = None
        if use_fx:
            fx_structure = st.radio("외화 구조", [
                "① 외화RP→달러 그대로 키움 외화이체→달러매수",
                "② 외화RP→매일 원화환전→키움 원화이체 (비추천)",
                "③ 원화RP→키움 원화이체→원화주문 (추천)",
            ], index=2)
            fx_transfer = st.number_input("외화 이체수수료(/일)", 0, 5000, 700)
            fx_cost_rate = st.number_input("환전비용률(%, 총투자금 대비 1회)", 0.0, 5.0, 0.0, 0.05) / 100

        # 종목 비중
        st.divider()
        st.markdown("**종목 비중**")
        qld_w = st.number_input("QLD %", 0.0, 100.0, 50.0, 5.0)
        tqqq_w = st.number_input("TQQQ %", 0.0, 100.0, 50.0, 5.0)
        etc_w = max(0.0, 100.0 - qld_w - tqqq_w)
        st.caption(f"기타 {etc_w:.0f}% (합계 {qld_w + tqqq_w + etc_w:.0f}%)")
        exp_return = st.number_input("예상 연수익률(%) — 참고용 평가금액", -50.0, 100.0, 0.0, 1.0) / 100

    # 이체수수료: 외화구조 ①이면 외화이체, 그 외 원화이체
    transfer_fee = fx_transfer if (use_fx and fx_structure and fx_structure.startswith("①")) else won_transfer

    # ================= 현재 시나리오 계산
    try:
        cur = run_scenario(total=total, pre_amount=pre_amount, days=int(days), year_days=int(year_days),
                           rp_yield=rp_yield, tax_rate=tax_rate, debt_rate=debt_rate,
                           sub_mode=sub_mode_k, buy_fee_rate=buy_fee_rate,
                           transfer_fee_per_day=transfer_fee, fx_cost_rate=fx_cost_rate,
                           calendar_basis=cal_basis, label="현재 설정")
    except CashPlanError as e:
        st.error(f"입력 오류: {e}")
        return
    if abs(qld_w + tqqq_w - 100.0) > 0.01 and etc_w == 0:
        st.warning("종목 비중 합이 100%가 아닙니다. '기타'로 자동 배분되었습니다.")

    df = cur["df"]

    # ================= 요약 카드
    st.subheader("📊 핵심 요약 (현재 설정)")
    c = st.columns(4)
    c[0].metric("총 투자금", _bignum(cur["총투자금"]))
    c[0].caption(korean_money(cur["총투자금"], "KRW"))
    c[1].metric("1일 투자금", _bignum(cur["1일투자금"]))
    c[2].metric("선투입 소진일", f"{cur['선투입소진일']:.0f} 거래일")
    c[3].metric("후순위 시작일", f"{cur['후순위시작일']:.0f} 거래일째")
    c = st.columns(4)
    c[0].metric("세전 RP 수익", _bignum(cur["세전RP수익"]))
    c[1].metric("세후 RP 수익", _bignum(cur["세후RP수익"]))
    c[2].metric("후순위 이자비용", "-" + _bignum(cur["후순위이자비용"]))
    c[3].metric("이체수수료", "-" + _bignum(cur["이체수수료"]))
    c = st.columns(4)
    c[0].metric("매수수수료", "-" + _bignum(cur["매수수수료"]))
    c[1].metric("환전비용", "-" + _bignum(cur["환전비용"]))
    net = cur["최종순효과"]
    c[2].metric("최종 순효과", ("+" if net >= 0 else "") + _bignum(net),
                delta=f"{net/total*100:+.3f}% (총투자금 대비)")
    c[3].metric("세후 실효", korean_money(net, "KRW"))
    if net < 0:
        st.warning("⚠️ 현재 설정에서는 순효과가 **마이너스**입니다 (비용 > RP수익). "
                   "조달방식·수수료·RP수익률을 조정해 보세요.")

    tabs = st.tabs(["📋 시나리오 비교", "📈 그래프", "🧾 종목별·예상평가", "📥 다운로드", "❓ 도움말"])

    # ================= 비교표
    with tabs[0]:
        cmp = compare_scenarios(dict(total=total, pre_amount=pre_amount, year_days=int(year_days),
                                     tax_rate=tax_rate, debt_rate=debt_rate,
                                     rp_won=RP_PRESETS["CMA RP형 (2.05%)"],
                                     rp_fx1=0.0325, rp_fx2=0.0400,
                                     compare_fee_rate=0.0025, calendar_basis=cal_basis))
        show_cols = ["시나리오", "1일투자금", "선투입소진일", "후순위사용기간", "세후RP수익",
                     "후순위이자비용", "이체수수료", "매수수수료", "최종순효과"]
        st.dataframe(cmp[show_cols], hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="localized")
                                    for c in show_cols if cmp[c].dtype.kind == "f"})
        best = cmp.loc[cmp["최종순효과"].idxmax()]
        worst = cmp.loc[cmp["최종순효과"].idxmin()]
        st.success(f"✅ 최고: **{best['시나리오']}** → {_bignum(best['최종순효과'])} "
                   f"({korean_money(best['최종순효과'],'KRW')})")
        st.error(f"❌ 최저: **{worst['시나리오']}** → {_bignum(worst['최종순효과'])}")
        st.caption("• '한 번에 조달'은 이자가 전액이라 대개 순효과가 낮습니다. '매일 조달'이 일반적으로 유리합니다.")
        st.caption("• 수수료 0.25% 비교안은 총투자금의 0.25%가 매수수수료로 빠져 순효과가 크게 낮아집니다.")

    # ================= 그래프
    with tabs[1]:
        f1 = go.Figure(go.Scatter(x=df["거래일"], y=df["대기잔액"], fill="tozeroy",
                                  line=dict(color=ACCENT), name="대기잔액"))
        f1.update_layout(title="날짜별 남은 대기자금(RP 운용) 잔액", **_LAYOUT)
        st.plotly_chart(f1, width="stretch")

        f2 = go.Figure()
        f2.add_scatter(x=df["거래일"], y=df["누적투자금"], line=dict(color="#81C784"), name="누적 투자금")
        f2.update_layout(title="누적 투자금", **_LAYOUT)
        st.plotly_chart(f2, width="stretch")

        cc = st.columns(2)
        f3 = go.Figure(go.Scatter(x=df["거래일"], y=df["누적RP수익(세전)"],
                                  line=dict(color="#FFD54F"), name="누적 RP수익(세전)"))
        f3.update_layout(title="누적 RP 수익(세전)", **_LAYOUT)
        cc[0].plotly_chart(f3, width="stretch")
        f4 = go.Figure(go.Scatter(x=df["거래일"], y=df["누적이자비용"],
                                  line=dict(color="#E57373"), name="누적 이자비용"))
        f4.update_layout(title="누적 후순위 이자비용", **_LAYOUT)
        cc[1].plotly_chart(f4, width="stretch")

        # 최종 순효과 비교 막대
        cmp2 = compare_scenarios(dict(total=total, pre_amount=pre_amount, year_days=int(year_days),
                                      tax_rate=tax_rate, debt_rate=debt_rate,
                                      rp_won=RP_PRESETS["CMA RP형 (2.05%)"], calendar_basis=cal_basis))
        colors = ["#81C784" if v >= 0 else "#E57373" for v in cmp2["최종순효과"]]
        fb = go.Figure(go.Bar(x=cmp2["시나리오"], y=cmp2["최종순효과"], marker_color=colors,
                              text=[f"{v:,.0f}" for v in cmp2["최종순효과"]], textposition="outside"))
        fb.update_layout(title="시나리오별 최종 순효과 비교", **_LAYOUT)
        st.plotly_chart(fb, width="stretch")

    # ================= 종목별 · 예상평가
    with tabs[2]:
        weights = {"QLD": qld_w, "TQQQ": tqqq_w, "기타": etc_w}
        rows = []
        for nm, w in weights.items():
            if w <= 0:
                continue
            alloc = total * w / 100
            rows.append({"종목": nm, "비중": w / 100, "배분 투자금": alloc,
                         "1일 투자금": alloc / days,
                         "매수수수료": alloc * buy_fee_rate})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch",
                     column_config={"비중": st.column_config.NumberColumn(format="percent"),
                                    "배분 투자금": st.column_config.NumberColumn(format="localized"),
                                    "1일 투자금": st.column_config.NumberColumn(format="localized"),
                                    "매수수수료": st.column_config.NumberColumn(format="localized")})
        yrs = days / year_days
        simple_val = total * (1 + exp_return) ** yrs
        st.metric("단순 예상 평가금액(참고용)", _bignum(simple_val),
                  delta=_bignum(simple_val - total))
        st.warning("⚠️ 레버리지 ETF(QLD·TQQQ)는 **일간 복리·변동성 훼손**이 있어 단순 연수익률 계산은 "
                   "실제와 크게 다를 수 있습니다. 정확한 가격 시뮬레이션은 상단 모드의 '가격 백테스트'를 쓰세요.")

    # ================= 다운로드
    with tabs[3]:
        st.download_button("📄 일자별 현금흐름 CSV", df.to_csv(index=False).encode("utf-8-sig"),
                           "cashflow_daily.csv", "text/csv")
        cmp_full = compare_scenarios(dict(total=total, pre_amount=pre_amount, year_days=int(year_days),
                                          tax_rate=tax_rate, debt_rate=debt_rate,
                                          rp_won=RP_PRESETS["CMA RP형 (2.05%)"], calendar_basis=cal_basis))
        st.download_button("📄 시나리오 비교표 CSV", cmp_full.to_csv(index=False).encode("utf-8-sig"),
                           "scenario_compare.csv", "text/csv")
        inputs = {"총투자금": total, "선투입금": pre_amount, "후순위조달금": financed,
                  "총거래일": days, "연간거래일수": year_days, "RP종류": rp_kind,
                  "RP세전수익률": rp_yield, "이자소득세율": tax_rate, "후순위이자율": debt_rate,
                  "조달방식": sub_mode_k, "매수수수료율": buy_fee_rate, "이체수수료/일": transfer_fee,
                  "환전비용률": fx_cost_rate, "기간환산": "달력일" if cal_basis else "거래일"}
        xls = _build_excel(inputs, df, cmp_full, cur)
        st.download_button("📊 Excel 다운로드 (입력·일자별·비교·요약)", xls, "cash_plan.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ================= 도움말
    with tabs[4]:
        st.markdown("### 계산 모델")
        st.markdown(
            "- **1일 투자금** = 총 투자금 ÷ 총 거래일 수\n"
            "- **선투입 소진일** = 선투입금 ÷ 1일 투자금\n"
            "- **선투입 RP 수익** = (선투입/2) × RP연수익률 × (소진일÷연간거래일수) → 세후 ×(1−세율)\n"
            "- **후순위(매일)** 이자 = (후순위/2) × 이자율 × (후순위기간÷연간거래일수), RP 없음\n"
            "- **후순위(한번에)** 이자 = 후순위 × 이자율 × 기간, RP = (후순위/2) 운용\n"
            "- **최종 순효과** = 세후 RP수익 − 후순위 이자 − 이체수수료 − 환전비용 − 매수수수료")
        st.markdown("### 외화 RP 3구조")
        st.markdown(
            "1. **달러 그대로 외화이체→달러매수**: 환전 1회, 외화이체 700원/일. "
            "키움에서 달러 매수 가능 여부는 직접 확인 필요.\n"
            "2. **매일 원화 환전→원화이체 (비추천)**: 환전 중복 위험, 환전비용 반영.\n"
            "3. **원화 RP→원화이체→원화주문 (추천)**: 환전 0원, 자동화 가장 쉬움.")
        for d in DISCLAIMERS:
            st.caption("• " + d)


def _build_excel(inputs: dict, daily: pd.DataFrame, compare: pd.DataFrame, summary: dict) -> bytes:
    import xlsxwriter
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "nan_inf_to_errors": True})
    hdr = wb.add_format({"bold": True, "bg_color": "#1F3864", "font_color": "white", "border": 1})
    num = wb.add_format({"num_format": "#,##0"})

    def sheet(name, df):
        ws = wb.add_worksheet(name)
        for j, col in enumerate(df.columns):
            ws.write(0, j, str(col), hdr)
            ws.set_column(j, j, max(12, len(str(col)) + 2))
        for i, (_, row) in enumerate(df.iterrows(), 1):
            for j, col in enumerate(df.columns):
                v = row[col]
                if isinstance(v, (int, float)) and not pd.isna(v):
                    ws.write_number(i, j, float(v), num)
                else:
                    ws.write(i, j, "" if pd.isna(v) else str(v))

    sheet("입력값", pd.DataFrame([{"항목": k, "값": v} for k, v in inputs.items()]))
    sheet("일자별현금흐름", daily)
    sheet("시나리오비교", compare)
    summ = {k: v for k, v in summary.items() if k != "df"}
    sheet("요약", pd.DataFrame([{"항목": k, "값": v} for k, v in summ.items()]))
    wb.close()
    buf.seek(0)
    return buf.getvalue()
