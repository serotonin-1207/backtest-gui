# -*- coding: utf-8 -*-
"""TQQQ·QLD 공격형 투자 전략 최종 정리 — 팝업(모달) + 공유용 HTML.

이 앱으로 검증한 롤링 백테스트 결론을 한 장으로 정리한다:
거치식 vs 적립식, 분산 매수 기간·주기, TQQQ/QLD 비중(레버리지 배수).

검증 기반: 2010~현재 실측(배당 재투자 총수익=수정종가), 시작일을 매달 굴린 롤링,
각 3년 보유, 월 리밸런싱. TQQQ-QLD 일간수익 상관 0.9991(사실상 같은 자산).
세금·환율·수수료는 제외한 상대 비교 — 절대 수익이 아니라 '전략 간 우열' 판단용.
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
.sr { font-family:"Malgun Gothic",sans-serif; line-height:1.7; color:#e8eaf0; }
.sr h2 { color:#ffb74d; border-left:5px solid #ffb74d; padding-left:10px; margin-top:22px; }
.sr h3 { color:#4fc3f7; margin:16px 0 6px; }
.sr table { border-collapse:collapse; width:100%; margin:10px 0; font-size:13px; }
.sr th { background:#3a2e18; padding:7px; border:1px solid #4a3a20; text-align:left; }
.sr td { padding:7px; border:1px solid #4a3a20; }
.sr tr:nth-child(even) td { background:#1c1710; }
.sr .warn { background:#3a1a1a; border-left:5px solid #ff5252; padding:12px 15px; border-radius:8px; margin:12px 0; }
.sr .tip { background:#16301f; border-left:5px solid #66bb6a; padding:12px 15px; border-radius:8px; margin:12px 0; }
.sr .box { background:#182338; border-left:5px solid #4fc3f7; padding:12px 15px; border-radius:8px; margin:12px 0; }
.sr .neg{color:#ff8a80;font-weight:bold} .sr .pos{color:#a5d6a7;font-weight:bold}
</style>
"""

CORE_HTML = _CSS + """
<div class="sr">
<h2>🚀 TQQQ·QLD 공격형 전략 — 3줄 요약</h2>
<div class="box">
① <b>비중은 분산이 아니라 '레버리지 다이얼'</b> — TQQQ(3배)·QLD(2배)는 같은 나스닥100이라
상관 0.999. 섞는 건 실효 배수를 2~3배 사이에서 정하는 것.<br>
② <b>공격형 권장: TQQQ 50~75% + QLD 25~50%</b>(실효 2.5~2.75배)를 <b>6개월~1년에 걸쳐 매월 분산 매수</b>.<br>
③ <b>대가는 낙폭</b> — 최악 -74~-82%를 안 팔고 버틸 수 있어야 성립. 못 버티면 배수를 낮춰라.
</div>
</div>
"""

WEIGHT_HTML = _CSS + """
<div class="sr">
<h2>① 비중 (TQQQ : QLD) — 얼마나 공격적으로?</h2>
<p>롤링 3년 보유·월 리밸런싱 결과. 더 공격적일수록 <b>중앙 수익은 오르지만 낙폭은 깊어지고,
'운 나빴을 때 수익(하위10%)'은 오히려 낮아집니다.</b></p>
<table>
<tr><th>TQQQ : QLD</th><th>실효 배수</th><th>중앙 CAGR</th><th>하위10% CAGR</th><th>중앙 MDD</th><th>최악 MDD</th></tr>
<tr><td>0 : 100</td><td>2.0배</td><td>+33%</td><td class="pos">+13%</td><td>-42%</td><td>-64%</td></tr>
<tr><td>25 : 75</td><td>2.25배</td><td>+36%</td><td>+12%</td><td>-47%</td><td>-69%</td></tr>
<tr><td><b>50 : 50</b></td><td><b>2.5배</b></td><td><b>+40%</b></td><td>+11%</td><td>-51%</td><td>-74%</td></tr>
<tr><td><b>75 : 25</b></td><td><b>2.75배</b></td><td><b>+43%</b></td><td>+9%</td><td>-54%</td><td>-78%</td></tr>
<tr><td>100 : 0</td><td>3.0배</td><td>+45%</td><td class="neg">+7%</td><td>-58%</td><td class="neg">-82%</td></tr>
</table>
<div class="tip"><b>공격형 스윗스팟 = 50:50 ~ 75:25 (2.5~2.75배).</b>
100% TQQQ(3배)는 중앙 수익을 +5%p 더 얻자고 최악 -82% + 나쁜-타이밍 수익 감소를 감수하는 것이라,
'가장 공격적'이지만 효율은 오히려 떨어집니다. 1억 기준 최악 낙폭: 2.5배 → 한때 2,600만원, 3배 → 1,800만원.</div>
</div>
"""

