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
