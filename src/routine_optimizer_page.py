# -*- coding: utf-8 -*-
"""최적의 투자 루틴 추천 Streamlit 화면."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data_loader import get_price
from .routine_optimizer import dimension_winners, optimize_routines


@st.cache_data(ttl="1h", max_entries=8, show_spinner=False)
def _run_optimizer(
    assets: tuple[str, ...],
    durations: tuple[int, ...],
    objective: str,
    step_months: int,
    initial_ratio: float,
    fee_bp: float,
) -> tuple[pd.DataFrame, str]:
    price_data = {ticker: get_price(ticker, "yahoo", "USD") for ticker in assets}
    common_start = max(df.index.min() for df in price_data.values())
    common_end = min(df.index.max() for df in price_data.values())
    result = optimize_routines(
        price_data,
        list(durations),
        objective=objective,
        step_months=step_months,
        initial_ratio=initial_ratio,
        fee_bp=fee_bp,
    )
    return result, f"{common_start.date()} ~ {common_end.date()}"


def _top_chart(df: pd.DataFrame) -> go.Figure:
    top = df.head(15).sort_values("종합점수")
    labels = (
        top["자산"] + " · " + top["투자기간"] + " · " + top["투자방식"]
        + " · " + top["투자주기"]
    )
    fig = go.Figure(
        go.Bar(
            x=top["종합점수"],
            y=labels,
            orientation="h",
            marker_color=["#4fc3f7" if i < len(top) - 1 else "#66bb6a" for i in range(len(top))],
            text=[f"{v:.3f}" for v in top["종합점수"]],
            textposition="outside",
        )
    )
    fig.update_layout(
        title="상위 15개 투자 루틴 — 종합점수",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,24,35,1)",
        height=620,
        margin=dict(l=30, r=40, t=60, b=40),
        font=dict(family="Malgun Gothic, sans-serif"),
        xaxis_title="종합점수 (후보 간 상대 비교용)",
    )
    return fig


def render_routine_optimizer() -> None:
    st.title("🎯 최적의 투자 루틴 추천")
    st.caption(
        "QQQ·QLD·TQQQ의 실제 가격을 여러 시작일에서 반복 검증해 투자 주기·기간·자산·방식을 함께 추천합니다."
    )
    st.warning(
        "**중요:** 여기서 '최적'은 미래 수익 보장이 아니라 과거 여러 구간에서 수익과 위험의 균형이 "
        "가장 안정적이었던 조합입니다. TQQQ·QLD는 일간 목표 레버리지 상품이라 장기 성과가 "
        "기초지수의 정확한 3배·2배가 아닙니다."
    )

    with st.form("routine_optimizer_form"):
        assets = st.pills(
            "비교 자산",
            ["QQQ", "QLD", "TQQQ"],
            default=["QQQ", "QLD", "TQQQ"],
            selection_mode="multi",
        )
        durations = st.multiselect(
            "비교 투자기간",
            list(range(1, 16)),
            default=list(range(1, 11)),
            format_func=lambda y: f"{y}년",
        )
        c1, c2 = st.columns(2)
        objective = c1.segmented_control(
            "추천 성향", ["균형", "수익 우선", "방어 우선"], default="균형"
        )
        step_label = c2.selectbox(
            "시작일 검증 간격", ["3개월", "6개월", "12개월"], index=2,
            help="짧을수록 더 많은 시작일을 검사하지만 계산 시간이 늘어납니다.",
        )
        c4, c5, c6 = st.columns(3)
        initial_pct = c4.slider(
            "거치식 후 적립식의 최초 투자비중", 10, 90, 50, 10,
            format="%d%%",
        )
        fee_bp = c5.number_input("편도 매매비용(bp)", 0.0, 100.0, 5.0, 1.0)
        max_mdd_pct = c6.slider(
            "감당 가능한 최대 낙폭", 20, 90, 60, 5,
            format="-%d%%",
            help="롤링 검증의 최악 MDD가 이 값보다 깊은 조합은 추천에서 제외합니다.",
        )
        st.caption("라오어 무한매수법 V4.0(40분할)은 **TQQQ·SOXL**에만 적용됩니다.")
        submitted = st.form_submit_button(
            "전체 조합 분석하고 최적 루틴 추천", type="primary", width="stretch"
        )

    if submitted:
        if not assets or not durations:
            st.error("비교 자산과 투자기간을 각각 1개 이상 선택하세요.")
        else:
            step_months = {"3개월": 3, "6개월": 6, "12개월": 12}[step_label]
            with st.spinner("여러 시작일과 전체 투자 조합을 계산하고 있습니다…"):
                results, period = _run_optimizer(
                    tuple(assets),
                    tuple(int(y) for y in durations),
                    objective or "균형",
                    step_months,
                    initial_pct / 100.0,
                    fee_bp,
                )
            st.session_state["routine_optimizer_results"] = results
            st.session_state["routine_optimizer_period"] = period
            st.session_state["routine_optimizer_objective"] = objective or "균형"
            st.session_state["routine_optimizer_max_mdd"] = max_mdd_pct / 100.0

    all_results = st.session_state.get("routine_optimizer_results")
    if all_results is None:
        st.info("조건을 확인한 뒤 **전체 조합 분석하고 최적 루틴 추천**을 누르세요.")
        return
    if all_results.empty:
        st.error("완료된 롤링 검증 구간이 부족합니다. 기간을 줄이거나 검증 간격을 짧게 설정하세요.")
        return

    risk_limit = st.session_state.get("routine_optimizer_max_mdd", 0.60)
    results = all_results[all_results["최악MDD"] >= -risk_limit].reset_index(drop=True)
    if results.empty:
        st.error(
            f"최악 MDD -{risk_limit:.0%} 이내에서 조건을 만족하는 조합이 없습니다. "
            "감당 가능한 최대 낙폭을 높이거나 비교 자산을 조정하세요."
        )
        return
    excluded = len(all_results) - len(results)
    period = st.session_state.get("routine_optimizer_period", "")
    objective = st.session_state.get("routine_optimizer_objective", "균형")
    winners = dimension_winners(results)
    best = winners["전체"]

    st.success(
        f"**추천 루틴:** {best['자산']}에 **{best['투자방식']}**으로 "
        f"**{best['투자주기']} · {best['투자기간']}** 투자"
    )
    st.caption(
        f"공통 비교 데이터 {period} · 추천 성향 {objective} · "
        f"{int(best['검증구간수'])}개 시작 구간 검증 · 최악 MDD -{risk_limit:.0%} 이내 "
        f"({excluded}개 위험 초과 조합 제외)"
    )
    frequency_scores = (
        results[results["투자방식"].isin(["적립식", "거치식 후 적립식"])]
        .groupby("투자주기")["종합점수"].median()
        .sort_values(ascending=False)
    )
    if len(frequency_scores) >= 2 and frequency_scores.iloc[0] - frequency_scores.iloc[1] < 0.005:
        st.info(
            f"**투자 주기 실질 동률:** {frequency_scores.index[0]}와 "
            f"{frequency_scores.index[1]}의 점수 차이가 매우 작습니다. 이 경우 거래비용·자동이체 편의성을 "
            "고려해 더 꾸준히 지킬 수 있는 주기를 선택하는 것이 합리적입니다."
        )

    with st.container(horizontal=True):
        st.metric("최적 투자 주기", winners["투자주기"]["투자주기"], border=True)
        st.metric("최적 투자기간", winners["투자기간"]["투자기간"], border=True)
        st.metric("최적 자산", winners["자산"]["자산"], border=True)
        st.metric("최적 투자방식", winners["투자방식"]["투자방식"], border=True)

    with st.container(horizontal=True):
        st.metric("중앙 연수익률", f"{best['중앙연수익률']:.1%}", border=True)
        st.metric("하위 10% 연수익률", f"{best['하위10%연수익률']:.1%}", border=True)
        st.metric("중앙 MDD", f"{best['중앙MDD']:.1%}", border=True)
        st.metric("최악 MDD", f"{best['최악MDD']:.1%}", border=True)
        st.metric("수익 구간 비율", f"{best['수익구간비율']:.0%}", border=True)

    st.info(
        "**추천을 읽는 방법**\n\n"
        "- **중앙 연수익률:** 여러 시작일 결과의 한가운데 값으로, 한 번의 대박 구간 영향을 줄입니다.\n"
        "- **하위 10% 연수익률:** 시작 시점이 나빴을 때의 결과입니다. 높을수록 진입시점 의존성이 낮습니다.\n"
        "- **MDD:** 투자 중 고점 대비 최대 하락폭입니다. 수익률과 함께 반드시 확인하세요.\n"
        "- 위 네 개의 '최적' 카드는 각 항목을 다른 조건 전체에서 평가한 결과입니다. 카드만 임의로 "
        "조합하기보다 위의 **추천 루틴 전체 조합**을 우선 참고하세요."
    )

    st.plotly_chart(_top_chart(results), width="stretch")
    display = results.head(100).copy()
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        column_config={
            c: st.column_config.NumberColumn(format="percent")
            for c in ["중앙연수익률", "하위10%연수익률", "중앙MDD", "최악MDD", "수익구간비율"]
        },
    )
    st.caption(
        "거치식의 투자주기는 1회, 라오어는 매일 주문입니다. 매일·매주·매월·매분기·매년 주기 비교는 "
        "적립식과 거치식 후 적립식에 적용됩니다. QDL이 아니라 정식 티커 **QLD**를 사용합니다."
    )
