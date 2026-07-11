# 세로토닌 백테스트 — 전체 작업기록 (AI 인수인계 문서)

> 이 문서는 다른 AI(GPT 등)나 개발자가 이 프로젝트를 이어받을 수 있도록 작성된 완전한 기록입니다.
> 최종 갱신: 2026-07-11 (v1.6.0)

---

## 1. 프로젝트 개요

- **이름**: 세로토닌 백테스트 (제작 serotonin(이은호), serotonin.1207@gmail.com)
- **목적**: 미국·한국 지수/ETF/개별종목의 거치식·적립식·라오어 무한매수법 백테스트 + 적립식 현금관리(RP·조달이자·수수료) 계산
- **스택**: Python 3.14 + Streamlit + Plotly + pandas + yfinance + FinanceDataReader + xlsxwriter
- **소스**: `C:\python\backtest_gui` = git repo (main)
- **GitHub**: https://github.com/serotonin-1207/backtest-gui (공개)
- **웹앱**: https://backtest-gui-pprg8sqv4dx5dbgmvcjcxf.streamlit.app (Streamlit Community Cloud, git push 시 자동 재배포)
- **배포 확인법**: 사이드바 `🔖 버전 x.y.z` 표시로 반영 여부 확인 (gui.py의 `APP_VERSION`)

## 2. 파일 구조 및 역할

```
backtest_gui/
├─ main.py                  # 진입점. streamlit run 감지(runtime.exists) 실패 시 subprocess로 재실행
├─ requirements.txt         # ⚠️ pandas<3, numpy<2.5, pyarrow<24 상한 고정 (미고정 시 클라우드 Segfault)
├─ .streamlit/config.toml   # 다크 테마만. ⚠️ [server] headless 넣지 말 것(클라우드 이메일 프롬프트 행)
├─ PROJECT_작업기록.md       # 이 문서
├─ 1_설치.bat / 2_실행.bat   # 로컬 배포용. ⚠️ 반드시 CP949 + CRLF (UTF-8/LF면 cmd 파서 깨짐)
├─ 사용설명서.html           # 초보자 매뉴얼 (다크 테마 HTML)
└─ src/
   ├─ gui.py                # 메인 GUI. render()→모드 분기, _render_backtest(), 팝업 다이얼로그들, APP_VERSION
   ├─ data_loader.py        # 데이터 로딩+캐시. ASSET_PRESETS, route_ticker, get_price, tax_category
   ├─ backtest_engine.py    # 거치식/적립식 엔진. BacktestResult, run_backtest (fee_bp/slippage_bp/realized_gains)
   ├─ laoer_strategy.py     # 라오어 V2.2/V3.0. run_laoer(version=)
   ├─ cashflow_engine.py    # 불입/인출 이벤트 확장, dca_schedule
   ├─ metrics.py            # CAGR/MDD/XIRR/TWR/샤프/소르티노/칼마/무회복일
   ├─ currency.py           # 다중통화(KRW/USD/JPY/EUR/CNY/HKD), get_rates, get_fx_series, korean_money
   ├─ tax_engine.py         # 미국22%/국내ETF15.4%/국내주식 비과세
   ├─ synthetic_etf.py      # 레버리지 합성(일간수익률×배수), 배당 TR보정(apply_dividend_addback)
   ├─ interpret.py          # 결과 자동 해석 마크다운 생성
   ├─ validation.py         # 합성 vs 실제 ETF 검증(상관/추적오차)
   ├─ charts.py             # Plotly 차트 (PALETTE 고정 색)
   ├─ excel_export.py       # xlsxwriter 네이티브 차트 포함 Excel
   ├─ ai_report.py          # ai_analysis_request.md 생성
   ├─ cash_plan.py          # 적립식 현금관리 엔진 (순수함수)
   ├─ cash_plan_page.py     # 현금관리 계산기 화면
   ├─ guide.py              # 투자 가이드 팝업 3종 (경고/리포트/왜QQQ) + 차트
   ├─ indices_ref.py        # 미국 지수·레버리지 총정리 팝업 + index_ref_data.csv 차트
   └─ index_ref_data.csv    # 18개 지수/상품 월별 정규화 데이터 (precomputed)
```

## 3. 핵심 수식 (전부 검증됨 — §8 참고)

