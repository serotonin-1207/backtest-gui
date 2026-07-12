# -*- coding: utf-8 -*-
"""Streamlit GUI — 사이드바 설정 + KPI 카드 + 결과표 + Plotly 차트 (다크 모드 기본)."""
from __future__ import annotations

import traceback
from copy import copy
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from .ai_report import build_ai_report, save_ai_report
from .backtest_engine import run_backtest
from .charts import (fig_annual_returns, fig_cash_ratio, fig_drawdown,
                     fig_equity, fig_final_values, fig_monthly_heatmap, fig_t_series)
from .currency import (CURRENCY_LABELS, SUPPORTED, convert, cross_rate, get_fx_series,
                       get_rates, korean_money)
from .data_loader import (ASSET_PRESETS, INDEX_DIV_YIELD, PRICE_INDEX_TICKERS, SYNTH_BASE,
                          TOTAL_RETURN_TICKERS,
                          cache_status, clear_cache, get_price, route_ticker, tax_category)
from .excel_export import build_excel
from .interpret import interpret_results
from .laoer_strategy import run_laoer
from .metrics import summarize, twr_index, xirr
from .synthetic_etf import apply_dividend_addback, extend_with_synthetic
from .tax_engine import apply_annual_tax_drag, compute_tax, tax_schedule_asset
from .validation import validate_intraday_ohlc, validate_synthetic

OUT_DIR = Path(__file__).resolve().parent.parent / "output" / "reports"

# 배포 버전 — 변경 사항을 올릴 때마다 갱신. 화면에 표시되어 "최신 반영 여부"를 눈으로 확인할 수 있음.
APP_VERSION = "1.11.1 (2026-07-12) — 항셍테크 2배(7226) 추가, 사용자 티커 국가칸 숨김(자동판별 안내), 중국·홍콩 총정리에 레버리지(중국판 QQQ/QLD/TQQQ·SOXX) 섹션"

MONEY_COLS = ["총투입금", "추가불입", "중도인출", "순투입금", "최종순자산", "총이자",
              "세금", "세후최종순자산", "매매비용"]

# 주요 지수 실측 폭락 낙폭 비교 — 시작/종료일 선택 참고용 (고점→저점 낙폭 %)
_CRASH_EVENTS = ["닷컴버블\n2000-03~2002-10", "금융위기\n2007-10~2009-03",
                 "코로나\n2020-02~2020-03", "2022 긴축\n2021-11~2022-12",
                 "트럼프 관세\n2025-02~2025-04"]
_CRASH_DATA = {   # 지수: [닷컴, 금융위기, 코로나, 긴축, 관세] 낙폭 %
    "S&P500": [-49, -57, -34, -25, -19], "나스닥100(QQQ)": [-83, -54, -28, -36, -23],
    "나스닥종합": [-78, -56, -30, -36, -24], "다우존스": [-38, -54, -37, -22, -16],
    "반도체(SOX)": [-84, -69, -35, -46, -35], "코스피": [-56, -55, -36, -34, -14],
}
# 사건별 시장 고점일(시작일 버튼용) — '최고점부터 현재까지'
_CRASH_PEAKS = {
    "닷컴버블": date(2000, 3, 24), "금융위기(리먼)": date(2007, 10, 9),
    "코로나19": date(2020, 2, 19), "2022 긴축": date(2021, 11, 19),
    "트럼프 관세": date(2025, 2, 19),
}
_CRASH_REF_MD = """
**지수별 최대 낙폭 — 사건 · 기간(연도) 기준**

| 사건 (고점 → 저점 기간) | S&P500 | 나스닥100 | 나스닥종합 | 다우 | 반도체 | 코스피 |
|---|---|---|---|---|---|---|
| 닷컴버블 **2000-03 → 2002-10** | -49% | **-83%** | -78% | -38% | **-84%** | -56% |
| 금융위기 **2007-10 → 2009-03** | -57% | -54% | -56% | -54% | -69% | -55% |
| 코로나 **2020-02 → 2020-03** | -34% | -28% | -30% | -37% | -35% | -36% |
| 2022 긴축 **2021-11 → 2022-12** | -25% | -36% | -36% | -22% | -46% | -34% |
| 트럼프 관세 **2025-02 → 2025-04** | -19% | -23% | -24% | -16% | **-35%** | -14% |

**전고점 회복까지 걸린 시간 (연도)**

| 사건 | 저점 시점 | 회복 시점 | 소요 |
|---|---|---|---|
| 닷컴버블 | 2002-10 | S&P 2007 · 나스닥100 **2015** | 5~**13년** |
| 금융위기 | 2009-03 | 2011~2013 | 2~4년 |
| 코로나 | 2020-03 | 2020-06~11 | **3~9개월** |
| 2022 긴축 | 2022-10/12 | 2023-12~2024 (코스피 2025) | 1~3년 |
| 트럼프 관세 | 2025-04 | 2025-05~07 | **1~4개월** (매우 빠름) |
"""


def _fig_crash_bars():
    """사건별 지수 낙폭 그룹 막대 차트."""
    import plotly.graph_objects as go
    from .charts import PALETTE
    fig = go.Figure()
    for i, (idx_name, drops) in enumerate(_CRASH_DATA.items()):
        fig.add_trace(go.Bar(x=_CRASH_EVENTS, y=drops, name=idx_name,
                             marker_color=PALETTE[i % len(PALETTE)],
                             text=[f"{d}%" for d in drops], textposition="outside"))
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(20,24,35,1)", barmode="group", height=430,
                      font=dict(family="Malgun Gothic, sans-serif", size=12),
                      title="폭락 사건별 지수 낙폭 비교 (아래로 깊을수록 심한 하락)",
                      legend=dict(orientation="h", y=1.08), margin=dict(l=40, r=20, t=80, b=60))
    fig.update_yaxes(title="고점 대비 낙폭 (%)")
    return fig


def _fmt_rate(x: float) -> str:
    """환율 표시: 1 이상은 소수 2자리, 1 미만은 유효숫자 유지 (1 KRW = 0.000663 USD)."""
    return f"{x:,.2f}" if x >= 1 else f"{x:.6f}"


@st.dialog("📉 주요 지수 폭락 구간 (참고)", width="large")
def _dlg_crash():
    st.caption("백테스트 시작/종료일 잡을 때 참고하세요. 실측 기준이며 지수마다 고점·저점 날짜는 조금씩 다릅니다.")
    st.plotly_chart(_fig_crash_bars(), width="stretch")
    st.markdown(_CRASH_REF_MD)
    st.success("✅ **최종 결론** — ① 폭락은 10년에 2~4번 반드시 옵니다(회피 불가). "
               "② 같은 사건이라도 지수별 낙폭이 크게 다릅니다(닷컴: 다우 -38% vs 나스닥100 -83%). "
               "③ 회복은 3개월(코로나)~13년(닷컴)까지 제각각 — **'몇 년 물릴 수 있는가'를 기준으로 투자 규모를 정하세요.** "
               "④ 백테스트할 땐 시작일을 고점 직전(예: 2021-11)으로 놓고 최악을 확인해 보는 것이 정직한 검증입니다.")


@st.dialog("❓ 도움말 · 옵션 설명", width="large")
def _dlg_help():
    q = st.text_input("🔍 검색 (예: 라오어, 세금)", "", key="help_search")
    for k, v in HELP.items():
        if q.strip() and (q not in k and q not in v):
            continue
        st.markdown(f"**{k}** — {v}")


@st.dialog("📚 용어 사전", width="large")
def _dlg_glossary():
    q = st.text_input("🔍 검색 (예: MDD, 칼마)", "", key="glossary_search")
    for k, v in GLOSSARY.items():
        if q.strip() and (q.upper() not in k.upper() and q not in v):
            continue
        st.markdown(f"**{k}**  \n{v}")


