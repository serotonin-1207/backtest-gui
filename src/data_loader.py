# -*- coding: utf-8 -*-
"""데이터 로딩: 한/미 소스 라우팅 + 티커별 parquet 증분 캐시.

- 한국 자산(6자리 코드, KS11 등) -> FinanceDataReader (수정주가)
- 미국 자산(알파벳/^지수)       -> yfinance (auto_adjust=True, 수정주가)
- 캐시: data/cache/{ticker}.parquet + _meta.json
- 증분 업데이트: 마지막 저장일 다음 거래일부터만 다운로드
- 수정주가 소급 변경 감지: 겹치는 구간을 비교, 어긋나면 전체 재다운로드
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

log = logging.getLogger("data_loader")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = BASE_DIR / "data" / "cache"
# 클라우드(Streamlit Cloud 등) 읽기전용 환경 대비: 쓰기 불가하면 임시폴더로 폴백
try:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _probe = CACHE_DIR / ".write_test"
    _probe.write_text("ok", encoding="utf-8")
    _probe.unlink()
except Exception:
    CACHE_DIR = Path(tempfile.gettempdir()) / "backtest_gui_cache"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
META_PATH = CACHE_DIR / "_meta.json"

# ---------------------------------------------------------------- 프리셋
# key -> (표시이름, 티커, 소스, 통화)
ASSET_PRESETS: dict[str, dict] = {
    "S&P500":            {"ticker": "^GSPC",  "source": "yahoo", "currency": "USD"},
    "나스닥종합":         {"ticker": "^IXIC",  "source": "yahoo", "currency": "USD"},
    "다우존스":           {"ticker": "^DJI",   "source": "yahoo", "currency": "USD"},
    "나스닥100":          {"ticker": "^NDX",   "source": "yahoo", "currency": "USD"},
    "필라델피아반도체":    {"ticker": "^SOX",   "source": "yahoo", "currency": "USD"},
    "QQQ":               {"ticker": "QQQ",    "source": "yahoo", "currency": "USD"},
    "TQQQ":              {"ticker": "TQQQ",   "source": "yahoo", "currency": "USD"},
    "QLD":               {"ticker": "QLD",    "source": "yahoo", "currency": "USD"},
    "SPXL":              {"ticker": "SPXL",   "source": "yahoo", "currency": "USD"},
    "SOXL":              {"ticker": "SOXL",   "source": "yahoo", "currency": "USD"},
    "코스피":             {"ticker": "KS11",   "source": "fdr",   "currency": "KRW"},
    "코스닥":             {"ticker": "KQ11",   "source": "fdr",   "currency": "KRW"},
    "코스피200":          {"ticker": "KS200",  "source": "fdr",   "currency": "KRW"},
    "삼성전자":           {"ticker": "005930", "source": "fdr",   "currency": "KRW"},
    "SK하이닉스":         {"ticker": "000660", "source": "fdr",   "currency": "KRW"},
    "KODEX 레버리지":     {"ticker": "122630", "source": "fdr",   "currency": "KRW"},
    "KODEX 코스닥150레버리지": {"ticker": "233740", "source": "fdr", "currency": "KRW"},
    "KODEX 200":         {"ticker": "069500", "source": "fdr",   "currency": "KRW"},
    "TIGER 미국나스닥100": {"ticker": "133690", "source": "fdr",   "currency": "KRW"},
}

# 합성 가능한 레버리지 ETF: ticker -> (기초지수 티커, 배수, 현재 공시 순보수)
# 실제 상장 구간은 수정주가에 비용이 이미 반영되며, 아래 값은 상장 전 합성 구간에만 사용한다.
SYNTH_BASE: dict[str, tuple[str, float, float]] = {
    "TQQQ":   ("^NDX", 3.0, 0.0095),
    "QLD":    ("^NDX", 2.0, 0.0095),
    "SPXL":   ("^GSPC", 3.0, 0.0084),
    "SOXL":   ("^SOX", 3.0, 0.0075),
    "122630": ("KS200", 2.0, 0.0064),   # KODEX 레버리지
}

_KR_INDEX = {"KS11", "KQ11", "KS200"}

# 배당 제외 '가격지수' — ETF(배당 반영)와 섞어 비교하면 불리하게 보임
PRICE_INDEX_TICKERS = {"^GSPC", "^IXIC", "^NDX", "^DJI", "^SOX", "KS11", "KQ11", "KS200"}

# 공식적으로 배당 재투자를 포함해 산출되는 총수익 지수의 Yahoo 심볼.
# 제공 실패 시에만 INDEX_DIV_YIELD 고정 연율 근사로 폴백한다.
TOTAL_RETURN_TICKERS = {
    "^GSPC": "^SP500TR",  # S&P 500 Total Return Index (SPXT)
}

# 가격지수의 대략적 연 배당수익률 (TR 근사 보정용, 참고값)
INDEX_DIV_YIELD = {
    "^GSPC": 0.018, "^IXIC": 0.009, "^NDX": 0.008, "^DJI": 0.020, "^SOX": 0.010,
    "KS11": 0.018, "KQ11": 0.010, "KS200": 0.018,
}

# 국내 상장 ETF 티커 (매매차익 배당소득 15.4%)
KR_ETF_TICKERS = {"122630", "233740", "069500", "133690"}


def tax_category(ticker: str, currency: str) -> str:
    """자산 유형별 세금 카테고리 판정.
    us_overseas(미국 22%) / kr_etf(15.4%) / kr_stock(비과세) / none(지수)."""
    t = ticker.strip().upper()
    # 지수는 직접 매매 상품이 아니므로 통화와 관계없이 과세 대상에서 제외한다.
    if t.startswith("^") or t in _KR_INDEX:
        return "none"
    if currency == "USD":
        return "us_overseas"
    if t in KR_ETF_TICKERS:
        return "kr_etf"
    if re.fullmatch(r"\d{6}", t):
        return "kr_stock"
    return "none"


def route_ticker(ticker: str, override: str | None = None) -> tuple[str, str]:
    """티커 → (source, currency). 6자리 숫자/한국지수=fdr·KRW, 그 외=yahoo·USD.
    override: 'kr' 또는 'us'로 수동 지정."""
    t = ticker.strip().upper()
    if override == "kr":
        return "fdr", "KRW"
    if override == "us":
        return "yahoo", "USD"
    if re.fullmatch(r"\d{6}", t) or t in _KR_INDEX:
        return "fdr", "KRW"
    return "yahoo", "USD"


# ---------------------------------------------------------------- 메타
def _load_meta() -> dict:
    if META_PATH.exists():
        try:
            return json.loads(META_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_meta(meta: dict) -> None:
    _atomic_write_text(META_PATH, json.dumps(meta, ensure_ascii=False, indent=2))


def _atomic_write_text(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _atomic_save_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(".parquet.tmp")
    df.to_parquet(tmp)
    os.replace(tmp, path)


def _cache_path(ticker: str) -> Path:
    safe = ticker.replace("^", "_").replace("/", "_")
    return CACHE_DIR / f"{safe}.parquet"


def _last_expected_trading_day(today: date | None = None) -> date:
    d = today or date.today()
    d = d - timedelta(days=1)  # 오늘 종가는 미확정일 수 있어 전일까지 기대
    while d.weekday() >= 5:    # 주말 제외 (휴장일은 API 1회 호출로 확인)
        d -= timedelta(days=1)
    return d


# ---------------------------------------------------------------- 다운로드
def _download(ticker: str, source: str, start: str | None = None) -> pd.DataFrame:
    """OHLCV DataFrame(index=DatetimeIndex, columns=Open High Low Close Volume)."""
    if source == "fdr":
        import FinanceDataReader as fdr
        # start 미지정 시 전체 기간 (기본 호출은 최근 일부만 반환됨)
        df = fdr.DataReader(ticker, start or "1980-01-01")
    else:
        import yfinance as yf
        # start 미지정 시 period="max" (기본은 최근 1개월만 반환됨)
        if start:
            df = yf.download(ticker, start=start, auto_adjust=True, progress=False)
        else:
            df = yf.download(ticker, period="max", auto_adjust=True, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
    if df is None or df.empty:
        return pd.DataFrame()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    keep = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df[keep].dropna(subset=["Close"])
    return df


def get_price(ticker: str, source: str | None = None, currency: str | None = None,
              force_refresh: bool = False) -> pd.DataFrame:
    """증분 캐시를 사용한 가격 로딩. 실패 시 캐시로 폴백(attrs['stale']=True)."""
    if source is None:
        source, cur = route_ticker(ticker)
        currency = currency or cur
    path = _cache_path(ticker)
    meta = _load_meta()
    m = meta.get(ticker, {})

    cached = None
    if path.exists() and not force_refresh:
        try:
            cached = pd.read_parquet(path)
        except Exception:
            cached = None

    if cached is not None and not cached.empty:
        last = cached.index[-1].date()
        if last >= _last_expected_trading_day():
            cached.attrs.update({"currency": currency, "source": source, "stale": False})
            return cached  # 최신 — API 호출 생략
        # 증분: 겹침 검증용으로 최근 7일 전부터 재요청
        overlap_start = (cached.index[-1] - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        try:
            new = _download(ticker, source, start=overlap_start)
        except Exception as e:
            log.warning("증분 다운로드 실패(%s): %s — 캐시 사용", ticker, e)
            cached.attrs.update({"currency": currency, "source": source, "stale": True})
            return cached
        if new.empty:
            cached.attrs.update({"currency": currency, "source": source, "stale": False})
            return cached
        # 수정주가 소급 변경 감지: 겹치는 구간 Close 비교
        common = cached.index.intersection(new.index)
        refetch = False
        if len(common) > 0:
            a = cached.loc[common, "Close"].astype(float)
            b = new.loc[common, "Close"].astype(float)
            if ((a - b).abs() / b.clip(lower=1e-9) > 0.001).any():
                refetch = True
                log.info("[%s] 수정주가 소급 변경 감지 → 전체 재다운로드", ticker)
        if not refetch:
            add = new.loc[new.index > cached.index[-1]]
            df = pd.concat([cached, add]) if not add.empty else cached
            _atomic_save_parquet(df, path)
            meta[ticker] = {"last_date": str(df.index[-1].date()), "source": source,
                            "currency": currency, "updated_at": datetime.now().isoformat(timespec="seconds")}
            _save_meta(meta)
            df.attrs.update({"currency": currency, "source": source, "stale": False})
            return df
        force_refresh = True  # 아래 전체 재다운로드로

    # 최초 다운로드 또는 강제 새로고침
    try:
        df = _download(ticker, source)
    except Exception as e:
        if cached is not None and not cached.empty:
            log.warning("전체 다운로드 실패(%s): %s — 캐시 사용", ticker, e)
            cached.attrs.update({"currency": currency, "source": source, "stale": True})
            return cached
        raise RuntimeError(f"{ticker} 데이터를 가져올 수 없습니다: {e}") from e
    if df.empty:
        raise RuntimeError(f"{ticker} 데이터가 비어 있습니다 (source={source})")
    _atomic_save_parquet(df, path)
    meta[ticker] = {"last_date": str(df.index[-1].date()), "source": source,
                    "currency": currency, "updated_at": datetime.now().isoformat(timespec="seconds"),
                    "full_refresh_at": datetime.now().isoformat(timespec="seconds")}
    _save_meta(meta)
    df.attrs.update({"currency": currency, "source": source, "stale": False})
    return df


def cache_status() -> pd.DataFrame:
    """캐시된 티커 목록/최신일/갱신시각 표."""
    meta = _load_meta()
    rows = [{"티커": t, "최신 데이터일": m.get("last_date"), "소스": m.get("source"),
             "통화": m.get("currency"), "마지막 갱신": m.get("updated_at")} for t, m in meta.items()]
    return pd.DataFrame(rows)


def clear_cache(ticker: str | None = None) -> None:
    """ticker 지정 시 해당 캐시만, None이면 전체 삭제."""
    meta = _load_meta()
    if ticker:
        p = _cache_path(ticker)
        if p.exists():
            p.unlink()
        meta.pop(ticker, None)
    else:
        for p in CACHE_DIR.glob("*.parquet"):
            p.unlink()
        meta = {}
    _save_meta(meta)
