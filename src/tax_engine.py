# -*- coding: utf-8 -*-
"""자산 유형별 세금 계산 (실현손익 기반, 근사).

카테고리:
  - "us_overseas"       : 미국 직투/해외상장 ETF — 양도소득세 22%, 연 250만원 공제,
                          연간 손익통산, 실현손익을 거래일 환율로 원화 환산 후 과세.
  - "kr_etf"            : 국내상장 ETF(레버리지·해외 등) — 매매차익 배당소득 15.4%.
  - "kr_stock"          : 국내주식 직투 — 소액주주 양도차익 비과세(거래세는 수수료 옵션으로 처리 권장).
  - "none"              : 지수 등 비과세/비대상.

주의(근사):
  - 연도별 세금을 다음 해 첫 거래일에 보유자산 매도로 납부한 것으로 처리해 이후 복리 영향을 반영한다.
    마지막 연도 세금은 백테스트 종료일에 차감한다.
  - 국내 ETF는 손실 통산 없이 '실현이익 합계 × 15.4%'로 근사한다(보수적).
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

DEFAULT_PARAMS = {
    "us_rate": 0.22,               # 국세 20% + 지방 2%
    "us_deduction_krw": 2_500_000, # 연 기본공제
    "kr_etf_rate": 0.154,          # 배당소득세 15.4%
}


def compute_tax(realized_gains: list[tuple], category: str,
                to_krw=None, asset_to_krw_final: float = 1.0,
                params: dict | None = None) -> dict:
    """realized_gains: [(date, 실현손익_자산통화)]. 반환: 세금 정보 dict (자산통화 기준 total_tax_asset)."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    out = {"category": category, "total_tax_asset": 0.0, "total_tax_krw": 0.0,
           "taxable_krw": 0.0, "by_year": {}, "note": ""}
    if not realized_gains or category in ("none", "kr_stock"):
        if category == "kr_stock":
            out["note"] = "국내주식 양도차익 비과세 (거래세는 수수료 옵션으로 반영 권장)"
        return out

    if category == "us_overseas":
        to_krw = to_krw or (lambda amt, dt: amt)  # 환율 미지정 시 그대로(자산=원화 가정)
        by_year_krw: dict[int, float] = defaultdict(float)
        for dt, gain in realized_gains:
            by_year_krw[dt.year] += to_krw(gain, dt)
        tax_krw = 0.0
        year_detail = {}
        for y, net in sorted(by_year_krw.items()):
            taxable = max(0.0, net - p["us_deduction_krw"])
            t = taxable * p["us_rate"]
            tax_krw += t
            year_detail[y] = {"실현손익_원화": round(net), "과세표준": round(taxable), "세금": round(t)}
        out["total_tax_krw"] = tax_krw
        out["total_tax_asset"] = tax_krw / asset_to_krw_final if asset_to_krw_final else tax_krw
        out["taxable_krw"] = sum(v["과세표준"] for v in year_detail.values())
        out["by_year"] = year_detail
        out["note"] = "미국 양도소득세 22% (연 250만원 공제, 연간 손익통산, 거래일 환율 원화환산)"
        return out

    if category == "kr_etf":
        # 자산통화=KRW. 손실 통산 없이 실현이익 합계 × 15.4% (보수적 근사)
        by_year_pos: dict[int, float] = defaultdict(float)
        for dt, gain in realized_gains:
            if gain > 0:
                by_year_pos[pd.Timestamp(dt).year] += gain
        gains_pos = sum(by_year_pos.values())
        tax = gains_pos * p["kr_etf_rate"]
        out["total_tax_krw"] = tax
        out["total_tax_asset"] = tax
        out["taxable_krw"] = gains_pos
        out["by_year"] = {
            y: {"실현손익_원화": round(g), "과세표준": round(g),
                "세금": round(g * p["kr_etf_rate"])}
            for y, g in sorted(by_year_pos.items())
        }
        out["note"] = "국내상장 ETF 매매차익 배당소득세 15.4% (실현이익 합계 기준 근사)"
        return out

    return out


def tax_schedule_asset(tax_info: dict) -> dict[int, float]:
    """세금 상세를 자산통화 기준 연도별 납부액으로 배분한다."""
    explicit = tax_info.get("schedule_asset") or {}
    if explicit:
        return {int(year): float(amount) for year, amount in explicit.items() if float(amount) > 0}
    total_asset = float(tax_info.get("total_tax_asset", 0.0) or 0.0)
    by_year = tax_info.get("by_year") or {}
    total_base = sum(float(v.get("세금", 0.0) or 0.0) for v in by_year.values())
    if total_asset <= 0 or total_base <= 0:
        return {}
    return {
        int(year): total_asset * float(detail.get("세금", 0.0) or 0.0) / total_base
        for year, detail in by_year.items()
        if float(detail.get("세금", 0.0) or 0.0) > 0
    }


def apply_annual_tax_drag(
    equity: pd.Series,
    flows: dict | None,
    schedule: dict[int, float],
) -> tuple[pd.Series, list[tuple[pd.Timestamp, float]]]:
    """연도별 세금을 다음 해 첫 거래일에 자산 매도로 납부한 복리 영향을 근사한다.

    백테스트 마지막 연도의 세금은 종료일에 납부한다. 세금 납부 후에는 원래 전략의
    일간 TWR을 동일하게 적용하므로, 조기 납부로 사라진 원금의 이후 수익 기회도 제거된다.
    """
    eq = equity.astype(float).copy()
    if eq.empty or not schedule:
        return eq, []
    f = pd.Series(0.0, index=eq.index)
    for d, amount in (flows or {}).items():
        d = pd.Timestamp(d)
        if d in f.index:
            f.loc[d] += float(amount)

    payments_by_date: dict[pd.Timestamp, float] = defaultdict(float)
    last_year = int(eq.index[-1].year)
    for tax_year, amount in schedule.items():
        candidates = eq.index[eq.index.year > int(tax_year)]
        pay_date = candidates[0] if len(candidates) else eq.index[-1]
        # 미래 연도에 대한 세금은 현재 백테스트에 포함하지 않는다.
        if int(tax_year) <= last_year:
            payments_by_date[pd.Timestamp(pay_date)] += float(amount)

    adjusted = [float(eq.iloc[0]) - payments_by_date.get(pd.Timestamp(eq.index[0]), 0.0)]
    for i in range(1, len(eq)):
        prev = float(eq.iloc[i - 1])
        daily_return = ((float(eq.iloc[i]) - float(f.iloc[i])) / prev - 1.0) if prev > 0 else 0.0
        value = adjusted[-1] * (1.0 + daily_return) + float(f.iloc[i])
        value -= payments_by_date.get(pd.Timestamp(eq.index[i]), 0.0)
        adjusted.append(max(value, 0.0))
    payments = sorted((d, a) for d, a in payments_by_date.items() if a > 0)
    return pd.Series(adjusted, index=eq.index), payments