### 3-1. 성과 지표 (metrics.py)
- **총수익률** = 최종순자산 ÷ 순투입금 − 1 (순투입금 = 총투입 − 인출)
- **CAGR** = (끝/시작)^(365.25/일수) − 1 — TWR 지수에 적용
- **TWR**(시간가중): 일간 r_t = (E_t − F_t)/E_{t−1} − 1, F_t = 당일 외부 현금흐름(+불입/−인출). 누적곱.
  → 적립식에서 "입금 때문에 커진 것"을 제거한 순수 운용성과. CAGR/MDD/샤프/소르티노/칼마 모두 TWR 기준
- **XIRR**: 이분법(bisection, [-0.9999, 100]) — Σ CF_i/(1+r)^(days_i/365) = 0
- **MDD** = min(E/cummax(E) − 1)
- **최장무회복일**: 전고점 달성일부터 미회복 최장 달력일 (v1.5.0에서 고점일 기준으로 정밀화)
- **샤프** = mean(r)/std(r)×√252, **소르티노** = mean(r)/std(r<0)×√252, **칼마** = CAGR/|MDD|

### 3-2. 라오어 무한매수법 (laoer_strategy.py)
- **T값** = ceil(누적매수액/1회매수액 ×10)/10 (소수 둘째 자리 올림)
- **V2.2** (안정·40분할·단리): 오프셋 = (10 − T/2)%. 전반전(T<20): 1회분 절반 '평단가 LOC' + 절반 '평단×(1+오프셋) LOC'. 후반전: 전체 오프셋 LOC. 매도: 보유 1/4 '평단×(1+오프셋) LOC' + 3/4 '평단×1.10 지정가'. 세트 종료 시 원금 동일(단리)
- **V3.0** (공격·20분할·복리): 오프셋 = (15 − 1.5T)%, 지정가 +15%, 세트 종료 시 set_principal = cash (복리)
- 체결 근사: LOC 매수 = 종가≤지정가→종가 체결 / LOC 매도 = 종가≥지정가→종가 / 지정가 매도 = 고가≥지정가→지정가 (합성 구간은 종가만)
- 부분 매도 시 cum_buy −= 수량×평단 (원금 회수분 차감 → T 하락)
- 소진(T≥39.1 근사: cum_buy ≥ principal − one_buy×0.9): 대기 or 쿼터손절(보유 25% 매도 후 재개)
- 수수료: 회전액×(fee_bp+slip_bp)/1e4 현금 차감. 실현손익 = (순수령 − 수량×평단) 기록

### 3-3. 적립식 현금관리 (cash_plan.py) — 검증값 100% 재현
- 1일 투자금 = 총투자금/총거래일. 선투입 소진일 = 선투입/1일투자금
- **기간 환산 = 거래일수 ÷ 연간거래일수(252)** ← 스펙 본문의 /365는 오기, 검증값이 /252 기준
- RP수익(세전) = 평균잔액(금액/2) × 연수익률 × 기간, 세후 = ×(1−15.4%)
- 후순위 '매일': 이자 = (후순위/2)×이자율×기간, RP 없음 / '한번에': 전액 이자 + (후순위/2) RP
- 최종순효과 = 세후RP − 조달이자 − 이체수수료 − 환전비용 − 매수수수료
- **검증값**: 1년/3.25%/매일 → 최종 +1,083,000 (이체500원 시 +957,000) / 2년/2.05%/매일 → +812,400 (+560,400)

### 3-4. 세금 (tax_engine.py)
- 미국(us_overseas): 연도별 실현손익 합산(원화, 거래일 환율) → 연 250만원 공제 → 22%. 만기 청산 근사(최종값에서 일괄 차감)
- 국내ETF(kr_etf): 실현이익합×15.4% (손실통산 없음, 보수적) / 국내주식(kr_stock): 비과세 / 지수: none
- 분류: currency==USD→us_overseas, KR_ETF_TICKERS{122630,233740,069500,133690}→kr_etf, 6자리→kr_stock, 지수→none

### 3-5. 통화 (currency.py)
- rates = {통화: 1USD당}, yahoo "{cur}=X" (KRW 폴백: FDR 'USD/KRW')
- convert: value/rates[from]×rates[to] (USD 크로스). 왕복 무손실 검증됨
- 환율효과(언헤지): equity × 일별 FX 시계열 (gui._effective_series), 환효과기여 = 원화수익률 − 자산통화수익률
- korean_money: 조/억/만 2단위 표기 ("1억 2,345만원")

