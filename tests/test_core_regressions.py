from __future__ import annotations

import unittest

import pandas as pd

from src.backtest_engine import BacktestResult, run_backtest
from src.cash_plan import run_scenario
from src.charts import fig_equity
from src.currency import convert
from src.data_loader import tax_category
from src.gui import _at
from src.indices_ref import _chart_data, _fig, _fig_since_1990s
from src.laoer_strategy import run_laoer
from src.metrics import cagr, mdd, twr_index, xirr
from src.synthetic_etf import apply_dividend_addback, synthesize_close
from src.tax_engine import compute_tax


class CoreRegressionTests(unittest.TestCase):
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
