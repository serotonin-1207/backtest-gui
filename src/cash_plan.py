# -*- coding: utf-8 -*-
"""적립식 현금관리 계산기 엔진 (순수 함수).

적립식으로 해외주식을 매일 분할매수할 때, 투자되지 않은 '대기자금'의 RP 운용수익,
후순위 조달금의 이자비용, 이체·환전·매수 수수료를 계산해 '최종 순효과'를 산출한다.

기간 환산 규약: 운용기간(년) = 거래일수 ÷ 연간거래일수(기본 252).
  → 스펙 본문의 '/365'는 오기로 보이며, 모든 검증값은 이 '/거래일수' 기준과 일치한다.
  (calendar_basis=True 를 주면 /365 달력일 기준으로 계산)
"""
from __future__ import annotations

import pandas as pd


class CashPlanError(ValueError):
    """입력값 오류."""


# ---------------------------------------------------------------- 기초 함수
def calculate_daily_schedule(total: float, days: int) -> float:
    """1일 투자금 = 총 투자금 / 총 거래일 수."""
    if days <= 0:
        raise CashPlanError("투자기간(거래일 수)은 0보다 커야 합니다.")
    return total / days


def _year_fraction(period_days: float, year_days: int, calendar_basis: bool) -> float:
    return period_days / (365.0 if calendar_basis else year_days)


def calculate_rp_income(avg_balance: float, annual_yield: float, period_days: float,
                        year_days: int, tax_rate: float, calendar_basis: bool = False
                        ) -> tuple[float, float]:
    """대기자금 RP 수익. 반환 (세전, 세후)."""
    yrs = _year_fraction(period_days, year_days, calendar_basis)
    pretax = avg_balance * annual_yield * yrs
    aftertax = pretax * (1 - tax_rate)
    return pretax, aftertax


def calculate_debt_interest(principal: float, annual_rate: float, period_days: float,
                            year_days: int, calendar_basis: bool = False) -> float:
    """후순위 조달금 이자비용 (비용이므로 세금 무관)."""
    yrs = _year_fraction(period_days, year_days, calendar_basis)
    return principal * annual_rate * yrs


def calculate_fees(total: float, buy_fee_rate: float, transfer_fee_per_day: float,
                   days: int) -> tuple[float, float]:
    """(매수수수료, 이체수수료 총액)."""
    return total * buy_fee_rate, days * transfer_fee_per_day


# ---------------------------------------------------------------- 시나리오
def run_scenario(
    total: float = 300_000_000,
    pre_amount: float = 200_000_000,     # 선투입 대기자금
    days: int = 252,
    year_days: int = 252,
    rp_yield: float = 0.0325,            # 대기자금 RP 세전 연수익률
    tax_rate: float = 0.154,            # 이자소득세율
    debt_rate: float = 0.045,           # 후순위 조달 이자율
    sub_mode: str = "매일",              # "매일" | "한번에"
    buy_fee_rate: float = 0.0,          # 매수수수료율
    transfer_fee_per_day: float = 0.0,  # 이체수수료/일 (원화 500, 외화 700 등)
    fx_cost_rate: float = 0.0,          # 환전비용률 (총투자금 대비, 1회)
    calendar_basis: bool = False,
    label: str = "",
) -> dict:
    """한 시나리오 계산 → 요약 dict + 일자별 DataFrame(df)."""
    # ----- 검증
    if total <= 0:
        raise CashPlanError("총 투자금은 0보다 커야 합니다.")
    if pre_amount < 0:
        raise CashPlanError("선투입 금액은 음수가 될 수 없습니다.")
    if pre_amount > total:
        raise CashPlanError("선투입 금액이 총 투자금보다 클 수 없습니다.")
    if days <= 0 or year_days <= 0:
        raise CashPlanError("거래일 수는 0보다 커야 합니다.")
    financed = total - pre_amount          # 후순위 조달 필요액
    if financed < 0:
        raise CashPlanError("후순위 조달금액이 음수입니다.")

    daily = total / days
    exhaust_days = pre_amount / daily if daily > 0 else 0.0   # 선투입 소진일(거래일)
    exhaust_days = min(exhaust_days, days)
    sub_days = days - exhaust_days                            # 후순위 사용기간

    # ----- 선투입 2억 RP (평균잔액 = 선투입/2)
    pre_rp_pre, pre_rp_after = calculate_rp_income(
        pre_amount / 2, rp_yield, exhaust_days, year_days, tax_rate, calendar_basis)

    # ----- 후순위 조달
    if sub_mode == "한번에":
        debt_interest = calculate_debt_interest(financed, debt_rate, sub_days, year_days, calendar_basis)
        sub_rp_pre, sub_rp_after = calculate_rp_income(
            financed / 2, rp_yield, sub_days, year_days, tax_rate, calendar_basis)
    else:  # 매일 필요한 만큼 조달 (평균 사용액 = 후순위/2, RP 대기 없음)
        debt_interest = calculate_debt_interest(financed / 2, debt_rate, sub_days, year_days, calendar_basis)
        sub_rp_pre, sub_rp_after = 0.0, 0.0

    rp_pre = pre_rp_pre + sub_rp_pre
    rp_after = pre_rp_after + sub_rp_after

    # ----- 수수료
    buy_fee, transfer_fee = calculate_fees(total, buy_fee_rate, transfer_fee_per_day, days)
    fx_cost = total * fx_cost_rate

    # ----- 최종 순효과
    net = rp_after - debt_interest - transfer_fee - fx_cost - buy_fee

    summary = {
        "시나리오": label,
        "총투자금": total, "선투입금": pre_amount, "후순위조달금": financed,
        "총거래일": days, "1일투자금": daily,
        "선투입소진일": exhaust_days, "후순위시작일": exhaust_days, "후순위사용기간": sub_days,
        "조달방식": sub_mode,
        "세전RP수익": rp_pre, "세후RP수익": rp_after,
        "후순위이자비용": debt_interest,
        "매수수수료": buy_fee, "이체수수료": transfer_fee, "환전비용": fx_cost,
        "최종순효과": net,
    }
    summary["df"] = _daily_frame(pre_amount, financed, days, daily, exhaust_days, sub_days,
                                 sub_mode, pre_rp_pre, sub_rp_pre, debt_interest)
    return summary


