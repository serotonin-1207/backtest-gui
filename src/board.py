# -*- coding: utf-8 -*-
"""사용자 의견 게시판 — 구글 폼(입력) + 공개 시트 CSV(목록) 백엔드.

구글 클라우드 '서비스 계정'을 쓰지 않는다. (조직 정책
iam.disableServiceAccountKeyCreation 으로 키 생성이 막히는 문제를 회피)

- 입력: 구글 폼을 화면에 임베드 → 응답이 연결된 구글 시트에 자동 저장
- 목록: 시트의 '공개' 탭(이메일 제외)을 '웹에 게시'한 CSV를 읽어 표시

st.secrets 구조 (Streamlit Cloud → Manage app → Settings → Secrets):
    [board]
    form_embed_url = "https://docs.google.com/forms/d/e/FORM_ID/viewform?embedded=true"
    csv_url = "https://docs.google.com/spreadsheets/d/e/.../pub?gid=0&single=true&output=csv"

두 URL 모두 공개 주소라 '비밀'은 아니지만, 코드 수정 없이 바꿀 수 있도록 secrets에 둔다.
이메일은 '공개' 탭에 넣지 않으므로 목록/CSV 어디에도 노출되지 않는다.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st


def _cfg(key: str) -> str:
    try:
        return str(st.secrets["board"].get(key, "")).strip()
    except Exception:
        return ""


def form_embed_url() -> str:
    return _cfg("form_embed_url")


def csv_url() -> str:
    return _cfg("csv_url")


def is_configured() -> bool:
    """입력 폼 주소가 있으면 게시판을 활성화한다(목록 CSV는 선택)."""
    return bool(form_embed_url())


@st.cache_data(ttl=60, show_spinner=False)
def fetch_posts(url: str) -> pd.DataFrame:
    """공개 CSV를 읽어 작성시각·닉네임·의견(·운영자 답변)을 최신순으로 반환.

    열 이름은 폼/시트 설정에 따라 달라질 수 있어 이름을 유연하게 매칭한다.
    이메일 열은 애초에 공개 탭에 없으므로 여기서도 다루지 않는다.
    '답변'(운영자 답글) 열은 공개 탭에 있을 때만 표시된다(없으면 빈 값).
    """
    df = pd.read_csv(url)
    if df.empty:
        return pd.DataFrame(columns=["작성시각", "닉네임", "의견", "답변"])
    cols = {str(c).strip(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    def col_text(name_or_none, default=""):
        if name_or_none is None:
            return default
        s = df[name_or_none].astype(str).str.strip()
        return s.where(~s.str.lower().isin(["nan", ""]), default)

    tcol = pick("작성시각", "타임스탬프", "Timestamp") or df.columns[0]
    ncol = pick("닉네임", "이름", "Nickname", "name")
    mcol = pick("의견", "내용", "Message", "message")
    rcol = pick("답변", "운영자답변", "운영자 답변", "Reply", "답글")
    out = pd.DataFrame({
        "작성시각": df[tcol].astype(str) if tcol is not None else "",
        "닉네임": col_text(ncol, "익명"),
        "의견": col_text(mcol),
        "답변": col_text(rcol),
    })
    out = out[out["의견"].str.strip().ne("")]
    return out.iloc[::-1].reset_index(drop=True)
