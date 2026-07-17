# -*- coding: utf-8 -*-
"""대한소방공제회 퇴직급여(적립식) 시뮬레이션 — QQQ 비교용 별도 모듈.

기존 QQQ/백테스트 코드는 건드리지 않고, 소방공제회를 '투자방식'의 하나로 추가하기 위한
독립 클래스(FirefighterFund)와 실행 함수(run_firefighter_fund)를 제공한다.

■ 이율(중요)
  - **연 5.03% 복리 = 2026-01-01부터 적용된 공식 현재 이율.**
  - 그 외 시나리오(3.5%/4.5%/5.5%)와 변동금리 예시는 모두 **가정(추정)** 이다.
    임의의 과거 소방공제회 이율을 만들어 쓰지 않는다.

■ 계산 규칙(요청 명세)
  - 매월 납입일(기본 20일, 변경 가능)에 월 납입액을 더한다. 그 달에 납입일이 없으면 말일에 납입.
  - 일 단위 시뮬레이션. 윤년 366일 / 평년 365일.
  - 일 유효이율 = (1 + 연이율) ** (1/연일수) − 1. 매일 잔액에 반영(연복리·일할).
  - 세율은 '부가금(이자)'에만 적용. 원금에는 과세하지 않는다.
  - 물가상승률을 반영한 실질가치도 계산.

■ 이번 앱 적용(사용자 지시로 단순화)
  - 중도해약(해약금)은 무시 → 항상 부가금 100% 지급.
  - '20년 이상 저세율'은 문구 안내만 하고, 비교는 공격적 이율(5.03%)·복리·**저세율**로 계산.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass

import pandas as pd

from .backtest_engine import BacktestResult
from .metrics import xirr

# 연 이율 시나리오 (5.03%만 공식, 나머지는 가정)
RATE_SCENARIOS = {
    "보수적 3.5% (가정)": 0.035,
    "기준 4.5% (가정)": 0.045,
    "공격적 5.03% (2026-01-01 공식)": 0.0503,
    "초공격적 5.5% (가정)": 0.055,
}
DEFAULT_RATE = 0.0503  # 2026-01-01 적용 현재 이율(공식)

# 세율 시나리오 — 부가금(이자)에만 적용
TAX_SCENARIOS = {"면세 0%": 0.0, "저세율 1.5%": 0.015, "기본 3.3%": 0.033}
DEFAULT_TAX = 0.015  # 저세율(장기·20년 이상 가정)

# 변동금리 예시(가정) — 연차(1-based) 구간별 연이율
VARIABLE_RATE_EXAMPLE = [(10, 0.0503), (20, 0.045), (30, 0.040)]


def midterm_payout_rate(years: float) -> float:
    """중도탈퇴 가입기간별 부가금 지급률(참고용). 해약금 무시 시 30년 정상퇴직=100%."""
    if years < 1:
        return 0.0
    if years < 5:
        return 0.40
    if years < 10:
        return 0.50
    if years < 15:
        return 0.60
    if years < 20:
        return 0.70
    return 1.0


@dataclass
class FirefighterFund:
    """소방공제회 적립식 일 단위 시뮬레이터."""

    monthly_deposit: float                 # 월 납입액(원)
    annual_rate: float = DEFAULT_RATE      # 고정 연이율
    pay_day: int = 20                      # 납입일(1~31, 말일 초과 시 말일 납입)
    tax_rate: float = DEFAULT_TAX          # 부가금(이자)에만 적용
    rate_schedule: list | None = None      # 변동금리 [(연차상한, 연이율), ...] 없으면 고정
    inflation: float = 0.0                 # 실질가치 환산용 연 물가상승률

    def __post_init__(self):
        # ---- 입력값 검증
        if self.monthly_deposit <= 0:
            raise ValueError("월 납입액은 0보다 커야 합니다.")
        if not (1 <= int(self.pay_day) <= 31):
            raise ValueError("납입일은 1~31 사이여야 합니다.")
        if not (-1.0 < self.annual_rate < 5.0):
            raise ValueError("연이율 값이 비정상입니다.")
        if not (0.0 <= self.tax_rate < 1.0):
            raise ValueError("세율은 0~1 사이여야 합니다.")
        self.pay_day = int(self.pay_day)

    # ---- 납입일 판정 (말일 초과 시 그 달 말일)
    def _is_payday(self, d: pd.Timestamp) -> bool:
        last = calendar.monthrange(d.year, d.month)[1]
        return d.day == min(self.pay_day, last)

    # ---- 해당 날짜의 연이율
    def _annual_rate(self, d: pd.Timestamp, start_year: int) -> float:
        if not self.rate_schedule:
            return self.annual_rate
        year_idx = d.year - start_year + 1
        for upto, rate in self.rate_schedule:
            if year_idx <= upto:
                return rate
        return self.rate_schedule[-1][1]

    def simulate(self, start, end) -> tuple[pd.DataFrame, list]:
        """일별 세전 잔액·누적원금 DataFrame과 납입일 리스트 반환."""
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)
        if end <= start:
            raise ValueError("종료일은 시작일보다 뒤여야 합니다.")
        dates = pd.date_range(start, end, freq="D")
        balance = 0.0
        principal = 0.0
        deposit_dates: list[pd.Timestamp] = []
        bal_arr, prin_arr = [], []
        for d in dates:
            # 1) 납입일이면 납입
            if self._is_payday(d):
                balance += self.monthly_deposit
                principal += self.monthly_deposit
                deposit_dates.append(d)
            # 2~4) 연이율 → 일 유효이율(윤년 366/평년 365) → 하루치 이자
            rate = self._annual_rate(d, start.year)
            diy = 366 if calendar.isleap(d.year) else 365
            daily_rate = (1.0 + rate) ** (1.0 / diy) - 1.0
            balance += balance * daily_rate
            # 5) 기록
            bal_arr.append(balance)
            prin_arr.append(principal)
        df = pd.DataFrame({"세전잔액": bal_arr, "누적원금": prin_arr}, index=dates)
        return df, deposit_dates


def run_firefighter_fund(
    start,
    end,
    monthly_deposit: float,
    currency: str = "KRW",
    annual_rate: float = DEFAULT_RATE,
    pay_day: int = 20,
    tax_rate: float = DEFAULT_TAX,
    rate_schedule: list | None = None,
    inflation: float = 0.0,
    name: str | None = None,
) -> BacktestResult:
    """소방공제회 결과를 BacktestResult(세후 잔액 곡선)로 반환. 상세는 res.firefighter_summary."""
    fund = FirefighterFund(monthly_deposit, annual_rate, pay_day, tax_rate,
                           rate_schedule, inflation)
    df, deposit_dates = fund.simulate(start, end)
    # 첫 납입 전(잔액 0) 구간은 잘라 TWR·CAGR이 정상 계산되게 한다.
    if (df["세전잔액"] > 0).any():
        df = df.iloc[int((df["세전잔액"] > 0).values.argmax()):]
    balance = df["세전잔액"]
    principal = df["누적원금"]
    interest = balance - principal                     # 부가금(이자)
    after_tax = principal + interest * (1.0 - tax_rate)  # 세후 잔액 곡선

    res = BacktestResult(name=name or f"소방공제회 {annual_rate * 100:.2f}%", currency=currency)
    res.equity = after_tax
    res.equity_gross = balance
    res.total_invested = float(principal.iloc[-1])
    for d in deposit_dates:                            # XIRR·TWR용 현금흐름
        res.cashflows.append((d, -monthly_deposit))
        res.flows[d] = res.flows.get(d, 0.0) + monthly_deposit
    res.cashflows.append((df.index[-1], float(after_tax.iloc[-1])))

    # ---- 상세 요약(요청한 반환값)
    prin = float(principal.iloc[-1])
    gross = float(balance.iloc[-1])
    interest_final = gross - prin
    tax_amt = interest_final * tax_rate
    final_after = prin + interest_final * (1.0 - tax_rate)
    years = max((df.index[-1] - df.index[0]).days / 365.25, 1e-9)
    res.firefighter_summary = {
        "총납입원금": prin,
        "세전최종자산": gross,
        "누적부가금": interest_final,
        "적용세율": tax_rate,
        "예상세금": tax_amt,
        "세후최종자산": final_after,
        "누적수익률": (final_after / prin - 1.0) if prin > 0 else 0.0,
        "XIRR": xirr(res.cashflows),
        "명목최종자산": final_after,
        "실질최종자산": final_after / ((1.0 + inflation) ** years),
        "연이율": annual_rate,
        "물가상승률": inflation,
    }
    return res
