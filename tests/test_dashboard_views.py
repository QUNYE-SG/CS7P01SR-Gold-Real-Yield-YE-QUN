import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from analysis import analyze, load_data
from app import public_summary, write_commercial_dashboard, write_dashboard, write_launch_page


ROOT = Path(__file__).resolve().parents[1]


class DashboardViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = analyze(load_data(ROOT / "data" / "market_data.csv"), "market_data.csv")

    def test_commercial_payload_contains_aggregates_only(self):
        public = public_summary(self.payload)
        self.assertEqual(len(public["strategies"]), 4)
        self.assertEqual(public["strategies"][0]["horizon"], 4)
        self.assertNotIn("details", public)
        self.assertNotIn("candles", public)
        self.assertNotIn("data", public)
        self.assertNotIn("group", public["strategies"][0])

    def test_commercial_page_hides_rules_and_event_rows(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "commercial.html"
            write_commercial_dashboard(self.payload, output)
            html = output.read_text(encoding="utf-8")
        self.assertIn("信号观察方案 ", html)
        self.assertIn("自愿订阅", html)
        self.assertNotIn("A+B+C", html)
        self.assertNotIn("相关系数", html)
        self.assertNotIn("signal_date", html)
        self.assertNotIn("2015-10-02", html)
        self.assertNotIn("market_data.csv", html)
        self.assertIn("不会提交、保存或发送", html)

    def test_school_page_contains_method_and_audit_sections(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "school.html"
            write_dashboard(self.payload, output)
            html = output.read_text(encoding="utf-8")
        self.assertIn("A+B+C（正极端相关）", html)
        self.assertIn("C：正极端相关", html)
        self.assertIn("D：负极端相关", html)
        self.assertIn("相关系数 ≥ +0.80", html)
        self.assertIn("分段稳定性比较", html)
        self.assertIn("逐次记录", html)
        self.assertIn("signal_date", html)

    def test_recalculated_preview_generates_pages_and_reports_undefined_correlation(self):
        payload = analyze(
            load_data(ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv"),
            "market_data_pine5_raw_recalc_preview.csv",
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            school = root / "research_dashboard.html"
            commercial = root / "commercial_dashboard.html"
            index = root / "index.html"
            write_dashboard(payload, school)
            write_commercial_dashboard(payload, commercial)
            write_launch_page(school, commercial, index)
            school_html = school.read_text(encoding="utf-8")
            commercial_html = commercial.read_text(encoding="utf-8")
            index_html = index.read_text(encoding="utf-8")

        self.assertIn("correlation_unavailable_count", school_html)
        self.assertIn(f"\"correlation_unavailable_count\":{payload['data']['correlation_unavailable_count']}", school_html)
        self.assertIn("research_dashboard.html", index_html)
        self.assertIn("commercial_dashboard.html", index_html)
        self.assertNotIn("market_data_pine5_raw_recalc_preview.csv", commercial_html)

    def test_launcher_links_to_both_versions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            school = root / "research_dashboard.html"
            commercial = root / "commercial_dashboard.html"
            index = root / "index.html"
            write_launch_page(school, commercial, index)
            html = index.read_text(encoding="utf-8")
        self.assertIn('href="research_dashboard.html"', html)
        self.assertIn('href="commercial_dashboard.html"', html)

    def test_preview_launcher_opens_the_same_v2_ranked_result(self):
        launcher = (ROOT / "RUN_PINE5_RECALC_PREVIEW.bat").read_text(encoding="utf-8")
        self.assertIn('RUN_TOP2_PINE5_PACKAGE.bat', launcher)
        self.assertNotIn('app.py', launcher)


if __name__ == "__main__":
    unittest.main()
