# -*- coding: utf-8 -*-
"""실행: streamlit run main.py  (python main.py 로 실행해도 자동으로 Streamlit을 띄움)

클라우드(Streamlit Cloud)에서는 항상 `streamlit run main.py` 로 구동되므로
런타임 감지가 True가 되어 곧바로 render() 된다. 로컬에서 `python main.py` 로
직접 실행한 경우에만 streamlit run 으로 재실행한다(무한 재실행 방지 가드 포함).
"""
import os
import sys
from pathlib import Path


def _in_streamlit_runtime() -> bool:
    """Streamlit 런타임 안에서 실행 중인지 견고하게 판별."""
    # 1순위: 공식 런타임 존재 여부 API
    try:
        from streamlit.runtime import exists
        if exists():
            return True
    except Exception:
        pass
    # 2순위: 스크립트 실행 컨텍스트
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx() is not None:
            return True
    except Exception:
        pass
    return False


if _in_streamlit_runtime() or os.environ.get("BT_GUI_RELAUNCHED") == "1":
    from src.gui import render
    render()
else:
    # python main.py 로 직접 실행한 경우 → streamlit run 으로 재실행
    import subprocess
    here = Path(__file__).resolve().parent
    env = {**os.environ, "BT_GUI_RELAUNCHED": "1"}  # 재실행 루프 방지
    print("Streamlit 앱을 시작합니다... 브라우저가 자동으로 열립니다.")
    print("자동으로 열리지 않으면 브라우저에서 http://localhost:8501 로 접속하세요.")
    sys.exit(subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(here / "main.py")],
        cwd=str(here), env=env,
    ))