### 3-6. 합성 ETF (synthetic_etf.py)
- 합성 일수익 = 기초지수 일수익×배수 − 연보수/252. 단순 장기배수 곱 금지
- SYNTH_BASE: TQQQ/QLD←^NDX, SPXL←^GSPC, SOXL←^SOX, 122630←KS200
- 검증: TQQQ 합성 vs 실제 일수익 상관 0.999, QLD 0.996
- 배당 TR보정: 가격지수에 연배당률/252 가산 (INDEX_DIV_YIELD: ^GSPC 1.8%, ^NDX 0.8% 등)

## 4. 주요 기능 (버전 이력)

| 버전 | 내용 |
|---|---|
| 1.0 MVP | 데이터 캐시(parquet 증분+수정주가 소급감지), 거치식/적립식/라오어V2.2, 불입/인출+XIRR, 대출A(4.5%), Excel(네이티브차트), ai_analysis_request.md, README/도움말 |
| v2 | **적립식 총수익률 버그 수정**(equity[0]→순투입금 기준, 성과지표는 TWR), 해석 탭, 용어사전 |
| v3 | 다중통화(기준화폐 선택→자산통화 환산투입→표시통화 출력) |
| 1.1.0 | 현실화 4종: 세금/배당TR보정/환율효과(언헤지)/매매비용(bp) — 전부 기본 OFF |
| 1.2.0 | 적립식 현금관리 계산기 모드 (cash_plan) |
| 1.3.x | 투자 가이드 팝업(경고/리포트), 배포 안정화(requirements 상한 고정) |
| 1.4.x | 라오어 V3.0, 티커추가 UX(검증→목록→비움), 폭락참고, QQQ/QLD/TQQQ 리포트, 왜QQQ 팝업, 지수·레버리지 총정리(18종 차트), 참고자료 메인 이동, 모바일(배너 여백·멀티셀렉트 X 숨김) |
| 1.5.0 | 전 팝업 차트+최종결론 보강, 폭락표 연도, 도움말/용어 검색, 무회복일 정밀화 |
| 1.6.0 | 기본 자산 QQQ·QLD·TQQQ, 미국 지수 장기차트 2종·쉬운 해설, 지수 과세분류·환율 휴장일·라오어 거래비용 현금 오류 수정, 성과 차트를 TWR 기준으로 통일, 회귀 테스트 추가 |

## 5. 실측 데이터 (문서·팝업에 사용, 하드코딩된 참조값)

