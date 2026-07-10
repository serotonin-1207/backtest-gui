@echo off
cd /d "%~dp0"
echo ============================================
echo   투자 백테스트 GUI - 최초 1회 설치
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 goto NOPYTHON

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [확인] Python %PYVER% 감지됨
echo.
echo [1/3] 가상환경(venv) 생성 중... (약 10초)
python -m venv venv
if errorlevel 1 goto FAIL

echo [2/3] 프로그램 구동에 필요한 패키지 설치 중... (약 2~5분, 인터넷 필요)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if errorlevel 1 goto FAIL

echo [3/3] 설치 확인 중...
python -c "import streamlit, plotly, pandas, yfinance, FinanceDataReader, xlsxwriter, pyarrow"
if errorlevel 1 goto FAIL

echo.
echo ============================================
echo   설치 완료!
echo   이제 "2_실행.bat" 를 더블클릭하면 됩니다.
echo ============================================
pause
exit /b 0

:NOPYTHON
echo [오류] 이 컴퓨터에 Python이 설치되어 있지 않습니다.
echo.
echo   1. 잠시 후 열리는 사이트에서 최신 Python을 다운로드해 설치하세요.
echo   2. 설치 첫 화면에서 반드시 "Add python.exe to PATH" 체크!
echo   3. 설치 후 이 파일(1_설치.bat)을 다시 더블클릭하세요.
echo.
start https://www.python.org/downloads/
pause
exit /b 1

:FAIL
echo.
echo [오류] 설치 중 문제가 발생했습니다.
echo   - 인터넷 연결을 확인하세요.
echo   - 회사 PC라면 보안 프로그램이 pip를 차단할 수 있습니다.
echo   - 해결이 안 되면 이 창을 캡처해서 배포자에게 문의하세요.
pause
exit /b 1
