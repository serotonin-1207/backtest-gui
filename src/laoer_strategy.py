# -*- coding: utf-8 -*-
"""라오어 무한매수법 V2.2 (안정형 · 40분할 · 단리) 백테스트.

T값 = 누적매수액 / 1회매수액 (소수점 둘째 자리에서 올림 → 소수 첫째 자리 유지)
  - T < 20  : 전반전 — 1회분의 절반 '평단가 LOC' + 절반 '평단 +(10 - T/2)% LOC'
  - T >= 20 : 후반전 — 1회분 전체 '평단 +(10 - T/2)% LOC'
매도(매일 2건): 보유수량 1/4 '평단 +(10 - T/2)% LOC', 3/4 '평단 +10% 지정가'
소진(T >= 39.1): 기본 '대기', 옵션 '쿼터손절'(보유 1/4 시장가 매도 후 재개)

체결 근사(종가 기준 시뮬레이션):
  - LOC 매수: 종가 <= 지정가 → 종가 체결
  - LOC 매도: 종가 >= 지정가 → 종가 체결
  - 지정가 매도(+10%): 당일 고가 >= 지정가 → 지정가 체결 (합성 구간은 종가로 판정)
  - 부분 매도 시 누적매수액에서 '매도 수량 x 평단'(원금 부분)을 차감 — T값 하락
수수료·슬리피지: 매매 회전액에 (fee_bp+slippage_bp)를 곱해 현금에서 차감(전략 로직은 호가 기준 유지).
실현손익: 매도마다 (순수령 - 수량 x 평단)을 기록해 세금 계산에 사용.
"""
from __future__ import annotations

import math

import pandas as pd

from .backtest_engine import BacktestResult
from .cashflow_engine import expand_events


def _ceil1(x: float) -> float:
    """소수점 둘째 자리에서 올림 (39.12 -> 39.2)."""
    return math.ceil(round(x * 10, 6)) / 10


