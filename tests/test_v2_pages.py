import copy
import unittest
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

from analysis import load_data
from build_top2_package import calculate_rankings, qualifying_rankings
from v2_pages import calendar_years, dashboard_page, presentation_model


ROOT = Path(__file__).resolve().parents[1]
# Frozen layout-regression fixture; corrected live data has separate tests.
INPUT = ROOT / "tests" / "fixtures" / "v2_legacy_same_day_20261002.csv"


class PageTags(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.tags = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class ExpandableViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ranked, cls.details, cls.metadata = calculate_rankings(load_data(INPUT))
        cls.eligible = qualifying_rankings(ranked)
        cls.model = presentation_model(cls.eligible, cls.details, cls.metadata)

    def test_frequency_uses_full_calendar_span_not_signal_span(self):
        self.assertAlmostEqual(self.model["years"], 4018 / 365.2425)
        self.assertEqual(self.model["unique_signal_count"], 12)
        self.assertAlmostEqual(self.model["unique_annual_frequency"], 12 / (4018 / 365.2425))
        for group in self.model["groups"]:
            self.assertEqual(group["sample_count"], 12)
            for plan in group["plans"]:
                self.assertEqual(plan["sample_count"], 12)
                self.assertEqual(len(plan["events"]), 12)
                self.assertEqual(f'{plan["annual_frequency"]:.1f}', "1.1")

    def test_same_signal_dates_are_not_summed_across_eight_horizons(self):
        self.assertEqual(len(self.model["groups"]), 2)
        self.assertEqual([len(group["plans"]) for group in self.model["groups"]], [5, 3])
        self.assertEqual([group["wins"] for group in self.model["groups"]], [10, 9])
        self.assertEqual(self.model["groups"][0]["dates"], self.model["groups"][1]["dates"])
        self.assertEqual(self.model["groups"][0]["dates"][0], "2016-02-09")
        self.assertEqual(self.model["groups"][0]["dates"][-1], "2025-10-06")
        counts = dict(self.model["year_counts"])
        self.assertEqual(counts[2016], 3)
        self.assertEqual(counts[2024], 3)
        self.assertEqual(counts[2025], 3)
        self.assertEqual(counts[2026], 0)
        self.assertEqual(sum(counts.values()), 12)

    def test_calendar_covers_every_sample_year_and_preserves_unique_counts(self):
        years = self.model["calendar_years"]
        self.assertEqual([year["year"] for year in years], list(range(2015, 2027)))
        self.assertEqual([(year["year"], year["count"]) for year in years], self.model["year_counts"])
        dates = [day for year in years for day in year["dates"]]
        self.assertEqual(tuple(dates), self.model["signal_dates"])
        self.assertEqual(len(dates), 12)
        self.assertEqual(sum(len(plan["dates"]) for group in self.model["groups"]
                             for plan in group["plans"]), 96)
        first, last = years[0], years[-1]
        self.assertTrue(first["partial"])
        self.assertEqual(first["coverage_start"], "2015-10-02")
        self.assertTrue(last["partial"])
        self.assertEqual(last["coverage_end"], "2026-10-02")
        self.assertTrue(all(not year["partial"] for year in years[1:-1]))

    def test_calendar_months_have_correct_monday_first_positions(self):
        year = next(year for year in self.model["calendar_years"] if year["year"] == 2016)
        self.assertEqual([month["month"] for month in year["months"]], [2, 6, 9])
        self.assertEqual(year["dates"], ["2016-02-09", "2016-06-14", "2016-09-05"])
        for month in year["months"]:
            self.assertTrue(all(len(week) == 7 for week in month["weeks"]))
            for day in month["signal_days"]:
                columns = [week.index(day) for week in month["weeks"] if day in week]
                self.assertEqual(columns, [date(2016, month["month"], day).weekday()])

    def test_calendar_supports_leap_days_and_deduplicates_dates(self):
        years = calendar_years(["2024-02-29", "2024-02-29", "2024-02-01"],
                               date(2024, 1, 1), date(2024, 12, 31))
        self.assertEqual(years[0]["count"], 2)
        month = years[0]["months"][0]
        self.assertEqual(month["signal_days"], [1, 29])
        self.assertEqual([week.index(29) for week in month["weeks"] if 29 in week], [3])
        self.assertFalse(years[0]["partial"])

    def test_calendar_rejects_invalid_or_out_of_sample_dates(self):
        for days in (["2024-02-30"], ["2023-12-31"], ["2025-01-01"]):
            with self.assertRaises(ValueError):
                calendar_years(days, date(2024, 1, 1), date(2024, 12, 31))
        with self.assertRaisesRegex(ValueError, "结束日期"):
            calendar_years([], date(2025, 1, 1), date(2024, 1, 1))

    def test_calendar_controls_are_unique_and_all_twelve_dates_are_marked(self):
        for commercial in (False,):
            page = dashboard_page(self.model, commercial=commercial)
            tags = PageTags(page).tags
            ids = [attrs["id"] for _, attrs in tags if "id" in attrs]
            self.assertEqual(len(ids), len(set(ids)))
            controls = [attrs["aria-controls"] for _, attrs in tags if "aria-controls" in attrs]
            self.assertTrue(all(target in ids for target in controls))
            years = [attrs for _, attrs in tags if "data-calendar-year" in attrs]
            self.assertEqual(len(years), 36)
            global_years = [attrs for attrs in years if "data-signal-count" in attrs]
            self.assertEqual([attrs["data-calendar-year"] for attrs in global_years],
                             [str(year) for year in range(2015, 2027)])
            marked = [attrs for _, attrs in tags if "signal-day" in attrs.get("class", "").split()]
            # Only the secondary, group-specific audit calendars are interactive.
            self.assertEqual(len(marked), 24)
            self.assertEqual({attrs["data-date"] for attrs in marked}, set(self.model["signal_dates"]))
            self.assertTrue(all(attrs["aria-pressed"] == "false" for attrs in marked))
            self.assertLess(page.index('id="signal-calendar"'), page.index('id="strategies"'))
            self.assertIn("跨期限次数不相加", page)

    def test_distinct_date_groups_keep_their_own_calendars(self):
        details = copy.deepcopy(self.details)
        eligible = copy.deepcopy(self.eligible[:2])
        changed = next(event for event in details if event["group"] == "positive" and event["horizon"] == 3)
        changed["signal_date"] = "2016-02-10"
        model = presentation_model(eligible, details, self.metadata)
        tags = PageTags(dashboard_page(model)).tags
        marked = [attrs for _, attrs in tags if "signal-day" in attrs.get("class", "").split()]
        self.assertEqual(len(marked), 12 + 12)
        for index, group in enumerate(model["groups"], start=1):
            group_dates = {attrs["data-date"] for attrs in marked
                           if attrs["aria-controls"].startswith(f"group-calendar-{index}-")}
            self.assertEqual(group_dates, set(group["dates"]))

    def test_empty_calendar_shows_zero_years_without_false_signal_days(self):
        model = presentation_model([], [], self.metadata)
        page = dashboard_page(model)
        tags = PageTags(page).tags
        self.assertEqual(sum("data-calendar-year" in attrs for _, attrs in tags), 12)
        self.assertEqual(sum("data-date" in attrs for _, attrs in tags), 0)
        self.assertTrue(all(year["count"] == 0 and not year["months"] for year in model["calendar_years"]))
        self.assertIn("样本期内未出现信号", page)
        self.assertIn("部分年份样本", page)
        self.assertIn(self.metadata["first_date"], page)
        self.assertIn(self.metadata["last_date"], page)

    def test_equal_probability_without_equal_dates_does_not_merge(self):
        eligible = copy.deepcopy(self.eligible[:2])
        details = copy.deepcopy(self.details)
        changed = next(event for event in details if event["group"] == "positive" and event["horizon"] == 3)
        changed["signal_date"] = "2016-02-10"
        model = presentation_model(eligible, details, self.metadata)
        self.assertEqual(len(model["groups"]), 2)
        self.assertEqual(model["unique_signal_count"], 13)

    def test_zero_span_and_empty_eligibility_have_no_division_error(self):
        metadata = {**self.metadata, "first_date": "2026-10-02", "last_date": "2026-10-02"}
        model = presentation_model([], [], metadata)
        self.assertIsNone(model["unique_annual_frequency"])
        self.assertEqual(model["unique_signal_count"], 0)
        self.assertIn("当前没有达到", dashboard_page(model))
        self.assertNotIn("nan", dashboard_page(model).lower())

    def test_sample_mismatch_and_duplicate_dates_are_rejected(self):
        details = copy.deepcopy(self.details)
        details.pop(next(index for index, event in enumerate(details)
                         if event["group"] == "positive" and event["horizon"] == 1))
        with self.assertRaisesRegex(ValueError, "样本数"):
            presentation_model(self.eligible, details, self.metadata)
        details = copy.deepcopy(self.details)
        events = [event for event in details if event["group"] == "positive" and event["horizon"] == 1]
        events[1]["signal_date"] = events[0]["signal_date"]
        with self.assertRaisesRegex(ValueError, "样本数"):
            presentation_model(self.eligible, details, self.metadata)

    def test_frequency_changes_when_dataset_span_changes(self):
        metadata = {**self.metadata, "last_date": "2037-10-02"}
        model = presentation_model(self.eligible, self.details, metadata)
        self.assertAlmostEqual(model["unique_annual_frequency"], self.model["unique_annual_frequency"] / 2, places=3)
        self.assertIn("年均 0.5 次 / 年", dashboard_page(model))

    def test_research_view_keeps_secondary_audit_details_and_every_horizon(self):
        for commercial in (False,):
            page = dashboard_page(self.model, commercial=commercial)
            self.assertEqual(page.count('<details class="strategy-group"'), 2)
            self.assertEqual(page.count('<details class="plan"'), 8)
            self.assertNotIn('<details class="strategy-group" open', page)
            self.assertIn('data-expand="true"', page)
            self.assertIn('data-expand="false"', page)
            for horizon in (1, 3, 4, 5, 6, 7, 8, 9):
                self.assertIn(f'data-horizon="{horizon}"', page)
            for day in self.model["groups"][0]["dates"]:
                self.assertIn(f'datetime="{day}"', page)
            self.assertIn("入场日期", page)
            self.assertIn("观察结束日期", page)
            self.assertIn('tabindex="0"', page)
            self.assertIn('scope="col"', page)
            self.assertEqual(page.count('<details class="audit-details"'), 2)
            self.assertNotIn('<details class="audit-details" open', page)

    def test_commercial_view_has_static_cards_without_dropdowns_or_event_tables(self):
        page = dashboard_page(self.model, commercial=True)
        tags = PageTags(page).tags
        ids = [attrs["id"] for _, attrs in tags if "id" in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertFalse(any(tag in ("details", "summary", "table", "input", "form") for tag, _ in tags))
        self.assertFalse(any("aria-expanded" in attrs or "data-expand" in attrs for _, attrs in tags))
        self.assertFalse(any("hidden" in attrs for _, attrs in tags))
        self.assertNotIn("查看月历", page)
        self.assertNotIn("入场日期", page)
        self.assertNotIn("观察结束日期", page)
        self.assertNotIn("按期限核对", page)
        result_cards = [attrs for tag, attrs in tags if tag == "article"
                        and "result-card" in attrs.get("class", "").split()]
        self.assertEqual(len(result_cards), self.model["plan_count"])
        self.assertEqual({attrs["data-horizon"] for _, attrs in tags if "data-horizon" in attrs},
                         {"1", "3", "4", "5", "6", "7", "8", "9"})
        self.assertIn("商业化版", page)
        self.assertIn("本页不收集联系方式", page)
        for target in ("performance", "signal-calendar", "subscribe"):
            self.assertIn(target, ids)
            self.assertIn(f'href="#{target}"', page)

    def test_commercial_calendar_dates_and_counts_are_all_visible_once(self):
        page = dashboard_page(self.model, commercial=True)
        tags = PageTags(page).tags
        cards = [attrs for tag, attrs in tags if "data-calendar-year" in attrs]
        self.assertEqual(len(cards), 12)
        self.assertEqual([(int(attrs["data-calendar-year"]), int(attrs["data-signal-count"]))
                          for attrs in cards], self.model["year_counts"])
        self.assertEqual(sum(int(attrs["data-signal-count"]) for attrs in cards), 12)
        for attrs in cards:
            state = "has-signals" if int(attrs["data-signal-count"]) else "no-signals"
            self.assertIn(state, attrs["class"].split())
        times = [attrs["datetime"] for tag, attrs in tags if tag == "time"]
        self.assertEqual(tuple(times), self.model["signal_dates"])
        self.assertIn("部分年份样本", page)
        self.assertNotIn("覆盖 10/02—12/31", page)
        self.assertNotIn("覆盖 01/01—10/02", page)

    def test_commercial_summary_and_calendar_recalculate_without_fixed_counts(self):
        details = copy.deepcopy(self.details)
        changed = next(event for event in details if event["group"] == "positive" and event["horizon"] == 3)
        changed["signal_date"] = "2016-02-10"
        model = presentation_model(self.eligible[:2], details, self.metadata)
        page = dashboard_page(model, commercial=True)
        self.assertIn("2 种方案，逐项看清", page)
        self.assertIn("13 个信号出现日期，逐次结果看清", page)
        self.assertIn('datetime="2016-02-10"', page)
        empty = presentation_model([], [], self.metadata)
        empty_page = dashboard_page(empty, commercial=True)
        self.assertIn("当前没有达到", empty_page)
        self.assertIn("0 个信号出现日期，逐次结果看清", empty_page)
        self.assertFalse(any(tag == "time" for tag, _ in PageTags(empty_page).tags))

    def test_public_view_has_dates_but_no_prices_algorithm_or_csv_links(self):
        research = dashboard_page(self.model)
        public = dashboard_page(self.model, commercial=True)
        self.assertIn("入场开盘价", research)
        self.assertIn("单次毛收益", research)
        self.assertIn("实际利率高于五个交易日前", research)
        self.assertIn('href="signal_details.csv"', research)
        for hidden in ("入场开盘价", "退出收盘价", "单次毛收益", "实际利率高于五个交易日前",
                       "signal_details.csv", "market_data_pine5_raw_recalc.csv", "0.80", "相关系数 ≥"):
            self.assertNotIn(hidden, public)
        event = next(event for event in self.details if event["group"] == "positive")
        self.assertIn(event["signal_date"], public)
        self.assertNotIn(f'{event["entry_open"]:,.2f}', public)
        self.assertIn("不构成访问权限隔离", public)

    def test_user_supplied_labels_are_escaped_and_model_does_not_mutate_inputs(self):
        eligible = copy.deepcopy(self.eligible)
        eligible[0]["group_label"] = '<img src=x onerror="bad()">'
        before = copy.deepcopy(eligible)
        model = presentation_model(eligible, self.details, self.metadata)
        self.assertEqual(eligible, before)
        page = dashboard_page(model)
        self.assertIn("&lt;img", page)
        self.assertNotIn('<img src=x', page)


if __name__ == "__main__":
    unittest.main()
