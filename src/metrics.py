# -*- coding: utf-8 -*-
"""성과·리스크 지표: CAGR, MDD, 샤프, 소르티노, 칼마, XIRR, 무회복 기간 등."""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def total_return(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] == 0:
        return 0.0
    return equity.iloc[-1] / equity.iloc[0] - 1.0


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] <= 0 or equity.iloc[-1] <= 0:
        return 0.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return 0.0
    return (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0


def drawdown_series(equity: pd.Series) -> pd.Series:
    peak = equity.cummax()
    return equity / peak - 1.0


def mdd(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    return float(drawdown_series(equity).min())


def longest_underwater_days(equity: pd.Series) -> int:
    """최장 무회복 기간(일수, 달력일). 전고점 '달성일'부터 회복 직전까지 측정."""
    longest = 0
    peak_val = float("-inf")
    peak_dt = None
    for dt, v in equity.items():
        if peak_dt is None or v >= peak_val:
            peak_val, peak_dt = v, dt
        else:
            longest = max(longest, (dt - peak_dt).days)
    return longest


def annual_volatility(equity: pd.Series) -> float:
    r = equity.pct_change().dropna()
    if len(r) < 2:
        return 0.0
    return float(r.std() * np.sqrt(TRADING_DAYS))


def sharpe(equity: pd.Series, rf: float = 0.0) -> float:
    r = equity.pct_change().dropna()
    if len(r) < 2 or r.std() == 0:
        return 0.0
    excess = r - rf / TRADING_DAYS
    return float(excess.mean() / r.std() * np.sqrt(TRADING_DAYS))


def sortino(equity: pd.Series, rf: float = 0.0) -> float:
    r = equity.pct_change().dropna()
    downside = r[r < 0]
    if len(r) < 2 or len(downside) == 0 or downside.std() == 0:
        return 0.0
    excess = r - rf / TRADING_DAYS
    return float(excess.mean() / downside.std() * np.sqrt(TRADING_DAYS))


def calmar(equity: pd.Series) -> float:
    m = abs(mdd(equity))
    if m == 0:
        return 0.0
    return cagr(equity) / m


def annual_returns(equity: pd.Series) -> pd.Series:
    """연도별 수익률."""
    yearly = equity.resample("YE").last()
    first = equity.iloc[0]
    prev = pd.concat([pd.Series([first]), yearly[:-1]])
    prev.index = yearly.index
    out = yearly / prev - 1.0
    out.index = out.index.year
    return out


def monthly_returns_table(equity: pd.Series) -> pd.DataFrame:
    """월별 수익률 피벗(행=연도, 열=월)."""
    monthly = equity.resample("ME").last().pct_change().dropna()
    df = pd.DataFrame({"y": monthly.index.year, "m": monthly.index.month, "r": monthly.values})
    return df.pivot(index="y", columns="m", values="r")


# ---------------------------------------------------------------- TWR
def twr_index(equity: pd.Series, flows: dict | None = None) -> pd.Series:
    """시간가중 수익률(TWR) 지수 (시작=1).

    적립식·불입·인출이 있으면 평가액 곡선 자체는 '입금 때문에' 커지므로,
    외부 현금흐름(flows: {date: +투입/-인출})의 효과를 제거한 순수 운용 성과를 만든다.
    flows가 없으면 단순 정규화와 동일."""
    if equity.iloc[0] <= 0:
        return equity / max(equity.iloc[0], 1e-9)
    if not flows:
        return equity / equity.iloc[0]
    f = pd.Series(0.0, index=equity.index)
    for d, a in flows.items():
        d = pd.Timestamp(d)
        if d in f.index:
            f.loc[d] += a
    vals = [1.0]
    for i in range(1, len(equity)):
        prev = equity.iloc[i - 1]
        r = ((equity.iloc[i] - f.iloc[i]) / prev - 1.0) if prev > 0 else 0.0
        vals.append(vals[-1] * (1.0 + r))
    return pd.Series(vals, index=equity.index)


# ---------------------------------------------------------------- XIRR
def xnpv(rate: float, dates: list, amounts: list[float]) -> float:
    t0 = dates[0]
    return sum(a / (1.0 + rate) ** ((d - t0).days / 365.0) for d, a in zip(dates, amounts))


def xirr(cashflows: list[tuple]) -> float | None:
    """cashflows: [(date, amount)]. 투입=음수, 회수=양수. 이분법(안정적)."""
    flows = sorted((pd.Timestamp(d), float(a)) for d, a in cashflows if a != 0)
    if len(flows) < 2:
        return None
    dates = [f[0] for f in flows]
    amounts = [f[1] for f in flows]
    if not (any(a < 0 for a in amounts) and any(a > 0 for a in amounts)):
        return None
    lo, hi = -0.9999, 100.0
    f_lo = xnpv(lo, dates, amounts)
    f_hi = xnpv(hi, dates, amounts)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = xnpv(mid, dates, amounts)
        if abs(f_mid) < 1e-8:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def summarize(equity: pd.Series, cashflows: list[tuple] | None = None,
              flows: dict | None = None, net_invested: float | None = None) -> dict:
    """핵심 지표 일괄 계산.

    - 총수익률: 순투입금 대비 단순 수익률 (적립식도 직관적으로 맞는 값)
    - CAGR/MDD/변동성/샤프/소르티노/칼마/무회복일: TWR(불입·인출 효과 제거) 기준
    - XIRR: 실제 현금흐름 기준 연환산 (돈의 시간가치 반영)
    """
    twr = twr_index(equity, flows)
    if net_invested and net_invested > 0:
        simple = equity.iloc[-1] / net_invested - 1.0
    else:
        simple = float(twr.iloc[-1] - 1.0)
    out = {
        "총수익률": simple,
        "TWR수익률": float(twr.iloc[-1] - 1.0),
        "CAGR": cagr(twr),
        "MDD": mdd(twr),
        "연율변동성": annual_volatility(twr),
        "샤프": sharpe(twr),
        "소르티노": sortino(twr),
        "칼마": calmar(twr),
        "최장무회복일": longest_underwater_days(twr),
    }
    out["XIRR"] = xirr(cashflows) if cashflows else None
    return out
