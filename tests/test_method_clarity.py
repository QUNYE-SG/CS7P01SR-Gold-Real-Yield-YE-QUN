"""The explanation clarifies existing rules without changing the algorithm."""
import unittest
from pathlib import Path

from analysis import load_data
from build_top2_package import calculate_rankings, qualifying_rankings
from v2_pages import dashboard_page, presentation_model

ROOT = Path(__file__).resolve().parents[1]


class MethodClarityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ranked, details, metadata = calculate_rankings(load_data(ROOT / 'data/market_data_pine5_raw_recalc_preview.csv'))
        cls.model = presentation_model(qualifying_rankings(ranked), details, metadata)

    def test_chinese_research_states_endpoints_path_freedom_and_strict_close_comparison(self):
        page = dashboard_page(self.model)
        for text in ('均使用已完成日线', '一、实际利率五日净上涨', '二、黄金守住此前收盘低点',
                     '中间四个交易日的利率可以上涨、下跌、持平', '也可以高于当天',
                     '两端利率相等时，不满足条件', '此前五个交易日不包含当天', '不是盘中最低价',
                     '当天收盘价等于该低点时，不满足条件', '不代表整个算法忽略中间数据',
                     '五日相关性仍按既定规则计算', '入选信号至少间隔五个交易日'):
            self.assertIn(text, page)

    def test_english_research_has_matching_rules_and_keeps_deduplication_order(self):
        page = dashboard_page(self.model, language='en')
        for text in ('all conditions use completed daily bars', 'four intervening trading days',
                     'without additional path restrictions', 'Equal endpoint yields do not qualify',
                     'Those five days exclude the evaluation day', 'not intraday lows',
                     'A close equal to that low does not qualify', 'before correlation classification'):
            self.assertIn(text, page)

    def test_commercial_view_keeps_its_existing_algorithm_nondisclosure(self):
        for language in ('zh', 'en'):
            page = dashboard_page(self.model, commercial=True, language=language)
            for text in ('中间四个交易日', 'four intervening trading days', '0.80', 'Endpoint-only'):
                self.assertNotIn(text, page)


if __name__ == '__main__':
    unittest.main()
