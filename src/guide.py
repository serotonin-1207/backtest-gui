# -*- coding: utf-8 -*-
"""투자 가이드 & 시뮬레이션 리포트 — 웹앱 상단 고정 배너 + 팝업(모달) + HTML 다운로드.

레버리지 ETF 위험 경고와, TQQQ 실측 기반 '적립식 전략 시뮬레이션'을 문서화한다.
수치는 프로그램 엔진으로 실제 계산한 값(재현 가능).
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
.gd { font-family:"Malgun Gothic",sans-serif; line-height:1.7; color:#e8eaf0; }
.gd h2 { color:#4fc3f7; border-left:5px solid #4fc3f7; padding-left:10px; margin-top:26px; }
.gd h3 { color:#82d4fa; margin-top:20px; }
.gd .warn { background:#3a2418; border-left:5px solid #ff7043; padding:12px 16px; border-radius:8px; margin:14px 0; }
.gd .tip  { background:#16301f; border-left:5px solid #66bb6a; padding:12px 16px; border-radius:8px; margin:14px 0; }
.gd .big  { font-size:19px; font-weight:bold; color:#ff8a65; }
.gd table { border-collapse:collapse; width:100%; margin:12px 0; font-size:13.5px; }
.gd th { background:#22304d; padding:8px; border:1px solid #2a3550; text-align:left; }
.gd td { padding:8px; border:1px solid #2a3550; }
.gd tr:nth-child(even) td { background:#161e30; }
.gd .step { background:#141b2b; border:1px solid #2a3550; border-radius:8px; padding:10px 14px; margin:8px 0; }
.gd code { background:#0e1420; border:1px solid #2a3550; padding:1px 6px; border-radius:4px; color:#ffd54f; }
.gd .neg { color:#ff8a80; font-weight:bold; } .gd .pos { color:#a5d6a7; font-weight:bold; }
</style>
"""

