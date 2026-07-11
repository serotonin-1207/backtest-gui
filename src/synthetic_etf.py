# -*- coding: utf-8 -*-
"""레버리지 ETF 합성: 기초지수 '일간 수익률 x 배수'로 생성 (장기수익률 단순 배수 곱 금지).

동일 시작일 비교 옵션(B)에서 실제 상장 이전 구간을 합성 데이터로 채운다.
합성 구간은 is_synthetic=True 로 표시하여 표·차트에 '합성 데이터' 라벨을 붙인다.
"""
from __future__ import annotations

import pandas as pd

from .data_loader import SYNTH_BASE, get_price

TRADING_DAYS = 252


def synthesize_close(base_close: pd.Series, leverage: float, annual_fee: float = 0.0) -> pd.Series:
    """기초지수 일간 수익률 x 배수 - 일할 보수 로 합성 종가 시계열 생성 (시작값 100)."""
    daily = base_close.pct_change().fillna(0.0) * leverage - annual_fee / TRADING_DAYS
    if not daily.empty:
        daily.iloc[0] = 0.0
    return 100.0 * (1.0 + daily).cumprod()


def apply_dividend_addback(ohlc: pd.DataFrame, annual_yield: float) -> pd.DataFrame:
    """가격지수(배당 제외)에 연 배당수익률을 일할로 더해 총수익(TR) 근사 시계열 생성.

    일간 총수익 = 가격수익률 + 연배당수익률/252. O/H/L/C 전체에 동일 배율 적용.
    """
    if annual_yield <= 0:
        return ohlc
    close = ohlc["Close"].astype(float)
    daily = close.pct_change().fillna(0.0) + annual_yield / TRADING_DAYS
    if not daily.empty:
        daily.iloc[0] = 0.0
    tr = close.iloc[0] * (1.0 + daily).cumprod()
    scale = (tr / close).values
    out = ohlc.copy()
    for col in ("Open", "High", "Low", "Close"):
        if col in out.columns:
            out[col] = out[col].astype(float).values * scale
    out.attrs.update(ohlc.attrs)
    return out


def extend_with_synthetic(ticker: str, actual: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """실제 상장 이전 구간을 합성으로 채운 OHLC와 is_synthetic 마스크 반환.

    합성 구간은 Open=High=Low=Close(종가만 존재) 로 취급 — 지정가 매도 체결 판정 시
    고가 정보가 없으므로 종가 기준으로만 체결된다(보수적).
    """
    if ticker not in SYNTH_BASE:
        mask = pd.Series(False, index=actual.index)
        return actual, mask

    base_ticker, lev, fee = SYNTH_BASE[ticker]
    base = get_price(base_ticker)
    synth_close = synthesize_close(base["Close"].astype(float), lev, fee)

    first_actual = actual.index[0]
    pre = synth_close.loc[synth_close.index < first_actual]
    if pre.empty:
        mask = pd.Series(False, index=actual.index)
        return actual, mask

    # 실제 첫 종가에 이어붙도록 스케일 조정
    anchor = synth_close.loc[synth_close.index >= first_actual]
    scale = float(actual["Close"].iloc[0]) / float(anchor.iloc[0]) if not anchor.empty \
        else float(actual["Close"].iloc[0]) / float(pre.iloc[-1])
    pre = pre * scale

    pre_df = pd.DataFrame({"Open": pre, "High": pre, "Low": pre, "Close": pre, "Volume": 0.0})
    out = pd.concat([pre_df, actual])
    out = out[~out.index.duplicated(keep="last")].sort_index()
    mask = pd.Series(out.index < first_actual, index=out.index)
    out.attrs.update(actual.attrs)
    return out, mask
