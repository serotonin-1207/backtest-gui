# -*- coding: utf-8 -*-
"""AI 재분석용 결과 추출 — ai_analysis_request.md 자동 생성."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

QUESTIONS = """## AI 분석 요청 질문
1. 이 전략들 중 위험 대비 수익(칼마·소르티노) 기준으로 가장 우수한 것은? 근거는?
2. 최종 순자산 1등 전략의 성과가 '실력'인지 '진입 시점 운'인지, 민감도 분포로 판단해줘.
3. MDD와 최장 무회복 기간을 고려할 때, 내가 심리적으로 버틸 수 있는 전략은 어느 것인가?
4. 레버리지/대출 전략의 감쇠·마진콜 위험이 실제로 결과를 얼마나 훼손했는가?
5. 환율 반영 ON/OFF 차이가 결론을 바꾸는가? 환효과를 제거해도 여전히 유효한 전략은?
6. 세금(미국 22%·국내 15.4%) 반영 후 순위가 바뀌는 전략이 있는가?
7. 라오어 무한매수법 V4.0(TQQQ·SOXL) vs 거치식·적립식을 이 데이터에서 어떻게 평가하는가?
8. 적립식 vs 거치식, 어떤 시장 국면에서 각각 유리했는가?
9. 이 백테스트의 가장 큰 한계·과최적화 위험은 무엇인가?
10. 다음에 추가로 돌려볼 만한 시나리오를 3개 제안해줘.
"""

DISCLAIMER = "> ※ 백테스트 결과는 미래 수익을 보장하지 않습니다. 레버리지 ETF·대출 전략은 변동성 감쇠와 강제청산 위험이 있습니다.\n"


def build_ai_report(results: list, summary_df: pd.DataFrame, settings: dict,
                    csv_path: str | None = None) -> str:
    lines: list[str] = []
    lines.append("# 백테스트 결과 AI 분석 요청")
    lines.append(f"\n생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    lines.append(DISCLAIMER)

    lines.append("\n## 1. 설정 요약\n")
    for k, v in settings.items():
        lines.append(f"- **{k}**: {v}")

    lines.append("\n## 2. 핵심 지표표\n")
    df = summary_df.copy()
    for col in df.columns:
        if col in ("총수익률", "CAGR", "XIRR", "MDD", "연율변동성"):
            df[col] = df[col].map(lambda x: f"{x:.2%}" if pd.notna(x) else "-")
        elif df[col].dtype.kind in "fi":
            df[col] = df[col].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "-")
    lines.append(df.to_markdown(index=False))

    lines.append("\n## 3. 주요 이벤트 로그\n")
    any_event = False
    for r in results:
        evs = [e for e in r.events_log if e["구분"] in ("추가불입", "중도인출", "대출실행", "대출이자", "대출상환", "쿼터손절")]
        if evs:
            any_event = True
            lines.append(f"\n### {r.name}")
            for e in evs[:50]:
                d = pd.Timestamp(e["date"]).date()
                lines.append(f"- {d} {e['구분']}: {e['금액']:,.0f}")
    if not any_event:
        lines.append("- (추가 불입/인출/대출 이벤트 없음)")

    lines.append("\n## 4. 라오어 세트 요약\n")
    any_set = False
    for r in results:
        if r.laoer_sets is not None and not r.laoer_sets.empty:
            any_set = True
            s = r.laoer_sets
            done = s[s["종료사유"] != "진행중"]
            win = (done["세트손익"] > 0).mean() if len(done) else 0
            lines.append(f"- **{r.name}**: 완료 세트 {len(done)}개, 승률 {win:.0%}, "
                         f"평균 소요 {done['소요일'].mean():.0f}일" if len(done)
                         else f"- **{r.name}**: 완료 세트 없음 (진행 중)")
    if not any_set:
        lines.append("- (라오어 전략 없음)")

    lines.append("\n## 5. 진입 시점 민감도")
    lines.append("- (확장 예정 — sensitivity 모듈 추가 후 분위수 자동 기재)")

    if csv_path:
        lines.append(f"\n## 원본 데이터\n- 결과 CSV: `{csv_path}`")

    lines.append("\n" + QUESTIONS)
    return "\n".join(lines)


def save_ai_report(text: str, out_dir: str | Path) -> Path:
    out = Path(out_dir) / "ai_analysis_request.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return out
