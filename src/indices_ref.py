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
    return pd.read_csv(_DATA, index_col=0, parse_dates=True)


def _fig() -> go.Figure:
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
        title="상장 시점부터 누적 수익률 (각 상품 시작=100, 로그)",
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(20,24,35,1)",
        font=dict(family="Malgun Gothic, sans-serif", size=12),
        legend=dict(font=dict(size=10)), margin=dict(l=40, r=10, t=50, b=40), height=520,
        hovermode="x unified")
    return fig


def _full_doc() -> bytes:
    body = EXPLAIN + PRODUCTS_HTML + SUMMARY_HTML
    html = ("<!DOCTYPE html><html lang='ko'><head><meta charset='UTF-8'>"
            "<title>미국 지수 & 레버리지 상품 총정리</title></head>"
            "<body style='background:#0e1420;margin:0;padding:24px'>"
            f"<div style='max-width:900px;margin:0 auto'>{body}</div></body></html>")
    return html.encode("utf-8")


@st.dialog("📊 미국 지수 & 레버리지 상품 총정리", width="large")
def _dlg_indices():
    st.html(EXPLAIN)
    st.html(PRODUCTS_HTML)
    st.markdown("### 📈 누적 수익률 차트 (상장 시점부터)")
    st.caption("각 상품을 상장 시점 100으로 맞춘 로그스케일 누적수익. 범례를 클릭하면 켜고 끌 수 있습니다. "
               "회색 점선=원지수, 파랑=1배, 주황=2배, 빨강=3배.")
    st.plotly_chart(_fig(), use_container_width=True)
    st.html(SUMMARY_HTML)
    st.download_button("📥 이 문서를 HTML로 저장 (새 탭에서 열기·공유·인쇄)", _full_doc(),
                       "us_indices_leverage.html", "text/html", use_container_width=True)


def render_indices_button(container=None):
    """사이드바 등에 버튼 배치 — 누르면 팝업."""
    tgt = container or st
    if tgt.button("📊 미국 지수·레버리지 총정리 (차트)", use_container_width=True, key="btn_indices_ref"):
        _dlg_indices()
