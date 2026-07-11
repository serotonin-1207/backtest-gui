"""미국 지수·ETF 참조 CSV를 공개 시장 데이터로 재생성한다."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "index_ref_data.csv"
META = ROOT / "data" / "reference_metadata.json"

SYMBOLS = {
    "S&P500": "^GSPC",
    "나스닥100": "^NDX",
    "나스닥종합": "^IXIC",
    "다우존스": "^DJI",
    "러셀2000": "^RUT",
    "반도체(SOX)": "^SOX",
    "QQQ(나100 1x)": "QQQ",
    "QLD(나100 2x)": "QLD",
    "TQQQ(나100 3x)": "TQQQ",
    "SPY(S&P 1x)": "SPY",
    "SSO(S&P 2x)": "SSO",
    "UPRO(S&P 3x)": "UPRO",
    "SOXX(반도체 1x)": "SOXX",
    "SOXL(반도체 3x)": "SOXL",
    "DIA(다우 1x)": "DIA",
    "UDOW(다우 3x)": "UDOW",
    "IWM(러셀 1x)": "IWM",
    "TNA(러셀 3x)": "TNA",
}


def download_monthly(symbol: str) -> pd.Series:
    df = yf.download(symbol, period="max", auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"{symbol}: 데이터가 비어 있습니다.")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close = df["Close"].astype(float).dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    monthly = close.resample("ME").last()
    if monthly.empty or monthly.iloc[0] <= 0:
        raise RuntimeError(f"{symbol}: 유효한 가격이 없습니다.")
    return monthly / monthly.iloc[0] * 100.0


def main() -> None:
    columns = {}
    errors = []
    for label, symbol in SYMBOLS.items():
        try:
            columns[label] = download_monthly(symbol)
            print(f"OK {label} ({symbol}): {len(columns[label])}개월")
        except Exception as exc:
            errors.append(f"{label}({symbol}): {exc}")
    if errors:
        raise RuntimeError("\n".join(errors))
    df = pd.concat(columns, axis=1).sort_index()
    df.index.name = "date"
    df.to_csv(OUT, encoding="utf-8")

    meta = json.loads(META.read_text(encoding="utf-8"))
    meta["generated_at_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta["rows"] = len(df)
    meta["columns"] = len(df.columns)
    meta["data_start"] = str(df.index.min().date())
    meta["data_end_label"] = str(df.index.max().date())
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved: {OUT} ({df.shape[0]} x {df.shape[1]})")


if __name__ == "__main__":
    main()
