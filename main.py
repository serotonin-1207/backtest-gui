# -*- coding: utf-8 -*-
"""실행: streamlit run main.py  (python main.py 로 실행해도 자동으로 Streamlit을 띄움)"""
import sys
from pathlib import Path


def _running_in_streamlit() -> bool:
    """streamlit run 으로 실행 중인지 판별."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


if _running_in_streamlit():
    from src.gui import render
    render()
else:
    # python main.py 로 직접 실행한 경우 → streamlit run 으로 재실행
    import subprocess
    here = Path(__file__).resolve().parent
    print("Streamlit 앱을 시작합니다... 브라우저가 자동으로 열립니다.")
    print("자동으로 열리지 않으면 브라우저에서 http://localhost:8501 로 접속하세요.")
    # cwd를 프로젝트 폴더로 고정 → 어디서 실행해도 .streamlit 테마/설정이 적용됨
    sys.exit(subprocess.call(
        [sys.executable, "-m", "streamlit", "run", str(here / "main.py")],
        cwd=str(here),
    ))
