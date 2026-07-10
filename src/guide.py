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
<h2>📊 리포트: 적립식 vs 거치식 · 적립 주기 · 기간 최적화 (TQQQ 실측)</h2>
<p>이 리포트의 모든 숫자는 <b>이 프로그램의 가격 백테스트 엔진</b>으로 직접 계산했습니다. 아래 "재현 방법"대로
누구나 똑같이 확인할 수 있습니다.</p>

<h2>1. 실험 설계 & 우리 앱에서 재현하는 법</h2>
<p><b>공통 설정</b> — 상단 <code>🧭 모드 = 📈 가격 백테스트</code>, 사이드바 <code>자산 선택 = TQQQ</code>,
<code>투자금 = 100,000,000</code>. (달러 자산이라 비교엔 단위 무관)</p>

<h3>실험 ① 장기 상승장 진입 — "상승장에선 뭐가 유리?"</h3>
<div class="step">
<b>설정</b>: 시작일 <code>2015-01-01</code>, 종료일 <code>오늘</code>, 투자 방식 = <b>거치식 + 적립식</b> 동시 체크 →
📥 적립식 설정에서 <b>적립 주기 = 매월</b>, <b>적립 기간 = 1년/2년/3년</b>을 각각 바꿔 실행.<br>
<b>왜</b>: 2015년 이후는 대표적 장기 상승장. 상승장에서 거치식(일찍 몰빵)과 적립식(나눠 사기)의 차이를 봄.
</div>

<h3>실험 ② 최악의 타이밍 진입 — "고점에 잘못 들어가면?"</h3>
<div class="step">
<b>설정</b>: 시작일만 <code>2021-11-01</code>로 변경(나머지 동일).<br>
<b>왜</b>: 2021년 11월은 사상 최고점 직전. 직후 2022년 대폭락을 통과 → "진입 운이 나빴을 때" 적립식이 얼마나 방어하는지 봄.
</div>

<h3>실험 ③ 적립 주기 비교 — "매일 vs 매주 vs 매월?"</h3>
<div class="step">
<b>설정</b>: 시작일 <code>2020-01-01</code>, 투자 방식 = 적립식, 적립 기간 = 2년, <b>적립 주기 = 매일 / 매주 / 매월</b>을 각각 실행.<br>
<b>왜</b>: 코로나 급락·급등이 섞인 구간에서 주기만 바꿔 결과가 갈리는지 봄.
</div>

<h2>2. 결과 (실측)</h2>
<h3>① 장기 상승장 (2015~현재)</h3>
<table>
<tr><th>방식</th><th>최종 배수</th><th>MDD</th></tr>
<tr><td>거치식(일시)</td><td class="pos">39.4배</td><td>-82%</td></tr>
<tr><td>적립식 1년 / 2년 / 3년</td><td>35.7 / 35.8 / 30.4배</td><td>-82%</td></tr>
</table>

<h3>② 최악 타이밍 (2021-11 고점 ~ 현재)</h3>
<table>
<tr><th>방식</th><th>최종 배수</th><th>MDD</th><th>무회복 기간</th></tr>
<tr><td>거치식(일시)</td><td class="neg">2.02배</td><td class="neg">-82%</td><td class="neg">3.0년</td></tr>
<tr><td>적립식 1년 / 2년 / 3년</td><td class="pos">4.29 / 4.83 / 4.16배</td><td>-58%</td><td>0.6년</td></tr>
</table>

<h3>③ 적립 주기 (2020 진입, 2년 분할)</h3>
<table>
<tr><th>주기</th><th>매일</th><th>매주</th><th>매월</th></tr>
<tr><td>최종 배수</td><td>4.68배</td><td>4.67배</td><td>4.76배</td></tr>
</table>

<h2>3. 결과 해석</h2>
<ul>
<li><b>상승장(①)엔 거치식이 유리</b>(39.4배 vs 30~36배) — 돈이 일찍 들어가서. 단, <b>적립이 끝나 전액 보유가 되면
MDD는 똑같이 -82%</b>. 적립식은 "진입 위험"만 줄이지 "보유 중 폭락"은 못 없앱니다.</li>
<li><b>최악 타이밍(②)엔 적립식 압승</b> — 거치식 2배·MDD -82%·3년 물림 vs 적립식 4.8배·MDD -58%·0.6년.
폭락장에 싸게 담아 회복 때 큰 포지션이 튐. <b>레버리지 ETF와 적립식은 특히 궁합이 좋습니다.</b></li>
<li><b>주기(③)는 거의 무차별</b> (4.68 / 4.67 / 4.76배). 매일·매주·매월 차이는 오차 수준.</li>
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

<div class="warn" style="margin-top:20px">
<b>⚠️ 한계·재현성</b>: 위 수치는 과거에 TQQQ가 살아남은 특정 구간 결과입니다. 폭락 깊이·시점이 다르면 결과가 달라지고,
세금·수수료·환율을 켜면 값이 낮아집니다. <b>백테스트는 미래 수익을 보장하지 않습니다.</b>
</div>
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


def render_pinned_guides():
    """웹앱 상단 고정 배너 — 클릭하면 팝업(모달)으로 크게 표시."""
    with st.container(border=True):
        st.markdown("#### 📌 투자 전 필독 — 레버리지 ETF 위험 & 적립식 전략 가이드")
        st.caption("아래 버튼을 누르면 큰 팝업 창으로 자세히 열립니다. 각 문서는 HTML로 저장해 새 탭·지인 공유·인쇄도 가능합니다.")
        c = st.columns(2)
        if c[0].button("⚠️ 레버리지 ETF 생존 경고 열기", use_container_width=True, key="btn_guide_warn"):
            _dlg_warning()
        if c[1].button("📊 적립식 전략 시뮬레이션 리포트 열기", use_container_width=True, key="btn_guide_report"):
            _dlg_report()
