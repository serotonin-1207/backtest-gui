# -*- coding: utf-8 -*-
"""라오어 무한매수법 V4.0 — 40분할, TQQQ·SOXL, GENERAL/REVERSE/COMPLETED.

명세(V4.0)는 라이브 주문 생성용이라, 본 모듈은 그 결정론적 계산 로직을 그대로 구현하고
일봉(OHLC) 백테스트로 각색한다. 각색·미확정(§30) 결정은 아래에 명시한다.

체결 근사(일봉):
  - LOC 매수(지정가 L): 종가 ≤ L 이면 종가에 체결
  - LOC 매도(지정가 L): 종가 ≥ L 이면 종가에 체결
  - MOC 매도: 종가에 무조건 체결
  - 지정가(LIMIT) 매도(+15%/+20%, 프리+본장+애프터): 당일 고가 ≥ 지정가 이면 지정가에 체결
  - 리버스 별지점 위 매도 / 아래 매수: 종가 vs 별지점(직전5일 평균)으로 한쪽 체결

§30 각색 결정:
  1. LOC 사다리 없음 — 지정가 1점에 예산 전액(명세상 lower ladder는 optional).
  2. 초기 매수 큰수 상단배수(1.10~1.15)는 '체결 보장'용 → 백테스트에선 종가 체결로 처리.
  3. 부분체결 T: 명세 기본 이산 규칙만(전체 +1 / 절반 +0.5).
  4. 쿼터매도 수량 = floor(qty*0.25), 리버스 매도 = floor(qty/20) (명세 §11/§16).
  5. 별지점 위 매도 = LOC(종가≥별), 아래 매수 = LOC(종가≤별).
  6. 수수료·세금은 현금에만 반영, T엔 미반영.
  7~9. 프리/본장/애프터·휴장·분할은 일봉/수정주가로 흡수.
  10. 환율·원화성과는 앱 상위(gui)에서 처리.
  * 주식수량: 백테스트 수익률 정확도를 위해 '연속(소수)'으로 계산(실매매는 §27 floor).
"""
from __future__ import annotations

import pandas as pd

from .backtest_engine import BacktestResult

SPLITS = 40
SUPPORTED_SYMBOLS = ("TQQQ", "SOXL")

# §3 종목별 상수
SYMBOL_CONST = {
    "TQQQ": {"final_tp": 0.15, "reverse_exit_loss": -0.15,
             "star_base": 15.0, "star_coef": 0.75, "reverse_exit_mult": 0.85},
    "SOXL": {"final_tp": 0.20, "reverse_exit_loss": -0.20,
             "star_base": 20.0, "star_coef": 1.00, "reverse_exit_mult": 0.80},
}


class UnsupportedSymbolError(ValueError):
    pass


class InsufficientPriceDataError(ValueError):
    pass


def _const(symbol: str) -> dict:
    if symbol not in SYMBOL_CONST:
        raise UnsupportedSymbolError(f"V4.0 지원 종목은 TQQQ·SOXL 뿐입니다: {symbol}")
    return SYMBOL_CONST[symbol]


# ---------------------------------------------------------------- §5,6 일반모드 별
def calculate_general_star_percent(symbol: str, T: float) -> float:
    c = _const(symbol)
    return c["star_base"] - c["star_coef"] * T


def calculate_general_star_price(symbol: str, average_price: float, T: float) -> float:
    star_percent = calculate_general_star_percent(symbol, T)
    return average_price * (1.0 + star_percent / 100.0)


# ---------------------------------------------------------------- §7 1회 매수 시도금액
def calculate_general_daily_budget(cash: float, T: float) -> float:
    denominator = SPLITS - T
    if denominator <= 0:
        return 0.0
    return cash / denominator


# ---------------------------------------------------------------- §11 쿼터매도
def calculate_general_quarter_sell_quantity(quantity: float) -> float:
    from math import floor
    return float(floor(quantity * 0.25))


