# -*- coding: utf-8 -*-
"""Plotly 차트 (다크 템플릿, 전략별 고정 색상)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# 전략별 고정 색상 팔레트 — 표·카드·모든 차트 공통
PALETTE = ["#4FC3F7", "#FFB74D", "#81C784", "#F06292", "#BA68C8",
           "#FFD54F", "#4DB6AC", "#E57373", "#90A4AE", "#AED581"]

_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(20,24,35,1)",
    font=dict(family="Malgun Gothic, sans-serif", size=13),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    margin=dict(l=40, r=20, t=60, b=40),
    hovermode="x unified",
)


def color_of(i: int) -> str:
    return PALETTE[i % len(PALETTE)]


def fig_equity(results: list, log_scale: bool = False, normalize: bool = True) -> go.Figure:
    """누적 수익률(시작=100) 또는 순자산 곡선 겹쳐 보기. 불입▲/인출▼ 마커 포함."""
    fig = go.Figure()
    for i, r in enumerate(results):
        eq = r.equity.dropna()
        if normalize:
            from .metrics import twr_index
            y = twr_index(eq, r.flows) * 100
        else:
            y = eq
        name = r.name + (" [합성포함]" if r.is_synthetic_used else "")
        fig.add_trace(go.Scatter(x=eq.index, y=y, name=name,
                                 line=dict(color=color_of(i), width=1.8)))
        # 불입/인출 마커
        ups = [(e["date"], e["금액"]) for e in r.events_log if e["구분"] == "추가불입"]
        downs = [(e["date"], e["금액"]) for e in r.events_log if e["구분"] == "중도인출"]
        for evs, sym, nm in [(ups, "triangle-up", "추가불입"), (downs, "triangle-down", "중도인출")]:
            if evs:
                xs = [d for d, _ in evs]
                ys = [float(y.loc[d]) if d in y.index else None for d, _ in evs]
                fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", showlegend=False,
                                         marker=dict(symbol=sym, size=11, color=color_of(i),
                                                     line=dict(color="white", width=1)),
                                         name=f"{r.name} {nm}", hovertext=[f"{nm} {a:,.0f}" for _, a in evs]))
    fig.update_layout(title="누적 수익률 (시작=100)" if normalize else "순자산 곡선", **_LAYOUT)
    if log_scale:
        fig.update_yaxes(type="log")
    return fig


def fig_drawdown(results: list) -> go.Figure:
    """언더워터(drawdown) 플롯."""
    fig = go.Figure()
    for i, r in enumerate(results):
        from .metrics import twr_index
        perf = twr_index(r.equity.dropna(), r.flows)
        dd = perf / perf.cummax() - 1.0
        fig.add_trace(go.Scatter(x=dd.index, y=dd * 100, name=r.name,
                                 fill="tozeroy", line=dict(color=color_of(i), width=1)))
    fig.update_layout(title="언더워터 플롯 (고점 대비 낙폭 %)", **_LAYOUT)
    return fig


def fig_final_values(results: list, values: list | None = None, unit: str = "") -> go.Figure:
    """전략별 최종 순자산 막대. values로 환산값을 넘기면 그 값으로 표시."""
    vals = values if values is not None else [r.final_value for r in results]
    fig = go.Figure(go.Bar(
        x=[r.name for r in results],
        y=vals,
        marker_color=[color_of(i) for i in range(len(results))],
        text=[f"{v:,.0f}" for v in vals], textposition="outside",
    ))
    fig.update_layout(title=f"전략별 최종 순자산{f' ({unit})' if unit else ''}", **_LAYOUT)
    return fig


def fig_annual_returns(results: list) -> go.Figure:
    from .metrics import annual_returns, twr_index
    fig = go.Figure()
    for i, r in enumerate(results):
        ar = annual_returns(twr_index(r.equity.dropna(), r.flows))
        fig.add_trace(go.Bar(x=ar.index.astype(str), y=ar * 100, name=r.name,
                             marker_color=color_of(i)))
    fig.update_layout(title="연도별 수익률 (%)", barmode="group", **_LAYOUT)
    return fig


def fig_monthly_heatmap(result) -> go.Figure:
    from .metrics import monthly_returns_table, twr_index
    tbl = monthly_returns_table(twr_index(result.equity.dropna(), result.flows))
    fig = go.Figure(go.Heatmap(
        z=tbl.values * 100, x=[f"{m}월" for m in tbl.columns], y=tbl.index.astype(str),
        colorscale="RdBu", zmid=0, colorbar=dict(title="%"),
        hovertemplate="%{y} %{x}: %{z:.1f}%<extra></extra>"))
    fig.update_layout(title=f"월별 수익률 히트맵 — {result.name}", **_LAYOUT)
    fig.update_yaxes(autorange="reversed")
    return fig


def fig_t_series(results: list) -> go.Figure:
    """라오어 T값 변화."""
    fig = go.Figure()
    for i, r in enumerate(results):
        if r.t_series is None:
            continue
        fig.add_trace(go.Scatter(x=r.t_series.index, y=r.t_series, name=r.name,
                                 line=dict(color=color_of(i), width=1.2)))
    fig.add_hline(y=20, line_dash="dash", line_color="gray",
                  annotation_text="후반전 경계 T=20")
    fig.add_hline(y=39.1, line_dash="dot", line_color="red",
                  annotation_text="원금 소진 T=39.1")
    fig.update_layout(title="라오어 T값 변화", **_LAYOUT)
    return fig


def fig_cash_ratio(results: list) -> go.Figure:
    """현금 비중 변화."""
    fig = go.Figure()
    for i, r in enumerate(results):
        if r.cash_series is None:
            continue
        ratio = (r.cash_series / r.equity.replace(0, pd.NA)).astype(float) * 100
        fig.add_trace(go.Scatter(x=ratio.index, y=ratio, name=r.name,
                                 line=dict(color=color_of(i), width=1.2)))
    fig.update_layout(title="현금 비중 (%)", **_LAYOUT)
    return fig
