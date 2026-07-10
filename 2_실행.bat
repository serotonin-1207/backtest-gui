@echo off
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo [안내] 아직 설치되지 않았습니다. 먼저 "1_설치.bat" 를 더블클릭하세요.
    pause
    exit /b 1
)

echo ============================================
echo   투자 백테스트 GUI 시작
echo   잠시 후 브라우저가 자동으로 열립니다.
echo   (안 열리면 브라우저에서 http://localhost:8501 접속)
echo.
echo   ※ 프로그램을 끝내려면 이 검은 창을 닫으세요.
echo ============================================
echo.

call venv\Scripts\activate.bat
streamlit run main.py
pause