# ---------------------------------------------------------------- §12 최종 지정가 매도
def calculate_final_sell_price(symbol: str, average_price: float) -> float:
    return average_price * (1.0 + _const(symbol)["final_tp"])


# ---------------------------------------------------------------- §17 리버스 별지점
def calculate_reverse_star_price(recent_closes) -> float:
    closes = list(recent_closes)
    if len(closes) < 5:
        raise InsufficientPriceDataError("리버스 별지점: 직전 5거래일 종가 필요")
    latest_five = closes[-5:]
    return sum(latest_five) / 5.0


# ---------------------------------------------------------------- §16 리버스 매도수량
def calculate_reverse_sell_quantity(quantity: float) -> float:
    from math import floor
    return float(floor(quantity / 20.0))


# ---------------------------------------------------------------- §19 리버스 쿼터매수
def calculate_reverse_buy_budget(cash: float) -> float:
    return cash / 4.0


# ---------------------------------------------------------------- T 업데이트
def update_T_after_general_quarter_sell(T: float) -> float:
    return T * 0.75


def update_T_after_final_sell_with_buy(previous_T: float, full_buy: bool) -> float:
    return previous_T * 0.25 + (1.0 if full_buy else 0.5)


def update_T_after_reverse_sell(T: float) -> float:
    return T * 0.95


def update_T_after_reverse_buy(T: float) -> float:
    return T + (40.0 - T) * 0.25


# ---------------------------------------------------------------- 모드 판정 §4,15,21,22
def should_enter_reverse_mode(mode: str, T: float) -> bool:
    return mode == "GENERAL" and T > 39.0


def should_exit_reverse_mode(symbol: str, close_price: float, average_price: float) -> bool:
    return close_price > average_price * _const(symbol)["reverse_exit_mult"]


def is_cycle_completed(quantity: float) -> bool:
    return quantity <= 1e-12


# ---------------------------------------------------------------- §27 수량
def quantity_from_budget(budget: float, price: float, fractional: bool = True) -> float:
    if budget <= 0 or price <= 0:
        return 0.0
    q = budget / price
    if fractional:
        return q
    from math import floor
    return float(floor(q))


