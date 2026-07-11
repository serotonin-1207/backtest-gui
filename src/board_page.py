# -*- coding: utf-8 -*-
"""의견 게시판 Streamlit 화면 (Google Sheets 백엔드)."""
from __future__ import annotations

import time

import streamlit as st

from . import board

_COOLDOWN_SEC = 20  # 연속 등록 방지(초)


def _setup_notice() -> None:
    st.info(
        "게시판이 아직 연결되지 않았습니다. 운영자 설정이 필요합니다.\n\n"
        "**설정 방법 (운영자용)**\n"
        "1. Google Sheets에서 빈 시트를 하나 만들고 주소(URL)를 복사합니다.\n"
        "2. Google Cloud에서 **서비스계정**을 만들고 JSON 키를 내려받습니다.\n"
        "3. 시트를 그 서비스계정 이메일(`...@....iam.gserviceaccount.com`)에 **편집 권한**으로 공유합니다.\n"
        "4. Streamlit Cloud → **Manage app → Settings → Secrets** 에 아래를 붙여넣습니다.\n"
    )
    st.code(
        '[gcp_service_account]\n'
        'type = "service_account"\n'
        'project_id = "..."\n'
        'private_key_id = "..."\n'
        'private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"\n'
        'client_email = "...@....iam.gserviceaccount.com"\n'
        'client_id = "..."\n'
        'token_uri = "https://oauth2.googleapis.com/token"\n\n'
        '[board]\n'
        'sheet_url = "https://docs.google.com/spreadsheets/d/..../edit"',
        language="toml",
    )
    st.caption(
        "JSON 키의 각 항목을 위 형식에 그대로 옮기면 됩니다. private_key의 줄바꿈은 `\\n` 그대로 둡니다. "
        "시트 첫 행 헤더(작성시각·닉네임·이메일·의견·상태)는 자동으로 만들어집니다."
    )


def render_board() -> None:
    st.title("💬 의견 게시판")
    st.caption(
        "앱을 쓰면서 느낀 점·버그·개선 아이디어를 자유롭게 남겨주세요. "
        "**닉네임만 필수**이고 이메일은 선택입니다(답변이 필요할 때만)."
    )

    if not board.is_configured():
        _setup_notice()
        return

    with st.form("board_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nickname = c1.text_input(
            "닉네임 *", max_chars=board.MAX_NICK, placeholder="예: 투자하는너구리"
        )
        email = c2.text_input(
            "이메일 (선택)", max_chars=board.MAX_EMAIL,
            placeholder="답변 받을 이메일 (비워도 됩니다)",
        )
        message = st.text_area(
            "의견 *", max_chars=board.MAX_MSG, height=120,
            placeholder="자유롭게 남겨주세요. (링크·URL은 스팸 방지를 위해 제한됩니다)",
        )
        submitted = st.form_submit_button("의견 남기기", type="primary", width="stretch")

    if submitted:
        elapsed = time.time() - st.session_state.get("board_last_submit", 0.0)
        if elapsed < _COOLDOWN_SEC:
            st.warning(f"잠시 후 다시 시도해주세요. ({int(_COOLDOWN_SEC - elapsed)}초 후)")
        else:
            ok, msg = board.add_post(nickname, message, email)
            if ok:
                st.session_state["board_last_submit"] = time.time()
                st.success(msg)
            else:
                st.error(msg)

    st.divider()
    try:
        posts = board.fetch_posts()
    except Exception:
        st.error("게시글을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.")
        return

    st.subheader(f"최근 의견 ({len(posts)})")
    if posts.empty:
        st.caption("아직 등록된 의견이 없습니다. 첫 의견을 남겨보세요!")
        return

    for _, row in posts.head(100).iterrows():
        with st.container(border=True):
            st.markdown(f"**{row['닉네임']}**  ·  {row['작성시각']}")
            st.text(str(row["의견"]))
