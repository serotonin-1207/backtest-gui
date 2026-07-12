# -*- coding: utf-8 -*-
"""중국·홍콩 주요 지수/ETF/종목 총정리 — 팝업(모달) + 대표 지수 누적수익 차트.

각 지수·ETF·대표 종목이 무엇인지 소개하고, 홍콩·본토 시장 구분과 투자 시 주의점(규제·세금·
상장폐지 리스크)을 정리한다. 차트는 앱의 실측 로더(get_price)로 대표 지수 4종을 즉석 정규화한다.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

_CSS = """
<style>
.cr { font-family:"Malgun Gothic",sans-serif; line-height:1.7; color:#e8eaf0; }
.cr h2 { color:#ef5350; border-left:5px solid #ef5350; padding-left:10px; margin-top:24px; }
.cr table { border-collapse:collapse; width:100%; margin:10px 0; font-size:13px; }
.cr th { background:#4a1f22; padding:7px; border:1px solid #55292c; text-align:left; }
.cr td { padding:7px; border:1px solid #55292c; }
.cr tr:nth-child(even) td { background:#2a1618; }
.cr .warn { background:#3a2418; border-left:5px solid #ff7043; padding:10px 14px; border-radius:8px; margin:12px 0; }
.cr .tip { background:#16301f; border-left:5px solid #66bb6a; padding:10px 14px; border-radius:8px; margin:12px 0; }
.cr .neg{color:#ff8a80;font-weight:bold} .cr .pos{color:#a5d6a7;font-weight:bold}
</style>
"""

# ---------------- 홍콩 지수
HK_INDEX_HTML = _CSS + """
<div class="cr">
<h2>🇭🇰 홍콩 주요 지수</h2>
<table>
<tr><th>지수</th><th>구성</th><th>성격</th></tr>
<tr><td><b>항셍지수 (HSI)</b></td><td>홍콩 상장 대형주 80여 종목</td>
<td>홍콩 증시 대표 벤치마크(‘홍콩의 코스피’). 텐센트·HSBC·알리바바·메이투안·AIA 등.</td></tr>
<tr><td><b>항셍 중국기업 (HSCEI, H주)</b></td><td>홍콩 상장 <b>중국 본토기업</b> 대표주</td>
<td>국유은행·보험·에너지 비중이 큼. ‘H주’ 지수. 본토 경기·정책에 민감.</td></tr>
<tr><td><b>항셍테크 (HSTECH)</b></td><td>홍콩 상장 중국 기술주 30종</td>
<td>텐센트·알리바바·메이투안·샤오미·JD 등 ‘중국판 나스닥’. 규제·성장 테마에 크게 출렁.</td></tr>
</table>
<p style="font-size:12px;color:#c9a2a2">※ 항셍테크는 원지수 히스토리가 데이터 제공사에 없어, 앱에는 이를 추종하는
ETF <b>3033.HK</b>(항셍테크 ETF)로 담았습니다.</p>
</div>
"""

# ---------------- 중국 본토 지수
CN_INDEX_HTML = _CSS + """
<div class="cr">
<h2>🇨🇳 중국 본토 주요 지수</h2>
<table>
<tr><th>지수</th><th>거래소/구성</th><th>성격</th></tr>
<tr><td><b>상하이종합 (SSE Composite)</b></td><td>상하이거래소 전 종목</td>
<td>대형 국유기업·금융 비중 큼. 본토 시장 대표 심리 지표.</td></tr>
<tr><td><b>선전성분 (SZSE Component)</b></td><td>선전거래소 대표 종목</td>
<td>기술·성장·제조 비중이 높아 상하이보다 변동성 큼.</td></tr>
<tr><td><b>CSI300 (후선300)</b></td><td>상하이+선전 우량주 300</td>
<td>본토 A주 대표 벤치마크(‘본토의 S&P500’). 앱에는 ETF <b>ASHR</b>로 담음.</td></tr>
<tr><td>창업판 (ChiNext)</td><td>선전의 성장·벤처 보드</td>
<td>‘중국판 코스닥’. 신성장·중소형 성장주.</td></tr>
<tr><td>과창판 (STAR Market)</td><td>상하이의 첨단기술 보드</td>
<td>반도체·바이오·AI 등 하드테크 중심. 신생·고변동.</td></tr>
</table>
<div class="tip"><b>A주·H주·ADR이 뭔가요?</b> 같은 중국 기업이라도 상장 시장이 다릅니다.
<b>A주</b>=본토(상하이·선전, 위안), <b>H주</b>=홍콩(홍콩달러), <b>ADR</b>=미국(달러) 상장.
접근성·환율·규제·세금이 달라, 같은 회사라도 가격·수익률이 갈립니다.</div>
</div>
"""

# ---------------- 대표 ETF
ETF_HTML = _CSS + """
<div class="cr">
<h2>📦 중국·홍콩 대표 ETF (국내외 매매 접근용)</h2>
<table>
<tr><th>ETF</th><th>추종</th><th>특징</th></tr>
<tr><td><b>FXI</b></td><td>중국 대형주(주로 홍콩상장)</td><td>가장 오래된 대표 중국 ETF(2004~).</td></tr>
<tr><td><b>MCHI</b></td><td>MSCI 중국(홍콩+ADR 광범위)</td><td>중국 전반을 폭넓게 담음.</td></tr>
<tr><td><b>KWEB</b></td><td>중국 인터넷·플랫폼</td><td>텐센트·알리바바·핀둬둬·메이투안 등. <b>규제에 매우 민감</b>.</td></tr>
<tr><td><b>ASHR</b></td><td>본토 A주 CSI300</td><td>위안 표시 본토 우량주에 직접 노출.</td></tr>
<tr><td><b>CQQQ</b></td><td>중국 기술주</td><td>기술 섹터 집중.</td></tr>
<tr><td class="neg"><b>YINN</b></td><td>FTSE차이나 <b>3배</b></td><td>초고위험 레버리지. 폭락 시 -90%급.</td></tr>
<tr><td class="neg"><b>CWEB</b></td><td>중국 인터넷 <b>2배</b></td><td>KWEB의 2배 레버리지. 고위험.</td></tr>
</table>
</div>
"""

# ---------------- 중국·홍콩판 레버리지 (미국 상품 대응)
LEVERAGE_HTML = _CSS + """
<div class="cr">
<h2>🚀 중국·홍콩판 QQQ·QLD·TQQQ / SOXX (레버리지 대응)</h2>
<p>미국의 나스닥·반도체 1·2·3배 상품에 대응하는 홍콩·중국 상품을 정리했습니다.
배수가 클수록 <b>수익도 손실도 배수만큼</b> 커지고, 일간 재설정·변동성 감쇠로 장기 성과는
지수의 정확한 배수가 아닙니다.</p>
<h3 style="color:#ff8a80">① 나스닥형(기술주) 사다리</h3>
<table>
<tr><th>미국</th><th>배수</th><th>중국·홍콩 대응</th><th>티커</th><th>비고</th></tr>
<tr><td>QQQ</td><td>1배</td><td><b>항셍테크</b>(중국판 나스닥)·중국 인터넷·기술</td>
<td><b>3033.HK</b> · KWEB · CQQQ</td><td class="pos">앱에 있음</td></tr>
<tr><td>QLD</td><td>2배</td><td>항셍테크 2배 / 차이나인터넷 2배</td>
<td><b>7226.HK</b>(홍콩) · CWEB(미국)</td><td class="pos">앱에 있음</td></tr>
<tr><td class="neg">TQQQ</td><td>3배</td><td><b>순수 3배 중국 기술주는 없음</b> → 가장 가까운 3배</td>
<td>YINN(중국 대형주 3배)</td><td class="pos">앱에 있음(대형주 기준)</td></tr>
</table>
<h3 style="color:#ffb74d">② 광의 지수 2배</h3>
<table>
<tr><th>지수</th><th>1배</th><th>2배</th></tr>
<tr><td>항셍지수(HSI)</td><td>항셍 ETF / ^HSI</td><td><b>7200.HK</b>(2배 롱)</td></tr>
<tr><td>CSI300 (본토 A주)</td><td>ASHR</td><td><b>CHAU</b>(A주 2배)</td></tr>
</table>
<h3 style="color:#4fc3f7">③ 반도체 사다리 (SOXX·USD·SOXL 대응)</h3>
<table>
<tr><th>미국</th><th>배수</th><th>중국 대응</th><th>티커</th></tr>
<tr><td>SOXX/SMH</td><td>1배</td><td>중국 반도체 ETF</td><td><b>3191.HK</b> · 512760.SS · 159995.SZ(본토)</td></tr>
<tr><td>USD</td><td>2배</td><td class="neg">중국 반도체 2배 ETF 없음</td><td>—</td></tr>
<tr><td class="neg">SOXL</td><td>3배</td><td class="neg">중국 반도체 3배 ETF 없음</td><td>—</td></tr>
<tr><td>(개별 대장주)</td><td>—</td><td>SMIC(‘중국의 TSMC’) · 화훙반도체</td><td>0981.HK·688981.SS · 1347.HK</td></tr>
</table>
<div class="warn"><b>⚠️ 꼭 알아두기</b><br>
· <b>순수 3배 중국 기술주·중국 반도체 레버리지 ETF는 존재하지 않습니다.</b> 3배는 YINN(대형주 전체)뿐입니다.<br>
· 홍콩 <b>7xxx.HK</b> 상품은 ‘롱/인버스’ 쌍입니다. 실측 확인: <b>7226.HK=항셍테크 2배 롱</b>,
7552.HK=2배 인버스(숏). <b>7200.HK=항셍 2배 롱</b>. 매매 전 방향을 꼭 확인하세요.<br>
· 레버리지·인버스는 장기 보유 시 변동성 감쇠로 원지수와 크게 벌어질 수 있습니다.</div>
<div class="tip"><b>🛠 앱에서 쓰는 법</b> — <b>7226.HK</b>는 사이드바 <b>자산 선택</b>에 이미 있습니다.
목록에 없는 것(7200.HK·CHAU·YANG·3191.HK·0981.HK·1347.HK 등)은 사이드바
<b>‘사용자 티커 추가’</b>에 티커를 그대로 입력하면 됩니다(홍콩 <code>.HK</code>, 상하이 <code>.SS</code>,
선전 <code>.SZ</code> 자동 인식).</div>
</div>
"""

# ---------------- 대표 종목
STOCK_HTML = _CSS + """
<div class="cr">
<h2>🏢 홍콩·중국 대표 종목</h2>
<table>
<tr><th>종목</th><th>티커(앱)</th><th>사업</th></tr>
<tr><td><b>텐센트</b></td><td>0700.HK</td><td>위챗·게임·핀테크·클라우드. 홍콩 대장주.</td></tr>
<tr><td><b>알리바바</b></td><td>9988.HK / BABA</td><td>전자상거래·클라우드. 홍콩·미국 동시 상장.</td></tr>
<tr><td><b>메이투안</b></td><td>3690.HK</td><td>음식배달·로컬 서비스 플랫폼.</td></tr>
<tr><td><b>BYD</b></td><td>1211.HK</td><td>전기차·배터리. 중국 EV 대표.</td></tr>
<tr><td><b>샤오미</b></td><td>1810.HK</td><td>스마트폰·IoT·전기차(SU7).</td></tr>
<tr><td><b>핀둬둬(PDD)</b></td><td>PDD</td><td>이커머스(해외 ‘테무’ 모회사).</td></tr>
<tr><td><b>니오(NIO)</b></td><td>NIO</td><td>프리미엄 전기차.</td></tr>
<tr><td><b>바이두(BIDU)</b></td><td>BIDU</td><td>검색·AI·자율주행.</td></tr>
</table>
</div>
"""

# ---------------- 주의사항
CAUTION_HTML = _CSS + """
<div class="cr">
<h2>⚠️ 투자 전 꼭 아는 위험</h2>
<div class="warn">
<b>① 규제 리스크</b> — 2021년 빅테크·사교육·게임 규제로 중국 인터넷주가 반토막 났습니다.
정책 한 줄에 업종 전체가 급변할 수 있습니다.<br>
<b>② 미·중 갈등·상장폐지</b> — 미국 상장 중국 ADR은 회계·안보 이슈로 상장폐지·거래제한 위험이 있습니다.<br>
<b>③ 시장 구조</b> — 본토 A주는 외국인 접근이 제한적이고(후강퉁 등), VIE 지배구조 등 특유의 리스크가 있습니다.<br>
<b>④ 환율</b> — 홍콩달러(HKD)는 미국달러에 사실상 고정(페그), 위안(CNY)은 당국 관리변동입니다.
</div>
<div class="tip">
<b>💰 세금(한국 투자자)</b> — 홍콩·중국 <b>주식·ETF</b>는 미국과 동일한 <b>해외주식 양도소득세</b>
(연 250만원 공제 후 <b>22%</b>) 대상입니다. 지수 자체는 직접 매매 상품이 아니라 비과세 표시됩니다.
앱의 ‘세금’ 옵션을 켜면 반영됩니다.
</div>
<div class="tip">
<b>📈 직접 비교하려면</b> — 왼쪽 사이드바 <b>자산 선택</b>에서 항셍지수·상하이종합·텐센트·BYD 등
원하는 홍콩·중국 자산을 골라 백테스트하면, 거치식·적립식·라오어로 실제 수익·낙폭을 비교할 수 있습니다.
</div>
</div>
"""

_CORE_INDICES = [
    ("항셍지수", "^HSI", "HKD"),
    ("항셍 중국기업(H주)", "^HSCE", "HKD"),
    ("상하이종합", "000001.SS", "CNY"),
    ("선전성분", "399001.SZ", "CNY"),
]


def _core_index_chart():
    """대표 지수 4종을 공통 시작일=100으로 정규화한 누적수익 차트(실측)."""
    from .data_loader import get_price

    series = {}
    for name, ticker, cur in _CORE_INDICES:
        try:
            df = get_price(ticker, "yahoo", cur)
            s = df["Close"].astype(float).dropna()
            if len(s) > 10:
                series[name] = s
        except Exception:
            continue
    if len(series) < 2:
        return None
    common_start = max(s.index.min() for s in series.values())
    fig = go.Figure()
    palette = {"항셍지수": "#ef5350", "항셍 중국기업(H주)": "#ffb74d",
               "상하이종합": "#4fc3f7", "선전성분": "#66bb6a"}
    for name, s in series.items():
        s = s.loc[s.index >= common_start]
        if s.empty or s.iloc[0] == 0:
            continue
        norm = s / s.iloc[0] * 100.0
        fig.add_trace(go.Scatter(x=norm.index, y=norm.values, name=name,
                                 line=dict(color=palette.get(name), width=1.7)))
    fig.update_yaxes(type="log", title="누적 (공통 시작일=100, 로그스케일)")
    fig.update_layout(
        title=f"홍콩·중국 대표 지수 누적수익 (공통 시작 {common_start:%Y-%m} = 100)",
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(20,24,35,1)",
        font=dict(family="Malgun Gothic, sans-serif", size=12),
        legend=dict(font=dict(size=11)), margin=dict(l=40, r=10, t=50, b=40),
        height=460, hovermode="x unified")
    return fig


def _full_doc() -> bytes:
    body = (HK_INDEX_HTML + CN_INDEX_HTML + LEVERAGE_HTML + ETF_HTML
            + STOCK_HTML + CAUTION_HTML)
    html = ("<!DOCTYPE html><html lang='ko'><head><meta charset='UTF-8'>"
            "<title>중국·홍콩 지수 총정리</title></head>"
            "<body style='background:#0e1420;margin:0;padding:24px'>"
            f"<div style='max-width:900px;margin:0 auto'>{body}</div></body></html>")
    return html.encode("utf-8")


@st.dialog("🇨🇳🇭🇰 중국·홍콩 지수 총정리", width="large")
def _dlg_china():
    st.caption("홍콩·중국의 주요 지수·ETF·대표 종목을 소개합니다. 데이터: 공개 시장 데이터(yfinance).")
    st.html(HK_INDEX_HTML)
    st.html(CN_INDEX_HTML)
    st.markdown("### 📈 대표 지수 누적수익 (실측)")
    with st.spinner("홍콩·중국 대표 지수 데이터를 불러오는 중…"):
        fig = _core_index_chart()
    if fig is not None:
        st.plotly_chart(fig, width="stretch")
        st.caption("항셍·항셍 중국기업(H주)·상하이종합·선전성분을 공통 시작일 100으로 맞춘 로그스케일 "
                   "누적수익입니다. 배당 미포함 가격지수이며, 범례를 클릭해 켜고 끌 수 있습니다.")
    else:
        st.info("실시간 지수 데이터를 불러오지 못했습니다. 사이드바 **자산 선택**에서 직접 골라 백테스트해 보세요.")
    st.html(LEVERAGE_HTML)
    st.html(ETF_HTML)
    st.html(STOCK_HTML)
    st.html(CAUTION_HTML)
    st.success("✅ **핵심** — ① 홍콩(HSI)·본토(상하이·선전)·H주(HSCEI)는 서로 다른 시장입니다. "
               "② 인터넷·기술주는 규제 한 줄에 크게 흔들립니다. ③ 홍콩·중국 주식은 해외주식 양도세(22%) 대상입니다. "
               "④ 실제 수익·낙폭 비교는 사이드바 자산 선택에서 백테스트하세요.")
    st.download_button("📥 이 문서를 HTML로 저장 (새 탭에서 열기·공유·인쇄)", _full_doc(),
                       "china_hk_indices.html", "text/html", width="stretch")


def render_china_button(container=None):
    """참고 자료 바 등에 버튼 배치 — 누르면 팝업."""
    tgt = container or st
    if tgt.button("🇨🇳🇭🇰 중국·홍콩 지수 총정리 (차트)", width="stretch", key="btn_china_ref"):
        _dlg_china()
