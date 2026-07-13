# -*- coding: utf-8 -*-
"""방문자 카운터 — Google Apps Script 웹앱 백엔드(오늘/누적).

Streamlit Cloud는 파일이 재배포 때 초기화되므로 카운트를 외부에 보관한다.
서비스 계정을 쓰지 않고, 운영자 구글 계정으로 실행되는 Apps Script 웹앱을 호출한다
(조직 정책 iam.disableServiceAccountKeyCreation 회피).

st.secrets:
    [counter]
    script_url = "https://script.google.com/macros/s/XXXX/exec"

Apps Script는 GET 호출 시 카운트를 1 증가시키고 {"today":N,"total":M} JSON을 돌려준다.
?peek=1 이면 증가 없이 현재값만 반환. 세션당 1회만 증가시킨다(리런 중복 방지).
"""
from __future__ import annotations

import json
import urllib.request

import streamlit as st


def _url() -> str:
    try:
        return str(st.secrets["counter"]["script_url"]).strip()
    except Exception:
        return ""


def is_configured() -> bool:
    return _url().startswith("http")


def _fetch(peek: bool) -> dict | None:
    url = _url()
    if not url:
        return None
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}peek={'1' if peek else '0'}"
    try:
        with urllib.request.urlopen(full, timeout=4) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def render_visit_counter(container=None) -> None:
    """세션 첫 렌더에서 1회 카운트 증가 후, 오늘/누적을 캡션으로 표시."""
    tgt = container or st
    if not is_configured():
        return
    if "_visit_counts" not in st.session_state:
        st.session_state["_visit_counts"] = _fetch(peek=False) or {}
    d = st.session_state.get("_visit_counts") or {}
    today, total = d.get("today"), d.get("total")
    if today is None and total is None:
        return
    tgt.caption(f"👥 오늘 **{int(today):,}명** · 누적 **{int(total):,}명**")