SCHEDULE_HTML = _CSS + """
<div class="sr">
<h2>② 매수 일정 — 거치식 vs 적립식, 분산 기간·주기</h2>
<h3>분산 기간이 길수록: 기대수익 ↓, 타이밍 편차 ↓ (맞교환)</h3>
<table>
<tr><th>분산 기간 (TQQQ, 3년 보유)</th><th>중앙 CAGR</th><th>편차(상위90-하위10, 배수)</th></tr>
<tr><td>거치식(일시)</td><td>+46%</td><td class="neg">3.44 (가장 큼 = 타이밍 운 큼)</td></tr>
<tr><td><b>6개월</b></td><td><b>+40%</b></td><td>3.18</td></tr>
<tr><td><b>1년</b></td><td><b>+37%</b></td><td>2.98</td></tr>
<tr><td>2년</td><td>+30%</td><td class="pos">2.14 (가장 작음 = 안정)</td></tr>
</table>
<h3>주기(매일·매주·매월)는 사실상 무차별</h3>
<p>같은 분산 기간이면 매일·매주·매월의 중앙값·편차가 소수점까지 붙습니다. 6개월만 분산해도
매수가 6번 이상이라 타이밍이 평균화됩니다. <b>→ 자동이체 편한 '매월'로 하세요.</b>
('매월은 편차 클 것' 걱정은 1~2회로 몰아 살 때만 해당 = 사실상 거치식.)</p>
<div class="tip"><b>공격형 권장 일정 = 6개월(더 공격) ~ 1년(덜 공격) 분산, 매월 자동매수.</b>
레버리지는 장기 성장 자산이라 2년씩 현금으로 놀리면 기회비용이 큽니다 → 2년은 과함.
거치식(일시)은 변동성 큰 레버리지에서 타이밍 리스크가 가장 큽니다 → 비권장.</div>
</div>
"""

ZERO_HTML = _CSS + """
<div class="sr">
<h2>③ 레버리지가 0에 수렴하나? — 2배 vs 3배 진짜 최악장</h2>
<p><b>"정확히 0"은 사실상 불가능</b> — 3배가 하루 만에 0이 되려면 나스닥100이 하루 -33% 빠져야 하는데,
역대 최악 단일일이 -15%(1987)이고 -20%에서 증시가 강제 정지(서킷브레이커)됩니다.</p>
<p><b>하지만 긴 하락장의 감쇠로 -99%(실질 전멸)는 가능합니다</b> — 닷컴버블(2000~2002) 합성 시뮬레이션:</p>
<table>
<tr><th>레버리지</th><th>최대 낙폭</th><th>본전까지 필요 수익</th></tr>
<tr><td>나스닥100 (1x)</td><td>-83%</td><td>+485%</td></tr>
<tr><td>2배 (QLD형)</td><td class="neg">-98.6%</td><td>+7,061%</td></tr>
<tr><td>3배 (TQQQ형)</td><td class="neg">-99.9%</td><td>+176,628%</td></tr>
</table>
<p>1x도 전고점 회복에 <b>약 13년(2015년)</b> 걸렸고, 2·3배는 그 구간에서 <b>사실상 영구 미회복</b>입니다.</p>
<div class="tip"><b>적립식이면 다른가?</b> 지수가 회복하면 극적으로 다릅니다. 실제 TQQQ를 2021-11 고점(저점 -82%)부터
투자 시: 거치식 +83% vs <b>적립식 1년 +371%</b> — 바닥에서 싼 주식을 쌓아 회복 때 폭발합니다.
<b>단, 지수가 회복해야</b> 하고, 운용사가 상품을 청산(상장폐지)하면 손실이 그대로 확정됩니다
(2020년 3배 원유·변동성 ETF 실제 청산 사례 있음).</div>
<div class="warn"><b>핵심</b> — 바닥의 고통은 -78%든 -82%든 비슷합니다(맞는 직관). 진짜 차이는 <b>'회복 가능 여부'</b>와
꼬리 위험이며, 가장 큰 결정은 "2배냐 3배냐"보다 <b>"레버리지를 쓰느냐 마느냐"</b>입니다. 닷컴형 장이 오면
2·3배 모두 몇 년~영구 미회복이니, 그 구간에도 적립을 이어갈 현금과 심리가 있어야 이 전략이 성립합니다.</div>
</div>
"""

