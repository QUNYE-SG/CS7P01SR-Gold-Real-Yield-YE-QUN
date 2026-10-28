"""English is presentation-only: identical signals, outcomes and sample values."""

import copy
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

from analysis import load_data
from build_top2_package import calculate_rankings, qualifying_rankings
from v2_i18n import PAGE_NAMES, language_filename
from v2_pages import dashboard_page, launcher_page, presentation_model


ROOT = Path(__file__).resolve().parents[1]
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


class PageTags(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.tags = []
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def pages(model, language):
    return (
        launcher_page(model, language=language),
        dashboard_page(model, language=language, download_prefix="top2_pine5_20261004/"),
        dashboard_page(model, commercial=True, language=language),
    )


class EnglishPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = []
        for path in (ROOT / "data/market_data_pine5_raw_recalc_preview.csv",
                     ROOT / "tests/fixtures/v2_legacy_same_day_20261002.csv"):
            ranked, details, metadata = calculate_rankings(load_data(path))
            cls.models.append(presentation_model(qualifying_rankings(ranked), details, metadata))
        cls.models.append(presentation_model([], [], cls.models[0]["metadata"]))

    def test_every_english_page_including_accessibility_and_script_is_english(self):
        for model in self.models:
            for name, page in zip(PAGE_NAMES, pages(model, "en")):
                with self.subTest(name=name, plans=model["plan_count"]):
                    contexts = [page[max(0, m.start() - 35):m.start() + 70]
                                for m in list(HAN.finditer(page))[:12]]
                    self.assertFalse(contexts, contexts)
                    root = next(attrs for tag, attrs in PageTags(page).tags if tag == "html")
                    self.assertEqual(root["lang"], "en")
                    self.assertIn('hreflang="zh"', page)

    def test_english_views_request_original_text_without_changing_chinese_views(self):
        for model in self.models:
            for page in pages(model, "en"):
                tags = PageTags(page).tags
                root = next(attrs for tag, attrs in tags if tag == "html")
                body = next(attrs for tag, attrs in tags if tag == "body")
                self.assertEqual(root["translate"], "no")
                self.assertIn("notranslate", root["class"].split())
                self.assertEqual(body["translate"], "no")
                self.assertTrue(any(tag == "meta" and attrs.get("name") == "google" and
                                    attrs.get("content") == "notranslate" for tag, attrs in tags))
                for tag, attrs in tags:
                    self.assertNotEqual(attrs.get("translate"), "yes")
                    if "data-language" in attrs:
                        self.assertEqual(attrs.get("lang"), "en")
            for page in pages(model, "zh"):
                root = next(attrs for tag, attrs in PageTags(page).tags if tag == "html")
                self.assertNotIn("translate", root)

    def test_chinese_pages_are_preserved_with_corresponding_language_links(self):
        for name, page in zip(PAGE_NAMES, pages(self.models[0], "zh")):
            self.assertIn('<html lang="zh-CN">', page)
            self.assertIn('href="' + language_filename(name, "en") + '"', page)
            self.assertIn('data-language="zh" aria-current="true">中文</a>', page)
        self.assertIn("信号日", pages(self.models[0], "zh")[2])
        self.assertIn("未上涨（含持平）", pages(self.models[0], "zh")[2])

    def test_english_and_chinese_have_identical_statistical_and_event_attributes(self):
        for model in self.models:
            for zh, en in zip(pages(model, "zh"), pages(model, "en")):
                def event_signature(page):
                    return [(tag, {key: value for key, value in attrs.items()
                                   if key.startswith("data-") or key in ("datetime", "id", "aria-controls")})
                            for tag, attrs in PageTags(page).tags
                            if any(key.startswith("data-") or key in ("datetime", "id", "aria-controls")
                                   for key in attrs)]
                self.assertEqual(event_signature(zh), event_signature(en))
                self.assertEqual(re.findall(r"\d+\.\d+%", zh), re.findall(r"\d+\.\d+%", en))

    def test_english_navigation_stays_in_english_except_explicit_language_switch(self):
        for name, page in zip(PAGE_NAMES, pages(self.models[0], "en")):
            switches = [attrs for tag, attrs in PageTags(page).tags if "data-language" in attrs]
            self.assertEqual([(item["data-language"], item["href"]) for item in switches],
                             [("zh", name), ("en", language_filename(name, "en"))])
            self.assertEqual([item["data-language"] for item in switches if "aria-current" in item], ["en"])
            for tag, attrs in PageTags(page).tags:
                if tag == "a" and attrs.get("href") in PAGE_NAMES:
                    self.assertEqual(attrs.get("data-language"), "zh")
        research = pages(self.models[0], "en")[1]
        self.assertIn('href="top2_pine5_20261004/signal_details.csv"', research)

    def test_english_commercial_view_retains_static_calendar_and_no_data_disclosure(self):
        page = pages(self.models[0], "en")[2]
        self.assertFalse(any(tag in ("details", "summary", "table", "input", "form")
                             for tag, _ in PageTags(page).tags))
        self.assertNotIn("signal_details.csv", page)
        self.assertNotIn("0.80", page)
        self.assertIn("Not up (includes flat)", page)
        self.assertIn("Signal date", page)
        self.assertIn("Subsequent outcomes", page)
        self.assertIn("No information was saved or sent.", page)

    def test_research_translation_preserves_methodology_and_not_a_daily_forecast(self):
        page = pages(self.models[0], "en")[1]
        self.assertIn("before correlation classification", page)
        self.assertIn("strictly before each gold-bar date", page)
        self.assertIn("first subsequent trading-day open", page)
        self.assertIn("Nth subsequent trading-day close", page)
        self.assertIn("not predictions for that day", page)
        self.assertIn("Not up includes unchanged prices", page)

    def test_rendering_does_not_mutate_model_and_rejects_unknown_locale(self):
        before = copy.deepcopy(self.models[0])
        pages(self.models[0], "en")
        self.assertEqual(self.models[0], before)
        with self.assertRaises(ValueError):
            dashboard_page(self.models[0], language="fr")
        with self.assertRaises(ValueError):
            language_filename("../arbitrary.html", "en")


if __name__ == "__main__":
    unittest.main()
