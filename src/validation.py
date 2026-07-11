# -*- coding: utf-8 -*-
"""합성 vs 실제 레버리지 ETF 검증: CAGR, 일수익 상관, 추적오차, MDD 차이.
모든 수치는 실제 데이터로 계산한다 (하드코딩 금지)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data_loader import SYNTH_BASE, get_price
from .metrics import cagr, mdd
from .synthetic_etf import synthesize_close


def validate_synthetic(ticker: str) -> dict | None:
    """실제 상장 이후 겹치는 구간에서 합성 시계열과 실제 ETF를 비교."""
    if ticker not in SYNTH_BASE:
        return None
    base_ticker, lev, fee = SYNTH_BASE[ticker]
    actual = get_price(ticker)["Close"].astype(float)
    base = get_price(base_ticker)["Close"].astype(float)

    common = actual.index.intersection(base.index)
    if len(common) < 60:
        return None
    actual = actual.loc[common]
    synth = synthesize_close(base.loc[common], lev, fee)

    ra = actual.pct_change().dropna()
    rs = synth.pct_change().dropna()
    both = pd.concat([ra, rs], axis=1, keys=["actual", "synth"]).dropna()

    corr = float(both["actual"].corr(both["synth"]))
    te = float((both["actual"] - both["synth"]).std() * np.sqrt(252))  # 연율 추적오차
    return {
        "티커": ticker,
        "기초지수": base_ticker,
        "비교기간": f"{common[0].date()} ~ {common[-1].date()}",
        "합성 CAGR": cagr(synth),
        "실제 CAGR": cagr(actual),
        "일수익 상관": corr,
        "추적오차(연율)": te,
        "합성 MDD": mdd(synth),
        "실제 MDD": mdd(actual),
    }


def validate_intraday_ohlc(ticker: str, period: str = "60d", interval: str = "5m") -> dict:
    """최근 분봉을 일봉으로 재집계해 백테스트 일봉 OHLC와 비교한다."""
    import yfinance as yf

    raw = yf.download(
        ticker, period=period, interval=interval, auto_adjust=True,
        progress=False, prepost=False,
    )
    if raw is None or raw.empty:
        raise ValueError("분봉 데이터가 비어 있습니다. 티커 또는 제공 기간을 확인하세요.")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw.index = pd.to_datetime(raw.index)
    if raw.index.tz is not None:
        raw.index = raw.index.tz_convert("America/New_York").tz_localize(None)
    session_date = raw.index.normalize()
    intraday = raw.groupby(session_date).agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    ).dropna()

    daily = get_price(ticker, source="yahoo")[
        ["Open", "High", "Low", "Close"]
    ].astype(float)
    common = intraday.index.intersection(daily.index)
    if len(common) < 5:
        raise ValueError("일봉과 분봉의 공통 거래일이 5일 미만입니다.")
    a = intraday.loc[common]
    b = daily.loc[common]
    errors_bp = (a - b).abs().div(b.abs().clip(lower=1e-12)) * 10_000
    return {
        "티커": ticker,
        "검증기간": f"{common.min().date()} ~ {common.max().date()}",
        "공통거래일": len(common),
        "종가 평균오차(bp)": round(float(errors_bp["Close"].mean()), 2),
        "고가 평균오차(bp)": round(float(errors_bp["High"].mean()), 2),
        "저가 평균오차(bp)": round(float(errors_bp["Low"].mean()), 2),
        "최대 OHLC 오차(bp)": round(float(errors_bp.max().max()), 2),
    }