- **1배 지수 (2010~현재)**: 반도체SOX 35.3배/24.1% > 나스닥100 15.8배/18.2% > 나스닥종합 11.3배/15.8% > S&P500 6.67배/12.2% > 다우 4.97배/10.2% > 코스피 4.41배/9.4%. MDD: SOX -47%, 나100 -36%, S&P -34%
- **반도체는 최근만 급등 아님**: 2010~2021(AI붐 이전)도 10.8배/21.9%로 1위, 전 구간 1위
- **레버리지 상장 후**: TQQQ(2010~) 371배/43.4%/MDD-81.7%, SOXL 320배/42.4%/**-90.5%**, UPRO 129배/33%, QLD(2006~) 95배/25.5%/-83%
- **최악 타이밍(2021-11 고점~)**: 거치식 QQQ 1.92 ≈ TQQQ 2.04배(레버리지 이점 소멸!) vs 적립식2년 QQQ 2.26/QLD 3.52/TQQQ 4.88배, MDD -58%
- **상승장(2015~)**: 거치식 QQQ 7.65/QLD 22.3/TQQQ 39.8배
- **적립 주기(TQQQ 2020, 2년)**: 매일 4.68 ≈ 매주 4.67 ≈ 매월 4.76배 (무차별)
- **RP 대기수익(3억/1년/3.25%)**: 매일적립 세후 4,140,616 vs 매월 4,467,938 → 매월 +327,321원(+0.13%/년)
- **폭락**: 닷컴(2000-03→2002-10) 나100 -83%·회복 2015(13년) / 금융위기(2007-10→2009-03) ~-55% / 코로나(2020-02→03) -28~-37%·회복 3~9개월 / 2022긴축(2021-11→2022-12) -22~-46%
- **환율**: USD/KRW 약 1,509 (2026-07). 환효과: TQQQ 2018~ 달러 1204% vs 원화 1748%

## 6. 배포 관련 함정 (했던 삽질 — 반복 금지)

1. **yfinance는 start 없으면 최근 1개월만** → `period="max"` 필수. FDR도 기본 3000행 → start="1980-01-01"
2. **BAT 파일**: CP949 인코딩 + CRLF 필수. UTF-8이나 LF면 cmd가 줄을 깨서 오작동. PowerShell `WriteAllText(path, txt, GetEncoding(949))`로 저장
3. **Streamlit Cloud**: `.streamlit/config.toml`에 `[server] headless` 두면 이메일 프롬프트에 걸려 서버 안 뜸. main.py에서 streamlit 중첩 실행 금지(runtime.exists()로 감지)
4. **Segfault**: requirements 미고정 시 uv가 pandas3.0/numpy2.5/pyarrow24 설치 → Python3.14에서 크래시. 상한 고정으로 해결
5. **재배포 안 될 때**: Manage app → ⋮ → Reboot app. 반영 확인은 APP_VERSION으로
6. **st.dialog**: `@st.dialog(...)` 데코레이터, 내부에서 st.html(스타일 포함 HTML) 렌더 가능. st.markdown(unsafe)보다 안전
7. **모바일**: block-container padding-top 3rem(배너 잘림 방지), `[data-baseweb=select] [aria-label="Clear all"] display:none`(X 오탭 방지)
8. **포터블판**: 임베디드 Python(python-3.14.3-embed-amd64.zip) + ._pth에 `import site` 활성화 + get-pip → 무설치 실행

## 7. 배포물 (로컬)

- `C:\python\백테스트GUI_배포판.zip` (54KB, Python 필요, 1_설치.bat 방식)
- `C:\python\백테스트GUI_포터블판.zip` (152MB, 무설치, 임베디드 Python 내장)
- `C:\python\backtest_gui_완성본 1` (백업 스냅샷)
- ⚠️ **포터블판은 v1.1 시점 기준** — 최신 기능(현금관리·가이드·V3.0 등) 미포함. 재패키징 필요 시: 포터블 폴더에 src/ 등 덮어쓰고 재압축

## 8. 검증 상태 (2026-07-11 전체 검증 통과)

기존 24개 검증 항목에 더해 저장소 내 `unittest` 회귀 테스트 16개를 실행: CAGR·MDD·XIRR·TWR 폐형식, 거치식 가격비율, 현금관리 검증값, 환율 왕복·휴장일 직전값, 미국 지수 비과세 분류, 미국 세금 공제 후 22%, 국내주식 비과세, 라오어 거래비용 현금≥0, 합성 시작값, 지수 참조 데이터 미래날짜 방지, 두 장기차트 18개 구성 일치 — **전부 통과**.
발견·수정된 버그: ①적립식 총수익률(v2), ②무회복일 고점일 기준(1.5.0), ③미국 지수 22% 과세 오분류, ④환율 휴장일에 미래값 선택 가능성, ⑤라오어 거래비용 시 현금 음수, ⑥적립식 차트가 불입을 수익으로 표시, ⑦진행 중 월을 미래 월말로 표시(1.6.0). 알려진 근사(버그 아님): 세금 만기청산 일괄, 라오어 체결 낙관(수수료로 보정 가능), 배당 TR은 고정 연율 근사, 표시 환산은 현재 환율(엔진 계산은 일별 FX 지원).

## 9. 미구현 로드맵 (원 기획서 잔여)

- 진입시점 민감도 분석(sensitivity.py — 롤링 시작일 분포/분위수)
- 다자산 포트폴리오·리밸런싱(portfolio_engine.py), 상관관계 매트릭스
- 레짐/추세필터(200일 이평선 위에서만 매수)
- 워스트케이스 스트레스 테스트(폭락 구간만 잘라 리포트)
- 라오어 간이(Simple) 모드, 마진콜 시뮬레이션(대출 B형·유지증거금)
- 실질수익률(CPI), 벤치마크 알파/베타
- PySide6 데스크톱 버전 (로직은 이미 GUI 분리됨)
- 포터블판 최신화 재패키징

## 10. 사용자(운영자) 정보

- 한국어 사용. "백업해줘" = 폴더 전체를 `_완성본 N`으로 통째 복사
- 검증 중시: 수치는 반드시 실측·재현 가능해야 함. 결과가 이상하면 근본 원인을 찾는 스타일
- 커밋 후 반영 확인 습관: 웹앱 버전 표시 → 안 바뀌면 Reboot app 안내
