# -*- coding: utf-8 -*-
"""최상단 대시보드: '오늘 기준 N년 전 1천만원을 샀다면?' — TQQQ·QQQ·QLD 거치식/적립식 실측.

- 항상 오늘 기준(시작 = 최신 종가일에서 N년 전 첫 거래일, 종료 = 최신 확정 종가 ≈ 어제 종가).
- 거치식: 시작일에 1천만원 전액 매수.
- 적립식: 1천만원을 기간 내 매 거래일 균등 분할 매수(일별 매수액도 표기).
- 라오어 V3.0: 공격형 무한매수법(20분할·복리)으로 1천만원 운용.
- 배당 재투자(수정종가) 반영, 세금·환율·수수료 미반영.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from .data_loader import get_price
from .laoer_strategy import run_laoer

_ASSETS = [("QQQ", "USD"), ("QLD", "USD"), ("TQQQ", "USD")]
_PERIODS = [(10, "10년 전"), (5, "5년 전"), (1, "1년 전")]
_INVEST = 10_000_000  # 1천만원


@st.cache_data(ttl="6h", show_spinner=False)
def _compute(day_key: str) -> dict:
    """day_key(오늘 날짜)를 캐시 키로 받아 하루 1회 이상 갱신."""
    out: dict = {}
    end_dt = None
    for ticker, cur in _ASSETS:
        try:
            ohlc = get_price(ticker, "yahoo", cur)
            close = ohlc["Close"].astype(float).dropna()
        except Exception:
            continue
        e_dt, e_px = close.index[-1], float(close.iloc[-1])
        end_dt = e_dt if end_dt is None else max(end_dt, e_dt)
        rows: dict = {}
        for yrs, _ in _PERIODS:
            s = close.loc[close.index >= e_dt - pd.DateOffset(years=yrs)]
            if len(s) < 2 or float(s.iloc[0]) <= 0:
                rows[yrs] = None
                continue
            start_dt, start_px = s.index[0], float(s.iloc[0])
            n = len(s)
            per_day = _INVEST / n
            lump_mult = e_px / start_px
            dca_shares = float((per_day / s.to_numpy()).sum())
            dca_mult = dca_shares * e_px / _INVEST
            try:
                laoer_final = run_laoer(
                    ohlc, ticker, _INVEST, start=start_dt, end=e_dt, version="V3.0"
                ).final_value
                laoer_ret = laoer_final / _INVEST - 1.0
            except Exception:
                laoer_final, laoer_ret = None, None
            rows[yrs] = {
                "start": start_dt, "n_days": n, "per_day": per_day,
                "lump_ret": lump_mult - 1.0, "lump_final": _INVEST * lump_mult,
                "dca_ret": dca_mult - 1.0, "dca_final": _INVEST * dca_mult,
                "laoer_ret": laoer_ret, "laoer_final": laoer_final,
            }
        out[ticker] = rows
    out["_end"] = end_dt
    return out


def _won(v: float) -> str:
    eok = v / 1e8
    if eok >= 1:
        return f"{eok:.2f}억원"
    return f"{v / 1e4:,.0f}만원"


def render_whatif_dashboard() -> None:
    data = _compute(str(pd.Timestamp.today().date()))
    end_dt = data.get("_end")
    if end_dt is None:
        return
    with st.container(border=True):
        st.markdown("### 💰 1천만원을 투자했다면? — 거치식 vs 적립식 (오늘 기준)")
        st.caption(
            f"각 종목을 그 시점에 **1천만원** 넣어 **최신 종가({end_dt.date()})** 까지 보유한 결과입니다. "
            "**거치식**=시작일 전액 매수, **적립식**=기간 내 매 거래일 균등 분할, "
            "**라오어**=공격형 무한매수법 V3.0(20분할·복리). "
            "배당 재투자 반영 · 세금·환율·수수료 미반영 · 매일 자동 갱신."
        )
        for yrs, label in _PERIODS:
            sample = data.get("QQQ", {}).get(yrs) or data.get("TQQQ", {}).get(yrs)
            if sample:
                st.markdown(
                    f"**📅 {label} ({sample['start'].date()} ~ {end_dt.date()})** "
                    f"· 적립식 일별 매수액 약 **{sample['per_day']:,.0f}원** ({sample['n_days']:,}거래일)"
                )
            else:
                st.markdown(f"**📅 {label}**")
            cols = st.columns(len(_ASSETS))
            for i, (ticker, _) in enumerate(_ASSETS):
                r = data.get(ticker, {}).get(yrs)
                with cols[i].container(border=True):
                    if not r:
                        st.markdown(f"**{ticker}**  \n데이터 부족")
                        continue
                    laoer_line = (
                        f"라오어 **{r['laoer_ret']:+.0%}** → {_won(r['laoer_final'])}"
                        if r.get("laoer_ret") is not None else "라오어 —"
                    )
                    st.markdown(
                        f"**{ticker}**  \n"
                        f"거치식 **{r['lump_ret']:+.0%}** → {_won(r['lump_final'])}  \n"
                        f"적립식 **{r['dca_ret']:+.0%}** → {_won(r['dca_final'])}  \n"
                        f"{laoer_line}"
                    )
