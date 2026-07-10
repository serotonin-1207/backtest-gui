# -*- coding: utf-8 -*-
"""자산 유형별 세금 계산 (실현손익 기반, 근사).

카테고리:
  - "us_overseas"       : 미국 직투/해외상장 ETF — 양도소득세 22%, 연 250만원 공제,
                          연간 손익통산, 실현손익을 거래일 환율로 원화 환산 후 과세.
  - "kr_etf"            : 국내상장 ETF(레버리지·해외 등) — 매매차익 배당소득 15.4%.
  - "kr_stock"          : 국내주식 직투 — 소액주주 양도차익 비과세(거래세는 수수료 옵션으로 처리 권장).
  - "none"              : 지수 등 비과세/비대상.

주의(MVP 근사):
  - 세금은 '만기 청산 시 일괄' 개념으로 최종 순자산에서 차감한다. 라오어처럼 중간 실현이
    잦은 전략은 실제로는 매년 납부하지만, 여기서는 총액을 최종값에서 빼는 근사를 쓴다.
  - 국내 ETF는 손실 통산 없이 '실현이익 합계 × 15.4%'로 근사한다(보수적).
"""
from __future__ import annotations

from collections import defaultdict

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
        gains_pos = sum(g for _, g in realized_gains if g > 0)
        tax = gains_pos * p["kr_etf_rate"]
        out["total_tax_krw"] = tax
        out["total_tax_asset"] = tax
        out["taxable_krw"] = gains_pos
        out["note"] = "국내상장 ETF 매매차익 배당소득세 15.4% (실현이익 합계 기준 근사)"
        return out

    return out
