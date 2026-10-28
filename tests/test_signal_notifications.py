import copy
import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from alerting import latest_completed_signal, observation_cycle
from analysis import DailyObservation, load_data
from build_top2_package import calculate_rankings, qualifying_rankings
from signal_notifications import (acknowledge, acknowledge_email, claim_email,
                                  configure_email, prepare_notifications)
from v2_pages import presentation_model
from v2_commercial import commercial_page

ROOT = Path(__file__).resolve().parents[1]


def observations(count):
    return [DailyObservation(date(2026, 1, 1) + timedelta(days=i), 100+i, 100+i, 2.0, 0.2)
            for i in range(count)]


def event(day):
    historical = [{"horizon": h, "wins": 22 if h in (6, 10) else 18,
                   "sample_count": 31, "win_probability": (22 if h in (6, 10) else 18)/31}
                  for h in range(1, 11)]
    return {"event_id": day+":negative", "date": day, "group": "negative",
            "label": "负极端相关", "correlation": -0.9, "horizons": [6, 10],
            "cycle_results": observation_cycle(day, historical),
            "historical_results": [
                {"horizon": h, "wins": 22, "sample_count": 31, "win_probability": 22/31}
                for h in (6, 10)]}


class SignalNotificationTests(unittest.TestCase):
    def test_current_rankings_not_old_fixed_horizons(self):
        rows = load_data(ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv")
        # Add a prospective qualifying row; it has no subsequent outcome bars.
        extra = DailyObservation(rows[-1].date + timedelta(days=1), rows[-1].close,
                                 rows[-1].close+5, rows[-1].real_yield+0.1, -0.9)
        future = rows+[extra]
        with patch("alerting.deduplicate", return_value=[len(future)-1]):
            signal = latest_completed_signal(future)
        ranked, _, _ = calculate_rankings(rows)
        expected = sorted(int(item["horizon"]) for item in qualifying_rankings(ranked)
                          if item["group"] == "negative")
        self.assertEqual(signal["horizons"], expected)
        self.assertEqual(expected, [6, 10])

    def test_baseline_does_not_replay_history(self):
        with TemporaryDirectory() as tmp, patch("signal_notifications.latest_completed_signal") as probe:
            root = Path(tmp)
            report = prepare_notifications(observations(25), root/"state.json", root/"report.json")
            self.assertEqual(report["status"], "initialized")
            self.assertFalse(report["notify"])
            probe.assert_not_called()

    def test_pending_survives_retry_until_ack_then_is_not_repeated(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            rows = observations(25)
            prepare_notifications(rows, state, report)
            signal = event(observations(26)[-1].date.isoformat())
            with patch("signal_notifications.latest_completed_signal", return_value=copy.deepcopy(signal)):
                pending = prepare_notifications(observations(26), state, report)
                again = prepare_notifications(observations(26), state, report)
            self.assertEqual(len(pending["pending"]), 1)
            self.assertEqual(len(again["pending"]), 1)
            self.assertTrue(again["notify"])
            self.assertIn("22/31", pending["pending"][0]["message"])
            self.assertIn("不自动下单", pending["pending"][0]["message"])
            acknowledge(signal["event_id"], state, report)
            cleared = prepare_notifications(observations(26), state, report)
            self.assertFalse(cleared["notify"])
            acknowledge(signal["event_id"], state, report)  # idempotent

    def test_batch_catches_each_new_signal_without_later_rows(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(25), state, report)
            lengths = []
            def detect(rows):
                lengths.append(len(rows))
                return event(rows[-1].date.isoformat())
            with patch("signal_notifications.latest_completed_signal", side_effect=detect):
                result = prepare_notifications(observations(27), state, report)
            self.assertEqual(lengths, [26, 27])
            self.assertEqual(len(result["pending"]), 2)
            self.assertEqual(result["pending"][0]["historical_as_of"], "2026-01-26")

    def test_no_70_percent_horizon_still_reports_confirmed_signal(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(25), state, report)
            signal = event("2026-01-26")
            signal["horizons"] = []
            signal["cycle_results"] = observation_cycle(signal["date"], [])
            with patch("signal_notifications.latest_completed_signal", return_value=signal):
                result = prepare_notifications(observations(26), state, report)
            self.assertTrue(result["notify"])
            self.assertIn("暂无达到70%的重点观察日", result["pending"][0]["message"])
            self.assertEqual(len(result["pending"][0]["cycle_results"]), 10)

    def test_corrupt_state_and_date_rollback_fail_without_overwrite(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(26), state, report)
            before = state.read_bytes()
            with self.assertRaisesRegex(ValueError, "早于"):
                prepare_notifications(observations(25), state, report)
            self.assertEqual(state.read_bytes(), before)
            state.write_text('{"version": 1}', encoding="utf-8")
            before = state.read_bytes()
            with self.assertRaisesRegex(ValueError, "未重置"):
                prepare_notifications(observations(26), state, report)
            self.assertEqual(state.read_bytes(), before)

    def test_production_has_three_cards_and_46_unique_dates(self):
        # Fixed historical regression benchmark, not a hard-coded live count.
        rows = [row for row in load_data(ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv")
                if row.date.isoformat() <= "2026-10-06"]
        ranked, details, metadata = calculate_rankings(rows)
        model = presentation_model(qualifying_rankings(ranked), details, metadata)
        page = commercial_page(model)
        self.assertEqual(page.count('<article class="result-card'), 3)
        self.assertEqual(model["unique_signal_count"], 46)
        for horizon in (4, 6, 10):
            self.assertIn(f'data-plan-horizon="{horizon}"', page)
        self.assertIn("同组期限共用同一批历史信号，次数不相加", page)

    def test_chat_ack_preserves_email_then_gmail_receipt_deduplicates(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(25), state, report)
            configure_email("review-7175d36340e3@example.invalid", "review-8b81bcfb1708@example.invalid", state, report)
            signal = event("2026-01-26")
            with patch("signal_notifications.latest_completed_signal", return_value=copy.deepcopy(signal)):
                pending = prepare_notifications(observations(26), state, report)
            self.assertTrue(pending["email_notify"])
            self.assertEqual(pending["email_pending"][0]["recipient"], "review-7175d36340e3@example.invalid")
            chat = acknowledge(signal["event_id"], state, report)
            self.assertFalse(chat["notify"])
            self.assertTrue(chat["email_notify"])
            claimed = claim_email(signal["event_id"], state, report)
            self.assertTrue(claimed["email_claimed"])
            self.assertIn("22/31", claimed["email_event"]["body"])
            sent = acknowledge_email(signal["event_id"], "gmail123", "review-7175d36340e3@example.invalid", state, report)
            self.assertFalse(sent["email_notify"])
            self.assertEqual(sent["email_sent_count"], 1)
            again = prepare_notifications(observations(26), state, report)
            self.assertFalse(again["notify"])
            self.assertFalse(again["email_notify"])
            duplicate = acknowledge_email(signal["event_id"], "gmail123", "review-7175d36340e3@example.invalid", state, report)
            self.assertEqual(duplicate["email_sent_count"], 1)

    def test_uncertain_external_send_is_not_claimed_again(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(25), state, report)
            configure_email("review-7175d36340e3@example.invalid", "review-8b81bcfb1708@example.invalid", state, report)
            signal = event("2026-01-26")
            with patch("signal_notifications.latest_completed_signal", return_value=signal):
                prepare_notifications(observations(26), state, report)
            claim_email(signal["event_id"], state, report)
            again = claim_email(signal["event_id"], state, report)
            self.assertFalse(again["email_claimed"])
            self.assertEqual(again["email_event"]["status"], "sending")
            self.assertTrue(again["email_notify"])
            self.assertEqual(again["email_sent_count"], 0)

    def test_email_ack_requires_claim_recipient_and_message_id(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(25), state, report)
            configure_email("review-7175d36340e3@example.invalid", "review-8b81bcfb1708@example.invalid", state, report)
            signal = event("2026-01-26")
            with patch("signal_notifications.latest_completed_signal", return_value=signal):
                prepare_notifications(observations(26), state, report)
            before = state.read_bytes()
            with self.assertRaisesRegex(ValueError, "状态"):
                acknowledge_email(signal["event_id"], "gmail123", "review-7175d36340e3@example.invalid", state, report)
            self.assertEqual(before, state.read_bytes())
            claim_email(signal["event_id"], state, report)
            before = state.read_bytes()
            for message_id, recipient in (("", "review-7175d36340e3@example.invalid"), ("gmail123", "wrong@example.com")):
                with self.assertRaises(ValueError):
                    acknowledge_email(signal["event_id"], message_id, recipient, state, report)
                self.assertEqual(before, state.read_bytes())
            with self.assertRaises(ValueError):
                claim_email("2099-01-01:negative", state, report)
            self.assertEqual(before, state.read_bytes())

    def test_enabling_email_does_not_replay_or_reroute_chat_history(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(25), state, report)
            signal = event("2026-01-26")
            with patch("signal_notifications.latest_completed_signal", return_value=signal):
                prepare_notifications(observations(26), state, report)
            enabled = configure_email("review-7175d36340e3@example.invalid", "review-8b81bcfb1708@example.invalid", state, report)
            self.assertTrue(enabled["notify"])
            self.assertFalse(enabled["email_notify"])
            self.assertEqual(enabled["email_channel"]["enabled_after_date"], "2026-01-26")
            again = configure_email("review-7175d36340e3@example.invalid", "review-8b81bcfb1708@example.invalid", state, report)
            self.assertEqual(enabled["email_channel"], again["email_channel"])
            before = state.read_bytes()
            with self.assertRaisesRegex(ValueError, "不同"):
                configure_email("new@example.com", "review-8b81bcfb1708@example.invalid", state, report)
            self.assertEqual(before, state.read_bytes())

    def test_catch_up_mail_labels_older_signal_and_retains_each_event(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(25), state, report)
            configure_email("review-7175d36340e3@example.invalid", "review-8b81bcfb1708@example.invalid", state, report)
            with patch("signal_notifications.latest_completed_signal", side_effect=lambda rows: event(rows[-1].date.isoformat())):
                result = prepare_notifications(observations(27), state, report)
            self.assertEqual(len(result["email_pending"]), 2)
            first, latest = result["email_pending"]
            self.assertIn("补更发现", first["body"])
            self.assertNotIn("补更发现", latest["body"])
            self.assertNotEqual(first["marker"], latest["marker"])

    def test_corrupt_email_queue_does_not_reset_any_channel(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(25), state, report)
            configure_email("review-7175d36340e3@example.invalid", "review-8b81bcfb1708@example.invalid", state, report)
            contents = json.loads(state.read_text(encoding="utf-8"))
            contents["email_pending"] = [{"event_id": "bad", "recipient": "wrong@example.com"}]
            state.write_text(json.dumps(contents), encoding="utf-8")
            before = state.read_bytes()
            with self.assertRaisesRegex(ValueError, "未重置"):
                prepare_notifications(observations(26), state, report)
            self.assertEqual(before, state.read_bytes())

    def test_email_ack_preserves_chat_and_below_70_signal_also_creates_mail(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            state, report = root/"state.json", root/"report.json"
            prepare_notifications(observations(25), state, report)
            configure_email("review-7175d36340e3@example.invalid", "review-8b81bcfb1708@example.invalid", state, report)
            unqualified = event("2026-01-26")
            unqualified["horizons"] = []
            unqualified["cycle_results"] = observation_cycle(unqualified["date"], [])
            with patch("signal_notifications.latest_completed_signal", return_value=unqualified):
                result = prepare_notifications(observations(26), state, report)
            self.assertTrue(result["notify"])
            self.assertTrue(result["email_notify"])
            self.assertIn("暂无达到70%的重点观察日", result["email_pending"][0]["body"])
            claim_email(unqualified["event_id"], state, report)
            acknowledge_email(unqualified["event_id"], "gmail122", "review-7175d36340e3@example.invalid", state, report)
            signal = event("2026-01-27")
            with patch("signal_notifications.latest_completed_signal", return_value=signal):
                prepare_notifications(observations(27), state, report)
            claim_email(signal["event_id"], state, report)
            sent = acknowledge_email(signal["event_id"], "gmail123", "review-7175d36340e3@example.invalid", state, report)
            self.assertTrue(sent["notify"])
            self.assertFalse(sent["email_notify"])


if __name__ == "__main__":
    unittest.main()