# ================================================================ 백테스트 시뮬레이션
def run_laoer_v4(
    ohlc: pd.DataFrame,
    name: str,
    principal: float,
    symbol: str,
    start=None,
    end=None,
    fee_bp: float = 0.0,
    slippage_bp: float = 0.0,
    currency: str = "USD",
    fractional: bool = True,
) -> BacktestResult:
    """V4.0 일봉 백테스트. principal 전액을 시작일 현금으로 두고 사이클을 반복한다."""
    if symbol not in SUPPORTED_SYMBOLS:
        raise UnsupportedSymbolError(f"V4.0 지원 종목은 TQQQ·SOXL 뿐입니다: {symbol}")
    df = ohlc.copy()
    if start:
        df = df.loc[df.index >= pd.Timestamp(start)]
    if end:
        df = df.loc[df.index <= pd.Timestamp(end)]
    if len(df) < 2:
        raise ValueError(f"[{name}] 기간 내 데이터가 부족합니다.")

    c = (fee_bp + slippage_bp) / 1e4
    idx = df.index
    close = df["Close"].astype(float)
    high = df["High"].astype(float) if "High" in df else close

    res = BacktestResult(name=name, currency=currency)

    # 상태 (§2)
    mode = "GENERAL"
    cash = float(principal)
    quantity = 0.0
    average_price = 0.0
    T = 0.0
    total_buy_amount = 0.0
    is_first_reverse_day = False

    res.cashflows.append((idx[0], -float(principal)))
    res.total_invested = float(principal)

    eq_list, cash_list, t_list = [], [], []
    prev_closes: list[float] = []
    # 사이클(세트) 기록 — UI '라오어 세트' 탭용
    sets_log: list[dict] = []
    cycle_no = 1
    cycle_start_dt = idx[0]
    cycle_start_value = float(principal)
    cycle_max_T = 0.0

    def do_buy(amount: float, price: float) -> float:
        """amount 예산으로 price에 매수. 체결 수량 반환. 평단·현금·수수료·T기록은 밖에서."""
        nonlocal cash, quantity, average_price, total_buy_amount
        amount = min(amount, cash / (1.0 + c) if c > 0 else cash)
        if amount <= 0 or price <= 0:
            return 0.0
        q = quantity_from_budget(amount, price, fractional)
        if q <= 0:
            return 0.0
        spend = q * price
        fee = spend * c
        average_price = (average_price * quantity + spend + fee) / (quantity + q)  # §23
        quantity += q
        cash -= spend + fee
        total_buy_amount += spend
        res.total_fees += fee
        return q

    def do_sell(q: float, price: float, dt) -> None:
        nonlocal cash, quantity, average_price
        if q <= 0 or quantity <= 0:
            return
        q = min(q, quantity)
        proceeds = q * price
        fee = proceeds * c
        cash += proceeds - fee
        res.total_fees += fee
        res.realized_gains.append((dt, (proceeds - fee) - q * average_price))  # §24
        quantity -= q
        if quantity <= 1e-12:
            quantity = 0.0
            average_price = 0.0

    def start_new_cycle() -> None:
        nonlocal mode, T, average_price, is_first_reverse_day, total_buy_amount
        mode = "GENERAL"
        T = 0.0
        average_price = 0.0
        is_first_reverse_day = False
        total_buy_amount = 0.0

    for i, dt in enumerate(idx):
        px = float(close.loc[dt])
        hi = float(high.loc[dt])
        prev_close = prev_closes[-1] if prev_closes else px

        # ---- COMPLETED: 다음 거래일에 새 사이클 시작(잔금으로 복리)
        if mode == "COMPLETED":
            start_new_cycle()
            cycle_no += 1
            cycle_start_dt = dt
            cycle_start_value = cash
            cycle_max_T = 0.0

        # ---- 모드 전이(당일 주문 전, 직전 종가 기준) §25
        if mode == "GENERAL" and T > 39.0:
            mode = "REVERSE"
            is_first_reverse_day = True
        elif mode == "REVERSE" and not is_first_reverse_day:
            if should_exit_reverse_mode(symbol, prev_close, average_price):
                mode = "GENERAL"

        # ============================ GENERAL
        if mode == "GENERAL":
            prev_T = T
            sold_quarter = sold_final = False
            if quantity > 0:
                star_price = calculate_general_star_price(symbol, average_price, T)
                final_price = calculate_final_sell_price(symbol, average_price)
                quarter_qty = calculate_general_quarter_sell_quantity(quantity)
                final_qty = quantity - quarter_qty
                # 최종 지정가 매도(+tp): 당일 고가 도달 시 지정가 체결
                if hi >= final_price * (1.0 - 1e-12) and final_qty > 0:
                    do_sell(final_qty, final_price, dt)
                    sold_final = True
                # 쿼터 LOC 매도(별지점): 종가 ≥ 별지점 → 종가 체결
                if px >= star_price * (1.0 - 1e-12) and quarter_qty > 0:
                    do_sell(quarter_qty, px, dt)
                    sold_quarter = True

            bought_full = bought_half = False
            if quantity == 0.0 and T == 0.0 and total_buy_amount == 0.0:
                # §8 최초 매수 (종가 체결로 근사)
                budget = calculate_general_daily_budget(cash, T)
                if do_buy(budget, px) > 0:
                    bought_full = True
            elif T <= 39.0:
                budget = calculate_general_daily_budget(cash, T)
                star_price = calculate_general_star_price(symbol, average_price, T) \
                    if quantity > 0 else px
                if 0 <= T < 20 and quantity > 0:            # §9 전반전: 절반+절반
                    half = budget / 2.0
                    star_buy = star_price - 0.01
                    f1 = do_buy(half, px) if px <= star_buy * (1.0 + 1e-12) else 0.0
                    f2 = do_buy(half, px) if px <= average_price * (1.0 + 1e-12) else 0.0
                    if f1 > 0 and f2 > 0:
                        bought_full = True
                    elif f1 > 0 or f2 > 0:
                        bought_half = True
                elif 20 <= T <= 39 and quantity > 0:        # §10 후반전: 전체 별지점
                    star_buy = star_price - 0.01
                    if px <= star_buy * (1.0 + 1e-12):
                        if do_buy(budget, px) > 0:
                            bought_full = True

            # ---- T 업데이트 (§13,14) — 이벤트 유형 분리
            if quantity <= 1e-12 and (sold_final or sold_quarter):
                mode = "COMPLETED"                          # §22 사이클 완료
                res.events_log.append({"date": dt, "구분": "사이클완료", "금액": cash})
                sets_log.append({
                    "세트": cycle_no, "시작일": cycle_start_dt.date(), "종료일": dt.date(),
                    "소요일": (dt - cycle_start_dt).days, "최대T": round(cycle_max_T, 2),
                    "세트손익": round(cash - cycle_start_value, 2), "종료사유": "완료",
                })
            elif sold_final and (bought_full or bought_half):
                T = update_T_after_final_sell_with_buy(prev_T, bought_full)   # §14
            elif sold_quarter and not sold_final:
                T = update_T_after_general_quarter_sell(prev_T)               # §11
            elif bought_full:
                T = prev_T + 1.0                             # §13 전체
            elif bought_half:
                T = prev_T + 0.5                             # §13 절반

        # ============================ REVERSE
        elif mode == "REVERSE":
            if is_first_reverse_day:
                # §16 첫날 MOC 매도 floor(qty/20), 매수 없음
                sq = calculate_reverse_sell_quantity(quantity)
                if sq > 0:
                    do_sell(sq, px, dt)
                    T = update_T_after_reverse_sell(T)
                is_first_reverse_day = False
            else:
                try:
                    star = calculate_reverse_star_price(prev_closes)
                except InsufficientPriceDataError:
                    star = prev_close
                sq = calculate_reverse_sell_quantity(quantity)
                if px >= star * (1.0 - 1e-12) and sq > 0:      # §18 별 위 매도
                    do_sell(sq, px, dt)
                    T = update_T_after_reverse_sell(T)
                elif px <= star * (1.0 + 1e-12):               # §19 별 아래 쿼터매수
                    budget = calculate_reverse_buy_budget(cash)
                    if do_buy(budget, px) > 0:
                        T = update_T_after_reverse_buy(T)
            if quantity <= 1e-12:
                mode = "COMPLETED"
                res.events_log.append({"date": dt, "구분": "사이클완료(리버스)", "금액": cash})
                sets_log.append({
                    "세트": cycle_no, "시작일": cycle_start_dt.date(), "종료일": dt.date(),
                    "소요일": (dt - cycle_start_dt).days, "최대T": round(cycle_max_T, 2),
                    "세트손익": round(cash - cycle_start_value, 2), "종료사유": "완료(리버스)",
                })

        cycle_max_T = max(cycle_max_T, T)
        eq_list.append(cash + quantity * px)
        cash_list.append(cash)
        t_list.append(T)
        prev_closes.append(px)

    res.equity = pd.Series(eq_list, index=idx)
    res.equity_gross = res.equity
    res.cash_series = pd.Series(cash_list, index=idx)
    res.t_series = pd.Series(t_list, index=idx)
    res.cashflows.append((idx[-1], res.final_value))
    if quantity > 0:
        res.realized_gains.append((idx[-1], quantity * float(close.iloc[-1]) - quantity * average_price))
        sets_log.append({
            "세트": cycle_no, "시작일": cycle_start_dt.date(), "종료일": None,
            "소요일": (idx[-1] - cycle_start_dt).days, "최대T": round(cycle_max_T, 2),
            "세트손익": round(cash + quantity * float(close.iloc[-1]) - cycle_start_value, 2),
            "종료사유": "진행중",
        })
    res.laoer_sets = pd.DataFrame(sets_log)
    return res
