# -*- coding: utf-8 -*-
"""롤링 시작일 검증으로 투자 자산·주기·기간·방식을 함께 비교한다."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .cashflow_engine import dca_schedule
from .metrics import mdd

FREQUENCIES = ["매일", "매주", "매월", "매분기", "매년"]
STRATEGIES = ["거치식", "적립식", "라오어 무한매수법", "거치식 후 적립식"]


def _fast_xirr_values(years: np.ndarray, amounts: np.ndarray) -> float | None:
    """이미 숫자로 변환된 연수·현금흐름의 XIRR."""
    if not ((amounts < 0).any() and (amounts > 0).any()):
        return None
    try:
        from scipy.optimize import brentq

        def objective(rate: float) -> float:
            return float(np.sum(amounts / (1.0 + rate) ** years))

        return float(brentq(objective, -0.9999, 100.0, xtol=1e-8, maxiter=60))
    except (ImportError, ValueError, RuntimeError):
        pass
    rate = 0.10
    scale = max(float(np.abs(amounts).sum()), 1.0)
    for _ in range(15):
        base = 1.0 + rate
        if base <= 0:
            break
        powers = base ** years
        value = float(np.sum(amounts / powers))
        derivative = float(np.sum(-years * amounts / (powers * base)))
        if abs(value) < 1e-8 * scale:
            return rate
        if derivative == 0 or not np.isfinite(derivative):
            break
        new_rate = rate - value / derivative
        if not np.isfinite(new_rate) or new_rate <= -0.9999 or new_rate > 100:
            break
        rate = new_rate
    lo, hi = -0.9999, 100.0
    f_lo = float(np.sum(amounts / (1.0 + lo) ** years))
    for _ in range(60):
        mid = (lo + hi) / 2
        f_mid = float(np.sum(amounts / (1.0 + mid) ** years))
        if abs(f_mid) < 1e-8 * scale:
            return mid
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo = mid
            f_lo = f_mid
    return (lo + hi) / 2


def _fast_xirr(cashflows: list[tuple]) -> float | None:
    """대량 최적화용 XIRR."""
    if len(cashflows) < 2:
        return None
    dates = pd.to_datetime([d for d, _ in cashflows])
    amounts = np.asarray([a for _, a in cashflows], dtype=float)
    years = (dates - dates[0]).days.to_numpy(dtype=float) / 365.0
    return _fast_xirr_values(years, amounts)


@dataclass(frozen=True)
class RoutineConfig:
    asset: str
    years: int
    strategy: str
    frequency: str


def _contribution_result(
    close: pd.Series,
    strategy: str,
    frequency: str,
    initial_ratio: float,
    fee_bp: float,
) -> dict:
    """총투입금 1을 기준으로 거치·적립·혼합 전략을 계산한다."""
    idx = close.index
    fee = max(float(fee_bp), 0.0) / 1e4
    if strategy == "거치식":
        allocations = {idx[0]: 1.0}
    else:
        schedule = dca_schedule(idx[0], idx, frequency, None)
        if not schedule:
            schedule = [idx[0]]
        allocations: dict[pd.Timestamp, float] = {}
        if strategy == "적립식":
            each = 1.0 / len(schedule)
            for d in schedule:
                allocations[d] = allocations.get(d, 0.0) + each
        else:  # 거치식 후 적립식
            initial = min(max(float(initial_ratio), 0.0), 1.0)
            allocations[idx[0]] = initial
            later = [d for d in schedule if d != idx[0]]
            if later:
                each = (1.0 - initial) / len(later)
                for d in later:
                    allocations[d] = allocations.get(d, 0.0) + each
            else:
                allocations[idx[0]] += 1.0 - initial

    prices = close.to_numpy(dtype=float)
    allocation_values = np.zeros(len(idx), dtype=float)
    allocation_dates = list(allocations)
    positions = idx.get_indexer(allocation_dates)
    for pos, amount in zip(positions, allocations.values()):
        if pos >= 0:
            allocation_values[pos] += float(amount)
    shares = np.cumsum(allocation_values * (1.0 - fee) / prices)
    equity = shares * prices
    final = float(equity[-1]) * (1.0 - fee)
    contribution_positions = np.flatnonzero(allocation_values > 0)
    xirr_years = (
        (idx[contribution_positions] - idx[0]).days.to_numpy(dtype=float) / 365.0
    )
    xirr_amounts = -allocation_values[contribution_positions]
    xirr_years = np.append(xirr_years, (idx[-1] - idx[0]).days / 365.0)
    xirr_amounts = np.append(xirr_amounts, final)
    flows = allocation_values.copy()
    flows[0] = 0.0
    daily = np.zeros(len(equity), dtype=float)
    valid = equity[:-1] > 0
    target = np.nonzero(valid)[0] + 1
    daily[target] = (equity[target] - flows[target]) / equity[target - 1] - 1.0
    perf = np.cumprod(1.0 + daily)
    peak = np.maximum.accumulate(perf)
    drawdown = float(np.min(perf / peak - 1.0))
    return {
        "배수": final,
        "XIRR": _fast_xirr_values(xirr_years, xirr_amounts),
        "MDD": drawdown,
        "투자횟수": len(allocations),
    }


def _laoer_result(
    ohlc: pd.DataFrame,
    fee_bp: float,
    version: str,
    fill_buffer_bp: float,
) -> dict:
    """추천 대량 계산용 경량 라오어 시뮬레이터(외부 이벤트·상세 로그 없음)."""
    splits = 20 if version == "V3.0" else 40
    target = 15.0 if version == "V3.0" else 10.0
    prices = ohlc["Close"].to_numpy(dtype=float)
    highs = ohlc["High"].to_numpy(dtype=float) if "High" in ohlc else prices
    cost_rate = max(float(fee_bp), 0.0) / 1e4
    fill_buffer = max(float(fill_buffer_bp), 0.0) / 1e4
    set_principal = 1.0
    one_buy = set_principal / splits
    cash, shares, avg, cum_buy = 1.0, 0.0, 0.0, 0.0
    equities = []
    buy_count = 0

    def t_value() -> float:
        return np.ceil((cum_buy / one_buy) * 10.0 - 1e-10) / 10.0 if one_buy > 0 else 0.0

    def do_buy(spend: float, price: float) -> None:
        nonlocal cash, shares, avg, cum_buy, buy_count
        spend = min(spend, cash / (1.0 + cost_rate))
        if spend <= 0:
            return
        q = spend / price
        avg = (avg * shares + spend) / (shares + q)
        shares += q
        cum_buy += spend
        cash -= spend * (1.0 + cost_rate)
        buy_count += 1

    def do_sell(q: float, price: float) -> None:
        nonlocal cash, shares, cum_buy
        if q <= 0:
            return
        cash += q * price * (1.0 - cost_rate)
        shares -= q
        cum_buy = max(cum_buy - q * avg, 0.0)

    for px, hi in zip(prices, highs):
        if shares <= 1e-12 and cum_buy <= 1e-12:
            do_buy(one_buy, px)
            equities.append(cash + shares * px)
            continue
        t = t_value()
        offset = (15.0 - 1.5 * t) / 100.0 if version == "V3.0" else (target - t / 2) / 100.0
        star_pct = 0.15 if version == "V3.0" else target / 100.0
        pre_shares = shares
        q1, q2 = pre_shares * 0.25, pre_shares * 0.75
        s1 = px >= avg * (1.0 + offset) * (1.0 + fill_buffer) * (1.0 - 1e-12)
        s2 = hi >= avg * (1.0 + star_pct) * (1.0 + fill_buffer) * (1.0 - 1e-12)
        if s1:
            do_sell(q1, px)
        if s2:
            do_sell(q2, avg * (1.0 + star_pct))
        if s1 and s2:
            if version == "V3.0":
                set_principal = cash
            one_buy = set_principal / splits
            shares, avg, cum_buy = 0.0, 0.0, 0.0
            equities.append(cash)
            continue

        exhausted = cum_buy >= set_principal - one_buy * 0.9
        if not exhausted:
            t = t_value()
            offset = (15.0 - 1.5 * t) / 100.0 if version == "V3.0" else (target - t / 2) / 100.0
            remaining = max(set_principal - cum_buy, 0.0)
            budget = min(one_buy, remaining)
            spend = 0.0
            if t < 20.0:
                half = budget / 2
                if px <= avg * (1.0 - fill_buffer) * (1.0 + 1e-12):
                    spend += half
                if px <= avg * (1.0 + offset) * (1.0 - fill_buffer) * (1.0 + 1e-12):
                    spend += half
            elif px <= avg * (1.0 + offset) * (1.0 - fill_buffer) * (1.0 + 1e-12):
                spend = budget
            do_buy(spend, px)
        equities.append(cash + shares * px)

    equity = pd.Series(equities, index=ohlc.index)
    final = float(equity.iloc[-1])
    return {
        "배수": final,
        "XIRR": final ** (365.0 / max((ohlc.index[-1] - ohlc.index[0]).days, 1)) - 1.0,
        "MDD": mdd(equity),
        "투자횟수": buy_count,
    }


def _score(row: dict, objective: str) -> float:
    med = row["중앙연수익률"]
    p10 = row["하위10%연수익률"]
    med_dd = row["중앙MDD"]
    worst_dd = row["최악MDD"]
    positive = row["수익구간비율"]
    reliability = min(row["검증구간수"], 20) / 20
    if objective == "수익 우선":
        raw = 0.70 * med + 0.30 * p10
    elif objective == "방어 우선":
        raw = 0.30 * med + 0.15 * p10 + 0.30 * med_dd + 0.20 * worst_dd + 0.05 * (positive - 0.5)
    else:
        raw = 0.45 * med + 0.25 * p10 + 0.15 * med_dd + 0.10 * worst_dd + 0.05 * (positive - 0.5)
    return float(raw * (0.85 + 0.15 * reliability))


def optimize_routines(
    price_data: dict[str, pd.DataFrame],
    durations: list[int],
    objective: str = "균형",
    step_months: int = 6,
    initial_ratio: float = 0.5,
    fee_bp: float = 5.0,
    laoer_version: str = "V2.2",
    fill_buffer_bp: float = 20.0,
    min_windows: int = 5,
) -> pd.DataFrame:
    """후보 조합별 롤링 결과를 집계해 점수가 높은 순서로 반환한다."""
    if not price_data:
        return pd.DataFrame()
    common_start = max(df.index.min() for df in price_data.values())
    common_end = min(df.index.max() for df in price_data.values())
    records = []

    for years in sorted(set(int(y) for y in durations if int(y) > 0)):
        last_start = common_end - pd.DateOffset(years=years)
        starts = []
        d = pd.Timestamp(common_start)
        while d <= last_start:
            starts.append(d)
            d += pd.DateOffset(months=max(int(step_months), 1))
        if len(starts) < min_windows:
            continue

        configs = []
        for asset in price_data:
            configs.append(RoutineConfig(asset, years, "거치식", "1회"))
            configs.append(RoutineConfig(asset, years, "라오어 무한매수법", "매일 주문"))
            for freq in FREQUENCIES:
                configs.append(RoutineConfig(asset, years, "적립식", freq))
                configs.append(RoutineConfig(asset, years, "거치식 후 적립식", freq))

        for cfg in configs:
            df = price_data[cfg.asset]
            outcomes = []
            for start in starts:
                end = start + pd.DateOffset(years=years)
                window = df.loc[(df.index >= start) & (df.index <= end)].copy()
                if len(window) < max(120, int(years * 200)):
                    continue
                if cfg.strategy == "라오어 무한매수법":
                    out = _laoer_result(window, fee_bp, laoer_version, fill_buffer_bp)
                else:
                    out = _contribution_result(
                        window["Close"].astype(float),
                        cfg.strategy,
                        cfg.frequency,
                        initial_ratio,
                        fee_bp,
                    )
                if out["XIRR"] is not None and np.isfinite(out["XIRR"]):
                    outcomes.append(out)
            if len(outcomes) < min_windows:
                continue
            xirrs = np.array([o["XIRR"] for o in outcomes], dtype=float)
            mdds = np.array([o["MDD"] for o in outcomes], dtype=float)
            multiples = np.array([o["배수"] for o in outcomes], dtype=float)
            row = {
                "자산": cfg.asset,
                "투자기간": f"{years}년",
                "기간(년)": years,
                "투자방식": cfg.strategy,
                "투자주기": cfg.frequency,
                "검증구간수": len(outcomes),
                "중앙연수익률": float(np.median(xirrs)),
                "하위10%연수익률": float(np.quantile(xirrs, 0.10)),
                "중앙MDD": float(np.median(mdds)),
                "최악MDD": float(mdds.min()),
                "수익구간비율": float((xirrs > 0).mean()),
                "중앙최종배수": float(np.median(multiples)),
                "평균투자횟수": float(np.mean([o["투자횟수"] for o in outcomes])),
            }
            row["종합점수"] = _score(row, objective)
            records.append(row)
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records).sort_values(
        ["종합점수", "하위10%연수익률"], ascending=False
    ).reset_index(drop=True)


def dimension_winners(results: pd.DataFrame) -> dict[str, pd.Series]:
    """전체 1위와 각 질문별 최고 조합을 반환한다."""
    if results.empty:
        return {}

    def representative(pool: pd.DataFrame, column: str) -> pd.Series:
        # 다른 조건 한두 개의 우연한 최고값이 아니라 그룹 중앙점수가 가장 높은 값을 선택한다.
        winning_value = pool.groupby(column)["종합점수"].median().idxmax()
        candidates = pool[pool[column] == winning_value]
        return candidates.sort_values("종합점수", ascending=False).iloc[0]

    frequency_pool = results[
        results["투자방식"].isin(["적립식", "거치식 후 적립식"])
    ]
    return {
        "전체": results.iloc[0],
        "투자주기": representative(frequency_pool, "투자주기"),
        "투자기간": representative(results, "투자기간"),
        "자산": representative(results, "자산"),
        "투자방식": representative(results, "투자방식"),
    }
