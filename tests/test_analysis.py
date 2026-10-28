import unittest
from datetime import date, timedelta
from pathlib import Path
from statistics import correlation
from tempfile import TemporaryDirectory
from unittest.mock import patch

from analysis import DailyObservation, analyze, classify_correlation, deduplicate, load_data
from alerting import dispatch_once, latest_completed_signal, message_for


ROOT = Path(__file__).resolve().parents[1]


class SignalAnalysisTests(unittest.TestCase):
    def test_correlation_thresholds_are_inclusive(self):
        self.assertEqual(classify_correlation(0.80), "positive")
        self.assertEqual(classify_correlation(-0.80), "negative")
        self.assertEqual(classify_correlation(0.7999), "non_extreme")
        self.assertEqual(classify_correlation(-0.7999), "non_extreme")

    def test_signal_deduplication_uses_five_bar_minimum_gap(self):
        self.assertEqual(deduplicate([5, 8, 9, 14, 19]), [5, 14, 19])

    def test_frozen_csv_reproduces_reported_full_sample_results(self):
        rows = load_data(ROOT / "data" / "market_data.csv")
        result = analyze(rows)
        self.assertEqual((result["data"]["first_date"], result["data"]["last_date"]), ("2015-10-02", "2026-10-02"))
        self.assertEqual(result["data"]["common_ab_count"], 328)
        self.assertEqual(result["data"]["positive_count"], 15)
        self.assertEqual(result["data"]["negative_count"], 31)
        self.assertEqual(len(result["candles"]), 2841)
        self.assertGreaterEqual(result["candles"][0]["high"], max(result["candles"][0]["open"], result["candles"][0]["close"]))
        self.assertLessEqual(result["candles"][0]["low"], min(result["candles"][0]["open"], result["candles"][0]["close"]))
        full = {(item["group"], item["horizon"]): item["full"] for item in result["strategies"]}
        self.assertEqual((full[("positive", 4)]["wins"], full[("positive", 4)]["n"]), (11, 15))
        self.assertEqual((full[("positive", 5)]["wins"], full[("positive", 5)]["n"]), (10, 15))
        self.assertEqual((full[("positive", 9)]["wins"], full[("positive", 9)]["n"]), (10, 15))
        self.assertEqual((full[("negative", 10)]["wins"], full[("negative", 10)]["n"]), (22, 31))
        self.assertAlmostEqual(full[("positive", 4)]["mean_gross_return"], 0.007260191014946682)
        self.assertAlmostEqual(full[("positive", 9)]["mean_gross_return"], 0.014007516993897417)
        prob_keys = [(item["group"], item["horizon"]) for item in result["probability_ranking"]]
        return_keys = [(item["group"], item["horizon"]) for item in result["return_ranking"]]
        self.assertEqual(prob_keys, [("positive", 4), ("negative", 10), ("positive", 5), ("positive", 9)])
        self.assertEqual(return_keys, [("positive", 9), ("negative", 10), ("positive", 4), ("positive", 5)])

    def test_corrected_preview_preserves_exported_history_and_aligns_live_window(self):
        rows = load_data(ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv")
        undefined = next(row for row in rows if row.date.isoformat() == "2015-11-30")
        original = load_data(ROOT / "data" / "market_data.csv")
        exported = next(row for row in original if row.date == undefined.date)
        self.assertEqual(undefined.correlation, exported.correlation)

        result = analyze(rows)
        data = result["data"]
        grouped_total = (
            data["positive_count"]
            + data["negative_count"]
            + data["non_extreme_count"]
            + data["correlation_unavailable_count"]
        )
        self.assertEqual(grouped_total, data["common_ab_count"])
        self.assertTrue(all(item["correlation"] is not None for item in result["details"]))
        last = next(row for row in rows if row.date.isoformat() == "2026-10-02")
        self.assertEqual((last.open, last.high, last.low, last.close), (4181.7, 4227.67, 4125.25, 4141.65))
        # The source-switch row is live data: verify its five-day correlation
        # independently instead of fixing a value from before the FRED refresh.
        last_index = rows.index(last)
        window = rows[last_index - 4:last_index + 1]
        aligned_window = rows[last_index - 5:last_index]
        expected = correlation([row.close for row in window], [row.real_yield for row in aligned_window])
        self.assertAlmostEqual(last.correlation, expected)

    def test_latest_extreme_signal_is_detected_without_future_bars(self):
        rows = [
            DailyObservation(date(2026, 1, 1) + timedelta(days=i), 100 + i, 100 + i, 2.0, 0.2)
            for i in range(8)
        ]
        rows[-1] = DailyObservation(rows[-1].date, 107, 107, 2.2, 0.80)
        signal = latest_completed_signal(rows)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["date"], "2026-01-08")
        # Detection needs no future bars, but eight rows cannot estimate history.
        self.assertEqual(signal["horizons"], [])
        self.assertIn("正极端相关", message_for(signal))

    def test_notification_deduplication_uses_local_state_and_mock_senders(self):
        signal = {"event_id": "2026-01-08:positive", "date": "2026-01-08", "group": "positive", "label": "正极端相关", "correlation": 0.9, "horizons": [4, 5, 9]}
        env = {
            "SMTP_HOST": "smtp.example.test",
            "SMTP_USERNAME": "sender@example.test",
            "SMTP_PASSWORD": "example-only",
            "SMTP_TO": "reader@example.test",
            "WECHAT_WORK_WEBHOOK_URL": "https://example.test/robot-token",
        }
        with TemporaryDirectory() as directory, patch.dict("os.environ", env, clear=True):
            state = Path(directory) / "notification_state.json"
            with patch("alerting._send_email", return_value=(True, "邮件已发送。")) as email, patch(
                "alerting._send_wecom", return_value=(True, "企业微信消息已发送。")
            ) as wecom:
                dispatch_once(signal, state)
                second = dispatch_once(signal, state)
            email.assert_called_once()
            wecom.assert_called_once()
            self.assertIn("已发送过", "".join(second))
            self.assertNotIn("example-only", state.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