def _render_reference_bar():
    """메인 화면 상단(투자 전 필독 아래) 참고 자료 버튼 모음 — 누르면 팝업."""
    from .indices_ref import render_indices_button
    from .china_ref import render_china_button
    with st.container(border=True):
        st.markdown("#### 📖 참고 자료")
        c1, c2 = st.columns(2)
        if c1.button("📉 주요 지수 폭락 구간 (참고)", width="stretch", key="btn_ref_crash"):
            _dlg_crash()
        render_indices_button(c2)
        c3, c4 = st.columns(2)
        render_china_button(c3)
        if c4.button("❓ 도움말 · 옵션 설명", width="stretch", key="btn_ref_help"):
            _dlg_help()
        c5, _c6 = st.columns(2)
        if c5.button("📚 용어 사전", width="stretch", key="btn_ref_glossary"):
            _dlg_glossary()


def _add_custom_ticker():
    """➕추가 콜백 — 티커 존재 검증 후 목록에 담고 입력칸 비움."""
    raw = (st.session_state.get("new_ticker_input") or "").strip()
    if not raw:
        return
    ov = {"자동": None, "한국(kr)": "kr", "미국(us)": "us"}[st.session_state.get("new_ticker_ov", "자동")]
    src, cur = route_ticker(raw, ov)
    tk = raw.upper() if src == "yahoo" else raw
    try:
        df = get_price(tk, src, cur)
        ok = df is not None and not df.empty
    except Exception:
        ok = False
    if not ok:
        st.session_state.ticker_msg = ("error", f"'{raw}' — 존재하지 않거나 데이터를 찾을 수 없는 티커입니다.")
        return
    if any(t["ticker"] == tk for t in st.session_state.custom_tickers):
        st.session_state.ticker_msg = ("warn", f"{tk} 은(는) 이미 추가되어 있습니다.")
    else:
        st.session_state.custom_tickers.append({"name": tk, "ticker": tk, "source": src, "currency": cur})
        st.session_state.ticker_msg = ("ok", f"✅ {tk} 추가됨 ({cur})")
    st.session_state.new_ticker_input = ""      # 입력칸 초기화


def _remove_custom_ticker(i: int):
    if 0 <= i < len(st.session_state.custom_tickers):
        st.session_state.custom_tickers.pop(i)


def _bt_set_years(n: int):
    """빠른 기간 버튼 — 현재 기준 n년 전 ~ 오늘."""
    t = date.today()
    try:
        s = t.replace(year=t.year - n)
    except ValueError:          # 2/29 등
        s = t.replace(year=t.year - n, day=28)
    st.session_state.bt_start_date = s
    st.session_state.bt_end_date = t


def _bt_set_crash(peak: date):
    """폭락 버튼 — 시장 최고점 ~ 오늘."""
    st.session_state.bt_start_date = peak
    st.session_state.bt_end_date = date.today()


@st.cache_data(ttl=3600, show_spinner=False)
def _fx_series_cached(from_cur: str, to_cur: str):
    """일별 환율 시계열 (1시간 캐시). 실패 시 None."""
    try:
        return get_fx_series(from_cur, to_cur)
    except Exception:
        return None


def _fx_on_index(from_cur: str, to_cur: str, index):
    """from→to 일별 환율을 equity 인덱스에 맞춰 ffill 정렬. 없으면 None."""
    if from_cur == to_cur:
        return None
    s = _fx_series_cached(from_cur, to_cur)
    if s is None or len(s) == 0:
        return None
    return s.reindex(index.union(s.index)).sort_index().ffill().bfill().reindex(index)


def _at(series, d) -> float:
    """series에서 날짜 d의 값(가장 가까운 과거값). NaN 방지."""
    d = pd.Timestamp(d)
    if d in series.index and pd.notna(series.loc[d]):
        return float(series.loc[d])
    # 해당 날짜가 환율 휴장일이면 미래값을 당겨 쓰지 않고 직전 관측값을 사용한다.
    pos = min(max(series.index.searchsorted(d, side="right") - 1, 0), len(series) - 1)
    v = series.iloc[pos]
    return float(v) if pd.notna(v) else float(series.dropna().iloc[-1])


def _effective_series(r, fx_on: bool, base_code: str):
    """환율효과 반영 시 기준화폐 곡선 반환. (eq_eff, cashflows_eff, flows_eff, eff_ccy, 환효과기여)."""
    eqa = r.equity.dropna()
    if fx_on and r.currency != base_code:
        fx = _fx_on_index(r.currency, base_code, eqa.index)
        if fx is not None and fx.notna().any():
            eq = eqa * fx
            cfs = [(d, a * _at(fx, d)) for d, a in r.cashflows]
            flows = {d: a * _at(fx, d) for d, a in r.flows.items()}
            # 적립·인출 효과를 제거한 동일한 TWR 기준으로 환율 기여도를 비교한다.
            aret = float(twr_index(eqa, r.flows).iloc[-1] - 1.0)
            bret = float(twr_index(eq, flows).iloc[-1] - 1.0)
            return eq, cfs, flows, base_code, bret - aret
    return eqa, list(r.cashflows), dict(r.flows), r.currency, None


def _tax_info(r, fx_rates: dict):
    """실현손익 기반 세금 계산 (자산통화 total_tax_asset)."""
    cat = getattr(r, "tax_cat", "none")
    gains = getattr(r, "realized_gains", [])
    if cat == "us_overseas":
        fxk = _fx_on_index(r.currency, "KRW", r.equity.dropna().index)
        if fxk is not None and fxk.notna().any():
            to_krw = lambda amt, dt: amt * _at(fxk, dt)
            final_fx = float(fxk.dropna().iloc[-1])
        else:
            rate = cross_rate(r.currency, "KRW", fx_rates) or 1.0
            to_krw = lambda amt, dt: amt * rate
            final_fx = rate
        info = compute_tax(gains, cat, to_krw=to_krw, asset_to_krw_final=final_fx)
        schedule_asset = {}
        for year, detail in info.get("by_year", {}).items():
            tax_krw = float(detail.get("세금", 0.0) or 0.0)
            if tax_krw <= 0:
                continue
            later = fxk.index[fxk.index.year > int(year)] if fxk is not None else []
            pay_date = later[0] if len(later) else r.equity.index[-1]
            pay_fx = _at(fxk, pay_date) if fxk is not None else final_fx
            schedule_asset[int(year)] = tax_krw / pay_fx if pay_fx else tax_krw
        info["schedule_asset"] = schedule_asset
        return info
    return compute_tax(gains, cat)

HELP = {
    "자산": "백테스트 대상. 프리셋에서 고르거나 아래 '사용자 티커'로 직접 추가 (6자리 숫자=한국, 알파벳=미국 자동 판별).",
    "시작기준": "실제 데이터일: 각 자산의 실제 데이터 시작일부터. 동일 시작일(합성): TQQQ/QLD 등 상장 이전 구간을 기초지수 일간수익률x배수로 합성해 채움 — 합성 구간은 결과에 [합성포함] 표시.",
    "투자방식": "거치식: 시작일 전액 일시 투자 / 적립식: 주기별 분할 매수 / 라오어: 무한매수법(라오어 설정에서 V2.2·V3.0 선택). "
               "기본값은 거치식+적립식 동시 비교. 여러 개 고르면 선택 자산마다 각각 계산됩니다.",
    "티커추가": "티커를 입력하고 ➕추가를 누르면 존재하는 티커인지 확인 후 목록에 담깁니다. 6자리 숫자=한국, 알파벳=미국 자동 판별. "
               "목록의 ✖로 제거. 프리셋에 없는 종목(예: AAPL, NVDA, 000660)을 넣을 때 사용.",
    "불입인출": "특정 날짜의 추가 불입·중도 인출. 금액은 '투자금 기준 화폐'로 입력하며 자산 통화로 자동 환산. "
               "반복(매월/매년) 지정 가능. 모두 현금흐름으로 기록되어 XIRR에 정확히 반영됨.",
    "대출": "옵션 A(일시 대출형): 시작일 대출 실행, 매년 이자 차감(주식 매도), 종료일 원금 상환. 순자산 = 평가액 - 대출잔액.",
    "라오어": "V2.2(안정형·40분할·단리): 매도목표 +10%, 오프셋 (10−T/2)%. "
             "V3.0(공격형·20분할·복리): 매도목표 +15%, 오프셋 (15−1.5T)%, 세트마다 수익을 1회 매수금에 반영 → 수익·낙폭 모두 커짐. "
             "전반전은 절반 평단 LOC + 절반 오프셋 LOC, 후반전은 오프셋 LOC 하나. 매일 1/4 LOC + 3/4 지정가 매도.",
    "세금비용": "세금 반영(미국 22%/국내ETF 15.4%/국내주식 비과세), 지수 총수익 보정, 환율 효과(언헤지 일별환율), 매매 수수료·슬리피지(bp). "
               "모두 기본 OFF = 세전·비용0. 켜면 세전/세후를 나란히 비교합니다.",
    "모드": "📈 가격 백테스트: 자산 가격 기준 수익 시뮬레이션. 💵 적립식 현금관리 계산기: 대기자금 RP운용·조달이자·수수료의 순효과 계산. 💬 의견 게시판: 사용자 의견·버그·개선 아이디어 수렴.",
    "기준화폐": "투자금을 어느 통화로 입력하는지. 예: KRW 선택 + 10,000 입력 = 1만원 투자. "
               "자산의 거래 통화가 다르면(예: TQQQ=달러) 현재 환율로 환산한 금액이 투입됨.",
    "표시통화": "결과표·KPI의 금액을 선택한 통화로 현재 환율 기준 단순 환산해 표시. 기본값은 투자금 기준 화폐. "
               "(일별 환율을 반영한 언헤지 시뮬레이션은 확장 예정)",
}

