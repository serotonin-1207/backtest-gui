# -*- coding: utf-8 -*-
"""거치식/적립식 백테스트 엔진 (일별 시뮬레이션, 대출 옵션 A 포함).

현금흐름 부호 규약: 사용자 관점 — 투입(불입) = 음수, 인출·최종회수 = 양수.
수수료·슬리피지(bp)와 실현손익(세금 계산용)을 지원한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .cashflow_engine import dca_schedule, expand_events, snap_to_trading_day


@dataclass
class BacktestResult:
    name: str
    equity: pd.Series = None            # 순자산(대출원금 차감 후)
    equity_gross: pd.Series = None      # 대출 차감 전 평가액
    cashflows: list = field(default_factory=list)   # [(date, amount)] XIRR용
    flows: dict = field(default_factory=dict)       # {date: +투입/-인출} TWR용 (시작원금·최종회수 제외)
    events_log: list = field(default_factory=list)  # 불입/인출/이자 내역
    realized_gains: list = field(default_factory=list)  # [(date, 실현손익)] 세금용 (자산통화)
    total_invested: float = 0.0         # 총투입금(원금+불입)
    total_contrib: float = 0.0          # 추가 불입 합계
    total_withdraw: float = 0.0         # 중도 인출 합계
    total_fees: float = 0.0             # 매매 수수료+슬리피지 비용 합계
    loan_used: bool = False
    loan_amount: float = 0.0
    total_interest: float = 0.0
    currency: str = "USD"
    is_synthetic_used: bool = False
    laoer_sets: pd.DataFrame = None     # 라오어 전략만 사용
    t_series: pd.Series = None
    cash_series: pd.Series = None

    @property
    def final_value(self) -> float:
        return float(self.equity.iloc[-1]) if self.equity is not None and len(self.equity) else 0.0

    @property
    def net_invested(self) -> float:
        return self.total_invested - self.total_withdraw


def run_backtest(
    ohlc: pd.DataFrame,
    name: str,
    mode: str,                       # "거치식" | "적립식"
    capital: float,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    dca_freq: str = "매월",
    dca_years: float | None = None,
    events: list[dict] | None = None,
    loan_on: bool = False,
    loan_amount: float = 0.0,
    loan_rate: float = 0.045,
    currency: str = "USD",
    synthetic_mask: pd.Series | None = None,
    fee_bp: float = 0.0,             # 편도 매매 수수료 (basis point, 1bp=0.01%)
    slippage_bp: float = 0.0,        # 편도 슬리피지 (basis point)
) -> BacktestResult:
    close = ohlc["Close"].astype(float)
    if start:
        close = close.loc[close.index >= pd.Timestamp(start)]
    if end:
        close = close.loc[close.index <= pd.Timestamp(end)]
    if len(close) < 2:
        raise ValueError(f"[{name}] 기간 내 데이터가 부족합니다.")

    fee = fee_bp / 1e4
    slip = slippage_bp / 1e4
    idx = close.index
    res = BacktestResult(name=name, currency=currency,
                         loan_used=loan_on, loan_amount=loan_amount if loan_on else 0.0)
    if synthetic_mask is not None:
        res.is_synthetic_used = bool(synthetic_mask.reindex(idx).fillna(False).any())

    # ------- 이벤트/스케줄 준비
    ev = expand_events(events or [], idx[0], idx[-1], idx)
    ev_by_date: dict[pd.Timestamp, list[dict]] = {}
    for e in ev:
        ev_by_date.setdefault(e["date"], []).append(e)

    buy_dates: dict[pd.Timestamp, float] = {}
    if mode == "거치식":
        buy_dates[idx[0]] = capital
    else:  # 적립식
        sched = dca_schedule(idx[0], idx, dca_freq, dca_years)
        per = capital / max(len(sched), 1)
        for d in sched:
            buy_dates[d] = per

    # 대출(옵션 A: 시작일 일시 실행, 매년 이자 차감, 종료일 원금 상환)
    loan_outstanding = loan_amount if loan_on else 0.0
    if loan_on and loan_amount > 0:
        buy_dates[idx[0]] = buy_dates.get(idx[0], 0.0) + loan_amount
        res.events_log.append({"date": idx[0], "구분": "대출실행", "금액": loan_amount})
    interest_dates = set()
    if loan_on and loan_amount > 0:
        y = idx[0] + pd.DateOffset(years=1)
        while y <= idx[-1]:
            s = snap_to_trading_day(y, idx)
            if s is not None:
                interest_dates.add(s)
            y += pd.DateOffset(years=1)

    # ------- 상태 (shares/cash/cost_basis)
    shares = 0.0
    cash = 0.0
    cost_basis = 0.0     # 보유 주식의 총 취득원가 (세금 손익 계산용)
    equity_list, gross_list, cash_list = [], [], []

    def buy(amt: float, dt) -> None:
        """외부 자금 amt로 매수 (수수료·슬리피지 반영). 취득원가에 amt 전액 가산."""
        nonlocal shares, cost_basis
        if amt <= 0:
            return
        pxb = px * (1 + slip)
        q = amt * (1 - fee) / pxb
        res.total_fees += amt - q * px          # 수수료+슬리피지 비용
        shares += q
        cost_basis += amt

    def sell_net(net_needed: float, dt) -> float:
        """net_needed 만큼의 순현금을 확보하도록 주식 매도. 실현손익 기록. 실제 매도 순현금 반환."""
        nonlocal shares, cost_basis
        if net_needed <= 0 or shares <= 0:
            return 0.0
        unit_net = px * (1 - slip) * (1 - fee)   # 1주당 실수령
        q = min(shares, net_needed / unit_net)
        avg = cost_basis / shares if shares > 0 else px
        proceeds = q * unit_net
        gain = proceeds - q * avg
        res.total_fees += q * px - proceeds
        res.realized_gains.append((dt, gain))
        shares -= q
        cost_basis -= q * avg
        return proceeds

    for dt in idx:
        px = close.loc[dt]
        # 정기 매수 (외부 자금 유입 → 현금흐름 기록)
        if dt in buy_dates:
            amt = buy_dates[dt]
            user_amt = amt - (loan_amount if (loan_on and dt == idx[0]) else 0.0)
            if user_amt > 0:
                res.cashflows.append((dt, -user_amt))
                res.total_invested += user_amt
                if dt != idx[0]:  # 시작일 이후 적립 매수 = 외부 자금 유입 (TWR 조정)
                    res.flows[dt] = res.flows.get(dt, 0.0) + user_amt
            buy(amt, dt)
        # 추가 불입/중도 인출
        for e in ev_by_date.get(dt, []):
            if e["kind"] == "불입":
                res.cashflows.append((dt, -e["amount"]))
                res.total_invested += e["amount"]
                res.total_contrib += e["amount"]
                res.flows[dt] = res.flows.get(dt, 0.0) + e["amount"]
                buy(e["amount"], dt)
                res.events_log.append({"date": dt, "구분": "추가불입", "금액": e["amount"]})
            else:  # 인출
                value = shares * px * (1 - slip) * (1 - fee) + cash
                take = min(e["amount"], value)
                if take <= 0:
                    continue
                from_cash = min(cash, take)
                cash -= from_cash
                need = take - from_cash
                got = sell_net(need, dt)
                cash += got - need           # 매도 초과분(반올림 오차)은 현금에
                res.cashflows.append((dt, take))
                res.total_withdraw += take
                res.flows[dt] = res.flows.get(dt, 0.0) - take
                res.events_log.append({"date": dt, "구분": "중도인출", "금액": take})
        # 대출 이자(매년) — 주식 일부 매도로 납부
        if dt in interest_dates and loan_outstanding > 0:
            interest = loan_outstanding * loan_rate
            pay = min(interest, shares * px * (1 - slip) * (1 - fee) + cash)
            from_cash = min(cash, pay)
            cash -= from_cash
            need = pay - from_cash
            got = sell_net(need, dt)
            cash += got - need
            res.total_interest += pay
            res.events_log.append({"date": dt, "구분": "대출이자", "금액": pay})

        gross = shares * px + cash
        gross_list.append(gross)
        equity_list.append(gross - loan_outstanding)
        cash_list.append(cash)

    res.equity_gross = pd.Series(gross_list, index=idx)
    res.equity = pd.Series(equity_list, index=idx)
    res.cash_series = pd.Series(cash_list, index=idx)
    # 종료 시점: 보유 주식 청산 가정 → 미실현 손익을 실현손익으로 기록(세금용)
    if shares > 0:
        final_px = close.iloc[-1]
        avg = cost_basis / shares
        res.realized_gains.append((idx[-1], shares * final_px - cost_basis))
        _ = avg
    # 대출 원금 상환 후 잔액 회수 → XIRR 마지막 현금흐름
    res.cashflows.append((idx[-1], res.final_value))
    if loan_on and loan_amount > 0:
        res.events_log.append({"date": idx[-1], "구분": "대출상환", "금액": loan_amount})
    return res
