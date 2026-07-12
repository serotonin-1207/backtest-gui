# -*- coding: utf-8 -*-
"""의견 게시판 화면 — 구글 폼 임베드(입력) + 공개 시트 CSV(목록)."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from . import board


def _setup_notice() -> None:
    st.info(
        "게시판이 아직 연결되지 않았습니다. 운영자 설정이 필요합니다 "
        "(구글 클라우드·서비스 계정은 **필요 없습니다**)."
    )
    st.markdown(
        "**설정 방법 (운영자용, 약 10분·전부 무료)**\n\n"
        "1. **구글 폼 만들기** — [forms.google.com](https://forms.google.com) → 빈 양식. 질문 3개를 "
        "**이 순서**로 추가합니다.\n"
        "   - `닉네임` (단답형, **필수**)\n"
        "   - `이메일` (단답형, 선택)\n"
        "   - `의견` (장문형, **필수**)\n"
        "2. **응답을 시트로 연결** — 폼 상단 **응답** 탭 → **시트로 연결** → 새 스프레드시트 생성.\n"
        "3. **'공개' 탭 만들기** — 그 시트 아래 **`＋`** 로 새 탭을 만들고 이름을 `공개` 로. A1 칸에 아래를 붙여넣습니다."
    )
    st.code(
        '=QUERY(\'설문지 응답 시트1\'!A:D, "SELECT A,B,D", 1)',
        language="text",
    )
    st.markdown(
        "   - `설문지 응답 시트1` 은 **실제 응답 탭 이름**으로 바꾸세요(시트 아래에 표시됨).\n"
        "   - A=타임스탬프, B=닉네임, D=의견만 가져오고 **C(이메일)는 제외**됩니다.\n"
        "4. **'공개' 탭을 웹에 게시** — 시트 메뉴 **파일 → 공유 → 웹에 게시** → 게시 대상을 **`공개` 탭**, "
        "형식을 **쉼표로 구분된 값(.csv)** 으로 선택 → **게시** → 나오는 **주소(CSV)를 복사**.\n"
        "5. **폼 임베드 주소 복사** — 폼 우측 상단 **보내기** → **`< >`(삽입)** 탭 → iframe 코드의 "
        "`src=\"...\"` 안의 주소(`.../viewform?embedded=true`)를 복사.\n"
        "6. **Streamlit Cloud → Manage app → Settings → Secrets** 에 아래를 붙여넣기:"
    )
    st.code(
        '[board]\n'
        'form_embed_url = "https://docs.google.com/forms/d/e/FORM_ID/viewform?embedded=true"\n'
        'csv_url = "https://docs.google.com/spreadsheets/d/e/.../pub?gid=0&single=true&output=csv"',
        language="toml",
    )
    st.caption(
        "저장하면 앱이 자동 재시작되며 게시판이 켜집니다. 이메일은 '공개' 탭에 없으므로 "
        "목록·CSV 어디에도 노출되지 않고, 원본 응답 시트에서 운영자만 볼 수 있습니다."
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

    st.subheader("✍️ 의견 남기기")
    components.iframe(board.form_embed_url(), height=760, scrolling=True)

    st.divider()
    st.subheader("💬 최근 의견")
    url = board.csv_url()
    if not url:
        st.caption("목록 표시가 아직 설정되지 않았습니다(공개 CSV 주소 미설정). 입력은 위 폼으로 가능합니다.")
        return

    try:
        posts = board.fetch_posts(url)
    except Exception:
        st.caption(
            "목록을 불러오지 못했습니다. 방금 게시하셨다면 반영까지 몇 분 걸릴 수 있습니다. "
            "잠시 후 새로고침 해주세요."
        )
        return

    if posts.empty:
        st.caption("아직 등록된 의견이 없습니다. 위 폼으로 첫 의견을 남겨보세요!")
        return

    top = st.columns([3, 1])
    top[0].caption(f"총 {len(posts)}개 · 새 글은 반영까지 몇 분 걸릴 수 있습니다.")
    if top[1].button("🔄 새로고침", width="stretch"):
        board.fetch_posts.clear()
        st.rerun()

    for _, row in posts.head(100).iterrows():
        with st.container(border=True):
            st.markdown(f"**{row['닉네임']}**  ·  {row['작성시각']}")
            st.text(str(row["의견"]))
            reply = str(row.get("답변", "")).strip()
            if reply:
                st.info(f"💬 **운영자 답변**\n\n{reply}")
