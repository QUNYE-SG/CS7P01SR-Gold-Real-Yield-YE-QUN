import json
import shutil
import unittest
import csv
from statistics import correlation
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis import CORRELATION_COLUMN, YIELD_COLUMN
from update_v2_data import DEFAULT_INPUT
from update_v2_data import (
    HistoricalBar,
    YIELD_DATE_COLUMN,
    UpdateError,
    _ibkr_error_details,
    _parse_fred_payload,
    completed_gold_bars,
    merge_and_recalculate,
    run_update,
)


class V2UpdateTests(unittest.TestCase):
    def test_excludes_forming_and_future_gold_daily_bars(self):
        bars = [HistoricalBar(day, 10, 11, 9, 10)
                for day in ("2026-10-05", "2026-10-06", "2026-10-07")]
        now = datetime(2026, 10, 6, 0, 30, tzinfo=timezone.utc)
        self.assertEqual(completed_gold_bars(bars, now=now), bars[:1])

    def test_parses_fred_values_and_unpublished_observations(self):
        payload = json.dumps(
            {
                "observations": [
                    {"date": "2026-10-01", "value": "1.73"},
                    {"date": "2026-10-02", "value": "."},
                ]
            }
        )

        self.assertEqual(
            _parse_fred_payload(payload),
            {"2026-10-01": 1.73, "2026-10-02": None},
        )

    def test_rejects_fred_api_error_without_echoing_response_details(self):
        with self.assertRaises(UpdateError):
            _parse_fred_payload('{"error_code": 400, "error_message": "bad key"}')

    def test_normalizes_current_and_legacy_ibkr_error_callback_arguments(self):
        self.assertEqual(
            _ibkr_error_details((-1, 1791122666172, 2104, "market data farm connected", "")),
            (-1, 2104, "market data farm connected"),
        )
        self.assertEqual(
            _ibkr_error_details((1, 162, "historical data unavailable", "")),
            (1, 162, "historical data unavailable"),
        )
        self.assertIsNone(_ibkr_error_details((1, 162)))

    def test_merges_ibkr_bars_and_fred_yields_then_recalculates_five_day_correlation(self):
        fields = [
            "time", "open", "high", "low", "close", YIELD_COLUMN,
            "正相关", "负相关", CORRELATION_COLUMN, "备注",
        ]
        days = [(date(2026, 9, 28) + timedelta(days=index)).isoformat() for index in range(5)]
        closes = [10, 20, 30, 40, 50]
        existing = [
            {
                "time": day,
                "open": str(close),
                "high": str(close + 1),
                "low": str(close - 1),
                "close": str(close),
                YIELD_COLUMN: "9.9",
                "正相关": "0",
                "负相关": "0",
                CORRELATION_COLUMN: "0",
                "备注": "保留",
            }
            for day, close in zip(days, closes)
        ]
        bars = [
            HistoricalBar(days[-1], 51, 56, 50, 55),
            HistoricalBar("2026-10-03", 56, 60, 55, 59),
        ]
        fred = {
            "2026-09-25": 0.5,
            days[0]: 1.0,
            days[1]: 2.0,
            days[2]: 3.0,
            days[3]: None,
            days[4]: 5.0,
        }

        updated = merge_and_recalculate(fields, existing, bars, fred)

        self.assertEqual(len(updated), 6)
        self.assertEqual(updated[-2]["open"], "51.0")
        self.assertEqual(updated[-2]["close"], "55.0")
        self.assertEqual(updated[-2][YIELD_COLUMN], "5.0")
        self.assertEqual(updated[-1]["time"], "2026-10-03")
        self.assertEqual(updated[-1][YIELD_COLUMN], "")
        self.assertEqual(updated[3][YIELD_COLUMN], "")
        expected = correlation([10, 20, 30, 40, 55], [0.5, 1, 2, 3, 3])
        self.assertAlmostEqual(float(updated[-2][CORRELATION_COLUMN]), expected)
        self.assertEqual(updated[-2]["正相关"], updated[-2][CORRELATION_COLUMN])
        self.assertEqual(updated[-2]["负相关"], "0.0")
        self.assertEqual(existing[-1]["close"], "50")  # merge does not mutate source rows

    def test_full_update_builds_package_before_replacing_only_the_supplied_csv(self):
        with TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            input_copy = temp_root / "market_data.csv"
            package_dir = temp_root / "package"
            shutil.copyfile(DEFAULT_INPUT, input_copy)
            original_bytes = input_copy.read_bytes()
            with input_copy.open(encoding="utf-8-sig", newline="") as source:
                source_rows = list(csv.DictReader(source))

            # Supply the preceding observation when recomputing this isolated
            # fixture from its first row; this test verifies transaction safety.
            prior_context = {"2015-10-01": float(source_rows[0][YIELD_COLUMN])}
            result = run_update(input_copy, package_dir, bars=[], fred_values=prior_context,
                                source_start_date=None)

            self.assertEqual(result["row_count"], len(source_rows))
            self.assertEqual(result["last_date"], source_rows[-1]["time"])
            json.dumps(result)  # Status metadata must be JSON serializable.
            self.assertTrue(Path(result["package_zip"]).is_file())
            packaged_csv = package_dir / "market_data_pine5_raw_recalc.csv"
            self.assertEqual(input_copy.read_bytes(), packaged_csv.read_bytes())
            if result["data_changed"]:
                self.assertEqual((Path(result["backup_dir"]) / input_copy.name).read_bytes(), original_bytes)

    def test_source_switch_preserves_earlier_history_and_tracks_carried_fred_date(self):
        fields = ["time", "open", "high", "low", "close", YIELD_COLUMN,
                  "正相关", "负相关", CORRELATION_COLUMN, YIELD_DATE_COLUMN]
        old = [{"time": f"2026-09-{day}", "open": "10", "high": "11", "low": "9",
                "close": "10", YIELD_COLUMN: "9.9", "正相关": "0", "负相关": "-0.5",
                CORRELATION_COLUMN: "-0.5"} for day in (28, 29, 30)]
        old.append({**old[-1], "time": "2026-10-01"})
        old.append({**old[-1], "time": "2026-10-02"})
        bars = [HistoricalBar("2026-09-30", 20, 21, 19, 20),
                HistoricalBar("2026-10-02", 30, 31, 29, 30)]
        result = merge_and_recalculate(fields, old, bars,
                                       {"2026-09-25": 9.9, "2026-10-01": 2.88},
                                       source_start_date="2026-10-02")
        self.assertEqual(result[:4], old[:4])
        self.assertEqual(result[-1]["close"], "30.0")
        self.assertEqual(result[-1][YIELD_COLUMN], "2.88")
        self.assertEqual(result[-1][YIELD_DATE_COLUMN], "2026-10-01")

    def test_source_switch_requires_an_available_fred_observation(self):
        fields = ["time", "open", "high", "low", "close", YIELD_COLUMN,
                  "正相关", "负相关", CORRELATION_COLUMN]
        with self.assertRaises(UpdateError):
            merge_and_recalculate(fields, [], [HistoricalBar("2026-10-02", 10, 11, 9, 10)],
                                  {"2026-10-02": None}, source_start_date="2026-10-02")


if __name__ == "__main__":
    unittest.main()
