# -*- coding: utf-8 -*-
"""추가 불입/중도 인출 이벤트 확장 + 현금흐름 기록 (XIRR 반영용).

이벤트 형식(dict):
  {"date": "YYYY-MM-DD", "amount": 10_000_000, "kind": "불입"|"인출",
   "repeat": "없음"|"매월"|"매년", "until": "YYYY-MM-DD"(반복 종료, 없으면 백테스트 종료일)}
"""
from __future__ import annotations

import pandas as pd


def expand_events(events: list[dict], start: pd.Timestamp, end: pd.Timestamp,
                  trading_index: pd.DatetimeIndex) -> list[dict]:
    """반복 이벤트를 개별 (거래일 스냅) 이벤트 리스트로 확장. 날짜 오름차순."""
    out: list[dict] = []
    for ev in events:
        try:
            d0 = pd.Timestamp(ev["date"])
            amt = float(ev["amount"])
        except (KeyError, ValueError, TypeError):
            continue
        if amt <= 0:
            continue
        kind = ev.get("kind", "불입")
        repeat = ev.get("repeat", "없음")
        until = pd.Timestamp(ev["until"]) if ev.get("until") else end

        if repeat == "매월":
            dates = pd.date_range(d0, min(until, end), freq=pd.DateOffset(months=1))
        elif repeat == "매년":
            dates = pd.date_range(d0, min(until, end), freq=pd.DateOffset(years=1))
        else:
            dates = [d0]

        for d in dates:
            if d < start or d > end:
                continue
            snapped = snap_to_trading_day(d, trading_index)
            if snapped is not None:
                out.append({"date": snapped, "amount": amt, "kind": kind})
    out.sort(key=lambda e: e["date"])
    return out


def snap_to_trading_day(d: pd.Timestamp, idx: pd.DatetimeIndex):
    """d 이후 첫 거래일로 스냅. 범위를 벗어나면 None."""
    pos = idx.searchsorted(d)
    if pos >= len(idx):
        return None
    return idx[pos]


def dca_schedule(start: pd.Timestamp, idx: pd.DatetimeIndex, freq: str,
                 years: float | None) -> list[pd.Timestamp]:
    """적립 매수일 목록. freq: 매일/매주/매월/매년, years: 적립 기간(None=전체)."""
    end = idx[-1]
    if years:
        end = min(end, start + pd.DateOffset(days=int(years * 365.25)))
    if freq == "매일":
        return [d for d in idx if start <= d <= end]
    offset = {"매주": pd.DateOffset(weeks=1), "매월": pd.DateOffset(months=1),
              "매년": pd.DateOffset(years=1)}[freq]
    raw = pd.date_range(start, end, freq=offset)
    seen, out = set(), []
    for d in raw:
        s = snap_to_trading_day(d, idx)
        if s is not None and s <= end and s not in seen:
            seen.add(s)
            out.append(s)
    return out