# ============================================================ 가이드 1: 위험 경고
GUIDE1 = _CSS + """
<div class="gd">
<div class="warn"><span class="big">⚠️ 레버리지 ETF(TQQQ·QLD)는 "청산"보다 "폭락 + 감쇠로 인한 회복불능"이 진짜 위험입니다.</span></div>
<p style="color:#9aa4bb;font-size:13px">※ 여기서 <b>QQQ = 나스닥100 1배 ETF</b>, <b>QLD = 2배</b>, <b>TQQQ = 3배</b> 레버리지입니다.
아래 예시는 <b>TQQQ(3배)</b> 기준이며, 배수가 낮을수록(QLD, QQQ) 위험도 낮아집니다.</p>

<h2>1. 강제청산·마진콜은 없지만, 전액손실(0 수렴)은 가능합니다</h2>
<p>TQQQ(3배)·QLD(2배)는 펀드 <b>내부에서</b> 스왑·선물로 레버리지를 만듭니다. 내가 빌린 돈이 아니라
마진콜·강제청산이 <b>없습니다</b> — 최악에도 <b>빚은 안 지고 투자금이 0에 수렴</b>할 뿐입니다.</p>
<ul>
<li><b>3배(TQQQ)</b>: 기초지수가 하루 <span class="neg">-33.3%</span> 빠지면 이론상 -100%.</li>
<li><b>2배(QLD)</b>: 하루 -50%면 0 (사실상 불가능).</li>
<li>미국은 <b>서킷브레이커(-20%)</b>로 하루 만의 -33%는 방어됩니다. 하지만…</li>
</ul>

<h2>2. 진짜 위험 = 연속 폭락 + 변동성 감쇠 → 원금 회복이 훨씬 느림</h2>
<div class="warn">
2021년 11월 고점 <b>42.2</b> → 2022년 저점 <b>7.7</b> = <span class="neg">-82% 폭락</span>.<br>
저점에서 회복하려면 <span class="neg">+445%</span>가 필요합니다.
</div>
<p><b>변동성 감쇠(volatility decay)</b>: 레버리지 ETF는 <b>매일</b> 배수를 리셋합니다. 그래서 오르락내리락하면
장기적으로 가치가 갉아먹힙니다. 예를 들어 지수가 <code>-50% 후 +100%</code>로 <b>제자리로 돌아와도</b>,
3배 ETF는 원금에 한참 못 미칩니다. <b>즉 나스닥100이 전고점을 회복해도 TQQQ는 여전히 밑에 있을 수 있습니다.</b></p>

<h2>3. 실측 — 최악의 타이밍에 몰빵했다면 (TQQQ, 2021-11 고점 진입 ~ 현재)</h2>
<table>
<tr><th>방식</th><th>최종 배수</th><th>최대낙폭(MDD)</th><th>전고점 무회복 기간</th></tr>
<tr><td>거치식(일시 투입)</td><td class="neg">2.02배</td><td class="neg">-82%</td><td class="neg">3.0년</td></tr>
<tr><td>적립식 2년</td><td class="pos">4.83배</td><td>-58%</td><td>0.6년</td></tr>
</table>
<p>고점에 전액 넣으면 <b>3년간 계좌가 반토막 이하로 물려</b> 있었고 겨우 2배. 같은 시점 적립식은 폭락장에 싸게 담아 완화됐습니다.</p>

<h2>4. 경각심 — 스스로에게 물어보세요</h2>
<div class="warn">
• SNS·유튜브의 "몇백 % 수익"은 <b>대상승장에서 살아남은 사람들</b>의 이야기입니다(생존자 편향).<br>
• <b>내 계좌가 -80%가 됐을 때 (1억 → 2천만원) 팔지 않고 버틸 수 있습니까?</b> 대부분은 그 지점에서 던지고,
그게 실제 파산의 원인입니다.<br>
• 레버리지 ETF는 <b>잃어도 되는 돈</b>, 그리고 <b>-80%를 버틸 수 있는 규모</b>로만.
</div>
<p style="color:#9aa4bb;font-size:12px">※ 위 수치는 과거에 TQQQ가 살아남은 특정 구간 결과이며, 폭락의 깊이·시점이 다르면 결과도 달라집니다. 미래 수익을 보장하지 않습니다.</p>
</div>
"""

