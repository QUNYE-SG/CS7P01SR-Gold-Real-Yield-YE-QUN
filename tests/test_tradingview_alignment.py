import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis import CORRELATION_COLUMN, YIELD_COLUMN, load_data
from build_top2_package import calculate_rankings, qualifying_rankings, build_package
from update_v2_data import (
    CORRELATION_YIELD_COLUMN, CORRELATION_YIELD_DATE_COLUMN,
    merge_and_recalculate, restore_tradingview_history, UpdateError,
)
from v2_pages import presentation_model, dashboard_page

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        return list(reader.fieldnames), list(reader)


class TradingViewAlignmentTests(unittest.TestCase):
    def test_production_history_restores_every_exported_coefficient(self):
        _, source = read(ROOT / "data" / "market_data.csv")
        _, current = read(ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv")
        lookup = {r["time"]: r for r in source}
        for row in current:
            if row["time"] >= "2026-10-02":
                continue
            for field in ("open", "high", "low", "close", YIELD_COLUMN,
                          "正相关", "负相关", CORRELATION_COLUMN):
                self.assertEqual(row[field], lookup[row["time"]][field], (row["time"], field))
        for day, expected in (("2026-04-21", .19939010221109577),
                              ("2026-07-07", .9774872127386507),
                              ("2026-07-22", .8460328444779778)):
            value = next(r[CORRELATION_COLUMN] for r in current if r["time"] == day)
            self.assertAlmostEqual(float(value), expected, places=12)

    def test_all_twenty_production_combinations_are_rescreened(self):
        # These expected counts were verified through 2026-10-06. Later daily
        # updates can mature additional candidates; do not change the historical
        # benchmark or mistake a larger live sample for an algorithm regression.
        rows = [row for row in load_data(ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv")
                if row.date.isoformat() <= "2026-10-06"]
        ranked, details, meta = calculate_rankings(rows)
        self.assertEqual(len(ranked), 20)
        self.assertEqual(meta["group_counts"], {"positive": 15, "negative": 31, "non_extreme": 282, "unavailable": 0})
        eligible = qualifying_rankings(ranked)
        self.assertEqual([(r["group"], r["horizon"], r["wins"], r["sample_count"]) for r in eligible],
                         [("positive", 4, 11, 15), ("negative", 6, 22, 31), ("negative", 10, 22, 31)])
        model = presentation_model(eligible, details, meta)
        self.assertEqual(model["unique_signal_count"], 46)
        self.assertEqual(sum(count for year, count in model["year_counts"]), 46)
        self.assertEqual(len(model["groups"]), 2)
        page = dashboard_page(model, commercial=True)
        self.assertIn("73.3%", page)
        self.assertIn("71.0%", page)
        self.assertNotIn("83.3%", page)
        self.assertNotIn("75.0%", page)
        self.assertNotIn("<details", page)

    def test_holiday_fred_observation_is_not_lost_by_gold_row_shift(self):
        fields = ["time", "open", "high", "low", "close", YIELD_COLUMN,
                  "正相关", "负相关", CORRELATION_COLUMN]
        rows = [{"time": day, "open": "10", "high": "11", "low": "9", "close": "10",
                 YIELD_COLUMN: str(value), "正相关": "0", "负相关": "0", CORRELATION_COLUMN: "0"}
                for day, value in (("2026-04-02", 1.97), ("2026-04-06", 1.98))]
        updated = merge_and_recalculate(fields, rows, [],
                                        {"2026-04-03": 1.99, "2026-04-06": 1.98},
                                        source_start_date="2026-04-06")
        self.assertEqual(updated[0], rows[0])
        self.assertEqual(updated[1][CORRELATION_YIELD_DATE_COLUMN], "2026-04-03")
        self.assertEqual(float(updated[1][CORRELATION_YIELD_COLUMN]), 1.99)

    def test_same_day_yield_and_correlation_input_are_separate(self):
        fields = ["time", "open", "high", "low", "close", YIELD_COLUMN,
                  "正相关", "负相关", CORRELATION_COLUMN]
        row = dict(zip(fields, ["2026-10-05", "10", "11", "9", "10", "2", "0", "0", "0"]))
        updated = merge_and_recalculate(fields, [row], [],
                                        {"2026-10-02": 2.0, "2026-10-05": 2.1},
                                        source_start_date="2026-10-05")
        self.assertEqual(float(updated[0][YIELD_COLUMN]), 2.1)
        self.assertEqual(float(updated[0][CORRELATION_YIELD_COLUMN]), 2.0)
        self.assertEqual(updated[0][CORRELATION_YIELD_DATE_COLUMN], "2026-10-02")

    def test_restore_cannot_hide_changed_raw_history(self):
        fields, rows = read(ROOT / "data" / "market_data.csv")
        changed = [dict(rows[0])]
        changed[0]["close"] = "9999"
        with self.assertRaises(UpdateError):
            restore_tradingview_history(changed, rows)

    def test_corrected_package_matches_input_and_dynamic_eligible_rows(self):
        path = ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv"
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "package"
            ranked, archive = build_package(path, output)
            self.assertEqual((output / "market_data_pine5_raw_recalc.csv").read_bytes(), path.read_bytes())
            _, eligible = read(output / "eligible_70_plus.csv")
            expected = qualifying_rankings(ranked)
            self.assertEqual([(r["group"], int(r["horizon"])) for r in eligible],
                             [(r["group"], r["horizon"]) for r in expected])
            self.assertTrue(archive.is_file())
            self.assertIn("TradingView 原指标导出", (output / "research_dashboard.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
