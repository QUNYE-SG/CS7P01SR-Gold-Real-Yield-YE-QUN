"""Offline tests: never contact a mail service or modify the production outbox."""

import copy
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from alerting import latest_completed_signal, message_for, observation_cycle
from analysis import DailyObservation, load_data
from build_top2_package import calculate_rankings
from signal_notifications import (acknowledge, acknowledge_email, claim_email,
                                  configure_email, prepare_notifications)

ROOT = Path(__file__).resolve().parents[1]


class ForecastCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Freeze the replay window; daily updates must not change this benchmark.
        cls.rows = [r for r in load_data(ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv")
                    if r.date <= date(2026, 10, 16)]
        cls.prefix = [r for r in cls.rows if r.date <= date(2026, 10, 2)]

    def test_oct_2_signal_immediately_has_all_ten_as_of_rates(self):
        signal = latest_completed_signal(self.prefix)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["date"], "2026-10-02")
        self.assertEqual(signal["historical_as_of"], "2026-10-02")
        cycle = signal["cycle_results"]
        self.assertEqual([r["horizon"] for r in cycle], list(range(1, 11)))
        self.assertEqual([r["wins"] for r in cycle], [9, 7, 8, 11, 10, 9, 10, 10, 10, 9])
        self.assertEqual([r["sample_count"] for r in cycle], [15]*10)
        self.assertEqual([r["horizon"] for r in cycle if r["is_focus"]], [4])
        for row in cycle:
            self.assertEqual(row["win_probability"], row["wins"]/15)
        self.assertEqual(cycle[0]["expected_date"], "2026-10-05")
        self.assertEqual(cycle[3]["expected_date"], "2026-10-08")
        self.assertEqual(cycle[-1]["expected_date"], "2026-10-16")
        text = message_for(signal)
        self.assertEqual(text.count("｜历史上涨比例"), 10)
        self.assertEqual(text.count("★重点观察（≥70%）"), 1)
        self.assertIn("73.3%（11/15次）", text)
        self.assertIn("不是期间曾上涨或单日涨跌概率", text)
        self.assertIn("不等待未来结果", text)

    def test_every_horizon_reuses_the_existing_common_sample(self):
        ranked, _, _ = calculate_rankings(self.prefix)
        for group, coefficient in (("positive", .9), ("negative", -.9)):
            rows = self.prefix[:-1] + [DailyObservation(self.prefix[-1].date, 4100, 4200, 3.0, coefficient)]
            with patch("alerting.deduplicate", return_value=[len(rows)-1]):
                signal = latest_completed_signal(rows)
            expected = sorted((r for r in ranked if r["group"] == group), key=lambda r: r["horizon"])
            self.assertEqual([(r["wins"], r["sample_count"], r["win_probability"]) for r in signal["cycle_results"]],
                             [(r["wins"], r["sample_count"], r["win_probability"]) for r in expected])

    def test_threshold_uses_unrounded_values_and_includes_exact_70(self):
        cycle = observation_cycle("2026-10-02", [
            {"horizon": 1, "wins": 7, "sample_count": 10, "win_probability": .70},
            {"horizon": 2, "wins": 6999, "sample_count": 10000, "win_probability": .6999},
            {"horizon": 3, "wins": 0, "sample_count": 0, "win_probability": None},
        ])
        self.assertEqual([r["horizon"] for r in cycle if r["is_focus"]], [1])
        self.assertIsNone(cycle[2]["win_probability"])
        signal = latest_completed_signal(self.prefix)
        signal["cycle_results"] = cycle
        text = message_for(signal)
        self.assertIn("<70%（6999/10000次）", text)
        self.assertEqual(text.count("★重点观察（≥70%）"), 1)

    def test_weekday_dates_are_explicit_estimates_not_a_gold_holiday_calendar(self):
        cycle = observation_cycle("2026-12-24", [])
        self.assertEqual(cycle[0]["expected_date"], "2026-12-25")
        self.assertEqual(cycle[1]["expected_date"], "2026-12-28")
        signal = latest_completed_signal(self.prefix)
        text = message_for(signal)
        self.assertEqual(signal["date_basis"], "weekday_estimate")
        self.assertIn("未核验黄金节假日休市", text)
        self.assertIn("遇休市顺延", text)

    def test_insufficient_history_does_not_delay_a_confirmed_signal(self):
        rows = [DailyObservation(date(2026, 1, 1)+timedelta(days=i), 100+i, 100+i, 2.0, .2)
                for i in range(8)]
        rows[-1] = DailyObservation(rows[-1].date, 107, 107, 2.2, .8)
        signal = latest_completed_signal(rows)
        self.assertEqual(len(signal["cycle_results"]), 10)
        self.assertTrue(all(r["win_probability"] is None for r in signal["cycle_results"]))
        text = message_for(signal)
        self.assertEqual(text.count("样本不足"), 10)
        self.assertNotIn("0.0%", text)
        self.assertIn("暂无达到70%的重点观察日", text)
        with TemporaryDirectory() as tmp:
            state, report = Path(tmp)/"state.json", Path(tmp)/"report.json"
            prepare_notifications(rows[:-1], state, report)
            result = prepare_notifications(rows, state, report)
            self.assertTrue(result["notify"])
            self.assertEqual(result["pending"][0]["cycle_results"], signal["cycle_results"])

    def test_full_cycle_is_identical_in_chat_and_email_and_saved_after_acks(self):
        with TemporaryDirectory() as tmp:
            state, report = Path(tmp)/"state.json", Path(tmp)/"report.json"
            prepare_notifications(self.prefix[:-1], state, report)
            configure_email("review-7175d36340e3@example.invalid", "review-48975fd6076e@example.invalid", state, report)
            result = prepare_notifications(self.prefix, state, report)
            signal = result["pending"][0]
            self.assertEqual(len(result["pending"]), 1)
            self.assertEqual(len(result["email_pending"]), 1)
            self.assertIn(signal["message"], result["email_pending"][0]["body"])
            self.assertEqual(result["email_pending"][0]["body"].count("｜历史上涨比例"), 10)
            frozen = copy.deepcopy(signal)
            acknowledge(signal["event_id"], state, report)
            claim_email(signal["event_id"], state, report)
            acknowledge_email(signal["event_id"], "offline-mock-id", "review-7175d36340e3@example.invalid", state, report)
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved["forecasts"][signal["event_id"]], frozen)
            with patch("signal_notifications.latest_completed_signal", return_value=None):
                again = prepare_notifications(self.rows, state, report)
            self.assertFalse(again["notify"])
            self.assertFalse(again["email_notify"])
            self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["forecasts"][signal["event_id"]], frozen)
            # Later matured data may change the live table, never the original outlook.
            current, _, _ = calculate_rankings(self.rows)
            current_fourth = next(r for r in current if r["group"] == "positive" and r["horizon"] == 4)
            self.assertEqual(frozen["cycle_results"][3]["sample_count"], 15)
            self.assertEqual(current_fourth["sample_count"], 16)

    def test_catch_up_never_uses_later_probabilities_or_claims_timeliness(self):
        with TemporaryDirectory() as tmp:
            state, report = Path(tmp)/"state.json", Path(tmp)/"report.json"
            prepare_notifications(self.prefix[:-1], state, report)
            configure_email("review-7175d36340e3@example.invalid", "review-48975fd6076e@example.invalid", state, report)
            result = prepare_notifications(self.rows, state, report)
            signal = next(e for e in result["pending"] if e["date"] == "2026-10-02")
            self.assertTrue(signal["is_catch_up"])
            self.assertIn("补更发现", signal["message"])
            self.assertEqual(signal["historical_as_of"], "2026-10-02")
            self.assertEqual(signal["cycle_results"][3]["wins"], 11)
            self.assertEqual(signal["cycle_results"][3]["sample_count"], 15)
            mail = next(e for e in result["email_pending"] if e["date"] == "2026-10-02")
            self.assertEqual(mail["body"].count("补更发现"), 1)

    def test_legacy_pending_message_and_notification_baseline_are_not_rewritten(self):
        with TemporaryDirectory() as tmp:
            state, report = Path(tmp)/"state.json", Path(tmp)/"report.json"
            legacy = {"version": 1, "last_checked_date": "2026-10-02",
                      "pending": [{"event_id": "legacy", "message": "original message"}],
                      "announced_event_ids": ["older"]}
            state.write_text(json.dumps(legacy), encoding="utf-8")
            result = prepare_notifications(self.prefix, state, report)
            self.assertEqual(result["pending"], legacy["pending"])
            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(saved["last_checked_date"], legacy["last_checked_date"])
            self.assertEqual(saved["announced_event_ids"], ["older"])
            self.assertEqual(saved["forecasts"], {})


if __name__ == "__main__":
    unittest.main()