FINAL_HTML = _CSS + """
<div class="sr">
<h2>✅ 최종 결론 (공격형)</h2>
<div class="box">
<b>비중</b> TQQQ 50~75% + QLD 25~50% (실효 2.5~2.75배)<br>
<b>매수</b> 적립식으로 <b>6개월~1년</b>에 걸쳐 <b>매월</b> 자동 분산 (거치식·2년은 비권장)<br>
<b>보유</b> 장기 — 단, 폭락은 10년에 2~4번 반드시 온다는 전제로<br>
<b>기준</b> "얼마 벌까"가 아니라 <b>"최악 -74~-82%를 몇 년 버틸 수 있나"</b>로 배수를 정한다
</div>
<div class="warn">
<b>⚠️ 반드시 알아야 할 위험</b><br>
· 이 표는 2010년 이후 <b>대체로 상승장</b>이라 고배수에 유리하게 나온 값입니다. 닷컴급 장기 하락장이
오면 3배는 이보다 더 깊고 오래 무너집니다(레버리지 변동성 감쇠).<br>
· 최악 낙폭은 1억 → 한때 1,800만~2,600만원 수준입니다. 이 구간에서 파는 순간 전략은 실패합니다.<br>
· 세금·환율·수수료는 제외한 '전략 간 상대 비교'입니다. 실제 세후 수익은 이보다 낮습니다.<br>
· <b>과거 실측일 뿐 미래 보장이 아니며, 개별 투자 권유가 아닙니다.</b> 감당 가능한 범위에서 본인 책임하에.
</div>
</div>
"""


def _full_doc() -> bytes:
    body = CORE_HTML + WEIGHT_HTML + SCHEDULE_HTML + ZERO_HTML + FINAL_HTML
    html = ("<!DOCTYPE html><html lang='ko'><head><meta charset='UTF-8'>"
            "<title>TQQQ·QLD 공격형 투자 전략 정리</title></head>"
            "<body style='background:#0e1420;margin:0;padding:24px'>"
            f"<div style='max-width:900px;margin:0 auto'>{body}"
            "<p style='color:#6b7280;font-size:12px;margin-top:20px'>세로토닌 백테스트로 검증 · "
            "2010~현재 롤링(3년 보유·월 리밸런싱)·배당재투자 총수익 기준</p></div></body></html>")
    return html.encode("utf-8")


@st.dialog("🚀 TQQQ·QLD 공격형 전략 정리", width="large")
def _dlg_strategy():
    st.caption("이 앱으로 검증한 롤링 백테스트 결론 요약 · 2010~현재 · 배당재투자 총수익 · 세금/환율/수수료 제외(전략 간 상대 비교)")
    st.html(CORE_HTML)
    st.html(WEIGHT_HTML)
    st.html(SCHEDULE_HTML)
    st.html(ZERO_HTML)
    st.html(FINAL_HTML)
    st.download_button("📥 이 정리를 HTML로 저장 (새 탭에서 열기·공유·인쇄)", _full_doc(),
                       "tqqq_qld_aggressive_strategy.html", "text/html", width="stretch")


def render_strategy_button(container=None):
    """참고 자료 바 등에 버튼 배치 — 누르면 팝업."""
    tgt = container or st
    if tgt.button("🚀 TQQQ·QLD 공격형 전략 정리", width="stretch", key="btn_strategy_ref"):
        _dlg_strategy()