def _daily_frame(pre_amount, financed, days, daily, exhaust_days, sub_days, sub_mode,
                 pre_rp, sub_rp, debt_total) -> pd.DataFrame:
    """일자별 현금흐름 DataFrame (그래프·CSV용). 누적 RP/이자는 구간별 선형 램프
    (합계가 폐형식 총액과 정확히 일치)."""
    rows = []
    for d in range(1, days + 1):
        invested = daily * d
        if d <= exhaust_days:                    # 선투입 소진 구간
            wait = max(pre_amount - daily * d, 0.0)
            cum_rp = pre_rp * (d / exhaust_days) if exhaust_days > 0 else 0.0
            cum_int = 0.0
        else:                                    # 후순위 구간
            prog = (d - exhaust_days) / sub_days if sub_days > 0 else 1.0
            wait = max(financed - daily * (d - exhaust_days), 0.0) if sub_mode == "한번에" else 0.0
            cum_rp = pre_rp + sub_rp * prog
            cum_int = debt_total * prog
        rows.append({
            "거래일": d, "누적투자금": invested, "대기잔액": wait,
            "누적RP수익(세전)": cum_rp, "누적이자비용": cum_int,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 비교표
def compare_scenarios(base: dict) -> pd.DataFrame:
    """스펙의 표준 비교 시나리오 집합을 계산해 요약 DataFrame 반환.
    base: total/pre_amount/tax_rate/debt_rate/year_days 등 공통 입력 + rp_won/rp_fx 수익률."""
    total = base.get("total", 300_000_000)
    pre = base.get("pre_amount", 200_000_000)
    yd = base.get("year_days", 252)
    tax = base.get("tax_rate", 0.154)
    debt = base.get("debt_rate", 0.045)
    rp_won = base.get("rp_won", 0.0205)       # 원화 RP (CMA RP형)
    rp_won2 = base.get("rp_won2", 0.0235)     # 발행어음형 (참고, 표엔 rp_won 사용)
    rp_fx1 = base.get("rp_fx1", 0.0325)       # 외화 RP 3.25%
    rp_fx2 = base.get("rp_fx2", 0.0400)       # 외화 RP 4.00%
    fee_cmp = base.get("compare_fee_rate", 0.0025)
    cal = base.get("calendar_basis", False)

    def mk(label, days, rp, mode, transfer, fee=0.0, fx_cost=0.0):
        s = run_scenario(total=total, pre_amount=pre, days=days, year_days=yd,
                         rp_yield=rp, tax_rate=tax, debt_rate=debt, sub_mode=mode,
                         buy_fee_rate=fee, transfer_fee_per_day=transfer,
                         fx_cost_rate=fx_cost, calendar_basis=cal, label=label)
        s.pop("df", None)
        return s

    rows = []
    for yrs, days in (("1년", 252), ("2년", 504)):
        for mode in ("한번에", "매일"):
            for tf in (0, 500):
                rows.append(mk(f"{yrs}/원화RP/{mode}/이체{tf}원", days, rp_won, mode, tf))
    # 외화 RP (매일 조달, 이체 700원 가정, 1년 기준)
    rows.append(mk("외화RP 3.25% (1년/매일/외화이체700)", 252, rp_fx1, "매일", 700))
    rows.append(mk("외화RP 4.00% (1년/매일/외화이체700)", 252, rp_fx2, "매일", 700))
    # 매수수수료 0.25% 비교안 (1년/원화/매일/이체0)
    rows.append(mk("수수료 0.25% 비교 (1년/원화/매일)", 252, rp_won, "매일", 0, fee=fee_cmp))
    return pd.DataFrame(rows)
