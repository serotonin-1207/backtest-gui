# -*- coding: utf-8 -*-
"""백테스트 결과 자동 해석 — 규칙 기반 한국어 코멘터리 생성."""
from __future__ import annotations

import pandas as pd

from .currency import korean_money

LEVERAGE_KEYWORDS = ("TQQQ", "QLD", "SOXL", "SPXL", "레버리지", "122630", "233740")


def interpret_results(df: pd.DataFrame, display_currency: str | None = None) -> str:
    """요약표(df)를 읽고 해석 마크다운을 생성. df는 GUI 요약표 스키마를 따른다."""
    if df.empty:
        return "결과가 없습니다."
    L: list[str] = []
    cur = display_currency or (df["통화"].iloc[0] if df["통화"].nunique() == 1 else "")

    # 1) 수익 1위 vs 위험조정 1위
    by_final = df.sort_values("최종순자산", ascending=False)
    top = by_final.iloc[0]
    head = (f"### 💰 수익 관점\n**최종 순자산 1위는 `{top['전략명']}`** — "
            f"{top['최종순자산']:,.0f}{' ' + cur if cur else ''}")
    if cur in ("KRW", "USD"):
        head += f" ({korean_money(top['최종순자산'], cur)})"
    if pd.notna(top.get("원금대비배수")):
        head += f", 원금 대비 **{top['원금대비배수']:.1f}배**"
    if pd.notna(top.get("XIRR")):
        head += f", XIRR(연환산) {top['XIRR']:.1%}"
    L.append(head + ".")
    if df["칼마"].notna().any():
        by_calmar = df.sort_values("칼마", ascending=False)
        tc = by_calmar.iloc[0]
        if tc["전략명"] == top["전략명"]:
            L.append(f"위험조정(칼마) 기준으로도 `{tc['전략명']}`이 1위여서, 수익과 위험 균형이 모두 우수합니다.")
        else:
            L.append(f"\n하지만 **위험 대비 수익(칼마) 1위는 `{tc['전략명']}`**(칼마 {tc['칼마']:.2f}, "
                     f"MDD {tc['MDD']:.0%})입니다. `{top['전략명']}`은 수익은 크지만 "
                     f"MDD {top['MDD']:.0%}의 낙폭을 견뎌야 했습니다. "
                     f"'끝까지 들고 갈 수 있는가'가 두 전략 선택의 핵심입니다.")

    # 2) MDD 경고
    deep = df[df["MDD"] < -0.5]
    if not deep.empty:
        names = ", ".join(f"`{n}`" for n in deep["전략명"])
        worst = deep["MDD"].min()
        L.append(f"\n### ⚠️ 위험 관점\n{names} 은(는) 고점 대비 **{worst:.0%}까지 하락**한 구간이 있었습니다. "
                 f"자산이 절반 이하로 줄어든 상태를 수년간 버텨야 했다는 뜻으로, 실제로는 중도 포기 가능성이 큽니다.")
    if "최장무회복일" in df.columns and df["최장무회복일"].notna().any():
        lw = df.loc[df["최장무회복일"].idxmax()]
        if lw["최장무회복일"] > 365:
            L.append(f"`{lw['전략명']}`의 최장 무회복 기간은 **약 {lw['최장무회복일']/365:.1f}년** — "
                     f"이 기간 내내 계좌가 전고점 아래에 있었습니다.")
    lev = df[df["전략명"].str.contains("|".join(LEVERAGE_KEYWORDS), case=False, na=False)]
    if not lev.empty:
        L.append("레버리지 상품은 **변동성 감쇠(volatility decay)** 때문에 횡보장에서 기초지수보다 "
                 "구조적으로 불리하며, 위 백테스트 수치가 좋아도 미래에 같은 상승장이 반복된다는 보장은 없습니다.")

    # 3) 거치식 vs 적립식 (같은 자산 짝 비교)
    pair_lines = []
    for asset in {n.split("·")[0] for n in df["전략명"]}:
        sub = df[df["전략명"].str.startswith(asset + "·")]
        lump = sub[sub["전략명"].str.contains("거치식")]
        dca = sub[sub["전략명"].str.contains("적립식")]
        if len(lump) and len(dca):
            l, d = lump.iloc[0], dca.iloc[0]
            better = "거치식" if l["최종순자산"] > d["최종순자산"] else "적립식"
            pair_lines.append(f"- **{asset}**: 거치식 {l['최종순자산']:,.0f} vs 적립식 {d['최종순자산']:,.0f} → "
                              f"**{better} 우세**. " +
                              ("이 기간이 전반적 상승장이어서 일찍 전액 투입한 거치식이 유리했습니다. "
                               "적립식의 수익금이 적은 건 자금이 늦게 들어가 시장 노출 기간이 짧기 때문이며, "
                               "대신 진입 시점 위험이 분산됩니다." if better == "거치식" else
                               "시작 직후 하락/횡보 구간이 있어 싸게 나눠 산 적립식이 유리했습니다."))
    if pair_lines:
        L.append("\n### ⚖️ 거치식 vs 적립식\n" + "\n".join(pair_lines))

    # 4) 라오어
    lao = df[df["완료세트"].notna()] if "완료세트" in df.columns else pd.DataFrame()
    if not lao.empty:
        L.append("\n### ♾️ 라오어 관점")
        for _, r in lao.iterrows():
            L.append(f"- `{r['전략명']}`: 완료 세트 {int(r['완료세트'])}개. 세트 수가 많고 승률이 높아도 "
                     f"수익의 대부분을 지수 방향성이 결정합니다 — 하락 후 회복이 빠른 자산에서 유리한 전략입니다.")

    # 5) 합성/대출 주의
    if (df["데이터"] == "합성포함").any():
        L.append("\n### 🧪 데이터 주의\n'합성포함' 전략은 상장 이전 구간을 기초지수 일간수익률×배수로 만든 "
                 "**가상 가격**입니다. 실제 ETF의 보수·추적오차·유동성이 완전히 반영되지 않으므로 참고용입니다.")
    if (df["대출"] == "O").any():
        li = df[df["대출"] == "O"]
        L.append(f"\n### 🏦 대출 관점\n대출 전략의 총 납부 이자는 {li['총이자'].sum():,.0f}입니다. "
                 "이자보다 수익이 컸는지와 함께, 하락 구간에서 대출 원금이 그대로 남아 "
                 "순자산 낙폭(MDD)이 자기자본 대비 증폭된다는 점을 확인하세요.")

    # 6) 읽는 법
    L.append("\n### 📖 이 표를 읽는 순서 (권장)\n"
             "1. **XIRR**(연환산, 현금흐름 반영)로 전략 간 수익성을 비교 — 총수익률보다 공정합니다.\n"
             "2. **MDD·최장무회복일**로 '버틸 수 있는가'를 점검합니다.\n"
             "3. **칼마**(CAGR÷|MDD|)로 위험 대비 효율을 비교합니다 — 1 이상이면 우수한 편.\n"
             "4. 마지막으로 최종 순자산을 봅니다. 순서가 반대가 되면 과거 상승장에 과적합된 선택을 하기 쉽습니다.\n\n"
             "> ※ 단일 시작일 백테스트는 진입 시점 운에 크게 좌우됩니다. 백테스트 결과는 미래 수익을 보장하지 않습니다.")
    return "\n".join(x for x in L if x)
