# -*- coding: utf-8 -*-
"""상단 대시보드: '오늘 기준 N년 전 1천만원을 샀다면?' — TQQQ·QQQ·QLD 실측 수익률.

- 항상 오늘 기준으로 계산(투자 시작일 = 최신 종가일에서 N년 전 첫 거래일).
- 종료 = 최신 확정 종가(사실상 어제 종가). 배당 재투자(수정종가) 반영, 세금·환율·수수료 미반영.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from .data_loader import get_price

_ASSETS = [("TQQQ", "USD"), ("QQQ", "USD"), ("QLD", "USD")]
_PERIODS = [(10, "10년 전"), (5, "5년 전"), (1, "1년 전")]
_INVEST = 10_000_000  # 1천만원


@st.cache_data(ttl="6h", show_spinner=False)
def _compute(day_key: str) -> dict:
    """day_key(오늘 날짜)를 캐시 키로 받아 하루 1회 이상 갱신."""
    out: dict = {}
    end_dt = None
    for ticker, cur in _ASSETS:
        try:
            close = get_price(ticker, "yahoo", cur)["Close"].astype(float).dropna()
        except Exception:
            continue
        e_dt, e_px = close.index[-1], float(close.iloc[-1])
        end_dt = e_dt if end_dt is None else max(end_dt, e_dt)
        rows: dict = {}
        for yrs, _ in _PERIODS:
            s = close.loc[close.index >= e_dt - pd.DateOffset(years=yrs)]
            if len(s) < 2:
                rows[yrs] = None
                continue
            start_dt, start_px = s.index[0], float(s.iloc[0])
            mult = e_px / start_px if start_px > 0 else 0.0
            years = max((e_dt - start_dt).days / 365.25, 1e-9)
            rows[yrs] = {
                "start": start_dt, "ret": mult - 1.0, "final": _INVEST * mult,
                "cagr": mult ** (1.0 / years) - 1.0 if mult > 0 else 0.0,
            }
        out[ticker] = rows
    out["_end"] = end_dt
    return out


def _won(v: float) -> str:
    eok = v / 1e8
    if eok >= 1:
        return f"{eok:.2f}억"
    return f"{v / 1e4:,.0f}만"


def render_whatif_dashboard() -> None:
    data = _compute(str(pd.Timestamp.today().date()))
    end_dt = data.get("_end")
    if end_dt is None:
        return
    with st.container(border=True):
        st.markdown("#### 💰 1천만원을 투자했다면? (오늘 기준)")
        st.caption(
            f"각 종목을 그 시점에 **1천만원** 매수해 **최신 종가({end_dt.date()})** 까지 보유한 결과입니다. "
            "배당 재투자(수정종가) 반영 · 세금·환율·수수료 미반영 · 매일 자동 갱신."
        )
        for yrs, label in _PERIODS:
            sample = data.get("QQQ", {}).get(yrs) or data.get("TQQQ", {}).get(yrs)
            span = f" ({sample['start'].date()} ~ {end_dt.date()})" if sample else ""
            st.markdown(f"**📅 {label}에 샀다면**{span}")
            cols = st.columns(len(_ASSETS))
            for i, (ticker, _) in enumerate(_ASSETS):
                r = data.get(ticker, {}).get(yrs)
                if not r:
                    cols[i].metric(ticker, "데이터 부족", border=True)
                    continue
                cols[i].metric(
                    ticker, f"{r['ret']:+.0%}",
                    delta=f"→ {_won(r['final'])}원 · CAGR {r['cagr']:+.0%}",
                    delta_color="off", border=True,
                )
