# -*- coding: utf-8 -*-
"""미국 주요 지수 & 레버리지 상품(1·2·3배) 총정리 — 팝업(모달) + 누적수익률 차트.

각 지수 설명, 지수→1/2/3배 추종상품 목록, 상장 시점부터의 누적수익률 차트, 성과·위험 요약.
차트 데이터는 src/index_ref_data.csv (월별 정규화, 각 상품 상장=100).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_DATA = Path(__file__).resolve().parent / "index_ref_data.csv"

_CSS = """
<style>
.ir { font-family:"Malgun Gothic",sans-serif; line-height:1.7; color:#e8eaf0; }
.ir h2 { color:#4fc3f7; border-left:5px solid #4fc3f7; padding-left:10px; margin-top:24px; }
.ir table { border-collapse:collapse; width:100%; margin:10px 0; font-size:13px; }
.ir th { background:#22304d; padding:7px; border:1px solid #2a3550; text-align:left; }
.ir td { padding:7px; border:1px solid #2a3550; }
.ir tr:nth-child(even) td { background:#161e30; }
.ir .warn { background:#3a2418; border-left:5px solid #ff7043; padding:10px 14px; border-radius:8px; margin:12px 0; }
.ir .tip { background:#16301f; border-left:5px solid #66bb6a; padding:10px 14px; border-radius:8px; margin:12px 0; }
.ir .neg{color:#ff8a80;font-weight:bold} .ir .pos{color:#a5d6a7;font-weight:bold}
</style>
"""

# ---------------- 지수 설명
EXPLAIN = _CSS + """
<div class="ir">
<h2>📚 주요 지수는 무엇인가</h2>
<table>
<tr><th>지수</th><th>구성</th><th>성격</th></tr>
<tr><td><b>S&P500</b></td><td>미국 대형주 500개</td><td>미국 증시 대표 벤치마크. 가장 널리 쓰임.</td></tr>
<tr><td><b>나스닥100</b></td><td>나스닥 <b>비금융</b> 대형주 100개</td><td>애플·MS·엔비디아 등 빅테크 집중. 성장주 대표.</td></tr>
<tr><td>나스닥종합</td><td>나스닥 전체 3,000여 개</td><td>소형주까지 포함. 나스닥100보다 분산·변동 큼.</td></tr>
<tr><td>다우존스</td><td>초대형 우량주 30개</td><td>전통 산업 위주. 보수적·저성장.</td></tr>
<tr><td>러셀2000</td><td>미국 소형주 2,000개</td><td>경기 민감. 장기 성과는 대형주에 뒤짐.</td></tr>
<tr><td><b>반도체(SOX)</b></td><td>미국 반도체 30개</td><td>엔비디아·AMD·TSMC 등. <b>최고 수익·최고 위험</b>.</td></tr>
</table>
</div>
"""

# ---------------- 지수 → 1/2/3배 상품
PRODUCTS_HTML = _CSS + """
<div class="ir">
<h2>🎯 지수별 레버리지 상품 (1배 / 2배 / 3배)</h2>
<p>배수가 클수록 <b>수익도 손실도 배수만큼</b> 커집니다(일간 기준). 3배는 폭락 시 -90%급도 가능합니다.</p>
<table>
<tr><th>추종 지수</th><th>1배 (원지수 ETF)</th><th>2배</th><th>3배</th></tr>
<tr><td>나스닥100</td><td><b>QQQ</b> · QQQM</td><td><b>QLD</b></td><td class="neg"><b>TQQQ</b></td></tr>
<tr><td>S&P500</td><td>SPY · VOO · IVV</td><td>SSO</td><td class="neg">UPRO · SPXL</td></tr>
<tr><td>다우존스</td><td>DIA</td><td>DDM</td><td class="neg">UDOW</td></tr>
<tr><td>러셀2000(소형)</td><td>IWM</td><td>UWM</td><td class="neg">TNA</td></tr>
<tr><td>반도체</td><td>SOXX · SMH</td><td>USD</td><td class="neg">SOXL</td></tr>
<tr><td>기술 섹터</td><td>XLK · VGT</td><td>ROM</td><td class="neg">TECL</td></tr>
<tr><td>금융</td><td>XLF</td><td>UYG</td><td class="neg">FAS</td></tr>
<tr><td>에너지</td><td>XLE</td><td>DIG</td><td>ERX(현재 2배)</td></tr>
<tr><td>헬스케어</td><td>XLV</td><td>RXL</td><td class="neg">CURE</td></tr>
<tr><td>반도체(개별)</td><td>—</td><td>—</td><td class="neg">NVDL(엔비디아 2배)</td></tr>
</table>
<p style="font-size:12px;color:#9aa4bb">※ 티커·배수는 발행사(ProShares·Direxion 등) 기준이며 변경될 수 있습니다. 국내 증권사에서
매매·주식더모으기 가능 여부는 반드시 앱에서 확인하세요. 국내상장 유사상품(TIGER·KODEX 미국나스닥100 등)도 있습니다.</p>
</div>
"""

# ---------------- 성과·위험 요약 (실측)
SUMMARY_HTML = _CSS + """
<div class="ir">
<h2>📊 상장 이후 성과 · 위험 (실측)</h2>
<table>
<tr><th>상품</th><th>상장</th><th>누적</th><th>CAGR</th><th>역대 최악 MDD</th></tr>
<tr><td class="neg">TQQQ (나100 3배)</td><td>2010</td><td>371배</td><td>43.4%</td><td class="neg">-81.7%</td></tr>
<tr><td class="neg">SOXL (반도체 3배)</td><td>2010</td><td>320배</td><td>42.4%</td><td class="neg">-90.5%</td></tr>
<tr><td>UPRO (S&P 3배)</td><td>2009</td><td>129배</td><td>33.0%</td><td>-76.8%</td></tr>
<tr><td>QLD (나100 2배)</td><td>2006</td><td>95배</td><td>25.5%</td><td>-83.1%</td></tr>
<tr><td>UDOW (다우 3배)</td><td>2010</td><td>48배</td><td>26.5%</td><td>-80.3%</td></tr>
<tr><td>반도체(SOX 1배)</td><td>—</td><td>—</td><td class="pos">15.7%</td><td class="neg">-87.1%</td></tr>
<tr><td>나스닥100 (1배)</td><td>—</td><td>—</td><td>14.7%</td><td>-82.9%</td></tr>
<tr><td>QQQ (1배 ETF)</td><td>1999</td><td>17배</td><td>10.9%</td><td>-83.0%</td></tr>
<tr><td>SPY (S&P 1배)</td><td>1993</td><td>31배</td><td>10.8%</td><td>-55.2%</td></tr>
<tr><td>다우 / 러셀2000 (1배)</td><td>—</td><td>—</td><td>8~9%</td><td>-52~60%</td></tr>
</table>

<div class="tip">
<b>한눈 요약</b><br>
• <b>수익 1위(1배)</b>: 반도체(CAGR 15.7%) &gt; 나스닥100(14.7%) &gt; S&P500·나스닥종합(11%) &gt; 다우·러셀(8~9%).
반도체는 <b>최근만이 아니라 장기 내내 1위</b>였습니다.<br>
• <b>레버리지</b>: 3배 상품(TQQQ 43%·SOXL 42%·UPRO 33%)은 상승장에서 폭발하지만, <b>MDD가 -77~90%</b>로 참혹합니다.<br>
• <b>SOXL(반도체 3배)의 역대 MDD -90.5%</b> = 1억이 <b>1천만원</b>이 된 순간이 있었다는 뜻.
</div>

<div class="warn">
<b>⚠️ 레버리지·감쇠 경고</b>: 2·3배 상품은 <b>일간 리셋 구조</b>라 횡보·급락장에서 원지수보다 훨씬 불리하게 감쇠합니다.
장기 보유 시 반드시 <b>적립식·분산·감당 가능한 규모</b>로. 백테스트 수치는 미래를 보장하지 않습니다.
</div>
</div>
"""


@st.cache_data(show_spinner=False)
def _chart_data() -> pd.DataFrame:
    df = pd.read_csv(_DATA, index_col=0, parse_dates=True)
    # 진행 중인 월을 월말로 라벨링한 값이 미래 데이터처럼 보이지 않게 오늘로 보정한다.
    today = pd.Timestamp.today().normalize()
    future = df.index > today
    df.attrs["partial_month_adjusted"] = bool(future.any())
    if future.any():
        idx = df.index.to_series()
        idx.loc[future] = today
        df.index = pd.DatetimeIndex(idx)
        df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


_IDX_COLS = ["S&P500", "나스닥100", "나스닥종합", "다우존스", "러셀2000", "반도체(SOX)"]


def _fig() -> go.Figure:
    """① 상장 시점부터 — 각 상품 상장일=100 (레버리지 포함)."""
    df = _chart_data()
    fig = go.Figure()
    for col in df.columns:
        s = df[col].dropna()
        if "3x" in col or "3배" in col:
            color, w, dash = "#ff6e6e", 2.4, None
        elif "2x" in col or "2배" in col:
            color, w, dash = "#ffb74d", 1.9, None
        elif "1x" in col:
            color, w, dash = "#4fc3f7", 1.5, None
        else:  # 지수(원지수)
            color, w, dash = "#9aa4bb", 1.1, "dot"
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=col,
                                 line=dict(color=color, width=w, dash=dash)))
    fig.update_yaxes(type="log", title="누적 (상장=100, 로그스케일)")
    fig.update_layout(
        title="① 상장 시점부터 — 각 상품 상장일=100 (레버리지 포함, 상장일 제각각)",
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(20,24,35,1)",
        font=dict(family="Malgun Gothic, sans-serif", size=12),
        legend=dict(font=dict(size=10)), margin=dict(l=40, r=10, t=50, b=40), height=520,
        hovermode="x unified")
    return fig


def _fig_since_1990s() -> go.Figure:
    """② 1995년~현재 — ①과 동일한 지수·1배·2배·3배 구성을 재정규화."""
    df = _chart_data()
    base = "1995-01-01"
    fig = go.Figure()
    for col in df.columns:
        s = df[col].dropna()
        s = s.loc[s.index >= base]
        if s.empty or s.iloc[0] == 0:
            continue
        s = s / s.iloc[0] * 100.0
        if "3x" in col or "3배" in col:
            color, w, dash = "#ff6e6e", 2.4, None
        elif "2x" in col or "2배" in col:
            color, w, dash = "#ffb74d", 1.9, None
        elif "1x" in col:
            color, w, dash = "#4fc3f7", 1.5, None
        else:
            color, w, dash = "#9aa4bb", 1.1, "dot"
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=col,
                                 line=dict(color=color, width=w, dash=dash)))
    fig.update_yaxes(type="log", title="누적 (1995년 이후 첫 값=100, 로그스케일)")
    fig.update_layout(
        title="② 1995년~현재 — ①과 동일한 지수·1배·2배·3배 구성",
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(20,24,35,1)",
        font=dict(family="Malgun Gothic, sans-serif", size=12),
        legend=dict(font=dict(size=10)),
        margin=dict(l=40, r=10, t=60, b=40), height=520, hovermode="x unified")
    return fig


def _period_label(columns: list[str] | None = None, start: str | None = None) -> str:
    """차트에 실제로 표시되는 데이터의 시작·종료 기간."""
    df = _chart_data()
    if columns is not None:
        df = df[[col for col in columns if col in df.columns]]
    if start is not None:
        df = df.loc[df.index >= start]
    valid = df.dropna(how="all")
    if valid.empty:
        return "기간: 데이터 없음"
    return f"기간: {valid.index.min():%Y-%m} ~ {valid.index.max():%Y-%m}"


def _partial_month_caption() -> None:
    if _chart_data().attrs.get("partial_month_adjusted"):
        st.caption("※ 마지막 달은 아직 끝나지 않은 진행 중 월입니다. 월말 확정 수익률이 아니며 오늘까지의 값입니다.")


def _full_doc() -> bytes:
    body = EXPLAIN + PRODUCTS_HTML + SUMMARY_HTML
    html = ("<!DOCTYPE html><html lang='ko'><head><meta charset='UTF-8'>"
            "<title>미국 지수 & 레버리지 상품 총정리</title></head>"
            "<body style='background:#0e1420;margin:0;padding:24px'>"
            f"<div style='max-width:900px;margin:0 auto'>{body}</div></body></html>")
    return html.encode("utf-8")


def _fig_perf_risk():
    """상장 후 CAGR(막대) vs 역대 MDD(빨간선) — 실측."""
    names = ["SPY\n(S&P 1x)", "QQQ\n(나100 1x)", "QLD\n(2x)", "UDOW\n(다우3x)",
             "UPRO\n(S&P 3x)", "SOXL\n(반도체3x)", "TQQQ\n(나100 3x)"]
    cagrs = [10.8, 10.9, 25.5, 26.5, 33.0, 42.4, 43.4]
    mdds = [-55, -83, -83, -80, -77, -90, -82]
    colors = ["#4fc3f7", "#4fc3f7", "#ffb74d", "#ff8a65", "#ff8a65", "#d32f2f", "#d32f2f"]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=names, y=cagrs, name="상장 후 CAGR(%)", marker_color=colors,
                         text=[f"{c}%" for c in cagrs], textposition="outside"))
    fig.add_trace(go.Scatter(x=names, y=[-m for m in mdds], name="역대 최악 낙폭 |MDD|(%)",
                             mode="lines+markers+text", text=[f"{m}%" for m in mdds],
                             textposition="top center", line=dict(color="#ff6e6e", dash="dot")))
    fig.update_layout(title="배수가 오를수록: 수익(막대)도 커지지만 낙폭(빨간선)은 -80~90%대로 수렴",
                      template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(20,24,35,1)", height=400,
                      font=dict(family="Malgun Gothic, sans-serif", size=12),
                      margin=dict(l=40, r=20, t=60, b=40))
    return fig


@st.dialog("📊 미국 지수 & 레버리지 상품 총정리", width="large")
def _dlg_indices():
    st.plotly_chart(_fig_perf_risk(), width="stretch")
    st.caption("👆 핵심 한 장: 3배 상품(TQQQ·SOXL)은 CAGR 40%대지만 **역대 낙폭 -82~-90%** — "
               "수익은 배수를 따라가고, 위험은 그보다 먼저 한계치에 도달합니다.")
    st.html(EXPLAIN)
    st.html(PRODUCTS_HTML)
    st.markdown("### 📈 누적 수익률 차트 (상장 시점부터)")
    st.markdown(f"**{_period_label()}**")
    _partial_month_caption()
    st.caption("각 상품을 상장 시점 100으로 맞춘 로그스케일 누적수익. 범례를 클릭하면 켜고 끌 수 있습니다. "
               "회색 점선=원지수, 파랑=1배, 주황=2배, 빨강=3배.")
    st.plotly_chart(_fig(), width="stretch")
    st.info(
        "**1번 차트는 무엇인가요?** 각 지수와 ETF가 실제 데이터에 처음 등장한 날을 각각 100으로 놓고, "
        "상장 후 얼마나 늘거나 줄었는지 보여줍니다.\n\n"
        "**읽는 방법:** 100→500은 5배(+400%), 100→50은 반 토막(-50%)입니다. "
        "회색 점선은 원지수, 파랑은 1배, 주황은 2배, 빨강은 3배입니다. 세로축은 로그라서 "
        "100→200과 1,000→2,000이 같은 높이로 보입니다.\n\n"
        "**주의:** 상품마다 시작일이 달라 최종 높이만으로 누가 더 우수한지 단순 비교하면 안 됩니다. "
        "이 차트는 각 상품의 '실제 생존 기간 전체'와 장기 낙폭·회복 모습을 확인하는 용도입니다."
    )
    st.markdown("### 📈 누적 수익률 차트 (1990년대부터)")
    st.markdown(f"**{_period_label(start='1995-01-01')}**")
    _partial_month_caption()
    st.caption("1번과 동일한 원지수·1배·2배·3배 상품 전체 구성입니다. 각 시계열은 1995년 이후 "
               "첫 유효값을 100으로 맞췄으며, 1995년 이후 상장한 ETF는 실제 상장 시점부터 표시됩니다. "
               "회색 점선=원지수, 파랑=1배, 주황=2배, 빨강=3배.")
    st.plotly_chart(_fig_since_1990s(), width="stretch")
    st.info(
        "**2번 차트는 무엇인가요?** 1995년 이후 구간만 잘라 1번과 똑같은 18개 시계열을 보여줍니다. "
        "원지수는 1995년 첫 값을 100으로, 이후 상장한 ETF는 실제 상장 후 첫 값을 100으로 놓습니다.\n\n"
        "**읽는 방법:** 닷컴 버블, 금융위기, 코로나, 2022년 긴축 같은 위기에서 선이 얼마나 깊게 "
        "떨어지고 얼마나 오래 회복하지 못했는지 보세요. 빨간 3배선은 상승장에서 빠르지만 하락장에서 "
        "훨씬 깊게 무너지는 구조를 확인하는 데 유용합니다.\n\n"
        "**주의:** 상장 전 ETF 수익을 가상으로 만들지 않았기 때문에 ETF별 출발일은 여전히 다릅니다. "
        "같은 기간의 공정한 수익률 순위라기보다, 1995년 이후 시장 환경 속에서 실제 상품이 존재한 "
        "구간을 함께 살펴보는 차트입니다."
    )
    st.html(SUMMARY_HTML)
    st.success("✅ **최종 결론** — ① 1배 수익 서열: 반도체 > 나스닥100 > S&P500·나스닥종합 > 다우·러셀 (장기 일관). "
               "② 3배는 '상승장 전용 부스터'일 뿐 — TQQQ 371배의 이면은 -82%, SOXL 320배의 이면은 **-90.5%**. "
               "③ 추천 사고방식: **몇 배짜리를 살까**가 아니라 **-80%를 감당할 금액이 얼마인가**부터 정하고, "
               "그 금액만 2~3배에, 나머지는 1배(QQQ·SPY)에. ④ 모든 배수 상품은 감쇠 때문에 '지수 회복=내 회복'이 아님을 기억하세요.")
    st.download_button("📥 이 문서를 HTML로 저장 (새 탭에서 열기·공유·인쇄)", _full_doc(),
                       "us_indices_leverage.html", "text/html", width="stretch")


def render_indices_button(container=None):
    """사이드바 등에 버튼 배치 — 누르면 팝업."""
    tgt = container or st
    if tgt.button("📊 미국 지수·레버리지 총정리 (차트)", width="stretch", key="btn_indices_ref"):
        _dlg_indices()