# ---------------------------------------------------------------- 용어 사전
GLOSSARY = {
    "총수익률": "최종 순자산 ÷ 순투입금 − 1. 넣은 돈 대비 얼마나 불었는지의 단순 수익률. 기간의 길이는 반영하지 않음.",
    "CAGR": "연평균 복리 수익률. '매년 몇 %씩 복리로 굴린 것과 같은가'. 본 프로그램은 불입·인출 효과를 제거한 시간가중(TWR) 기준으로 계산.",
    "XIRR": "실제 현금흐름(투입·인출 날짜와 금액)을 모두 반영한 연환산 수익률. 적립식·불입·인출이 있는 전략끼리 비교할 때 가장 공정한 수익성 지표.",
    "TWR(시간가중수익률)": "입출금 타이밍의 영향을 제거한 '운용 실력' 수익률. 펀드 성과 비교의 표준. XIRR(돈가중)과 달리 언제 얼마를 넣었는지는 반영하지 않음.",
    "MDD (최대낙폭)": "기간 중 고점 대비 가장 크게 하락한 비율. -50%면 계좌가 반토막 났던 순간이 있었다는 뜻. 심리적으로 버틸 수 있는지의 핵심 지표.",
    "최장 무회복 기간": "전고점을 회복하지 못한 채 보낸 가장 긴 기간(일수). 길수록 '물려 있던' 기간이 길었다는 의미.",
    "언더워터 플롯": "고점 대비 낙폭(%)을 시간축으로 그린 차트. 0이면 신고가, 아래로 내려갈수록 하락 상태. 낙폭의 깊이와 회복까지 걸린 시간을 한눈에 봄.",
    "연율 변동성": "일간 수익률의 표준편차를 연 단위로 환산한 값. 클수록 가격 출렁임이 심함 (예: 지수 15~20%, 3배 레버리지 60%+).",
    "샤프 지수": "변동성 1단위당 초과수익. 높을수록 '흔들림 대비 수익'이 좋음. 1 이상이면 양호.",
    "소르티노 지수": "샤프와 비슷하지만 하락 변동성만 위험으로 간주. 상승 출렁임은 벌점을 주지 않아 공격적 전략 평가에 적합.",
    "칼마 지수": "CAGR ÷ |MDD|. '최악의 낙폭을 감수한 대가로 얻은 연수익'. 1 이상이면 우수. 장기 투자자에게 특히 유용.",
    "원금 대비 배수": "최종 순자산 ÷ 순투입금. 10배면 넣은 돈이 10배가 됐다는 뜻.",
    "순투입금": "총투입금(원금+추가불입) − 중도인출. 실제로 내 주머니에서 나간 순액.",
    "로그 스케일": "차트 세로축을 배수 기준으로 표시(100→200과 1,000→2,000이 같은 높이). 장기 복리 성장 비교에 필수 — 선형축은 최근 구간만 커 보이는 착시를 만듦.",
    "T값 (라오어)": "누적 매수액 ÷ 1회 매수액. 분할 수 중 몇 회차까지 썼는지. T<20 전반전, T≥20 후반전, 소진 근처면 원금 소진.",
    "라오어 V2.2 / V3.0": "V2.2=안정형(40분할·단리·매도 +10%). V3.0=공격형(20분할·복리·매도 +15%, 오프셋 15−1.5T%). V3.0은 수익도 낙폭도 더 큼.",
    "라오어 세트": "첫 매수부터 전량 매도(익절)까지의 한 사이클. 완료 세트 수가 많고 소요일이 짧을수록 회전이 잘 된 것.",
    "LOC 주문": "Limit On Close. 종가가 지정가보다 유리하면 종가로 체결되는 주문. 백테스트에서는 '종가 ≤ 매수지정가면 종가 매수'로 근사.",
    "MOC 주문": "Market On Close. 종가에 무조건 체결되는 시장가 주문.",
    "지정가 주문": "지정한 가격 이상(매도)/이하(매수)에서만 체결. 백테스트에서는 당일 고가가 지정가에 닿으면 지정가로 체결된 것으로 근사.",
    "합성 데이터": "레버리지 ETF 상장 이전 구간을 기초지수 일간수익률×배수로 만든 가상 가격. 실제 가격이 아니므로 '합성포함' 표시가 붙음.",
    "변동성 감쇠": "레버리지 ETF가 일간 수익률의 배수를 추적하기 때문에, 오르내림을 반복하는 횡보장에서 기초지수보다 손실이 누적되는 구조적 현상.",
    "거치식": "시작일에 전액 일시 투자. 상승장에 유리하지만 진입 시점 운에 크게 좌우됨.",
    "적립식": "일정 주기로 나눠 매수(코스트 애버리징). 진입 시점 위험이 분산되지만 상승장에서는 늦게 들어간 만큼 수익금이 적음.",
    "XIRR와 CAGR가 다른 이유": "CAGR(TWR)는 '전략 자체의 성과', XIRR는 '내 돈의 성과'. 적립식에서 상승장 후반에 돈이 많이 들어갔다면 XIRR가 CAGR보다 낮아질 수 있음.",
    "세후최종순자산 / 세후XIRR": "세금(미국 22%·국내ETF 15.4% 등)을 반영한 값. 세금 토글을 켜면 세전 옆에 함께 표시됩니다.",
    "환효과기여": "환율 효과 ON일 때, '원화(기준화폐) 수익률 − 자산통화 수익률'. 원화 약세면 +, 강세면 −. 달러자산 수익 중 환율이 기여한 몫.",
    "매매비용 / 슬리피지": "수수료(bp)와 체결 미끄러짐(bp)을 매 거래에 반영한 누적 비용. 라오어처럼 매매가 잦으면 커짐. 1bp=0.01%.",
    "RP (대기자금 운용)": "아직 투자 안 된 현금을 CMA RP·발행어음·외화RP로 굴려 얻는 이자. '적립식 현금관리 계산기' 모드에서 계산.",
    "후순위 조달": "적립 투자금이 부족할 때 빌려서 조달하는 자금. '한 번에'보다 '매일 필요한 만큼'이 이자를 아껴 대개 유리.",
}

