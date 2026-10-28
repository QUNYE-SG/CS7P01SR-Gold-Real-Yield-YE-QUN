"""Presentation-only checks: signal dates are not successful-outcome dates."""
import copy
import unittest
from html.parser import HTMLParser
from pathlib import Path

from analysis import load_data
from build_top2_package import calculate_rankings, qualifying_rankings
from v2_pages import dashboard_page, presentation_model

ROOT = Path(__file__).resolve().parents[1]


class OutcomeTags(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.outcomes = []
        self.times = []
        self.feed(page)

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if "data-outcome" in attrs:
            self.outcomes.append(attrs)
        if tag == "time":
            self.times.append(attrs["datetime"])


class CalendarOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ranked, cls.details, cls.metadata = calculate_rankings(
            load_data(ROOT / "data/market_data_pine5_raw_recalc_preview.csv"))
        cls.eligible = qualifying_rankings(cls.ranked)
        cls.model = presentation_model(cls.eligible, cls.details, cls.metadata)

    def test_every_selected_event_appears_once_with_its_own_outcome(self):
        parser = OutcomeTags(dashboard_page(self.model, commercial=True))
        expected = {
            (str(event["signal_date"]), str(event["group"]), int(event["horizon"])): event["win"]
            for event in self.details
            if (event["group"], event["horizon"]) in
               {(row["group"], row["horizon"]) for row in self.eligible}
        }
        actual = [(attrs["data-outcome-date"], attrs["data-outcome-group"], int(attrs["data-outcome-horizon"]))
                  for attrs in parser.outcomes]
        self.assertEqual(len(actual), len(set(actual)))
        self.assertEqual(set(actual), set(expected))
        self.assertEqual(tuple(parser.times), self.model["signal_dates"])
        for attrs, key in zip(parser.outcomes, actual):
            self.assertEqual(attrs["data-outcome"], "up" if expected[key] else "not-up")
        for row in self.eligible:
            events = [attrs for attrs in parser.outcomes
                      if attrs["data-outcome-group"] == row["group"] and
                      int(attrs["data-outcome-horizon"]) == row["horizon"]]
            self.assertEqual(len(events), row["sample_count"])
            self.assertEqual(sum(attrs["data-outcome"] == "up" for attrs in events), row["wins"])

    def test_equal_proportions_do_not_make_day_six_and_ten_results_identical(self):
        eligible = [{"group": "negative", "group_label": "负极端相关", "horizon": horizon,
                     "wins": 1, "sample_count": 2, "win_probability": .5} for horizon in (6, 10)]
        events = [{"group": "negative", "horizon": horizon, "signal_date": day, "win": win}
                  for day, horizon, win in (("2026-01-05", 6, True), ("2026-01-05", 10, False),
                                           ("2026-01-12", 6, False), ("2026-01-12", 10, True))]
        model = presentation_model(eligible, events, {"first_date": "2026-01-01", "last_date": "2026-01-31", "row_count": 21})
        parsed = OutcomeTags(dashboard_page(model, commercial=True))
        first = {int(item["data-outcome-horizon"]): item["data-outcome"] for item in parsed.outcomes
                 if item["data-outcome-date"] == "2026-01-05"}
        self.assertEqual(first, {6: "up", 10: "not-up"})
        self.assertEqual(model["unique_signal_count"], 2)

    def test_both_views_distinguish_signal_occurrence_from_future_outcome(self):
        public = dashboard_page(self.model, commercial=True)
        research = dashboard_page(self.model)
        self.assertIn("年份次数 = 信号次数", public)
        self.assertIn("信号出现日期", public)
        self.assertIn("未上涨（含持平）", public)
        self.assertIn("不是信号当天的涨跌", public)
        self.assertIn("同一信号的不同期限可能结果不同", public)
        self.assertNotIn("<details", public)
        self.assertNotIn("<table", public)
        self.assertIn("上涨指对应期限收盘价", research)
        self.assertIn("未上涨包括持平", research)

    def test_each_year_labels_signal_dates_and_future_results_above_its_list(self):
        public = dashboard_page(self.model, commercial=True)
        heading = '<div class="calendar-list-header"><span>信号日</span><span>后续结果</span></div>'
        self.assertEqual(public.count(heading), len(self.model["calendar_years"]))
        for card in public.split('<article class="calendar-year-card ')[1:]:
            card = card.split('</article>', 1)[0]
            self.assertLess(card.index(heading), card.index('<ul class="calendar-date-list"'))
            self.assertIn('年信号日与后续结果', card)

    def test_flat_return_is_not_presented_as_up_and_inputs_are_not_mutated(self):
        row = {"group": "positive", "group_label": "正极端相关", "horizon": 4,
               "wins": 0, "sample_count": 1, "win_probability": 0.0}
        event = {"group": "positive", "horizon": 4, "signal_date": "2026-01-05",
                 "win": False, "gross_return": 0.0}
        metadata = {"first_date": "2026-01-01", "last_date": "2026-01-31", "row_count": 21}
        before = copy.deepcopy(([row], [event], metadata))
        model = presentation_model([row], [event], metadata)
        parsed = OutcomeTags(dashboard_page(model, commercial=True))
        self.assertEqual(parsed.outcomes[0]["data-outcome"], "not-up")
        self.assertEqual(([row], [event], metadata), before)

    def test_string_false_is_not_accepted_as_a_successful_event(self):
        details = copy.deepcopy(self.details)
        selected = {(row["group"], row["horizon"]) for row in self.eligible}
        changed = next(event for event in details if (event["group"], event["horizon"]) in selected)
        changed["win"] = "False"
        with self.assertRaises(ValueError):
            presentation_model(self.eligible, details, self.metadata)


if __name__ == "__main__":
    unittest.main()
