"""참조 CSV의 구조와 수치 무결성을 검사한다."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "src" / "index_ref_data.csv"
EXPECTED_COLUMNS = 18


def main() -> None:
    df = pd.read_csv(PATH, index_col=0, parse_dates=True)
    errors = []
    if df.shape[1] != EXPECTED_COLUMNS:
        errors.append(f"열 개수: {df.shape[1]} (기대 {EXPECTED_COLUMNS})")
    if df.index.duplicated().any():
        errors.append("중복 날짜가 있습니다.")
    if not df.index.is_monotonic_increasing:
        errors.append("날짜가 오름차순이 아닙니다.")
    values = df.to_numpy(dtype=float, na_value=np.nan)
    if np.isinf(values).any():
        errors.append("무한대 값이 있습니다.")
    if (df <= 0).any().any():
        errors.append("0 이하 가격이 있습니다.")
    for col in df:
        s = df[col].dropna()
        if len(s) < 12:
            errors.append(f"{col}: 유효 월이 12개 미만입니다.")
        elif not np.isclose(float(s.iloc[0]), 100.0, rtol=0, atol=1e-6):
            errors.append(f"{col}: 첫 값이 100이 아닙니다 ({s.iloc[0]}).")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"reference data OK: {df.shape[0]} rows x {df.shape[1]} columns")


if __name__ == "__main__":
    main()