def run_laoer(
    ohlc: pd.DataFrame,
    name: str,
    principal: float,
    start=None,
    end=None,
    splits: int = 40,
    target_pct: float = 10.0,          # 지정가 매도 목표(%)
    boundary_t: float = 20.0,          # 전/후반 경계 T
    exhaustion: str = "대기",           # "대기" | "쿼터손절"
    quarter_cut_ratio: float = 0.25,
    events: list[dict] | None = None,
    contrib_mode: str = "다음 세트부터 반영",   # or "즉시 현금 추가"
    currency: str = "USD",
    synthetic_mask: pd.Series | None = None,
    fee_bp: float = 0.0,
    slippage_bp: float = 0.0,
    version: str = "V2.2",             # "V2.2"(안정·40분할·단리) | "V3.0"(공격·20분할·복리)
) -> BacktestResult:
    df = ohlc.copy()
    if start:
        df = df.loc[df.index >= pd.Timestamp(start)]
    if end:
        df = df.loc[df.index <= pd.Timestamp(end)]
    if len(df) < 2:
        raise ValueError(f"[{name}] 기간 내 데이터가 부족합니다.")

    c = (fee_bp + slippage_bp) / 1e4     # 편도 거래비용률 (회전액 대비)
    idx = df.index
    close = df["Close"].astype(float)
    high = df["High"].astype(float) if "High" in df else close

    res = BacktestResult(name=name, currency=currency)
    if synthetic_mask is not None:
        res.is_synthetic_used = bool(synthetic_mask.reindex(idx).fillna(False).any())
        syn = synthetic_mask.reindex(idx).fillna(False)
    else:
        syn = pd.Series(False, index=idx)

    ev = expand_events(events or [], idx[0], idx[-1], idx)
    ev_by_date: dict[pd.Timestamp, list[dict]] = {}
    for e in ev:
        ev_by_date.setdefault(e["date"], []).append(e)

    # ------- 상태
    set_principal = principal          # 이번 세트 원금 (V2.2 단리: 세트마다 동일)
    one_buy = set_principal / splits
    shares = 0.0
    avg = 0.0
    cum_buy = 0.0                      # 누적매수액(매도 시 원금부분 차감)
    cash = principal                   # 원금 + 실현손익 포함 보유 현금
    pending_contrib = 0.0              # 다음 세트 반영 대기 불입금
    set_no = 1
    set_start = idx[0]
    set_invested_max = 0.0
    set_cash_base = cash               # 세트 시작 시점 현금(외부 흐름 시 조정) → 세트손익 산출
    waiting = False                    # 소진 후 대기 상태

    res.cashflows.append((idx[0], -principal))
    res.total_invested = principal

    sets_log: list[dict] = []
    t_list, eq_list, cash_list = [], [], []

    def t_value() -> float:
        return _ceil1(cum_buy / one_buy) if one_buy > 0 else 0.0

    def offset_pct(T: float) -> float:
        """LOC 매수/1-4 매도 오프셋. V2.2=(target-T/2)%, V3.0=(15-1.5T)%."""
        if version == "V3.0":
            return (15.0 - 1.5 * T) / 100.0
        return (target_pct - T / 2) / 100.0

    star_pct = 0.15 if version == "V3.0" else target_pct / 100.0   # 3/4 지정가 목표

    def do_buy(spend: float, price: float) -> None:
        """호가(price) 기준으로 매수 + 거래비용 차감. 전략 로직(평단·cum_buy)은 호가 기준 유지."""
        nonlocal shares, avg, cum_buy, cash
        q = spend / price
        avg = (avg * shares + spend) / (shares + q) if (shares + q) > 0 else price
        shares += q
        cum_buy += spend
        cash -= spend
        cost = spend * c
        cash -= cost
        res.total_fees += cost

    def do_sell(q: float, price: float, dt) -> None:
        """q주를 price에 매도 + 거래비용 차감. 실현손익 기록. cum_buy에서 원금부분 차감."""
        nonlocal shares, cum_buy, cash
        if q <= 0:
            return
        proceeds = q * price
        cost = proceeds * c
        cash += proceeds - cost
        res.total_fees += cost
        res.realized_gains.append((dt, (proceeds - cost) - q * avg))
        shares -= q
        cum_buy = max(cum_buy - q * avg, 0.0)

    def close_set(dt, reason: str):
        nonlocal shares, avg, cum_buy, set_no, set_start, set_invested_max
        nonlocal set_principal, one_buy, cash, pending_contrib, waiting, set_cash_base
        sets_log.append({
            "세트": set_no, "시작일": set_start.date(), "종료일": dt.date(),
            "소요일": (dt - set_start).days, "최대투입액": round(set_invested_max, 2),
            "세트손익": round(cash - set_cash_base, 2),
            "종료사유": reason,
        })
        # 다음 세트 준비
        if pending_contrib > 0:
            set_principal += pending_contrib
            pending_contrib = 0.0
        if version == "V3.0":
            set_principal = cash        # 복리: 현재 자본으로 1회 매수금 재계산
        one_buy = set_principal / splits
        shares = 0.0
        avg = 0.0
        cum_buy = 0.0
        set_no += 1
        set_start = dt
        set_invested_max = 0.0
        set_cash_base = cash
        waiting = False

    for i, dt in enumerate(idx):
        px = close.loc[dt]
        hi = px if syn.loc[dt] else high.loc[dt]

        # ---------- 외부 현금흐름 (불입/인출)
        for e in ev_by_date.get(dt, []):
            if e["kind"] == "불입":
                res.cashflows.append((dt, -e["amount"]))
                res.total_invested += e["amount"]
                res.total_contrib += e["amount"]
                res.flows[dt] = res.flows.get(dt, 0.0) + e["amount"]
                res.events_log.append({"date": dt, "구분": "추가불입", "금액": e["amount"]})
                cash += e["amount"]
                set_cash_base += e["amount"]
                if contrib_mode == "즉시 현금 추가":
                    set_principal += e["amount"]  # 원금 소진 한도만 확대, 1회 매수금 유지
                else:  # 다음 세트부터 반영
                    pending_contrib += e["amount"]
            else:  # 인출: 현금 우선, 부족 시 주식 일부 매도
                take = min(e["amount"], cash + shares * px)
                if take <= 0:
                    continue
                from_cash = min(cash, take)
                cash -= from_cash
                remain = take - from_cash
                if remain > 0 and shares > 0:
                    q = min(shares, remain / px)
                    do_sell(q, px, dt)
                res.cashflows.append((dt, take))
                res.total_withdraw += take
                res.flows[dt] = res.flows.get(dt, 0.0) - take
                set_cash_base -= take
                res.events_log.append({"date": dt, "구분": "중도인출", "금액": take})

        # ---------- 세트 시작(첫 매수): 1회분 종가 매수
        if shares == 0.0 and cum_buy == 0.0:
            spend = min(one_buy, cash)
            if spend > 0 and px > 0:
                do_buy(spend, px)
                set_invested_max = max(set_invested_max, cum_buy)
            t_list.append(t_value())
            eq_list.append(cash + shares * px)
            cash_list.append(cash)
            continue

        T = t_value()
        sell_pct = offset_pct(T)                        # V2.2 (10-T/2)% / V3.0 (15-1.5T)%
        loc_sell_limit = avg * (1 + sell_pct)
        star_limit = avg * (1 + star_pct)               # 3/4 지정가 (+10% / +15%)

        # ---------- 매도 (보유 시, 매일 2건)
        sold_all = False
        if shares > 0:
            pre_shares = shares
            q1 = pre_shares * 0.25
            q2 = pre_shares - q1
            s1 = s2 = False
            if px >= loc_sell_limit:                    # 1/4 LOC 매도 → 종가 체결
                do_sell(q1, px, dt)
                s1 = True
            if hi >= star_limit:                        # 3/4 지정가 매도 → 지정가 체결
                do_sell(q2, star_limit, dt)
                s2 = True
            if s1 and s2:
                sold_all = True
        if sold_all or (shares > 0 and shares < 1e-9):
            close_set(dt, "전량매도")
            t_list.append(0.0)
            eq_list.append(cash + shares * px)
            cash_list.append(cash)
            continue

        # ---------- 소진 처리
        T = t_value()
        exhausted = cum_buy >= set_principal - one_buy * 0.9  # T >= 39.1 근사
        if exhausted:
            if exhaustion == "쿼터손절" and shares > 0 and not waiting:
                q = shares * quarter_cut_ratio
                do_sell(q, px, dt)
                res.events_log.append({"date": dt, "구분": "쿼터손절", "금액": q * px})
            else:
                waiting = True

        # ---------- 매수 (소진·대기 아니면)
        T = t_value()
        remaining = max(set_principal - cum_buy, 0.0)
        if remaining > 1e-9 and not waiting and shares >= 0:
            buy_pct = offset_pct(T)                     # V2.2 (10-T/2)% / V3.0 (15-1.5T)%
            loc_buy_limit = avg * (1 + buy_pct)
            budget = min(one_buy, remaining, cash)
            spent = 0.0
            if T < boundary_t:                          # 전반전: 절반 평단 LOC + 절반 (10-T/2)% LOC
                half = budget / 2
                if px <= avg and half > 0:
                    spent += half
                if px <= loc_buy_limit and half > 0:
                    spent += half
            else:                                       # 후반전: 전체 (10-T/2)% LOC
                if px <= loc_buy_limit and budget > 0:
                    spent = budget
            if spent > 0 and px > 0:
                do_buy(spent, px)
                set_invested_max = max(set_invested_max, cum_buy)

        t_list.append(t_value())
        eq_list.append(cash + shares * px)
        cash_list.append(cash)

    # ---------- 마감
    res.equity = pd.Series(eq_list, index=idx)
    res.equity_gross = res.equity
    res.t_series = pd.Series(t_list, index=idx)
    res.cash_series = pd.Series(cash_list, index=idx)
    res.cashflows.append((idx[-1], res.final_value))
    if shares > 0:  # 진행 중 세트 청산 가정 → 실현손익(세금용)
        res.realized_gains.append((idx[-1], shares * close.iloc[-1] - shares * avg))
        sets_log.append({
            "세트": set_no, "시작일": set_start.date(), "종료일": None,
            "소요일": (idx[-1] - set_start).days, "최대투입액": round(set_invested_max, 2),
            "세트손익": round(shares * close.iloc[-1] - cum_buy, 2), "종료사유": "진행중",
        })
    res.laoer_sets = pd.DataFrame(sets_log)
    return res