CHART_GUIDE = """
**누적 수익률 (시작=100)** — 모든 전략을 100에서 출발시켜 배수로 비교. 통화가 달라도 비교 가능.
기울기가 가파를수록 수익률이 높고, 급락 후 회복 속도가 전략의 성격을 보여줍니다.
장기 비교는 반드시 **로그 스케일**을 켜세요.

**언더워터 플롯** — 0 아래로 내려간 깊이가 낙폭, 다시 0에 닿을 때까지의 가로 길이가 회복 기간.
'얼마나 깊게, 얼마나 오래 물렸는가'를 보는 차트로, 최종 수익률보다 먼저 봐야 합니다.

**연도별 수익률** — 전략이 어느 해에 벌고 잃었는지. 특정 1~2개 연도가 수익 대부분을 만든 전략은
진입 시점 운에 취약합니다.

**월별 히트맵** — 파란색(하락)이 연속으로 몰린 구간이 고통 구간. 하락이 몇 달씩 이어졌는지 확인하세요.

**라오어 T값 차트** — T가 39.1(빨간 점선)에 자주 닿으면 원금 소진이 잦다는 뜻 = 하락장에서 물을 다 쓴 상태.
T가 낮은 상태로 세트가 빨리 끝날수록 이상적입니다.

**현금 비중** — 라오어·적립식에서 현금이 얼마나 놀고 있었는지. 현금 비중이 높으면 MDD는 낮아지지만
상승장 수익도 줄어듭니다.
"""


def _load_asset(ticker: str, source: str, currency: str, same_start: bool):
    """가격 로딩 (+동일 시작일 옵션이면 합성으로 앞구간 확장)."""
    df = get_price(ticker, source, currency)
    mask = None
    if same_start and ticker in SYNTH_BASE:
        df, mask = extend_with_synthetic(ticker, df)
    return df, mask


@st.cache_data(ttl=3600, show_spinner=False)
def _rates() -> tuple[dict, str]:
    """지원 통화 전체의 현재 환율 (1 USD당). 1시간 캐시."""
    return get_rates()


