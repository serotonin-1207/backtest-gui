# -*- coding: utf-8 -*-
"""Excel 내보내기 (xlsxwriter 네이티브 차트 — 편집 가능한 차트 객체 삽입).

시트: Summary / Annual_Returns / Monthly_Returns / Daily_Equity / Cashflows /
      Contributions_Withdrawals / Laoer_Sets / Loan_Details / Charts / Settings
"""
from __future__ import annotations

import io

import pandas as pd
import xlsxwriter

from .metrics import annual_returns, monthly_returns_table

DISCLAIMER = "※ 백테스트 결과는 미래 수익을 보장하지 않습니다. 레버리지 ETF는 변동성 감쇠(volatility decay)로 장기 보유 시 구조적 손실 위험이 있습니다."


def build_excel(results: list, summary_df: pd.DataFrame, settings: dict) -> bytes:
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "nan_inf_to_errors": True})

    fmt_hdr = wb.add_format({"bold": True, "bg_color": "#1F3864", "font_color": "white",
                             "border": 1, "align": "center"})
    fmt_num = wb.add_format({"num_format": "#,##0"})
    fmt_pct = wb.add_format({"num_format": "0.00%"})
    fmt_date = wb.add_format({"num_format": "yyyy-mm-dd"})

    def write_df(ws_name: str, df: pd.DataFrame, pct_cols: set[str] = frozenset()):
        ws = wb.add_worksheet(ws_name)
        for c, col in enumerate(df.columns):
            ws.write(0, c, str(col), fmt_hdr)
            ws.set_column(c, c, max(12, len(str(col)) + 2))
        for r, (_, row) in enumerate(df.iterrows(), start=1):
            for c, col in enumerate(df.columns):
                v = row[col]
                if pd.isna(v):
                    ws.write_blank(r, c, None)
                elif isinstance(v, pd.Timestamp):
                    ws.write_datetime(r, c, v.to_pydatetime(), fmt_date)
                elif isinstance(v, (int, float)):
                    ws.write_number(r, c, float(v), fmt_pct if str(col) in pct_cols else fmt_num)
                else:
                    ws.write(r, c, str(v))
        return ws

    # ---- Summary
    pct_cols = {"총수익률", "CAGR", "XIRR", "MDD", "연율변동성"}
    write_df("Summary", summary_df.reset_index(drop=True), pct_cols)
    ws = wb.get_worksheet_by_name("Summary")
    ws.write(len(summary_df) + 2, 0, DISCLAIMER)

    # ---- Daily_Equity (전략별 순자산)
    eq = pd.DataFrame({r.name: r.equity for r in results}).dropna(how="all")
    eq_out = eq.reset_index().rename(columns={"index": "Date"})
    eq_out.columns = ["Date"] + [str(c) for c in eq_out.columns[1:]]
    write_df("Daily_Equity", eq_out)

    # ---- Annual / Monthly
    ann = pd.DataFrame({r.name: annual_returns(r.equity.dropna()) for r in results})
    ann_out = ann.reset_index().rename(columns={"index": "연도"})
    write_df("Annual_Returns", ann_out, set(ann.columns.astype(str)))
    mon_frames = []
    for r in results:
        t = monthly_returns_table(r.equity.dropna())
        t.insert(0, "전략", r.name)
        mon_frames.append(t.reset_index().rename(columns={"y": "연도"}))
    mon = pd.concat(mon_frames, ignore_index=True) if mon_frames else pd.DataFrame()
    if not mon.empty:
        write_df("Monthly_Returns", mon, {str(c) for c in mon.columns if isinstance(c, int)})

    # ---- Cashflows
    cf_rows = [{"전략": r.name, "날짜": pd.Timestamp(d), "금액(투입-, 회수+)": a}
               for r in results for d, a in r.cashflows]
    write_df("Cashflows", pd.DataFrame(cf_rows))

    # ---- Contributions_Withdrawals
    ev_rows = [{"전략": r.name, "날짜": pd.Timestamp(e["date"]), "구분": e["구분"], "금액": e["금액"]}
               for r in results for e in r.events_log if e["구분"] in ("추가불입", "중도인출")]
    write_df("Contributions_Withdrawals",
             pd.DataFrame(ev_rows) if ev_rows else pd.DataFrame(columns=["전략", "날짜", "구분", "금액"]))

    # ---- Laoer_Sets
    lao_frames = []
    for r in results:
        if r.laoer_sets is not None and not r.laoer_sets.empty:
            t = r.laoer_sets.copy()
            t.insert(0, "전략", r.name)
            lao_frames.append(t)
    write_df("Laoer_Sets", pd.concat(lao_frames, ignore_index=True) if lao_frames
             else pd.DataFrame(columns=["전략", "세트", "시작일", "종료일", "소요일", "최대투입액", "세트손익", "종료사유"]))

    # ---- Loan_Details
    loan_rows = [{"전략": r.name, "날짜": pd.Timestamp(e["date"]), "구분": e["구분"], "금액": e["금액"]}
                 for r in results for e in r.events_log if e["구분"] in ("대출실행", "대출이자", "대출상환")]
    write_df("Loan_Details",
             pd.DataFrame(loan_rows) if loan_rows else pd.DataFrame(columns=["전략", "날짜", "구분", "금액"]))

    # ---- Settings (재현용 스냅샷)
    ws_set = wb.add_worksheet("Settings")
    ws_set.write(0, 0, "설정 항목", fmt_hdr)
    ws_set.write(0, 1, "값", fmt_hdr)
    ws_set.set_column(0, 1, 30)
    for i, (k, v) in enumerate(settings.items(), start=1):
        ws_set.write(i, 0, str(k))
        ws_set.write(i, 1, str(v))
    ws_set.write(len(settings) + 2, 0, DISCLAIMER)

    # ---- Charts (네이티브 차트 객체)
    ws_ch = wb.add_worksheet("Charts")
    n_rows = len(eq_out)
    n_res = len(results)

    line = wb.add_chart({"type": "line"})
    for i in range(n_res):
        line.add_series({
            "name":       ["Daily_Equity", 0, i + 1],
            "categories": ["Daily_Equity", 1, 0, n_rows, 0],
            "values":     ["Daily_Equity", 1, i + 1, n_rows, i + 1],
        })
    line.set_title({"name": "전략별 순자산 곡선"})
    line.set_size({"width": 900, "height": 420})
    ws_ch.insert_chart("B2", line)

    bar = wb.add_chart({"type": "column"})
    name_col = list(summary_df.columns).index("전략명") if "전략명" in summary_df.columns else 0
    val_col = list(summary_df.columns).index("최종순자산") if "최종순자산" in summary_df.columns else 1
    bar.add_series({
        "name": "최종 순자산",
        "categories": ["Summary", 1, name_col, len(summary_df), name_col],
        "values":     ["Summary", 1, val_col, len(summary_df), val_col],
    })
    bar.set_title({"name": "전략별 최종 순자산"})
    bar.set_size({"width": 900, "height": 420})
    ws_ch.insert_chart("B24", bar)

    if not ann.empty:
        bar2 = wb.add_chart({"type": "column"})
        for i in range(len(ann.columns)):
            bar2.add_series({
                "name":       ["Annual_Returns", 0, i + 1],
                "categories": ["Annual_Returns", 1, 0, len(ann_out), 0],
                "values":     ["Annual_Returns", 1, i + 1, len(ann_out), i + 1],
            })
        bar2.set_title({"name": "연도별 수익률"})
        bar2.set_size({"width": 900, "height": 420})
        ws_ch.insert_chart("B46", bar2)

    wb.close()
    buf.seek(0)
    return buf.getvalue()
