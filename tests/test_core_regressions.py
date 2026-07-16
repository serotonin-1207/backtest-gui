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
from src import laoer_v4
from src.laoer_v4 import (
    calculate_final_sell_price,
    calculate_general_daily_budget,
    calculate_general_quarter_sell_quantity,
    calculate_general_star_percent,
    calculate_general_star_price,
    calculate_reverse_buy_budget,
    calculate_reverse_sell_quantity,
    is_cycle_completed,
    run_laoer_v4,
    should_enter_reverse_mode,
    should_exit_reverse_mode,
    update_T_after_general_quarter_sell,
    update_T_after_reverse_buy,
    update_T_after_reverse_sell,
)
from src.metrics import cagr, mdd, twr_index, xirr
from src.synthetic_etf import apply_dividend_addback, synthesize_close
from src.tax_engine import apply_annual_tax_drag, compute_tax, tax_schedule_asset
from src.routine_optimizer import (
    _contribution_result,
    _fast_xirr,
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

    def test_laoer_v4_spec_scenarios(self):
        # 명세 §33 테스트 1~7 (결정론적 계산 함수)
        self.assertAlmostEqual(calculate_general_star_percent("TQQQ", 10), 7.5)
        self.assertAlmostEqual(calculate_general_star_price("TQQQ", 50, 10), 53.75)
        self.assertAlmostEqual(calculate_general_daily_budget(15000, 10), 500.0)
        self.assertAlmostEqual(calculate_general_star_percent("TQQQ", 30), -7.5)
        self.assertAlmostEqual(calculate_general_star_price("TQQQ", 50, 30), 46.25)
        self.assertAlmostEqual(calculate_general_daily_budget(5000, 30), 500.0)
        self.assertEqual(calculate_general_quarter_sell_quantity(200), 50)
        self.assertAlmostEqual(update_T_after_general_quarter_sell(24), 18.0)
        self.assertTrue(should_enter_reverse_mode("GENERAL", 39.5))
        self.assertEqual(calculate_reverse_sell_quantity(200), 10)
        self.assertAlmostEqual(update_T_after_reverse_sell(39.5), 37.525)
        self.assertAlmostEqual(calculate_reverse_buy_budget(700), 175.0)
        self.assertAlmostEqual(update_T_after_reverse_buy(37.525), 38.14375)
        self.assertTrue(should_exit_reverse_mode("TQQQ", 42.60, 50))
        self.assertFalse(should_exit_reverse_mode("TQQQ", 42.40, 50))
        self.assertTrue(is_cycle_completed(0))
        # SOXL 상수
        self.assertAlmostEqual(calculate_general_star_percent("SOXL", 0), 20.0)
        self.assertAlmostEqual(calculate_final_sell_price("SOXL", 50), 60.0)

    def test_laoer_v4_sim_invariants(self):
        # 폭락 후 회복 경로에서 현금 음수 없음·T 비음수·낙폭이 buy&hold보다 얕음
        rng = np.random.default_rng(7)
        returns = np.concatenate(
            [np.full(80, 0.002), np.full(120, -0.01), np.full(300, 0.004)]
        ) + rng.normal(0, 0.008, 500)
        idx = pd.bdate_range("2020-01-02", periods=len(returns))
        close = 100.0 * np.cumprod(1.0 + returns)
        high = close * (1.0 + np.abs(rng.normal(0.004, 0.003, len(close))))
        ohlc = pd.DataFrame({"Close": close, "High": high}, index=idx)
        r = run_laoer_v4(ohlc, "t", 1_000_000.0, "TQQQ", fee_bp=5.0)
        self.assertGreaterEqual(float(r.cash_series.min()), -1e-6)
        self.assertGreaterEqual(float(r.t_series.min()), -1e-9)
        self.assertLessEqual(float(r.t_series.max()), 40.5)
        hold_mdd = mdd(pd.Series(close, index=idx))
        self.assertGreater(mdd(r.equity), hold_mdd)  # 라오어 낙폭이 더 얕음
        with self.assertRaises(laoer_v4.UnsupportedSymbolError):
            run_laoer_v4(ohlc, "t", 1.0, "QQQ")

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

    def test_laoer_v4_fee_never_makes_cash_negative(self):
        idx = pd.bdate_range("2024-01-01", periods=60)
        close = pd.Series(100.0 * (0.99 ** np.arange(60)), index=idx)
        ohlc = pd.DataFrame({"Close": close, "High": close}, index=idx)
        result = run_laoer_v4(ohlc, "fee-test", 1000.0, "TQQQ", fee_bp=100.0)
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