# ============================================================ 리포트: 적립식 전략
REPORT = _CSS + """
<div class="gd">
<h2>📊 리포트: QQQ · QLD · TQQQ 적립식 vs 거치식 · 주기 · 기간 (실측)</h2>
<div class="tip">
<b>대상 3종 (모두 나스닥100 추종)</b> — <b>QQQ = 1배(나스닥100 ETF)</b>, <b>QLD = 2배</b>, <b>TQQQ = 3배</b> 레버리지.<br>
모든 숫자는 <b>이 프로그램의 가격 백테스트 엔진</b>으로 직접 계산했습니다(재현 가능). 투자금 1억, 세전 기준.
</div>

<h2>1. 실험 설계 & 우리 앱에서 재현하는 법</h2>
<p><b>공통</b> — 상단 <code>🧭 모드 = 📈 가격 백테스트</code>, 사이드바 <code>자산 선택 = QQQ, QLD, TQQQ</code>,
<code>투자금 = 100,000,000</code>.</p>
<div class="step"><b>① 장기 상승장</b>: 시작 <code>2015-01-01</code>, 종료 <code>오늘</code>, 방식 = 거치식 + 적립식(매월, 2년).
<b>왜</b>: 대표적 장기 상승장에서 배수별·방식별 차이를 봄.</div>
<div class="step"><b>② 최악 타이밍</b>: 시작만 <code>2021-11-01</code>(고점 직전, 2022 폭락 통과)로 변경.
<b>왜</b>: 진입 운이 나빴을 때 레버리지·적립식이 어떻게 되는지 봄.</div>
<div class="step"><b>③ 적립 주기</b>(TQQQ): 시작 <code>2020-01-01</code>, 적립 2년, 주기 = 매일/매주/매월.
<b>왜</b>: 주기만 바꿔 결과가 갈리는지 봄.</div>

<h2>2. 결과 (실측)</h2>
<h3>① 장기 상승장 (2015~현재)</h3>
<table>
<tr><th>종목(배수)</th><th>거치식 최종</th><th>적립식2년 최종</th><th>MDD</th></tr>
<tr><td>QQQ (1배)</td><td>7.65배</td><td>7.14배</td><td>-35%</td></tr>
<tr><td>QLD (2배)</td><td>22.3배</td><td>20.3배</td><td>-64%</td></tr>
<tr><td>TQQQ (3배)</td><td class="pos">39.8배</td><td>36.2배</td><td class="neg">-82%</td></tr>
</table>
<p>→ 상승장에선 <b>배수가 클수록 수익도 큼</b>. 대신 MDD가 QQQ -35% → TQQQ <b>-82%</b>로 급증.</p>

<h3>② 최악 타이밍 (2021-11 고점 ~ 현재)</h3>
<table>
<tr><th>종목(배수)</th><th>거치식 최종</th><th>적립식2년 최종</th><th>적립식 MDD</th></tr>
<tr><td>QQQ (1배)</td><td>1.92배</td><td>2.26배</td><td>-23%</td></tr>
<tr><td>QLD (2배)</td><td>2.21배</td><td>3.52배</td><td>-42%</td></tr>
<tr><td>TQQQ (3배)</td><td>2.04배</td><td class="pos">4.88배</td><td>-58%</td></tr>
</table>
<div class="warn">
<b>충격 포인트</b>: 최악의 타이밍에 <b>거치식</b>으로 넣으면 3배(TQQQ) <b>2.04배</b>가 1배(QQQ) <b>1.92배</b>와
거의 차이가 없습니다! <b>폭락 + 감쇠가 레버리지의 이점을 통째로 삼킨</b> 것입니다. 반면 <b>적립식</b>으로 바꾸면
TQQQ가 4.88배로 되살아납니다(폭락장에 싸게 담아서).
</div>

<h3>③ 적립 주기 (TQQQ, 2020 진입, 2년 분할)</h3>
<table>
<tr><th>주기</th><th>매일</th><th>매주</th><th>매월</th></tr>
<tr><td>최종 배수</td><td>4.68배</td><td>4.67배</td><td>4.76배</td></tr>
</table>
<p>→ 매일·매주·매월 <b>거의 무차별</b>(오차 수준).</p>

<h2>3. 결과 해석</h2>
<ul>
<li><b>레버리지 배수 = 양날의 검</b>: 상승장(①)엔 3배가 최고(39.8배)지만, 나쁜 타이밍(②)+거치식이면 3배 이점이 사라짐.
<b>레버리지는 "타이밍/변동성에 극도로 민감"</b>합니다.</li>
<li><b>적립식은 특히 고배수(TQQQ)에서 진가</b>: 최악 타이밍에도 거치식 2.04배 → 적립식 4.88배로 살림. 단, 적립이 끝나
전액 보유가 되면 MDD는 여전히 큼 — "진입 위험"만 줄이지 "보유 중 폭락"은 못 없앰.</li>
<li><b>주기는 거의 무차별</b>(③). 매주~매월이면 충분.</li>
</ul>

<h2>4. 대기자금 RP(이자)까지 넣으면 — 매일 vs 매월</h2>
<p>위 가격 백테스트는 <b>아직 투자 안 된 대기자금의 이자(RP)를 0으로</b> 가정합니다. 실제로는 그 돈을
CMA RP·발행어음·외화RP로 굴리므로, <b>매월(덜 자주)이 대기자금을 더 오래 들고 있어 RP를 더 법니다.</b></p>
<table>
<tr><th>적립 주기</th><th>대기자금 RP (세전)</th><th>세후</th></tr>
<tr><td>매일</td><td>4,894,345원</td><td>4,140,616원</td></tr>
<tr><td>매월</td><td>5,281,250원</td><td>4,467,938원</td></tr>
<tr><td><b>매월이 더 버는 RP</b></td><td class="pos">+386,905원</td><td class="pos">+327,321원</td></tr>
</table>
<p style="font-size:12px;color:#9aa4bb">조건: 총 3억, 1년(252거래일), RP 3.25%. 총투자금 대비 <b>약 +0.13%/년</b>.</p>
<div class="tip">
<b>상충 관계</b>: 덜 자주 살수록(매월) 대기자금 <b>RP ↑</b>(작지만 확실한 이자), 자주 살수록(매일) 주식 <b>노출 ↑</b>
(상승장이면 주가로 더 벌지만 방향에 좌우). RP 차이(0.13%/년)는 주가 변동(±수십%)보다 작아, <b>"주기는 큰 차이 없다"는
결론은 유지</b>되되, <b>"공짜 이자를 조금 더 챙기려면 매주~매월"</b>이 미세하게 낫습니다.
</div>
<p><b>우리 앱에서 RP 보기</b>: 상단 <code>🧭 모드 = 💵 적립식 현금관리 계산기</code> → 총투자금·선투입·기간·RP종류를
넣으면 대기자금 RP수익·후순위 이자·수수료의 <b>최종 순효과</b>가 나옵니다.</p>

<h2>5. 종합 — 어떻게 운용할지 판단 가이드</h2>
<table>
<tr><th>상황</th><th>추천</th></tr>
<tr><td>상승 확신 크고, -80% 낙폭도 버틸 자신 있음</td><td>거치식 또는 짧은 적립(1년)</td></tr>
<tr><td>진입 타이밍 불안 / 심리적으로 폭락 버티기 어려움</td><td><b>적립식 1~2년 (권장)</b></td></tr>
<tr><td>적립 주기</td><td>매주~매월 (RP 약간 이득). 매일도 OK. 매분기·매년은 비추천(타이밍 운 재유입)</td></tr>
<tr><td>적립 기간</td><td>1~2년. <b>최소 1년 이상 분산</b> (레버리지는 짧게 몰빵 금물)</td></tr>
<tr><td>대기자금</td><td>CMA RP·발행어음·외화RP로 운용, 후순위는 '매일 조달'이 효율적</td></tr>
<tr><td>보유 중 폭락까지 줄이고 싶다면</td><td>적립식 + 추세 필터(200일 이동평균선 위에서만 보유) 고려</td></tr>
</table>

<h2>6. 왜 결국 "QQQ(나스닥100)"인가?</h2>
<p>QQQ·QLD·TQQQ는 모두 나스닥100을 추종합니다. <b>1배 지수 중 왜 나스닥100이 우위인지</b>(S&P500·다우·나스닥종합·반도체
대비)는 상단 배너의 <b>"📈 왜 나스닥100(QQQ)인가?"</b> 버튼에서 자세히 다룹니다.</p>
<p>요약: 2010년 이후 나스닥100 CAGR <b>18.2%</b>로 S&P500(12.2%)·다우(10.2%)를 크게 앞서면서도
<b>MDD는 S&P500과 거의 같음(-36% vs -34%)</b> → "비슷한 낙폭에 더 높은 수익". 빅테크 성장주 집중 + 대형 우량주 100개(금융주 제외)가 이유입니다.</p>

<div class="warn" style="margin-top:20px">
<b>⚠️ 한계·재현성</b>: 위 수치는 과거에 QQQ·QLD·TQQQ가 살아남은 특정 구간 결과입니다. 폭락 깊이·시점이 다르면 결과가
달라지고, 세금·수수료·환율을 켜면 값이 낮아집니다. <b>백테스트는 미래 수익을 보장하지 않습니다.</b>
</div>
</div>
"""


