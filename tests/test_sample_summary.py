"""Public summary is coarse; research, data and signal results remain exact."""
import copy
import unittest
from pathlib import Path

from analysis import load_data
from build_top2_package import calculate_rankings, qualifying_rankings
from v2_pages import dashboard_page, launcher_page, presentation_model
from v2_sample_summary import public_sample_summary

ROOT = Path(__file__).resolve().parents[1]


class SampleSummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ranked, details, meta = calculate_rankings(load_data(ROOT / "data/market_data_pine5_raw_recalc_preview.csv"))
        cls.model = presentation_model(qualifying_rankings(ranked), details, meta)

    def test_current_sample_has_generalised_but_truthful_description(self):
        summary = public_sample_summary(self.model)
        self.assertEqual(summary["span"], "十余年")
        self.assertEqual(summary["size"], "近三千个交易日")
        self.assertIn("覆盖十余年", summary["summary"])

    def test_both_public_languages_hide_precise_sample_boundaries_and_row_count(self):
        meta = self.model["metadata"]
        for language in ("zh", "en"):
            for page in (launcher_page(self.model, language=language),
                         dashboard_page(self.model, commercial=True, language=language)):
                self.assertNotIn(meta["first_date"], page)
                self.assertNotIn(meta["last_date"], page)
                self.assertNotIn(f'{meta["row_count"]:,}', page)
                self.assertNotIn(f'{self.model["years"]:.1f}', page)
                self.assertNotIn("10/02—12/31", page)
            english = launcher_page(self.model, language=language)
            if language == "en":
                self.assertIn("10+ years", english)
                self.assertIn("Nearly 3,000 trading days", english)

    def test_research_keeps_the_exact_original_sample_and_auditable_results(self):
        meta = self.model["metadata"]
        for language in ("zh", "en"):
            page = dashboard_page(self.model, language=language)
            for value in (meta["first_date"], meta["last_date"], f'{meta["row_count"]:,}', f'{self.model["years"]:.1f}'):
                self.assertIn(value, page)

    def test_calendar_signal_dates_results_and_rates_are_not_blurred(self):
        for language in ("zh", "en"):
            page = dashboard_page(self.model, commercial=True, language=language)
            for day in self.model["signal_dates"]:
                self.assertIn(f'datetime="{day}"', page)
            for group in self.model["groups"]:
                self.assertIn(f'{group["win_probability"]:.1%}', page)
                for plan in group["plans"]:
                    for event in plan["events"]:
                        state = "up" if event["win"] else "not-up"
                        self.assertIn(f'data-outcome-date="{event["signal_date"]}"', page)
                        self.assertIn(f'data-outcome="{state}"', page)

    def test_later_and_smaller_samples_do_not_keep_inaccurate_fixed_claims(self):
        for years, count, span, size in ((11.5, 3001, "十余年", "约三千个交易日"),
                                         (21.0, 5600, "二十余年", "约 6,000 个交易日"),
                                         (.4, 80, "不足一年", "数十个交易日")):
            model = {"years": years, "metadata": {"row_count": count}}
            summary = public_sample_summary(model)
            self.assertEqual((summary["span"], summary["size"]), (span, size))

    def test_public_rendering_does_not_mutate_precise_metadata(self):
        before = copy.deepcopy(self.model)
        launcher_page(self.model, language="en")
        dashboard_page(self.model, commercial=True, language="en")
        self.assertEqual(self.model, before)


if __name__ == "__main__":
    unittest.main()
