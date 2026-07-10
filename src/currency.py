# -*- coding: utf-8 -*-
"""환율: 다중 통화 지원 (투자금 기준 화폐 + 대시보드 표시 화폐 전환).

- 지원 통화: KRW(원), USD(달러), JPY(엔), EUR(유로), CNY(위안), HKD(홍콩달러)
- 환율 소스: Yahoo "{통화}=X" (1 USD당 해당 통화 환율), KRW은 FDR 'USD/KRW' 폴백
- MVP는 '현재 환율 기준 단순 환산'만 제공. 일별 환율을 매일 곱하는
  언헤지 시뮬레이션(환효과 기여분)은 확장 단계에서 추가한다.
"""
from __future__ import annotations

from .data_loader import get_price

# 통화코드 -> (한글 단위, 표시 이름)
SUPPORTED: dict[str, tuple[str, str]] = {
    "KRW": ("원", "원화"),
    "USD": ("달러", "미국 달러"),
    "JPY": ("엔", "일본 엔"),
    "EUR": ("유로", "유로"),
    "CNY": ("위안", "중국 위안"),
    "HKD": ("홍콩달러", "홍콩 달러"),
}

CURRENCY_LABELS = {c: f"{c} ({SUPPORTED[c][0]})" for c in SUPPORTED}  # "KRW (원)" 등


def get_rates(currencies: list[str] | None = None) -> tuple[dict[str, float], str]:
    """(rates, 기준일). rates = {통화: 1 USD당 환율}, USD=1.0.

    개별 통화 조회 실패 시 해당 통화는 rates에서 빠진다(호출부에서 경고 처리).
    """
    curs = currencies or list(SUPPORTED)
    rates: dict[str, float] = {"USD": 1.0}
    dates = []
    for c in curs:
        if c == "USD":
            continue
        s = None
        try:
            s = get_price(f"{c}=X", source="yahoo", currency=c)["Close"].dropna()
        except Exception:
            if c == "KRW":
                try:
                    s = get_price("USD/KRW", source="fdr", currency="KRW")["Close"].dropna()
                except Exception:
                    s = None
        if s is not None and len(s):
            rates[c] = float(s.iloc[-1])
            dates.append(s.index[-1].date())
    ref_date = str(max(dates)) if dates else ""
    return rates, ref_date


def get_fx_series(from_cur: str, to_cur: str) -> "pd.Series | None":
    """일별 환율 시계열 (1 from_cur = ? to_cur). 과거 환율 효과(언헤지) 계산용.
    실패하거나 동일 통화면 None(=환산 불필요) 반환."""
    import pandas as pd
    if from_cur == to_cur:
        return None

    def usd_to(cur: str):
        if cur == "USD":
            return None  # 1.0 상수
        try:
            s = get_price(f"{cur}=X", source="yahoo", currency=cur)["Close"].astype(float)
            return s.dropna()
        except Exception:
            if cur == "KRW":
                try:
                    return get_price("USD/KRW", source="fdr", currency="KRW")["Close"].astype(float).dropna()
                except Exception:
                    return None
            return None

    sf = usd_to(from_cur)   # 1 USD = ? from
    st = usd_to(to_cur)     # 1 USD = ? to
    # cross: 1 from = (1/sf) USD = (st/sf) to
    if sf is None and st is None:
        return None
    if sf is None:          # from=USD → 1 USD = st to
        return st
    if st is None:          # to=USD → 1 from = 1/sf USD
        return 1.0 / sf
    common = sf.index.intersection(st.index)
    if len(common) == 0:
        return None
    return (st.loc[common] / sf.loc[common]).dropna()


def convert(value: float, from_cur: str, to_cur: str, rates: dict[str, float]) -> float:
    """현재 환율 기준 단순 환산 (USD 크로스). 환율 없는 통화면 원값 반환."""
    if from_cur == to_cur:
        return value
    if from_cur not in rates or to_cur not in rates:
        return value
    return value / rates[from_cur] * rates[to_cur]


def cross_rate(from_cur: str, to_cur: str, rates: dict[str, float]) -> float | None:
    """1 from_cur = ? to_cur."""
    if from_cur not in rates or to_cur not in rates:
        return None
    return rates[to_cur] / rates[from_cur]


def get_current_usdkrw() -> tuple[float, str]:
    """(1 USD당 KRW, 기준일) — 하위 호환용."""
    rates, d = get_rates(["KRW"])
    return rates["KRW"], d


def korean_money(v: float, currency: str = "KRW") -> str:
    """금액을 한글 단위로. 100,000,000 KRW -> '1억원', 123,456,789 -> '1억 2,345만원'."""
    unit = SUPPORTED.get(currency, (currency, currency))[0]
    sign = "-" if v < 0 else ""
    n = int(round(abs(v)))
    if n < 10_000:
        return f"{sign}{n:,}{unit}"
    parts: list[str] = []
    for name, div in (("조", 10**12), ("억", 10**8), ("만", 10**4)):
        q, n = divmod(n, div)
        if q:
            parts.append(f"{q:,}{name}")
        if len(parts) == 2:
            break
    return sign + " ".join(parts) + unit
