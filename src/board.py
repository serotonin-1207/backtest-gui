# -*- coding: utf-8 -*-
"""사용자 의견 게시판 — Google Sheets 저장 백엔드.

Streamlit Community Cloud는 로컬 파일이 재배포·리부트 때 초기화되므로 게시글은
외부(Google Sheets)에 보관한다. 서비스계정 키와 시트 주소는 st.secrets 로 주입한다
(코드/리포지토리에 노출되지 않음).

st.secrets 구조 (Streamlit Cloud → Manage app → Settings → Secrets):
    [gcp_service_account]
    type = "service_account"
    project_id = "..."
    private_key_id = "..."
    private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
    client_email = "...@....iam.gserviceaccount.com"
    client_id = "..."
    token_uri = "https://oauth2.googleapis.com/token"

    [board]
    sheet_url = "https://docs.google.com/spreadsheets/d/..../edit"

시트 헤더(A1:E1): 작성시각 | 닉네임 | 이메일 | 의견 | 상태
  - '상태' 칸에 '숨김'을 적으면 앱 목록에서 제외된다(운영자 수동 검열).
  - 이메일은 시트에만 저장되고 공개 목록에는 표시하지 않는다(최소 개인정보).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

HEADERS = ["작성시각", "닉네임", "이메일", "의견", "상태"]
KST = timezone(timedelta(hours=9))

MAX_NICK = 20
MAX_MSG = 1000
MAX_EMAIL = 100

_URL_RE = re.compile(
    r"(https?://|www\.|\b[\w-]+\.(com|net|org|io|co|kr|ru|cn|xyz|top|shop|info|biz)\b)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_configured() -> bool:
    """secrets 에 서비스계정 키와 시트 주소가 모두 있는지."""
    try:
        return (
            "gcp_service_account" in st.secrets
            and "board" in st.secrets
            and bool(st.secrets["board"].get("sheet_url"))
        )
    except Exception:
        return False


@st.cache_resource(show_spinner=False)
def _worksheet():
    """gspread 워크시트 핸들(세션 재사용). 헤더가 없으면 1회 생성한다."""
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=scopes
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["board"]["sheet_url"])
    ws = sheet.sheet1
    if not ws.row_values(1):
        ws.append_row(HEADERS, value_input_option="RAW")
    return ws


@st.cache_data(ttl=30, show_spinner=False)
def fetch_posts() -> pd.DataFrame:
    """게시글을 최신순으로 반환('숨김' 제외). 이메일 열은 목록에서 제거."""
    ws = _worksheet()
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        return pd.DataFrame(columns=["작성시각", "닉네임", "의견"])
    if "상태" in df.columns:
        df = df[df["상태"].astype(str).str.strip() != "숨김"]
    keep = [c for c in ["작성시각", "닉네임", "의견"] if c in df.columns]
    return df[keep].iloc[::-1].reset_index(drop=True)


def validate(nickname: str, message: str, email: str) -> tuple[bool, str]:
    """입력값 검증. (통과여부, 메시지)."""
    nickname = (nickname or "").strip()
    message = (message or "").strip()
    email = (email or "").strip()
    if not nickname:
        return False, "닉네임을 입력하세요."
    if len(nickname) > MAX_NICK:
        return False, f"닉네임은 {MAX_NICK}자 이내로 입력하세요."
    if not message:
        return False, "의견 내용을 입력하세요."
    if len(message) > MAX_MSG:
        return False, f"의견은 {MAX_MSG}자 이내로 입력하세요."
    if email:
        if len(email) > MAX_EMAIL or not _EMAIL_RE.match(email):
            return False, "이메일 형식이 올바르지 않습니다. 비워두셔도 됩니다."
    if _URL_RE.search(message) or _URL_RE.search(nickname):
        return False, "스팸 방지를 위해 링크(URL)가 포함된 글은 등록할 수 없습니다."
    return True, ""


def add_post(nickname: str, message: str, email: str = "") -> tuple[bool, str]:
    """검증 후 시트에 1행 추가. value_input_option='RAW'로 수식 주입(=,+,@) 방지."""
    ok, msg = validate(nickname, message, email)
    if not ok:
        return False, msg
    ts = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    row = [ts, nickname.strip(), email.strip(), message.strip(), ""]
    try:
        _worksheet().append_row(row, value_input_option="RAW")
    except Exception:
        return False, "저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    fetch_posts.clear()
    return True, "의견이 등록되었습니다. 감사합니다!"
