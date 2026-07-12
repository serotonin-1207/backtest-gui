# 세로토닌 백테스트 — 전체 작업기록 (AI 인수인계 문서)

> 이 문서는 다른 AI(GPT 등)나 개발자가 이 프로젝트를 이어받을 수 있도록 작성된 완전한 기록입니다.
> 최종 갱신: 2026-07-12 (v1.9.1)
> **새 세션/새 AI로 이어서 작업하려면 → §11 "이어서 작업하기"를 먼저 읽으세요.**

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
   ├─ routine_optimizer.py  # 롤링 시작일 기반 투자주기·기간·자산·방식 최적화
   ├─ routine_optimizer_page.py # 최적의 투자 루틴 추천 화면
   ├─ board.py              # 의견 게시판 백엔드(Google Sheets, gspread). is_configured/validate/add_post/fetch_posts
   ├─ board_page.py         # 의견 게시판 화면(입력폼+목록, secrets 미설정 시 설정안내)
   ├─ charts.py             # Plotly 차트 (PALETTE 고정 색)
   ├─ excel_export.py       # xlsxwriter 네이티브 차트 포함 Excel
   ├─ ai_report.py          # ai_analysis_request.md 생성
   ├─ cash_plan.py          # 적립식 현금관리 엔진 (순수함수)
   ├─ cash_plan_page.py     # 현금관리 계산기 화면
   ├─ guide.py              # 투자 가이드 팝업 3종 (경고/리포트/왜QQQ) + 차트
   ├─ indices_ref.py        # 미국 지수·레버리지 총정리 팝업 + index_ref_data.csv 차트
   ├─ china_ref.py          # 중국·홍콩 지수/ETF/종목 총정리 팝업 + 대표 지수 실측 차트(get_price)
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
- 미국(us_overseas): 연도별 실현손익 합산(원화, 거래일 환율) → 연 250만원 공제 → 22%. 다음 해 첫 거래일 납부·자산매도 복리효과 반영
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
| 1.7.0 | 참조 CSV 월간 자동생성·출처 메타데이터·CI, ETF 수정주가 재생성, 성과표 동적계산, 연도별 세금 납부 복리효과, 최근 5분봉 검증, 체결 안전마진, 공식 총수익 지수 우선 적용 |
| 1.8.0 | 최적의 투자 루틴 추천: QQQ·QLD·TQQQ, 5개 적립주기, 1~15년, 4개 투자방식 롤링 검증·위험한도·균형/수익/방어 점수, 경량 라오어·빠른 XIRR |
| 1.9.0 | 사이드바 빠른 기간 버튼(1/5/10/15/20/25/30년, 현재 기준), 주요 폭락 시작일 버튼(닷컴/금융위기/코로나/2022긴축/**트럼프관세** → 최고점~오늘), 폭락 참고표·막대차트에 트럼프 관세(2025-02→04) 추가. 날짜는 session_state(bt_start_date/bt_end_date) + on_click 콜백 제어 |
| 1.9.1 | 루틴 추천 버그 수정 3건(§8 ⑨~⑪): 경량 라오어 소진 대기 미유지·매수 예산 현금 상한 누락(변동장 최대 ±3%p → 전체 엔진과 1e-9 일치), 음수 점수 신뢰도 계수 역전, 위험한도 필터로 적립식 전멸 시 dimension_winners 크래시. 변동 경로 회귀 테스트 3개 추가(총 27개) |
| 1.11.2 | 사이드바 폭락 시작일 버튼에 '항셍테크(중국규제)' 추가(_CRASH_PEAKS, 고점 2021-02-17→현재). 폭락 참고표(_CRASH_REF_MD)에 중국 빅테크 규제 폭락 설명(항셍테크 -75%·2배 -96%, 알리바바 반독점·게임/사교육 규제). 미국지수와 시기·성격 달라 그룹 막대차트에는 미포함 |
| 1.11.1 | 항셍테크 2배 7226.HK 프리셋 추가(3033과 corr+0.996·기울기2.01로 2배 롱 확정, 7552=-2배숏). 사용자 티커 UI에서 '국가' 셀렉트박스 제거(자동판별) + .HK/.SS/.SZ 안내 캡션. china_ref에 '중국·홍콩판 QQQ/QLD/TQQQ·SOXX 레버리지' 섹션(순수 3배 테크·중국 반도체 레버리지 없음 명시, 7xxx.HK 롱/인버스 쌍 경고, 사용자 티커로 추가하는 법) |
| 1.11.0 | 🇨🇳🇭🇰 중국·홍콩 자산 추가: 프리셋에 지수(항셍 ^HSI·항셍중국기업 ^HSCE·상하이종합 000001.SS·선전성분 399001.SZ)·ETF(ASHR·3033.HK·FXI·MCHI·KWEB·CQQQ·YINN·CWEB)·홍콩주(텐센트·알리바바·메이투안·BYD·샤오미)·ADR(BABA·PDD·NIO·BIDU) 21종 추가(전부 yfinance 실측 검증). tax_category에 HKD/CNY 해외주식 22% 규칙·CN/HK 지수 none 추가, route_ticker에 .HK→HKD·.SS/.SZ→CNY, _download에 period=max 거부 시 start 폴백. 참고자료에 china_ref.py 소개 팝업(지수/ETF/종목 설명+실측 차트+규제·세금 주의). CSI300·창업판·STAR·항셍테크 원지수는 야후 미제공→ETF 대체. 회귀테스트 28개 |
| 1.10.2 | 사이드바에 텔레그램 채널 링크 추가 |
| 1.10.1 | 의견 게시판: 운영자 답변(시트 '답변' 열) 표시 |
| 1.10.0 | 💬 의견 게시판 모드 추가(§12). **구글 폼(입력 임베드) + 공개 시트 CSV(목록)** 방식 — 서비스 계정·JSON키·구글클라우드 불필요(조직 정책 iam.disableServiceAccountKeyCreation 우회). 닉네임 필수·이메일 선택이되 이메일은 '공개' 탭에서 제외해 목록/CSV 미노출(운영자 원본시트만). 스팸방어는 구글 폼이 처리, 목록 60초 캐시. secrets 미설정 시 설정안내 표시(앱 안 죽음). board.py/board_page.py. ⚠️초기엔 gspread 방식으로 만들었다가 조직 정책 벽에 막혀 폼 방식으로 전환함 |

## 5. 실측 데이터 (문서·팝업에 사용, 하드코딩된 참조값)

- **1배 지수 (2010~현재)**: 반도체SOX 35.3배/24.1% > 나스닥100 15.8배/18.2% > 나스닥종합 11.3배/15.8% > S&P500 6.67배/12.2% > 다우 4.97배/10.2% > 코스피 4.41배/9.4%. MDD: SOX -47%, 나100 -36%, S&P -34%
- **반도체는 최근만 급등 아님**: 2010~2021(AI붐 이전)도 10.8배/21.9%로 1위, 전 구간 1위
- **레버리지 상장 후**: TQQQ(2010~) 371배/43.4%/MDD-81.7%, SOXL 320배/42.4%/**-90.5%**, UPRO 129배/33%, QLD(2006~) 95배/25.5%/-83%
- **최악 타이밍(2021-11 고점~)**: 거치식 QQQ 1.92 ≈ TQQQ 2.04배(레버리지 이점 소멸!) vs 적립식2년 QQQ 2.26/QLD 3.52/TQQQ 4.88배, MDD -58%
- **상승장(2015~)**: 거치식 QQQ 7.65/QLD 22.3/TQQQ 39.8배
- **적립 주기(TQQQ 2020, 2년)**: 매일 4.68 ≈ 매주 4.67 ≈ 매월 4.76배 (무차별)
- **RP 대기수익(3억/1년/3.25%)**: 매일적립 세후 4,140,616 vs 매월 4,467,938 → 매월 +327,321원(+0.13%/년)
- **폭락**: 닷컴(2000-03→2002-10) 나100 -83%·회복 2015(13년) / 금융위기(2007-10→2009-03) ~-55% / 코로나(2020-02→03) -28~-37%·회복 3~9개월 / 2022긴축(2021-11→2022-12) -22~-46% / **트럼프관세(2025-02-19→2025-04-08) S&P-19%·나100-23%·반도체-35%·코스피-14%·회복 2025-05~07(1~4개월)**
- **폭락 버튼 시작일(고점)**: 닷컴 2000-03-24 / 금융위기 2007-10-09 / 코로나 2020-02-19 / 2022긴축 2021-11-19 / 트럼프관세 2025-02-19 (gui.py `_CRASH_PEAKS`)
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

## 8. 검증 상태 (2026-07-12 전체 검증 통과)

저장소 내 `unittest` 회귀 테스트 27개를 실행: 기존 CAGR·MDD·XIRR·TWR·세금·환율·라오어·참조데이터 검증에 더해 매분기 스케줄, 횡보장 원금 보존, 빠른 XIRR 일치, 경량 라오어와 전체 엔진 일치(상승장+폭락·약세·고변동 경로), 음수 점수 신뢰도 감점 방향, 적립식 없는 후보의 차원별 추천, 루틴 후보 정렬을 검증 — **전부 통과**.
발견·수정된 버그: ①적립식 총수익률(v2), ②무회복일 고점일 기준(1.5.0), ③미국 지수 22% 과세 오분류, ④환율 휴장일에 미래값 선택 가능성, ⑤라오어 거래비용 시 현금 음수, ⑥적립식 차트가 불입을 수익으로 표시, ⑦진행 중 월을 미래 월말로 표시, ⑧정확한 지정가 경계의 부동소수점 체결 누락(1.7.0), ⑨경량 라오어가 소진 후 대기 상태를 유지하지 않고 부분매도로 T가 내려가면 매수 재개 + 매수 예산에 현금 상한 누락 → 변동장에서 전체 엔진과 최대 ±3%p 오차(1.9.1), ⑩종합점수가 음수일 때 신뢰도 계수(0.85+0.15r)가 역방향(검증구간 적을수록 유리)으로 작동 → 음수는 나누기로 확대(1.9.1), ⑪위험한도 필터로 적립식 계열 전멸 시 dimension_winners idxmax 크래시 → 전체 후보 폴백(1.9.1). 알려진 근사·설계 특성(버그 아님): 국내ETF 과세표준 단순화, 장기 분봉 미제공 구간의 일봉 체결(안전마진·슬리피지로 보정), 총수익 지수 미제공 자산의 배당 연율 폴백, 현재환율 표시환산, 루틴 추천의 MDD는 TWR 기준이라 거치식·적립식·혼합이 사실상 동일(가격 낙폭)하고 적립식의 미투입 현금 완충은 미반영, 라오어는 원금 전액 첫날 투입(유휴현금이 XIRR 차감) vs 적립식은 투입 시점부터 계산.

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

---

## 11. 이어서 작업하기 (새 세션 / 새 AI 인수인계) ★중요

### 11-1. 작업 폴더 설정
- **작업 디렉토리(cwd)를 반드시 `C:\python\backtest_gui` 로 설정**한다. (git repo 루트, main 브랜치)
- 이 폴더 안에 `src/`, `main.py`, `PROJECT_작업기록.md`, `requirements.txt` 가 있어야 정상.
- 다른 폴더(C:\python 등)에서 시작하면 상대경로·import가 어긋난다.

### 11-2. 새 AI에게 줄 시작 프롬프트 (복붙용 템플릿)
```
작업 폴더: C:\python\backtest_gui  (여기를 작업 디렉토리로 설정)

이 프로젝트는 "세로토닌 백테스트"라는 Streamlit 웹앱이야.
먼저 C:\python\backtest_gui\PROJECT_작업기록.md 를 처음부터 끝까지 읽어.
그 문서에 전체 구조·수식·배포 함정·실측값·미구현 로드맵이 다 있어.

규칙:
- 코드는 src/ 안에 있고, 진입점은 main.py, 화면은 src/gui.py.
- 수치·데이터는 반드시 실측(get_price)으로 검증하고, 하드코딩 값은 근거를 남겨.
- 변경 후 반드시: ① python -c "import ast; ast.parse(open('src/gui.py',encoding='utf-8').read())" 로 문법 확인
  ② 가능하면 로컬에서 streamlit 실행해 눈으로 확인
  ③ src/gui.py의 APP_VERSION 을 올리고
  ④ git add -A && git commit && git push (push하면 Streamlit Cloud 자동 재배포)
- requirements.txt의 pandas<3/numpy<2.5/pyarrow<24 상한은 절대 풀지 마(클라우드 Segfault).
- .streamlit/config.toml에 [server] 섹션 넣지 마(클라우드 안 뜸).

오늘 할 일: (여기에 요청 작성)
```

### 11-3. 로컬 실행·검증 방법
- **실행**: 폴더에서 `streamlit run main.py` (또는 `2_실행.bat` 더블클릭). 브라우저 http://localhost:8501
- **문법 검증**: `python -c "import ast; [ast.parse(open('src/'+f,encoding='utf-8').read()) for f in ['gui.py','guide.py','indices_ref.py']]"`
- **회귀 테스트**: 저장소 `tests/` 의 unittest 실행 (`python -m pytest` 또는 `python -m unittest`). 수식/데이터 24개 검증
- **데이터 확인 스크립트 예시**: `from src.data_loader import get_price; get_price("TQQQ")`

### 11-4. 배포(웹앱 반영) 절차
1. `src/gui.py` 의 `APP_VERSION` 문자열을 올린다 (예: 1.9.0 → 1.10.0). ← 반영 확인 신호
2. `git add -A && git commit -m "..." && git push origin main`
3. 2~5분 뒤 웹앱(https://backtest-gui-pprg8sqv4dx5dbgmvcjcxf.streamlit.app) 사이드바 버전이 바뀌면 완료
4. 안 바뀌면: 웹앱 우하단 **Manage app → ⋮ → Reboot app** (사용자가 직접). 로그에 `Segmentation fault`면 requirements 문제, `headless` 관련이면 config.toml 문제
- GitHub 계정: serotonin-1207 (로컬에 gh CLI 인증됨). git push 시 자동 재배포

### 11-5. GPT 등 파일 업로드만 가능한 AI에게 넘길 때
- 이 **PROJECT_작업기록.md 파일 하나**만 줘도 전체 맥락 파악 가능 (구조·수식·함정 총망라).
- 실제 코드 수정까지 시키려면 `src/` 폴더 전체 + main.py + requirements.txt 를 함께 업로드.
- 무거운 것 제외 대상: `data/`(캐시 parquet), `venv/`, `python/`(임베디드), `__pycache__/`, `*.zip`
- 핵심 코드만 빠르게 파악하려면 읽는 순서: PROJECT_작업기록.md → src/gui.py(render 흐름) → 필요한 엔진(backtest_engine/laoer_strategy/cash_plan/routine_optimizer)

### 11-6. 현재 상태 요약 (2026-07-12 기준)
- 최신 버전 **v1.10.0**, 모든 커밋 push 완료(작업트리 깨끗), 웹앱 정상.
- 4개 모드: 📈 가격 백테스트 / 🎯 최적의 투자 루틴 추천 / 💵 적립식 현금관리 계산기 / 💬 의견 게시판.
- 최근 작업: 루틴 추천 버그 수정(v1.9.1), 의견 게시판 추가(v1.10.0).
- 바로 이어서 할 만한 것: §9 로드맵 (진입시점 민감도, 추세필터, 포터블판 재패키징 등).

---

## 12. 의견 게시판 설정 (운영자 1회 작업) ★게시판 쓰려면 필수

게시판은 코드로만 배포됐고, **구글 폼/시트 주소(secrets)를 넣기 전까지는 "설정 안내" 화면만 표시**된다(앱은 정상 동작). **구글 클라우드·서비스 계정은 필요 없다**(조직 정책으로 서비스 계정 키 생성이 막혀 폼 방식으로 전환함). 아래를 1회 설정하면 활성화된다.

1. **구글 폼 생성** — [forms.google.com](https://forms.google.com) → 빈 양식. 질문 3개를 **이 순서로**: `닉네임`(단답·필수), `이메일`(단답·선택), `의견`(장문·필수).
2. **응답을 시트로 연결** — 폼 **응답** 탭 → **시트로 연결** → 새 스프레드시트.
3. **'공개' 탭 생성** — 시트 아래 `＋`로 새 탭(이름 `공개`) → A1에 `=QUERY('설문지 응답 시트1'!A:D, "SELECT A,B,D", 1)` (응답 탭 실제 이름으로 교체). A=타임스탬프·B=닉네임·D=의견만, **C=이메일 제외**.
4. **'공개' 탭을 웹에 게시** — 시트 **파일 → 공유 → 웹에 게시** → 대상 `공개` 탭, 형식 `.csv` → 게시 → **CSV 주소 복사**.
5. **폼 임베드 주소 복사** — 폼 **보내기 → `< >`(삽입)** → `src="...viewform?embedded=true"` 복사.
6. **Streamlit Cloud → Manage app → Settings → Secrets** 에 붙여넣기:
   ```toml
   [board]
   form_embed_url = "https://docs.google.com/forms/d/e/FORM_ID/viewform?embedded=true"
   csv_url = "https://docs.google.com/spreadsheets/d/e/.../pub?gid=0&single=true&output=csv"
   ```
7. 저장 → 앱 자동 재시작 → 게시판 활성화.

**운영·정책**
- **이메일 비공개**: '공개' 탭(QUERY SELECT A,B,D)에서 이메일 열을 뺐으므로 목록/CSV 어디에도 안 나옴. 원본 응답 시트에서 운영자만 확인.
- **검열**: 부적절한 응답은 원본 응답 시트에서 해당 행 삭제(공개 탭 QUERY가 자동 반영). 최대 60초 캐시 후 목록에서 사라짐.
- **스팸 방어**: 입력이 구글 폼이라 구글의 기본 스팸/봇 방어를 그대로 이용. 필요 시 폼 설정에서 '로그인 필요' 또는 reCAPTCHA 강화 가능.
- **지연**: 새 글은 시트 반영 + 공개 CSV 캐시 때문에 목록에 뜨기까지 몇 분 걸릴 수 있음(정상). 폼 제출 자체는 즉시.
- **관련 코드**: `src/board.py`(주소 읽기·CSV 파싱), `src/board_page.py`(폼 임베드·목록). 추가 파이썬 패키지 없음.
- (참고) 서비스 계정(gspread) 방식으로도 구현 가능하나, 이 계정의 조직 정책 `iam.disableServiceAccountKeyCreation` 때문에 JSON 키 생성이 차단되어 폼 방식을 채택함.