def render():
    """진입점 — 공통 설정 + 모드 전환 (가격 백테스트 / 적립식 현금관리 계산기)."""
    st.set_page_config(page_title="세로토닌 백테스트", page_icon="📈", layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown("""<style>
        [data-testid="stMetricValue"] {font-variant-numeric: tabular-nums; font-size: 1.6rem;}
        div[data-testid="stDataFrame"] {font-variant-numeric: tabular-nums;}
        /* 멀티셀렉트: '전체 지우기(X)'가 아래화살표와 붙어 오탭되는 문제 → X 숨기고 간격 확보 */
        [data-baseweb="select"] [aria-label="Clear all"],
        [data-baseweb="select"] [title="Clear all"] { display:none !important; }
        [data-baseweb="select"] [data-baseweb="icon"] { padding:0 3px; }
        /* 모바일(좁은 화면) 대응 */
        @media (max-width: 640px) {
            [data-testid="stMetricValue"] {font-size: 1.1rem;}
            [data-testid="stMetricLabel"] {font-size: 0.78rem;}
            h1 {font-size: 1.4rem;}
            /* 상단 '투자 전 필독' 배너가 헤더에 가려 잘리지 않게 위 여백 확보 */
            .block-container {padding: 3rem 0.7rem 1rem !important;}
            /* 드롭다운 화살표를 키워 정확히 누르기 쉽게, X와 분리 */
            [data-baseweb="select"] svg {min-width:22px; min-height:22px;}
            [data-baseweb="select"] [data-baseweb="icon"] {padding:0 6px;}
        }
    </style>""", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 🧑‍💻 제작 serotonin(이은호)")
        st.markdown("📧 [serotonin.1207@gmail.com](mailto:serotonin.1207@gmail.com)")
        st.markdown("✈️ [세로토닌 | 편안한 적립식 투자](https://t.me/+NXtqnYZek3I1OTZl)")
        st.caption("문의 사항이나 수정 요청은 위 이메일·텔레그램으로 보내주세요.")
        st.caption(f"🔖 버전 {APP_VERSION}")
        st.divider()
        app_mode = st.radio(
            "🧭 모드",
            ["📈 가격 백테스트", "🎯 최적의 투자 루틴 추천", "💵 적립식 현금관리 계산기",
             "💬 의견 게시판"],
            key="app_mode",
        )
        st.divider()

    # 상단 고정 — 투자 가이드/리포트 (클릭 시 팝업)
    from .guide import render_pinned_guides
    render_pinned_guides()
    _render_reference_bar()

    if app_mode.startswith("💵"):
        from .cash_plan_page import render_cash_plan
        render_cash_plan()
        return
    if app_mode.startswith("🎯"):
        from .routine_optimizer_page import render_routine_optimizer
        render_routine_optimizer()
        return
    if app_mode.startswith("💬"):
        from .board_page import render_board
        render_board()
        return
    _render_backtest()


def _render_backtest():
    st.title("📈 세로토닌 백테스트")
    st.caption("제작 serotonin(이은호) · 미국·한국 지수/ETF/개별종목 · 거치식/적립식/라오어(V2.2·V3.0) · "
               "⚠️ 백테스트 결과는 미래 수익을 보장하지 않습니다. 레버리지 상품은 변동성 감쇠 위험이 있습니다.")

    # ================================================== 사이드바 (설정 패널)
    with st.sidebar:
        st.header("⚙️ 설정")

        default_assets = ["QQQ", "QLD", "TQQQ"]
        assets = st.multiselect("자산 선택", list(ASSET_PRESETS.keys()),
                                default=default_assets, help=HELP["자산"])

        if "custom_tickers" not in st.session_state:
            st.session_state.custom_tickers = []
        st.text_input(
            "사용자 티커 추가", key="new_ticker_input",
            placeholder="예: AAPL · 005930 · 0700.HK · 000001.SS",
            help="티커를 입력하고 ➕추가하면 존재하는 티커는 아래 목록에 담깁니다. 국가는 자동 판별됩니다.",
        )
        st.caption(
            "🌏 자동 판별 — 알파벳=미국, 6자리 숫자=한국, "
            "**`.HK`**=홍콩(예 `0700.HK`), **`.SS`**=상하이(예 `000001.SS`), **`.SZ`**=선전(예 `399001.SZ`)"
        )
        st.button("➕ 추가", on_click=_add_custom_ticker, width="stretch")
        msg = st.session_state.pop("ticker_msg", None)
        if msg:
            {"ok": st.success, "warn": st.warning, "error": st.error}[msg[0]](msg[1])
        if st.session_state.custom_tickers:
            st.caption("**추가된 사용자 티커**")
            for i, t in enumerate(st.session_state.custom_tickers):
                rc1, rc2 = st.columns([4, 1])
                rc1.markdown(f"• `{t['ticker']}` ({t['currency']})")
                rc2.button("✖", key=f"rm_tk_{i}", on_click=_remove_custom_ticker, args=(i,))

        start_basis = st.radio("데이터 시작 기준", ["실제 데이터 시작일", "동일 시작일(합성 채움)"],
                               help=HELP["시작기준"])
        same_start = start_basis.startswith("동일")

        st.session_state.setdefault("bt_start_date", date(2015, 1, 1))
        st.session_state.setdefault("bt_end_date", date.today())
        c1, c2 = st.columns(2)
        start_date = c1.date_input("시작일", key="bt_start_date", min_value=date(1980, 1, 1))
        end_date = c2.date_input("종료일", key="bt_end_date")

        st.caption("⏱️ 빠른 기간 (현재 기준)")
        yrs = [1, 5, 10, 15, 20, 25, 30]
        yc = st.columns(len(yrs))
        for i, n in enumerate(yrs):
            yc[i].button(f"{n}년", key=f"btn_yr_{n}", width="stretch",
                         on_click=_bt_set_years, args=(n,))
        st.caption("📉 주요 폭락 시작일 → 현재 (최고점부터 물렸을 때)")
        cc = st.columns(len(_CRASH_PEAKS))
        for i, (nm, pk) in enumerate(_CRASH_PEAKS.items()):
            cc[i].button(nm.split("(")[0], key=f"btn_crash_{i}", width="stretch",
                         on_click=_bt_set_crash, args=(pk,),
                         help=f"{nm} 시장 최고점 {pk} → 현재")
        st.caption("📉 폭락 구간·지수 총정리·도움말·용어사전은 상단 '참고 자료'에서 볼 수 있습니다.")

        modes = st.multiselect("투자 방식 (자산마다 각각 적용)",
                               ["거치식", "적립식", "라오어"], default=["거치식", "적립식"],
                               help=HELP["투자방식"])

        base_label = st.selectbox("투자금 기준 화폐", list(CURRENCY_LABELS.values()), index=0,
                                  help=HELP["기준화폐"])
        base_code = next(c for c, l in CURRENCY_LABELS.items() if l == base_label)

        capital = st.number_input("투자금 / 총투입금", min_value=100.0,
                                  value=100_000_000.0, step=10_000_000.0, format="%.0f",
                                  help="거치식: 시작일 전액 투자 / 적립식: 기간에 걸쳐 분할 / 라오어: 세트 원금. "
                                       "위에서 선택한 기준 화폐로 입력하며, 자산 통화가 다르면 현재 환율로 환산해 투입.")
        st.caption(f"💰 입력액: **{capital:,.0f} {base_code}** = **{korean_money(capital, base_code)}** — "
                   f"자산의 거래 통화가 다르면 현재 환율로 환산해 투입합니다.")

        with st.expander("📥 적립식 설정"):
            dca_freq = st.selectbox("적립 주기", ["매일", "매주", "매월", "매년"], index=2)
            dca_span = st.selectbox("적립 기간", ["전체", "1년", "3년", "5년", "직접입력"], index=0)
            dca_years = {"전체": None, "1년": 1.0, "3년": 3.0, "5년": 5.0}.get(dca_span)
            if dca_span == "직접입력":
                dca_years = st.number_input("적립 기간(년)", 0.5, 50.0, 3.0, 0.5)

        with st.expander("♾️ 라오어 설정 (투자방식에 '라오어' 선택 시)", expanded=False):
            laoer_ver_label = st.selectbox("라오어 버전",
                                           ["V2.2 (안정형·40분할·단리)", "V3.0 (공격형·20분할·복리)"], index=0,
                                           help="V2.2: 매도목표 +10%, 매수/매도 오프셋 (10−T/2)%. "
                                                "V3.0: 매도목표 +15%, 오프셋 (15−1.5T)%, 세트마다 복리로 1회 매수금 증가 → "
                                                "수익·낙폭 모두 커짐.")
            laoer_version = "V3.0" if laoer_ver_label.startswith("V3.0") else "V2.2"
            _def_split = 20 if laoer_version == "V3.0" else 40
            _def_target = 15.0 if laoer_version == "V3.0" else 10.0
            st.caption(HELP["라오어"])
            laoer_splits = st.number_input("분할 수", 10, 100, _def_split)
            laoer_target = st.number_input("지정가 매도 목표(%)", 1.0, 30.0, _def_target, 0.5)
            laoer_boundary = st.number_input("전/후반 경계 T", 5.0, 40.0, 20.0, 1.0)
            laoer_exhaustion = st.selectbox("원금 소진 시", ["대기", "쿼터손절"])
            laoer_contrib = st.selectbox("라오어 중 추가불입 처리",
                                         ["다음 세트부터 반영", "즉시 현금 추가"])
            fill_buffer_bp = st.number_input(
                "체결 안전마진(bp)", 0.0, 200.0, 0.0, 5.0,
                help="일봉 체결의 낙관 편향을 줄이는 보수적 조건입니다. 예: 20bp면 매수는 지정가보다 "
                     "0.2% 더 낮아야, 매도는 0.2% 더 높아야 체결된 것으로 봅니다. 0은 기존 방식입니다.",
            )

        with st.expander("💸 추가 불입 / 중도 인출", expanded=False):
            st.caption(HELP["불입인출"])
            ev_df = st.data_editor(
                pd.DataFrame([{"date": None, "kind": "불입", "amount": 0.0, "repeat": "없음"}]),
                num_rows="dynamic", key="events_editor",
                column_config={
                    "date": st.column_config.DateColumn("날짜"),
                    "kind": st.column_config.SelectboxColumn("구분", options=["불입", "인출"]),
                    "amount": st.column_config.NumberColumn("금액", min_value=0.0, format="localized"),
                    "repeat": st.column_config.SelectboxColumn("반복", options=["없음", "매월", "매년"]),
                })

        with st.expander("🏦 대출 (옵션 A: 일시 대출형)", expanded=False):
            st.caption(HELP["대출"])
            loan_on = st.toggle("대출 사용", value=False)
            loan_amount = st.number_input("대출금액 (기준 화폐)", 0.0, value=50_000_000.0,
                                          step=10_000_000.0, format="%.0f")
            st.caption(f"= {loan_amount:,.0f} {base_code} ({korean_money(loan_amount, base_code)})")
            loan_rate = st.number_input("대출금리(연 %)", 0.0, 30.0, 4.5, 0.1) / 100.0

        with st.expander("💵 세금 · 매매비용 · 환율효과 (현실화)", expanded=False):
            st.caption("기본값은 모두 OFF(세전·비용0·환율고정) = 기존 결과와 동일. 켜면 더 현실적인 값이 됩니다.")
            tax_on = st.toggle("세금 반영", value=False,
                               help="미국 자산: 양도소득세 22%(연 250만원 공제, 손익통산, 거래일 환율 원화환산). "
                                    "국내 ETF: 매매차익 15.4%. 국내주식: 양도차익 비과세. "
                                    "연도별 세금을 다음 해 첫 거래일에 납부한 복리 영향까지 반영합니다.")
            div_on = st.toggle("지수 배당 보정 (총수익 지수 우선)", value=False,
                               help="S&P500·나스닥100·코스피 등 '가격지수'는 배당이 빠져 있어 ETF와 비교 시 불리하게 보입니다. "
                                    "켜면 S&P500은 장기 조회 가능한 배당 재투자 총수익 지수를 우선 사용하고, "
                                    "나스닥100 등 "
                                    "제공되지 않는 지수만 연 배당률 근사로 보정합니다. ETF 수정주가는 이미 분배금·보수를 반영합니다.")
            fx_on = st.toggle("환율 효과 반영 (언헤지)", value=False,
                              help="달러 등 외화 자산을 기준화폐로 볼 때, 과거 '일별 환율 변동(환손익)'을 수익률에 반영합니다. "
                                   "OFF면 환헤지 가정(자산 통화 수익률만).")
            cc1, cc2 = st.columns(2)
            fee_bp = cc1.number_input("매매 수수료(bp, 편도)", 0.0, 100.0, 0.0, 1.0,
                                      help="1bp=0.01%. 예: 국내 5bp, 미국 8bp 정도. 라오어처럼 매매가 잦으면 영향 큼.")
            slip_bp = cc2.number_input("슬리피지(bp, 편도)", 0.0, 300.0, 0.0, 1.0,
                                       help="체결 미끄러짐. LOC/지정가 가정의 현실성 검증용.")

        st.divider()
        run_btn = st.button("🚀 백테스트 실행", type="primary", width="stretch")

        with st.expander("🗂️ 데이터 캐시 관리"):
            cs = cache_status()
            if not cs.empty:
                st.dataframe(cs, hide_index=True, height=200)
            refresh_ticker = st.text_input("강제 새로고침 티커", "")
            if st.button("해당 티커 캐시 재다운로드") and refresh_ticker.strip():
                clear_cache(refresh_ticker.strip())
                st.success(f"{refresh_ticker} 캐시 삭제 — 다음 실행 시 전체 재다운로드")
            confirm = st.checkbox("전체 캐시 삭제 확인")
            if st.button("⚠️ 전체 캐시 비우기") and confirm:
                clear_cache(None)
                st.success("전체 캐시 삭제 완료")


    # ================================================== 실행
    if run_btn:
        targets: list[dict] = []
        for a in assets:
            p = ASSET_PRESETS[a]
            targets.append({"name": a, **p})
        for t in st.session_state.get("custom_tickers", []):
            targets.append(dict(t))
        if not targets or not modes:
            st.warning("자산과 투자 방식을 각각 1개 이상 선택하세요.")
            st.stop()

        events = [r for r in ev_df.to_dict("records")
                  if r.get("date") and r.get("amount", 0) and r["amount"] > 0]
        for e in events:
            e["date"] = str(e["date"])

        # ---- 환율 로딩 (기준 화폐 -> 자산 통화 환산 + 표시 통화 전환용)
        try:
            fx_rates, fx_date = _rates()
        except Exception as e:
            fx_rates, fx_date = {"USD": 1.0}, ""
            st.warning(f"환율 조회 실패 — 통화 환산 없이 입력 숫자를 그대로 사용합니다 ({e})")
        need_curs = {t["currency"] for t in targets} | {base_code}
        missing = sorted(need_curs - set(fx_rates))
        if missing:
            st.warning("다음 통화의 환율을 가져오지 못해 해당 자산은 입력 숫자를 그대로 사용합니다: "
                       + ", ".join(missing))

        results, errors, stale_warn = [], [], []
        prog = st.progress(0.0, text="데이터 로딩 중…")
        total_jobs = len(targets) * len(modes)
        job = 0
        for tgt in targets:
            try:
                ohlc, mask = _load_asset(tgt["ticker"], tgt["source"], tgt["currency"], same_start)
                if div_on and tgt["ticker"] in PRICE_INDEX_TICKERS:
                    tr_ticker = TOTAL_RETURN_TICKERS.get(tgt["ticker"])
                    if tr_ticker:
                        try:
                            ohlc = get_price(tr_ticker, "yahoo", tgt["currency"])
                            ohlc.attrs["total_return_source"] = tr_ticker
                        except Exception:
                            ohlc = apply_dividend_addback(
                                ohlc, INDEX_DIV_YIELD.get(tgt["ticker"], 0.0)
                            )
                            ohlc.attrs["total_return_source"] = "연율 근사 폴백"
                    else:
                        ohlc = apply_dividend_addback(
                            ohlc, INDEX_DIV_YIELD.get(tgt["ticker"], 0.0)
                        )
                        ohlc.attrs["total_return_source"] = "연율 근사 폴백"
                if ohlc.attrs.get("stale"):
                    stale_warn.append(tgt["name"])
            except Exception as e:
                errors.append(f"{tgt['name']}: {e}")
                job += len(modes)
                continue
            # 기준 화폐 -> 자산 거래 통화 환산 (현재 환율 기준)
            acur = tgt["currency"]
            cap_a = convert(capital, base_code, acur, fx_rates)
            loan_a = convert(loan_amount, base_code, acur, fx_rates) if loan_on else 0.0
            events_a = [{**e, "amount": convert(e["amount"], base_code, acur, fx_rates)}
                        for e in events]
            for mode in modes:
                job += 1
                prog.progress(job / total_jobs, text=f"{tgt['name']} · {mode} 계산 중…")
                sname = f"{tgt['name']}·{mode}{laoer_version if mode == '라오어' else ''}"
                try:
                    if mode == "라오어":
                        r = run_laoer(ohlc, sname, cap_a, start=start_date, end=end_date,
                                      splits=int(laoer_splits), target_pct=laoer_target,
                                      boundary_t=laoer_boundary, exhaustion=laoer_exhaustion,
                                      events=events_a, contrib_mode=laoer_contrib,
                                      currency=acur, synthetic_mask=mask,
                                      fee_bp=fee_bp, slippage_bp=slip_bp,
                                      fill_buffer_bp=fill_buffer_bp, version=laoer_version)
                    else:
                        r = run_backtest(ohlc, sname, mode, cap_a, start=start_date, end=end_date,
                                         dca_freq=dca_freq, dca_years=dca_years, events=events_a,
                                         loan_on=loan_on, loan_amount=loan_a,
                                         loan_rate=loan_rate, currency=acur,
                                         synthetic_mask=mask,
                                         fee_bp=fee_bp, slippage_bp=slip_bp)
                    r.tax_cat = tax_category(tgt["ticker"], acur)
                    r.asset_ticker = tgt["ticker"]
                    results.append(r)
                except Exception as e:
                    errors.append(f"{sname}: {e}")
                    st.expander(f"오류 상세 — {sname}").code(traceback.format_exc())
        prog.empty()

        if stale_warn:
            st.warning("⚠️ 최신 데이터 갱신 실패 — 캐시 데이터로 계산: " + ", ".join(stale_warn))
        for e in errors:
            st.error(e)
        if not results:
            st.stop()

        rates_str = ", ".join(f"1 USD = {v:,.2f} {c}" for c, v in fx_rates.items() if c != "USD")
        settings_snapshot = {
            "자산": ", ".join(t["name"] for t in targets), "투자방식": ", ".join(modes),
            "기간": f"{start_date} ~ {end_date}", "시작기준": start_basis,
            "투자금": f"{capital:,.0f} {base_code} ({korean_money(capital, base_code)})",
            "기준화폐": f"{base_code} ({SUPPORTED.get(base_code, ('', ''))[1]})",
            "적용환율": f"{rates_str} (기준일 {fx_date})" if rates_str else "환산 없음",
            "적립주기": dca_freq, "적립기간": dca_span,
            "라오어": f"{laoer_version} {laoer_splits}분할, 목표 {laoer_target}%, 경계 T={laoer_boundary}, "
                      f"소진={laoer_exhaustion}, 체결 안전마진={fill_buffer_bp:.0f}bp",
            "대출": f"{'ON' if loan_on else 'OFF'} (금액 {loan_amount:,.0f} {base_code}, 금리 {loan_rate:.2%})",
            "불입/인출 이벤트 수": len(events),
            "세금": f"{'ON (미국22%/국내ETF15.4%)' if tax_on else 'OFF (세전)'}",
            "환율효과(언헤지)": f"{'ON (일별 환율 반영)' if fx_on else 'OFF (환헤지 가정)'}",
            "지수배당보정": f"{'ON (공식 총수익 지수 우선, 미제공 시 연율 근사)' if div_on else 'OFF'}",
            "매매비용": f"수수료 {fee_bp:.0f}bp + 슬리피지 {slip_bp:.0f}bp (편도)",
            "통화처리": "투자금은 기준 화폐로 입력 → 자산 통화로 현재 환율 환산 투입 → 표시 통화로 환산 출력",
        }
        st.session_state["results"] = results
        st.session_state["settings"] = settings_snapshot
        st.session_state["base_code"] = base_code
        st.session_state["fx"] = (fx_rates, fx_date)
        st.session_state["adv"] = {"tax_on": tax_on, "fx_on": fx_on, "div_on": div_on,
                                   "fee_bp": fee_bp, "slip_bp": slip_bp}

    # ================================================== 결과 표시
    results = st.session_state.get("results")
    if not results:
        st.info("좌측 사이드바에서 자산·투자방식을 고른 뒤 **백테스트 실행**을 누르세요.")
        return
    settings_snapshot = st.session_state.get("settings", {})
    adv = st.session_state.get("adv", {})
    tax_on = adv.get("tax_on", False)
    fx_on = adv.get("fx_on", False)
    fee_used = adv.get("fee_bp", 0.0) > 0 or adv.get("slip_bp", 0.0) > 0
    base_code_s = st.session_state.get("base_code", "KRW")
    fx_rates, fx_date = st.session_state.get("fx", ({}, ""))
    if not fx_rates:
        try:
            fx_rates, fx_date = _rates()
        except Exception:
            fx_rates, fx_date = {"USD": 1.0}, ""

    # ---- 요약표 구성 (환율효과·세금·매매비용 반영)
    rows = []
    for r in results:
        eq_eff, cfs_eff, flows_eff, eff_ccy, fx_contrib = _effective_series(r, fx_on, base_code_s)
        conv = 1.0 if eff_ccy == r.currency else (cross_rate(r.currency, eff_ccy, fx_rates) or 1.0)
        net_inv = r.net_invested * conv
        final_v = float(eq_eff.iloc[-1])
        m = summarize(eq_eff, cfs_eff, flows=flows_eff, net_invested=net_inv)

        tax_eff = 0.0
        after_xirr = None
        if tax_on:
            ti = _tax_info(r, fx_rates)
            tax_eff = convert(ti["total_tax_asset"], r.currency, eff_ccy, fx_rates)
            schedule = {
                year: convert(amount, r.currency, eff_ccy, fx_rates)
                for year, amount in tax_schedule_asset(ti).items()
            }
            after_equity, tax_payments = apply_annual_tax_drag(
                eq_eff, flows_eff, schedule
            )
            cfs_after = list(cfs_eff)
            if cfs_after:
                d_last, _ = cfs_after[-1]
                cfs_after[-1] = (d_last, float(after_equity.iloc[-1]))
            after_xirr = xirr(cfs_after)
            after_final = float(after_equity.iloc[-1])
        else:
            after_final = final_v

        rows.append({
            "전략명": r.name, "통화": eff_ccy,
            "데이터": "합성포함" if r.is_synthetic_used else "실제",
            "총투입금": r.total_invested * conv, "추가불입": r.total_contrib * conv,
            "중도인출": r.total_withdraw * conv, "순투입금": net_inv,
            "최종순자산": final_v,
            "원금대비배수": final_v / net_inv if net_inv > 0 else None,
            "총수익률": m["총수익률"], "CAGR": m["CAGR"], "XIRR": m["XIRR"],
            "MDD": m["MDD"], "연율변동성": m["연율변동성"], "샤프": m["샤프"],
            "소르티노": m["소르티노"], "칼마": m["칼마"], "최장무회복일": m["최장무회복일"],
            "대출": "O" if r.loan_used else "-", "총이자": r.total_interest * conv,
            "매매비용": getattr(r, "total_fees", 0.0) * conv,
            "세금": tax_eff, "세후최종순자산": after_final, "세후XIRR": after_xirr,
            "환효과기여": fx_contrib,
            "완료세트": len(r.laoer_sets[r.laoer_sets["종료사유"] != "진행중"])
                       if r.laoer_sets is not None and not r.laoer_sets.empty else None,
        })
    summary_df = pd.DataFrame(rows)

    # 토글이 꺼진 열은 표에서 제외 (혼란 방지)
    drop = []
    if not tax_on:
        drop += ["세금", "세후최종순자산", "세후XIRR"]
    if not fx_on:
        drop += ["환효과기여"]
    if not fee_used:
        drop += ["매매비용"]
    summary_df = summary_df.drop(columns=[c for c in drop if c in summary_df.columns])

    cur_options = list(CURRENCY_LABELS)
    tc1, tc2 = st.columns([2, 3])
    disp_label = tc1.radio("표시 통화", [CURRENCY_LABELS[c] for c in cur_options],
                           index=cur_options.index(base_code_s) if base_code_s in cur_options else 0,
                           horizontal=True, help=HELP["표시통화"])
    target_cur = next(c for c in cur_options if CURRENCY_LABELS[c] == disp_label)

    used_curs = sorted(set(summary_df["통화"]) | {base_code_s})
    xr_lines = []
    for c in used_curs:
        if c == target_cur:
            continue
        xr = cross_rate(c, target_cur, fx_rates)
        if xr:
            xr_lines.append(f"1 {c} = {_fmt_rate(xr)} {target_cur}")
    tc2.caption(f"투자금 기준 화폐: **{base_code_s}** · 적용 환율: "
                + (" · ".join(xr_lines) if xr_lines else "환산 없음")
                + (f" (기준일 {fx_date})" if fx_date else "")
                + " — 현재 환율 단순 환산 표시값. 일별 환율 반영 시뮬레이션은 확장 예정.")
    with tc2.expander("🌍 지원 통화 환율 전체 보기"):
        fx_rows = []
        for c, (unit, name) in SUPPORTED.items():
            xr = cross_rate(c, target_cur, fx_rates)
            fx_rows.append({"통화": c, "이름": name,
                            "1 USD당": f"{fx_rates[c]:,.4f}" if c in fx_rates else "조회 실패",
                            f"1 {c} = ? {target_cur}": _fmt_rate(xr) if xr else "-"})
        st.dataframe(pd.DataFrame(fx_rows), hide_index=True, width="stretch")

    miss_rows = [c for c in set(summary_df["통화"]) if c not in fx_rates]
    if target_cur and miss_rows and any(c != target_cur for c in miss_rows):
        st.warning("환율 미확보 통화(" + ", ".join(miss_rows) + ")는 원래 금액 그대로 표시됩니다.")

    display_df = summary_df.copy()
    for col in MONEY_COLS:
        if col not in display_df.columns:
            continue
        display_df[col] = [convert(v, c, target_cur, fx_rates) if pd.notna(v) else v
                           for v, c in zip(summary_df[col], summary_df["통화"])]
    display_df["통화"] = [target_cur if c in fx_rates and target_cur in fx_rates else c
                          for c in summary_df["통화"]]

    # ---- KPI 카드 (최종순자산 1위 전략)
    best = display_df.sort_values("최종순자산", ascending=False).iloc[0]
    st.subheader(f"🏆 최종 순자산 1위: {best['전략명']}")
    k = st.columns(5)
    k[0].metric("최종 순자산", f"{best['최종순자산']:,.0f} {best['통화']}")
    k[0].caption(f"**{korean_money(best['최종순자산'], best['통화'])}**")
    k[1].metric("CAGR", f"{best['CAGR']:.2%}")
    k[1].caption("연평균 복리 수익률")
    k[2].metric("XIRR", f"{best['XIRR']:.2%}" if pd.notna(best["XIRR"]) else "-")
    k[2].caption("현금흐름 반영 연수익률")
    k[3].metric("MDD", f"{best['MDD']:.2%}")
    k[3].caption("최대 낙폭")
    k[4].metric("칼마", f"{best['칼마']:.2f}")
    k[4].caption("CAGR ÷ |MDD|")

    tabs = st.tabs(["📋 요약표", "🧭 결과 해석", "📈 차트", "💰 현금흐름·이벤트",
                    "♾️ 라오어 세트", "✅ 합성 검증", "📤 내보내기"])

    # ---- 요약표
    with tabs[0]:
        sort_opts = ["최종순자산", "XIRR", "MDD", "칼마", "CAGR", "완료세트"]
        if "세후최종순자산" in display_df.columns:
            sort_opts.insert(1, "세후최종순자산")
        sort_key = st.selectbox("정렬 기준", sort_opts, index=0)
        asc = sort_key == "MDD"
        show = display_df.sort_values(sort_key, ascending=asc, na_position="last")
        pct_cols = ("총수익률", "CAGR", "XIRR", "MDD", "연율변동성", "세후XIRR", "환효과기여")
        st.dataframe(show, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="percent" if c in
                                    pct_cols else "localized")
                                    for c in show.columns if show[c].dtype.kind == "f"})
        # 한글 금액 요약 줄
        lines = [f"- **{r['전략명']}**: 최종 순자산 {r['최종순자산']:,.0f} {r['통화']} = "
                 f"**{korean_money(r['최종순자산'], r['통화'])}**"
                 + (f" → 세후 **{korean_money(r['세후최종순자산'], r['통화'])}**" if "세후최종순자산" in show.columns else "")
                 for _, r in show.iterrows()]
        st.markdown("**💬 금액 한글 표기**\n" + "\n".join(lines))
        st.caption("ℹ️ 총수익률=순투입금 대비 단순 수익률 · CAGR/MDD/샤프 등=불입·인출 효과를 제거한 "
                   "시간가중(TWR) 기준 · XIRR=실제 현금흐름 기준 연환산. 자세한 정의는 좌측 '📚 용어 사전' 참고.")
        notes = []
        if tax_on:
            notes.append("세금: 미국 22%(연 250만원 공제·손익통산·거래일 환율) / 국내ETF 15.4% / 국내주식 비과세. "
                         "연도별 세금을 다음 해 첫 거래일에 납부한 것으로 처리해 이후 복리 손실까지 반영합니다.")
        if fx_on:
            notes.append("환율효과 ON: 외화 자산을 기준화폐로 볼 때 과거 일별 환율 변동을 수익률에 반영했습니다. "
                         "'환효과기여' = 원화수익률 − 자산통화수익률.")
        if fee_used:
            notes.append("매매비용(수수료+슬리피지)이 매 거래에 반영되어 '매매비용' 열에 누적 표시됩니다.")
        for n in notes:
            st.caption("• " + n)
        if summary_df["데이터"].eq("합성포함").any():
            st.caption("⚠️ '합성포함' 전략은 상장 이전 구간을 기초지수 일간수익률×배수로 합성한 데이터입니다 — 실제 가격이 아닙니다.")

    # ---- 결과 해석
    with tabs[1]:
        st.markdown(interpret_results(display_df, target_cur))
        with st.expander("📈 차트는 이렇게 읽으세요"):
            st.markdown(CHART_GUIDE)
        with st.expander("📚 용어 사전 (전체)"):
            for kk, vv in GLOSSARY.items():
                st.markdown(f"**{kk}**  \n{vv}")

    # ---- 차트
    with tabs[2]:
        # 요약표와 동일한 환율효과·현금흐름 기준의 복사본으로 차트를 그린다.
        chart_results = []
        for r in results:
            cr = copy(r)
            eq_eff, _, flows_eff, eff_ccy, _ = _effective_series(r, fx_on, base_code_s)
            cr.equity = eq_eff
            cr.flows = flows_eff
            cr.currency = eff_ccy
            if r.cash_series is not None:
                raw_eq = r.equity.reindex(eq_eff.index).replace(0, pd.NA)
                scale = (eq_eff / raw_eq).ffill().bfill()
                cr.cash_series = r.cash_series.reindex(eq_eff.index) * scale
            chart_results.append(cr)

        c1, _ = st.columns([1, 3])
        log_scale = c1.toggle("로그 스케일", value=False,
                              help="세로축을 배수 기준으로 — 장기 복리 비교 시 필수")
        normalize = c1.toggle("시작=100 정규화", value=True)
        st.plotly_chart(fig_equity(chart_results, log_scale, normalize), width="stretch")
        st.plotly_chart(fig_drawdown(chart_results), width="stretch")
        cc1, cc2 = st.columns(2)
        conv_vals = [convert(r.final_value, r.currency, target_cur, fx_rates) for r in chart_results]
        cc1.plotly_chart(fig_final_values(chart_results, conv_vals, target_cur), width="stretch")
        cc2.plotly_chart(fig_annual_returns(chart_results), width="stretch")
        pick = st.selectbox("월별 히트맵 전략", [r.name for r in results])
        target = next(r for r in chart_results if r.name == pick)
        st.plotly_chart(fig_monthly_heatmap(target), width="stretch")
        if any(r.cash_series is not None for r in chart_results):
            st.plotly_chart(fig_cash_ratio(chart_results), width="stretch")

    # ---- 현금흐름
    with tabs[3]:
        cf_rows = [{"전략": r.name, "날짜": pd.Timestamp(d).date(), "금액(투입-, 회수+)": a}
                   for r in results for d, a in r.cashflows]
        st.dataframe(pd.DataFrame(cf_rows), hide_index=True, width="stretch",
                     column_config={"금액(투입-, 회수+)": st.column_config.NumberColumn(format="localized")})
        ev_rows = [{"전략": r.name, "날짜": pd.Timestamp(e["date"]).date(), "구분": e["구분"],
                    "금액": e["금액"]} for r in results for e in r.events_log]
        if ev_rows:
            st.markdown("**이벤트 내역 (불입/인출/대출/쿼터손절)**")
            st.dataframe(pd.DataFrame(ev_rows), hide_index=True, width="stretch",
                         column_config={"금액": st.column_config.NumberColumn(format="localized")})

    # ---- 라오어
    with tabs[4]:
        lao = [r for r in results if r.laoer_sets is not None and not r.laoer_sets.empty]
        if not lao:
            st.info("라오어 전략이 없습니다. 사이드바에서 '라오어 V2.2'를 선택하세요.")
        else:
            st.plotly_chart(fig_t_series(lao), width="stretch")
            for r in lao:
                st.markdown(f"**{r.name} — 세트별 매매 내역**")
                done = r.laoer_sets[r.laoer_sets["종료사유"] != "진행중"]
                if len(done):
                    win = (done["세트손익"] > 0).mean()
                    st.caption(f"완료 세트 {len(done)}개 · 승률 {win:.0%} · 평균 소요 {done['소요일'].mean():.0f}일 "
                               f"· 최악 세트손익 {done['세트손익'].min():,.0f}")
                st.dataframe(r.laoer_sets, hide_index=True, width="stretch")

    # ---- 검증
    with tabs[5]:
        st.caption("합성 데이터(기초지수 일간수익률×배수)가 실제 레버리지 ETF와 얼마나 유사한지 — 실제 상장 이후 겹치는 구간에서 계산")
        v_ticks = st.multiselect("검증 대상", list(SYNTH_BASE.keys()), default=["TQQQ", "QLD"])
        if st.button("검증 실행"):
            vrows = []
            for t in v_ticks:
                try:
                    v = validate_synthetic(t)
                    if v:
                        vrows.append(v)
                except Exception as e:
                    st.error(f"{t}: {e}")
            if vrows:
                vdf = pd.DataFrame(vrows)
                for c in ("합성 CAGR", "실제 CAGR", "추적오차(연율)", "합성 MDD", "실제 MDD"):
                    vdf[c] = vdf[c].map(lambda x: f"{x:.2%}")
                vdf["일수익 상관"] = vdf["일수익 상관"].map(lambda x: f"{x:.3f}")
                st.dataframe(vdf, hide_index=True, width="stretch")
        st.divider()
        st.markdown("#### 🔬 최근 분봉으로 일봉 체결 데이터 확인")
        st.caption("무료 분봉 제공 범위 때문에 최근 약 60일만 검증합니다. 5분봉을 일봉으로 다시 합쳐 "
                   "백테스트가 사용하는 종가·고가·저가와 얼마나 일치하는지 확인합니다.")
        intraday_ticker = st.text_input("분봉 검증 티커", value="TQQQ", key="intraday_ticker")
        if st.button("최근 5분봉 검증 실행", key="run_intraday_validation"):
            try:
                iv = validate_intraday_ohlc(intraday_ticker.strip().upper())
                st.dataframe(pd.DataFrame([iv]), hide_index=True, width="stretch")
                st.info("오차가 크면 라오어 설정의 **체결 안전마진(bp)**과 슬리피지를 높여 "
                        "보수적으로 다시 계산하세요. 장기 분봉은 무료 소스 제한으로 제공되지 않습니다.")
            except Exception as e:
                st.error(f"분봉 검증 실패: {e}")

    # ---- 내보내기
    with tabs[6]:
        excel_bytes = build_excel(results, summary_df, settings_snapshot)
        st.download_button("📊 Excel 다운로드 (차트 포함)", excel_bytes,
                           file_name="backtest_results.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.download_button("📄 요약 CSV 다운로드", summary_df.to_csv(index=False).encode("utf-8-sig"),
                           file_name="backtest_summary.csv", mime="text/csv")
        ai_md = build_ai_report(results, summary_df, settings_snapshot)
        ai_md += "\n\n## 자동 해석 (프로그램 생성)\n" + interpret_results(display_df, target_cur)
        try:
            path = save_ai_report(ai_md, OUT_DIR)
            st.success(f"AI 분석 요청 파일 자동 저장: `{path}`")
        except Exception:
            st.info("이 서버에서는 파일 자동 저장을 건너뜁니다 — 아래 버튼으로 내려받으세요.")
        st.download_button("🤖 ai_analysis_request.md 다운로드", ai_md.encode("utf-8"),
                           file_name="ai_analysis_request.md", mime="text/markdown")
        with st.expander("미리보기"):
            st.markdown(ai_md)