# ============================================================ 왜 나스닥100(QQQ)? (1배 지수 비교)
WHY_QQQ = _CSS + """
<div class="gd">
<h2>📈 왜 "나스닥100(QQQ)"인가? — 다른 1배 지수와 비교</h2>
<div class="tip">
QQQ·QLD·TQQQ는 모두 나스닥100을 추종합니다. 여기서는 <b>레버리지 얘기가 아니라</b>, 대표적인
<b>1배 지수 ETF끼리</b> 비교해 왜 <b>나스닥100(=QQQ)</b>이 우위인지 봅니다.<br>
비교 대상: S&P500(SPY·VOO) · 다우존스(DIA) · 나스닥종합 · 필라델피아 반도체(SOXX·SMH) · 코스피.
</div>

<h2>1. 장기 성과 (거치식, 배당 제외 가격지수)</h2>
<table>
<tr><th>지수(대표 ETF)</th><th>2010~ (배수/CAGR)</th><th>2015~</th><th>MDD</th></tr>
<tr><td>다우존스 (DIA)</td><td>4.97배 / 10.2%</td><td>2.95배 / 9.8%</td><td>-37%</td></tr>
<tr><td>코스피</td><td>4.41배 / 9.4%</td><td>3.88배 / 12.5%</td><td>-44%</td></tr>
<tr><td>S&P500 (SPY·VOO)</td><td>6.67배 / 12.2%</td><td>3.67배 / 11.9%</td><td>-34%</td></tr>
<tr><td>나스닥종합</td><td>11.3배 / 15.8%</td><td>5.54배 / 16.0%</td><td>-36%</td></tr>
<tr><td><b>나스닥100 (QQQ)</b></td><td class="pos">15.8배 / 18.2%</td><td class="pos">7.03배 / 18.4%</td><td>-36%</td></tr>
<tr><td>반도체 (SOXX·SMH)</td><td>35.3배 / 24.1%</td><td>18.8배 / 29.0%</td><td class="neg">-47%</td></tr>
</table>

<h2>2. 핵심 — "비슷한 낙폭으로 더 높은 수익"</h2>
<div class="tip">
2010년 이후 <b>나스닥100 CAGR 18.2%</b>는 S&P500(12.2%)·다우(10.2%)·코스피(9.4%)를 크게 앞섭니다.
그런데 <b>최대낙폭(MDD)은 -36%로 S&P500(-34%)과 거의 같습니다.</b><br>
→ <b>위험(낙폭)은 비슷한데 수익은 더 높다</b> = 1배 지수 중 위험 대비 성과가 가장 좋다는 뜻입니다. 이게 "왜 QQQ"의 핵심입니다.
</div>

<h2>3. 왜 나스닥100이 앞섰나 (구성의 차이)</h2>
<ul>
<li><b>vs 다우(30개 가치주)</b>: 다우는 전통 산업 대형주 30개 위주라 <b>성장주가 적어</b> 최하위. 애플·엔비디아 같은 폭발 성장주 비중이 낮음.</li>
<li><b>vs S&P500(500개)</b>: 광범위하게 분산돼 안정적이지만, <b>성장 낮은 전통 섹터(금융·에너지·산업재) 비중</b>이 커서 나스닥100보다 수익이 낮음.</li>
<li><b>vs 나스닥종합(3,000여 개)</b>: 소형·부실주가 다수 섞여 발목을 잡음. <b>나스닥100은 그중 대형 우량주 100개 + 금융주 제외</b> → 알짜만 담아 더 나은 성과.</li>
<li><b>나스닥100의 힘</b>: 애플·MS·엔비디아·아마존·구글·메타·테슬라 등 <b>플랫폼·반도체 빅테크에 집중</b>. 지난 15년 이 기업들의 <b>이익·현금흐름 승자독식</b>이 지수를 끌어올렸습니다.</li>
</ul>

<h2>4. 정직한 반전 — "가장 많이 오른 건 QQQ가 아니다"</h2>
<div class="warn">
실제 <b>수익 1위는 반도체(SOX)</b>였습니다(2010~ 35배, CAGR 24%). 하지만 반도체는 <b>MDD -47%(닷컴 땐 -84%)</b>로
변동성이 훨씬 크고 <b>한 섹터에 집중</b>돼 위험이 큽니다. 즉 "더 높은 수익 = 더 큰 위험"의 전형.<br>
→ 그래서 대중적 1순위는 <b>"충분히 높은 수익 + 상대적 분산(빅테크 100개)"의 균형점인 나스닥100(QQQ)</b>이고,
여기에 배수를 건 것이 QLD(2배)·TQQQ(3배)입니다.
</div>

<h2>5. 잊지 말 것 — 나스닥100의 꼬리위험</h2>
<div class="warn">
나스닥100도 <b>닷컴버블 때 -83%</b> 폭락 후 <b>전고점 회복에 약 13년(2000→2015)</b>이 걸렸습니다. 기술주 쏠림은
<b>한 번 무너지면 회복이 매우 느릴 수</b> 있습니다. 그래서 <b>거치식 몰빵보다 적립식·기간 분산</b>이 중요합니다.
</div>
<p style="font-size:12px;color:#9aa4bb">※ 지난 15년은 저금리 + 빅테크 전성기였습니다. 금리·산업 국면이 바뀌면 미래엔 다른 지수가 앞설 수 있습니다.
백테스트는 미래를 보장하지 않습니다.</p>
</div>
"""


