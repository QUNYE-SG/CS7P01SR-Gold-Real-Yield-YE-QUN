import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from build_top2_package import build_package, calculate_rankings, qualifying_rankings
from analysis import load_data


ROOT = Path(__file__).resolve().parents[1]
# Frozen legacy presentation fixture, not the corrected production ranking.
INPUT = ROOT / "tests" / "fixtures" / "v2_legacy_same_day_20261002.csv"


class RankedPackageTests(unittest.TestCase):
    def test_v2_entry_points_route_to_the_recalculated_ranking(self):
        for launcher_name in ("RUN_LOCAL_DEMO.bat", "RUN_PINE5_RECALC_PREVIEW.bat"):
            launcher = (ROOT / launcher_name).read_text(encoding="utf-8")
            self.assertIn("RUN_TOP2_PINE5_PACKAGE.bat", launcher)
            self.assertNotIn("app.py", launcher)

        for page_name in ("index.html", "research_dashboard.html", "commercial_dashboard.html"):
            page = (ROOT / "output" / page_name).read_text(encoding="utf-8")
            self.assertNotIn("http-equiv=\"refresh\"", page)
            self.assertIn("research_dashboard.html", page)
            self.assertIn("commercial_dashboard.html", page)
        research = (ROOT / "output" / "research_dashboard.html").read_text(encoding="utf-8")
        self.assertIn('href="top2_pine5_20261004/signal_details.csv"', research)

    def test_ranks_all_twenty_sign_group_and_horizon_combinations(self):
        rows = load_data(INPUT)
        ranked, details, metadata = calculate_rankings(rows)

        self.assertEqual(len(ranked), 20)
        self.assertEqual(metadata["common_ab_count"], 328)
        self.assertEqual(metadata["group_counts"]["positive"], 12)
        self.assertEqual(metadata["group_counts"]["negative"], 77)
        self.assertEqual(len(details), (12 + 77) * 10)
        self.assertEqual(set(row["horizon"] for row in ranked), set(range(1, 11)))
        self.assertEqual({row["group"] for row in ranked}, {"positive", "negative"})
        sort_keys = [
            (-row["win_probability"], 0 if row["group"] == "positive" else 1, row["horizon"])
            for row in ranked
        ]
        self.assertEqual(sort_keys, sorted(sort_keys))

    def test_includes_every_strategy_at_or_above_seventy_percent(self):
        ranked, _, _ = calculate_rankings(load_data(INPUT))
        eligible = qualifying_rankings(ranked)

        self.assertEqual(
            [(row["group"], row["horizon"]) for row in eligible],
            [("positive", 1), ("positive", 3), ("positive", 4), ("positive", 8), ("positive", 9),
             ("positive", 5), ("positive", 6), ("positive", 7)],
        )
        self.assertTrue(all(row["win_probability"] >= 0.70 for row in eligible))
        self.assertEqual([row["win_probability"] for row in eligible[:5]], [10 / 12] * 5)
        self.assertEqual([row["win_probability"] for row in eligible[5:]], [9 / 12] * 3)

    def test_creates_a_separate_auditable_package_and_zip(self):
        with TemporaryDirectory() as tmp:
            package_dir = Path(tmp) / "top2_package"
            ranked, zip_path = build_package(INPUT, package_dir)
            self.assertEqual(len(ranked), 20)
            self.assertEqual(
                {path.name for path in package_dir.iterdir()},
                {"index.html", "research_dashboard.html", "commercial_dashboard.html",
                 "index_en.html", "research_dashboard_en.html", "commercial_dashboard_en.html",
                 "eligible_70_plus.csv", "ranking_20.csv", "signal_details.csv", "market_data_pine5_raw_recalc.csv", "README.md"},
            )
            self.assertTrue(zip_path.is_file())
            page = (package_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="research_dashboard.html"', page)
            self.assertIn('href="commercial_dashboard.html"', page)
            research = (package_dir / "research_dashboard.html").read_text(encoding="utf-8")
            self.assertIn("历史方案 · 8 种 / 2 组", research)
            self.assertEqual(research.count('<details class="strategy-group"'), 2)
            self.assertEqual(research.count('<details class="plan"'), 8)
            self.assertIn("83.3%", research)
            self.assertIn("75.0%", research)
            self.assertIn("年均 1.1 次 / 年", research)
            self.assertNotIn("平均毛收益", page)
            self.assertNotIn("未来预测", page)
            self.assertNotIn("不代表未来", page)
            ranking_csv = (package_dir / "ranking_20.csv").read_text(encoding="utf-8-sig")
            eligible_csv = (package_dir / "eligible_70_plus.csv").read_text(encoding="utf-8-sig")
            details_csv = (package_dir / "signal_details.csv").read_text(encoding="utf-8-sig")
            self.assertNotIn("mean_gross_return", ranking_csv)
            self.assertIn("gross_return", details_csv)
            self.assertEqual(len(eligible_csv.splitlines()), 9)
            with zipfile.ZipFile(zip_path) as archive:
                self.assertTrue(any(name.endswith("/eligible_70_plus.csv") for name in archive.namelist()))
                self.assertTrue(any(name.endswith("/research_dashboard.html") for name in archive.namelist()))
                self.assertTrue(any(name.endswith("/commercial_dashboard.html") for name in archive.namelist()))
                for name in ("index_en.html", "research_dashboard_en.html", "commercial_dashboard_en.html"):
                    self.assertTrue(any(item.endswith("/" + name) for item in archive.namelist()))

    def test_all_five_tied_highest_probability_plans_are_included(self):
        rows = load_data(INPUT)
        ranked, _, _ = calculate_rankings(rows)
        highest = [row for row in qualifying_rankings(ranked) if row["win_probability"] == 10 / 12]

        self.assertEqual(len(highest), 5)
        self.assertEqual({row["horizon"] for row in highest}, {1, 3, 4, 8, 9})
        self.assertTrue(all(row["wins"] == 10 and row["sample_count"] == 12 for row in highest))


if __name__ == "__main__":
    unittest.main()
