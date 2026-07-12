from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.backtest_engine import BacktestResult, run_backtest
from src.cash_plan import run_scenario
from src.cashflow_engine import dca_schedule
from src.charts import fig_equity
from src.currency import convert
from src.data_loader import ASSET_PRESETS, route_ticker, tax_category
from src.gui import _at
from src.indices_ref import _chart_data, _fig, _fig_since_1990s
from src.laoer_strategy import run_laoer
from src.metrics import cagr, mdd, twr_index, xirr
from src.synthetic_etf import apply_dividend_addback, synthesize_close
from src.tax_engine import apply_annual_tax_drag, compute_tax, tax_schedule_asset
from src.routine_optimizer import (
    _contribution_result,
    _fast_xirr,
    _laoer_result,
    _score,
    dimension_winners,
    optimize_routines,
)


class CoreRegressionTests(unittest.TestCase):
    def test_quarterly_schedule_is_supported(self):
        idx = pd.bdate_range("2020-01-01", "2021-01-05")
        schedule = dca_schedule(idx[0], idx, "매분기", None)
        self.assertGreaterEqual(len(schedule), 4)
        self.assertLessEqual(len(schedule), 6)

    def test_fast_xirr_matches_reference_xirr(self):
        flows = [
            (pd.Timestamp("2020-01-01"), -50.0),
            (pd.Timestamp("2020-06-01"), -25.0),
            (pd.Timestamp("2021-01-01"), -25.0),
            (pd.Timestamp("2023-01-01"), 150.0),
        ]
        self.assertAlmostEqual(_fast_xirr(flows), xirr(flows), places=7)

    def test_flat_market_routines_preserve_principal_without_fees(self):
        idx = pd.bdate_range("2020-01-01", "2022-01-03")
        close = pd.Series(100.0, index=idx)
        for strategy, frequency in (
            ("거치식", "1회"),
            ("적립식", "매월"),
            ("거치식 후 적립식", "매분기"),
        ):
            result = _contribution_result(close, strategy, frequency, 0.5, 0.0)
            self.assertAlmostEqual(result["배수"], 1.0)

    def test_routine_optimizer_returns_ranked_candidates(self):
        idx = pd.bdate_range("2010-01-01", "2024-12-31")
        close = pd.Series(
            100.0 * (1.0004 ** pd.RangeIndex(len(idx))), index=idx
        )
        ohlc = pd.DataFrame({"Close": close, "High": close}, index=idx)
        results = optimize_routines(
            {"QQQ": ohlc, "QLD": ohlc * 1.0},
            [1, 2],
            step_months=12,
            fee_bp=0,
            min_windows=5,
        )
        self.assertFalse(results.empty)
        self.assertTrue(results["종합점수"].is_monotonic_decreasing)
        winners = dimension_winners(results)
        self.assertEqual(
            set(winners), {"전체", "투자주기", "투자기간", "자산", "투자방식"}
        )

    def test_fast_laoer_matches_full_engine_without_events(self):
        idx = pd.bdate_range("2020-01-01", periods=500)
        close = pd.Series(
            100.0 * (1.0003 ** pd.RangeIndex(len(idx))), index=idx
        )
        ohlc = pd.DataFrame({"Close": close, "High": close * 1.005}, index=idx)
        fast = _laoer_result(ohlc, 5.0, "V2.2", 20.0)
        full = run_laoer(
            ohlc,
            "full",
            1.0,
            fee_bp=5.0,
            fill_buffer_bp=20.0,
            version="V2.2",
        )
        self.assertAlmostEqual(fast["배수"], full.final_value, places=9)
        self.assertAlmostEqual(fast["MDD"], mdd(full.equity), places=9)

    def test_fast_laoer_matches_full_engine_on_volatile_paths(self):
        # 상승만으로는 소진(대기)·현금 부족 경로가 실행되지 않으므로
        # 폭락 후 회복·약세장·고변동 랜덤 경로에서 전체 엔진과 일치를 확인한다.
        rng = np.random.default_rng(42)
        paths = [
            np.concatenate(
                [np.full(60, 0.001), np.full(120, -0.006), np.full(320, 0.004)]
            ),
            np.full(400, -0.002) + rng.normal(0, 0.01, 400),
            rng.normal(0.0005, 0.02, 600),
            rng.normal(0.0005, 0.02, 600),
        ]
        for returns in paths:
            idx = pd.bdate_range("2020-01-02", periods=len(returns))
            close = 100.0 * np.cumprod(1.0 + returns)
            high = close * (1.0 + np.abs(rng.normal(0.004, 0.003, len(close))))
            ohlc = pd.DataFrame({"Close": close, "High": high}, index=idx)
            for version, splits, target in (("V2.2", 40, 10.0), ("V3.0", 20, 15.0)):
                fast = _laoer_result(ohlc, 5.0, version, 20.0)
                full = run_laoer(
                    ohlc,
                    "full",
                    1.0,
                    fee_bp=5.0,
                    fill_buffer_bp=20.0,
                    version=version,
                    splits=splits,
                    target_pct=target,
                )
                self.assertAlmostEqual(fast["배수"], full.final_value, places=9)
                self.assertAlmostEqual(fast["MDD"], mdd(full.equity), places=9)

    def test_score_penalizes_fewer_windows_even_when_negative(self):
        row = {
            "중앙연수익률": -0.10,
            "하위10%연수익률": -0.30,
            "중앙MDD": -0.40,
            "최악MDD": -0.60,
            "수익구간비율": 0.3,
        }
        for objective in ("균형", "수익 우선", "방어 우선"):
            few = _score({**row, "검증구간수": 5}, objective)
            many = _score({**row, "검증구간수": 20}, objective)
            self.assertLess(few, many)

    def test_dimension_winners_survive_without_dca_candidates(self):
        base = {
            "투자기간": "5년", "기간(년)": 5, "검증구간수": 8,
            "중앙연수익률": 0.2, "하위10%연수익률": 0.05, "중앙MDD": -0.3,
            "최악MDD": -0.5, "수익구간비율": 0.9, "중앙최종배수": 2.0,
            "평균투자횟수": 10.0,
        }
        results = pd.DataFrame([
            {**base, "자산": "TQQQ", "투자방식": "라오어 무한매수법",
             "투자주기": "매일 주문", "종합점수": 0.15},
            {**base, "자산": "QQQ", "투자방식": "거치식",
             "투자주기": "1회", "종합점수": 0.10},
        ])
        winners = dimension_winners(results)
        self.assertEqual(winners["전체"]["투자방식"], "라오어 무한매수법")
        self.assertIn("투자주기", winners)

    def test_metric_closed_forms(self):
        idx = pd.to_datetime(["2024-01-01", "2024-12-31"])
        equity = pd.Series([100.0, 110.0], index=idx)
        expected = 1.1 ** (365.25 / 365.0) - 1.0
        self.assertAlmostEqual(cagr(equity), expected)
        self.assertAlmostEqual(xirr([(idx[0], -100.0), (idx[1], 110.0)]), 0.1)
        self.assertAlmostEqual(
            mdd(pd.Series([100.0, 80.0, 120.0], index=pd.date_range("2024-01-01", periods=3))),
            -0.2,
        )

    def test_twr_removes_external_contribution(self):
        idx = pd.bdate_range("2024-01-01", periods=3)
        equity = pd.Series([100.0, 210.0, 231.0], index=idx)
        twr = twr_index(equity, {idx[1]: 100.0})
        self.assertAlmostEqual(float(twr.iloc[-1]), 1.21)

    def test_buy_and_hold_matches_price_ratio(self):
        idx = pd.bdate_range("2024-01-01", periods=3)
        ohlc = pd.DataFrame({"Close": [100.0, 105.0, 120.0]}, index=idx)
        result = run_backtest(ohlc, "hold", "거치식", 1000.0)
        self.assertAlmostEqual(result.final_value, 1200.0)
        self.assertAlmostEqual(result.total_invested, 1000.0)

    def test_currency_conversion_round_trip(self):
        rates = {"USD": 1.0, "KRW": 1300.0, "JPY": 150.0}
        krw = convert(100.0, "USD", "KRW", rates)
        self.assertEqual(krw, 130000.0)
        self.assertAlmostEqual(convert(krw, "KRW", "USD", rates), 100.0)

    def test_us_tax_deduction_and_rate(self):
        gains = [(pd.Timestamp("2024-12-31"), 10_000_000.0)]
        tax = compute_tax(gains, "us_overseas")
        self.assertEqual(tax["taxable_krw"], 7_500_000.0)
        self.assertEqual(tax["total_tax_krw"], 1_650_000.0)

    def test_domestic_stock_is_tax_free(self):
        gains = [(pd.Timestamp("2024-12-31"), 10_000_000.0)]
        tax = compute_tax(gains, "kr_stock")
        self.assertEqual(tax["total_tax_krw"], 0.0)

    def test_annual_tax_payment_reduces_future_compounding(self):
        idx = pd.to_datetime(["2024-12-31", "2025-01-02", "2025-12-31"])
        equity = pd.Series([100.0, 100.0, 200.0], index=idx)
        adjusted, payments = apply_annual_tax_drag(
            equity, {}, {2024: 10.0}
        )
        self.assertEqual(payments, [(pd.Timestamp("2025-01-02"), 10.0)])
        self.assertAlmostEqual(float(adjusted.iloc[-1]), 180.0)

    def test_tax_schedule_preserves_total_asset_tax(self):
        info = {
            "total_tax_asset": 300.0,
            "by_year": {2023: {"세금": 100.0}, 2024: {"세금": 200.0}},
        }
        schedule = tax_schedule_asset(info)
        self.assertAlmostEqual(sum(schedule.values()), 300.0)
        self.assertAlmostEqual(schedule[2023], 100.0)

    def test_fill_buffer_blocks_borderline_laoer_sale(self):
        idx = pd.bdate_range("2024-01-01", periods=3)
        ohlc = pd.DataFrame(
            {"Close": [100.0, 110.05, 110.05], "High": [100.0, 110.05, 110.05]},
            index=idx,
        )
        normal = run_laoer(ohlc, "normal", 1000.0, splits=1, fill_buffer_bp=0)
        buffered = run_laoer(ohlc, "buffered", 1000.0, splits=1, fill_buffer_bp=100)
        normal_done = normal.laoer_sets["종료사유"].eq("전량매도").sum()
        buffered_done = buffered.laoer_sets["종료사유"].eq("전량매도").sum()
        self.assertGreater(normal_done, buffered_done)

    def test_cash_plan_reference_value(self):
        result = run_scenario(
            total=300_000_000,
            pre_amount=200_000_000,
            days=252,
            rp_yield=0.0325,
            debt_rate=0.045,
            sub_mode="매일",
        )
        self.assertAlmostEqual(result["최종순효과"], 1_083_000.0, places=6)

    def test_us_indices_are_not_taxed_like_etfs(self):
        for ticker in ("^GSPC", "^NDX", "^IXIC", "^DJI", "^SOX"):
            self.assertEqual(tax_category(ticker, "USD"), "none")
        self.assertEqual(tax_category("QQQ", "USD"), "us_overseas")

    def test_china_hk_tax_and_routing(self):
        # 홍콩·중국 지수는 직접 매매 상품이 아니므로 비과세 표시
        for ticker, cur in (("^HSI", "HKD"), ("^HSCE", "HKD"),
                            ("000001.SS", "CNY"), ("399001.SZ", "CNY")):
            self.assertEqual(tax_category(ticker, cur), "none")
        # 홍콩·중국 주식/ETF는 미국과 동일한 해외주식 양도세(us_overseas)
        for ticker, cur in (("0700.HK", "HKD"), ("3033.HK", "HKD"),
                            ("FXI", "USD"), ("BABA", "USD")):
            self.assertEqual(tax_category(ticker, cur), "us_overseas")
        # 커스텀 티커 라우팅: 접미사로 통화 판별
        self.assertEqual(route_ticker("0700.HK"), ("yahoo", "HKD"))
        self.assertEqual(route_ticker("000001.SS"), ("yahoo", "CNY"))
        self.assertEqual(route_ticker("399001.SZ"), ("yahoo", "CNY"))
        # 프리셋에 홍콩·중국 대표 자산이 실제로 담겨 있는지
        for name in ("항셍지수(HK)", "상하이종합", "텐센트(HK)", "중국인터넷(KWEB)",
                     "항셍테크 2배(7226)"):
            self.assertIn(name, ASSET_PRESETS)
        self.assertEqual(ASSET_PRESETS["항셍테크 2배(7226)"]["currency"], "HKD")

    def test_fx_lookup_uses_previous_observation(self):
        s = pd.Series(
            [1300.0, 1320.0],
            index=pd.to_datetime(["2024-01-05", "2024-01-08"]),
        )
        self.assertEqual(_at(s, "2024-01-06"), 1300.0)

    def test_laoer_fee_never_makes_cash_negative(self):
        idx = pd.bdate_range("2024-01-01", periods=3)
        ohlc = pd.DataFrame({"Close": 100.0, "High": 100.0}, index=idx)
        result = run_laoer(
            ohlc, "fee-test", principal=1000.0, splits=1, fee_bp=100.0
        )
        self.assertGreaterEqual(float(result.cash_series.min()), -1e-9)

    def test_laoer_withdrawal_accounts_for_selling_cost(self):
        idx = pd.bdate_range("2024-01-01", periods=3)
        ohlc = pd.DataFrame({"Close": 100.0, "High": 100.0}, index=idx)
        result = run_laoer(
            ohlc,
            "withdraw-test",
            principal=1000.0,
            splits=1,
            fee_bp=100.0,
            events=[{"date": idx[1], "amount": 1000.0, "kind": "인출"}],
        )
        self.assertGreaterEqual(float(result.cash_series.min()), -1e-9)

    def test_normalized_equity_chart_uses_twr(self):
        idx = pd.bdate_range("2024-01-01", periods=3)
        result = BacktestResult(
            name="dca",
            equity=pd.Series([100.0, 200.0, 200.0], index=idx),
            flows={idx[1]: 100.0},
        )
        fig = fig_equity([result], normalize=True)
        self.assertEqual(list(fig.data[0].y), [100.0, 100.0, 100.0])

    def test_synthetic_series_starts_at_exactly_100(self):
        idx = pd.bdate_range("2024-01-01", periods=3)
        base = pd.Series([100.0, 101.0, 102.0], index=idx)
        synth = synthesize_close(base, leverage=3.0, annual_fee=0.01)
        self.assertAlmostEqual(float(synth.iloc[0]), 100.0)

    def test_dividend_adjustment_preserves_first_price(self):
        idx = pd.bdate_range("2024-01-01", periods=3)
        ohlc = pd.DataFrame({"Close": [100.0, 101.0, 102.0]}, index=idx)
        adjusted = apply_dividend_addback(ohlc, 0.02)
        self.assertAlmostEqual(float(adjusted["Close"].iloc[0]), 100.0)

    def test_reference_chart_dates_are_not_in_the_future(self):
        df = _chart_data()
        self.assertLessEqual(df.index.max(), pd.Timestamp.today().normalize())

    def test_reference_charts_have_identical_series(self):
        names1 = [trace.name for trace in _fig().data]
        names2 = [trace.name for trace in _fig_since_1990s().data]
        self.assertEqual(names1, names2)
        self.assertEqual(len(names1), 18)


if __name__ == "__main__":
    unittest.main()