def _full_doc(title: str, body: str) -> bytes:
    html = (f"<!DOCTYPE html><html lang='ko'><head><meta charset='UTF-8'>"
            f"<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{title}</title></head><body style='background:#0e1420;margin:0;padding:24px'>"
            f"<div style='max-width:860px;margin:0 auto'>{body}</div></body></html>")
    return html.encode("utf-8")


@st.dialog("⚠️ 레버리지 ETF 생존 경고", width="large")
def _dlg_warning():
    st.html(GUIDE1)
    st.download_button("📥 이 경고문을 HTML로 저장 (새 탭에서 열기·공유·인쇄)",
                       _full_doc("레버리지 ETF 생존 경고", GUIDE1),
                       "leverage_warning.html", "text/html", use_container_width=True)


@st.dialog("📊 적립식 전략 시뮬레이션 리포트", width="large")
def _dlg_report():
    st.html(REPORT)
    st.download_button("📥 이 리포트를 HTML로 저장 (새 탭에서 열기·공유·인쇄)",
                       _full_doc("적립식 전략 시뮬레이션 리포트", REPORT),
                       "dca_strategy_report.html", "text/html", use_container_width=True)


@st.dialog("📈 왜 나스닥100(QQQ)인가?", width="large")
def _dlg_why():
    st.html(WHY_QQQ)
    st.download_button("📥 이 문서를 HTML로 저장 (새 탭에서 열기·공유·인쇄)",
                       _full_doc("왜 나스닥100(QQQ)인가 — 1배 지수 비교", WHY_QQQ),
                       "why_qqq.html", "text/html", use_container_width=True)


def render_pinned_guides():
    """웹앱 상단 고정 배너 — 클릭하면 팝업(모달)으로 크게 표시."""
    with st.container(border=True):
        st.markdown("#### 📌 투자 전 필독 — 레버리지 ETF 위험 & 지수/전략 가이드")
        st.caption("버튼을 누르면 큰 팝업 창으로 자세히 열립니다. 각 문서는 HTML로 저장해 새 탭·지인 공유·인쇄도 가능합니다.")
        c = st.columns(2)
        if c[0].button("⚠️ 레버리지 ETF 생존 경고", use_container_width=True, key="btn_guide_warn"):
            _dlg_warning()
        if c[1].button("📊 적립식 전략 시뮬레이션 리포트", use_container_width=True, key="btn_guide_report"):
            _dlg_report()
        if st.button("📈 왜 나스닥100(QQQ)인가? — 1배 지수 비교", use_container_width=True, key="btn_guide_why"):
            _dlg_why()
