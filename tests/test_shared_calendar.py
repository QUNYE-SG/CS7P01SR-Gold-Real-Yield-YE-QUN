"""Both views expose the same visible per-horizon outcomes and signal dates."""

import copy
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from analysis import load_data
from build_top2_package import calculate_rankings, qualifying_rankings
from v2_pages import dashboard_page, presentation_model
from v2_signal_calendar import SIGNAL_CALENDAR_CSS, signal_calendar

ROOT = Path(__file__).resolve().parents[1]


def calendar_fragment(page):
    return re.search(r'<section\b[^>]*\bid="signal-calendar"[^>]*>.*?</section>', page, re.S).group()


class CalendarTags(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.tags = []
        self.feed(calendar_fragment(page))

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class SharedCalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = []
        for path in (ROOT / "data/market_data_pine5_raw_recalc_preview.csv",
                     ROOT / "tests/fixtures/v2_legacy_same_day_20261002.csv"):
            ranked, details, metadata = calculate_rankings(load_data(path))
            cls.models.append(presentation_model(qualifying_rankings(ranked), details, metadata))
        cls.models.append(presentation_model([], [], cls.models[0]["metadata"]))

    def test_both_languages_have_identical_calendar_markup_across_views(self):
        for model in self.models:
            for language in ("zh", "en"):
                research = dashboard_page(model, language=language)
                commercial = dashboard_page(model, commercial=True, language=language)
                self.assertEqual(calendar_fragment(research), calendar_fragment(commercial))
                self.assertIn(SIGNAL_CALENDAR_CSS, research)
                self.assertIn(SIGNAL_CALENDAR_CSS, commercial)

    def test_primary_calendar_needs_no_expansion_or_javascript_in_either_view(self):
        for model in self.models:
            for commercial in (False, True):
                page = dashboard_page(model, commercial=commercial)
                tags = CalendarTags(page).tags
                self.assertFalse(any(tag in ("button", "details", "table", "script") for tag, _ in tags))
                self.assertFalse(any(key in attrs for _, attrs in tags
                                     for key in ("hidden", "aria-controls", "aria-expanded")))
                self.assertNotIn("查看月历", calendar_fragment(page))
                self.assertIn("无需展开", calendar_fragment(page))
                headers = '<div class="calendar-list-header"><span>信号日</span><span>后续结果</span></div>'
                self.assertEqual(calendar_fragment(page).count(headers), len(model["calendar_years"]))

    def test_counts_dates_and_every_selected_outcome_are_exact_and_not_duplicated(self):
        for model in self.models:
            expected = {(day, item["group"], str(item["horizon"])): "up" if item["win"] else "not-up"
                        for day, items in model["signal_outcomes"].items() for item in items}
            for commercial in (False, True):
                for language in ("zh", "en"):
                    tags = CalendarTags(dashboard_page(model, commercial=commercial, language=language)).tags
                    dates = [attrs["datetime"] for tag, attrs in tags if tag == "time"]
                    self.assertEqual(tuple(dates), model["signal_dates"])
                    cards = [attrs for tag, attrs in tags if "data-calendar-year" in attrs]
                    self.assertEqual([(int(item["data-calendar-year"]), int(item["data-signal-count"]))
                                      for item in cards], model["year_counts"])
                    self.assertEqual(sum(int(item["data-signal-count"]) for item in cards), model["unique_signal_count"])
                    outcomes = [attrs for tag, attrs in tags if "data-outcome" in attrs]
                    keys = [(item["data-outcome-date"], item["data-outcome-group"], item["data-outcome-horizon"])
                            for item in outcomes]
                    self.assertEqual(len(keys), len(set(keys)))
                    self.assertEqual(dict(zip(keys, (item["data-outcome"] for item in outcomes))), expected)

    def test_static_cards_are_not_attached_to_the_interactive_audit_handlers(self):
        research = dashboard_page(self.models[0])
        self.assertIn(".signal-calendar:not(.outcome-calendar)", research)
        self.assertIn('class="calendar-year-panel"', research)
        self.assertIn('<details class="audit-details"', research)
        self.assertIn('href="signal_details.csv"', research)
        self.assertIn("实际利率高于五个交易日前", research)

    def test_rendering_and_shared_styles_do_not_change_the_model(self):
        before = copy.deepcopy(self.models)
        for model in self.models:
            signal_calendar(model)
            dashboard_page(model)
            dashboard_page(model, commercial=True, language="en")
        self.assertEqual(self.models, before)


if __name__ == "__main__":
    unittest.main()
