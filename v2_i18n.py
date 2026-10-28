"""Static English presentation of the shared V2 templates.

No model values, event attributes, CSV data, rules or notification state are
changed. Both locales are generated together; no network translator is used.
"""

from __future__ import annotations

import calendar
import re


PAGE_NAMES = ("index.html", "research_dashboard.html", "commercial_dashboard.html")


def language_filename(page_name: str, language: str) -> str:
    if page_name not in PAGE_NAMES or language not in ("zh", "en"):
        raise ValueError("Unsupported V2 page or language.")
    return page_name if language == "zh" else page_name.removesuffix(".html") + "_en.html"


# Complete sentences are translated before numeric labels. Keeping the shared
# templates as the source prevents the English version from drifting in layout,
# calculations, result selection or the scope of the commercial presentation.
SENTENCES = {
    "从黄金与实际利率的历史关系中，观察值得关注的时刻。精选历史上涨比例 ≥70% 的期限方案，让表现与发生日期清晰呈现。":
        "Explore notable signals in the historical relationship between gold and real yields. View horizons with a historical up rate of at least 70%, alongside their signal dates and outcomes.",
    "日期标记信号出现，不代表当天上涨或后续一定上涨。每个日期旁分别标注对应期限的历史结果，无需展开。":
        "Dates mark signal occurrences, not same-day gains or a promise of future gains. Each date shows the observed outcome for its selected horizon, with no expansion needed.",
    "结果比较信号后首个交易日的开盘价与第 N 个交易日的收盘价；不是信号当天的涨跌，也不要求中间每天连续上涨。同一信号的不同期限可能结果不同。按信号日期去重，跨期限次数不相加；首尾年份仅计实际覆盖区间。历史统计不保证未来结果。":
        "An outcome compares the opening price on the first trading day after the signal with the closing price on the Nth subsequent trading day. It is not the signal-day price change and does not require consecutive daily gains. Horizons for the same signal can have different outcomes. Signal dates are counted once, not added across horizons. The first and last years include only the actual sample coverage. Historical statistics do not guarantee future results.",
    "每张卡片对应一个观察期限。同组期限共用同一批历史信号，次数不相加；日历按信号日期去重。历史上涨比例不是未来预测，年均次数也不是每年固定次数。":
        "Each card represents one observation horizon. Horizons in the same group share the same historical signals; their counts are not added together. The calendar counts unique signal dates. Historical up rates are not forecasts, and the annual average is not a fixed yearly count.",
    "提醒服务围绕研究定义的信号展开，帮助关注黄金市场的读者持续观察。研究信息不替代独立判断，也不执行交易。":
        "The proposed alert service follows research-defined signals to support ongoing observation of the gold market. Research information does not replace independent judgment, and this website does not execute trades.",
    "正式开放前，将说明提醒方式、频率、隐私处理和取消方法，并由订阅者主动确认。":
        "Before a public launch, alert channels, frequency, privacy practices and cancellation options will be explained, with explicit subscriber consent.",
    "目前尚未接入客户登记与通知服务。本页不收集联系方式，不保存或发送订阅信息。":
        "Public subscriber registration and notifications are not connected. This page does not collect contact details or store or send subscription information.",
    "这是本地演示，尚未开通正式订阅；没有保存或发送任何信息。":
        "This is a local demo. Public subscriptions are not available. No information was saved or sent.",
    "历史统计不代表未来结果；小样本结果存在不确定性。":
        "Historical statistics do not predict future results. Small samples carry uncertainty.",
    "两个本地入口用于展示区分，不构成访问权限隔离；本页尚未公开部署。":
        "The two local views separate presentation only, not access permissions. This page is not publicly deployed.",
    "校内研究看完整过程，商业化版看精炼结果。":
        "Explore the full research process or a concise presentation of the results.",
    "面向课程、研讨与数据复核，保留完整研究口径。":
        "For coursework, discussion and verification, with full methodology and audit details.",
    "方案归类 · 历史概率 · 年均频率":
        "Grouped horizons · Historical up rates · Annual frequency",
    "年份日历、信号月日与每个期限的逐次记录":
        "Year and month calendars, signal dates and per-horizon event records",
    "算法条件、原始价格及研究 CSV 下载":
        "Signal rules, underlying prices and research CSV downloads",
    "面向市场读者，以清晰的概率卡片与信号日历呈现研究成果。":
        "For market readers, with clear historical performance cards and a signal calendar.",
    "历史表现 · 年均频率 · 方案归类":
        "Historical performance · Annual frequency · Grouped horizons",
    "年份、次数与具体月日直接显示，无需展开":
        "Years, counts and signal dates shown directly, without dropdowns",
    "提醒服务演示，不呈现研究明细与算法":
        "Alert-service prototype; no detailed research tables or algorithm disclosure",
    "两个入口使用相同的 V2 统计结果；每次数据更新会同时重建。均为本地展示，不执行交易，也不代表公开部署或访问权限隔离。":
        "Both views use the same V2 statistics and are rebuilt together after each data update. They are local presentations, do not execute trades and do not imply public deployment or separate access permissions.",
    "同一次信号，各期限结果分别判断；上涨指对应期限收盘价高于信号后首个交易日开盘价，未上涨包括持平。百分比是该方案全样本历史比例，不是当天预测。":
        "Outcomes for the same signal are assessed separately at each horizon. Up means the horizon closing price exceeds the opening price on the first trading day after the signal; Not up includes unchanged prices. Percentages are historical proportions across the horizon sample, not predictions for that day.",
    "次数统计信号出现，不是上涨成功；点击年份及信号日查看各期限的上涨／未上涨结果。":
        "Counts refer to signal occurrences, not successful outcomes. Select a year and a signal date to see Up / Not up outcomes for each horizon.",
    "按独立信号日期去重；点开信号日查看当日对应方案。":
        "Unique signal dates are counted once. Select a signal date to inspect its horizons. ",
    "首尾年份仅计入实际覆盖区间。":
        "The first and last years include only the actual sample coverage.",
    "只展示发生信号的月份；金色日期可点击查看对应方案。":
        "Only months with signals are shown. Select a gold-highlighted date to view its horizons.",
    "0 次表示样本覆盖区间内无信号，不代表未覆盖日期。":
        "Zero means no signals in the covered sample window; it says nothing about dates outside that window.",
    "具体日期已显示在年份卡片中；展开月历需要浏览器启用 JavaScript。":
        "Signal dates are listed on the year cards. Enable JavaScript to open the monthly calendars.",
    "点击方案组查看日历；需要核对时，再展开研究明细。":
        "Open a group to view its calendar; expand the audit details only when needed.",
    "不同期限可能对应同一批历史信号，次数不相加。年均出现次数是历史频率，不是年度上涨概率，也不保证下一年出现同样次数。":
        "Different horizons can share the same historical signals, so their counts are not added. The annual average is a historical frequency, not a yearly probability of gains or a guarantee of next-year occurrences.",
    "A+B 候选条件：实际利率高于五个交易日前；黄金收盘价高于此前五个交易日最低收盘价。入选信号至少间隔五个交易日。":
        "A+B candidates: the real yield is above its value five trading days earlier, and the gold closing price is above the lowest closing price in the previous five trading days. Candidates are deduplicated with a minimum five-trading-day gap before correlation classification.",
    "A+B 候选条件：均使用已完成日线。":
        "A+B candidates: all conditions use completed daily bars.",
    "一、实际利率五日净上涨":
        "1. Net increase in the real yield over five trading days",
    "当天实际利率 ＞ 五个交易日前的实际利率。只比较两端，不要求每天连续上涨。中间四个交易日的利率可以上涨、下跌、持平，也可以高于当天，不设额外走势限制。两端利率相等时，不满足条件。":
        "Real yield on the evaluation day > real yield five trading days earlier. Only the two endpoints are compared; the yield need not rise every day. During the four intervening trading days, yields may rise, fall, remain unchanged or exceed the evaluation-day yield, without additional path restrictions. Equal endpoint yields do not qualify.",
    "二、黄金守住此前收盘低点":
        "2. Gold closes above the preceding closing-price low",
    "当天黄金收盘价 ＞ 此前五个交易日中的最低收盘价。此前五个交易日不包含当天；比较的是收盘价，不是盘中最低价。当天收盘价等于该低点时，不满足条件。":
        "Gold closing price on the evaluation day > lowest closing price over the previous five trading days. Those five days exclude the evaluation day. The comparison uses closing prices, not intraday lows. A close equal to that low does not qualify.",
    "“只比较两端”仅用于判断实际利率高于五个交易日前这一条件，不代表整个算法忽略中间数据；五日相关性仍按既定规则计算。入选信号至少间隔五个交易日。":
        "Endpoint-only comparison applies solely to the five-trading-day net-yield condition; it does not mean the entire algorithm ignores intervening data. Five-point correlation is still calculated under the existing alignment rules. Candidates are deduplicated with a minimum five-trading-day gap before correlation classification.",
    "黄金收盘价与实际利率的五日原始数值相关系数 ≥ +0.80 为正极端相关，≤ −0.80 为负极端相关。":
        "The five-point Pearson correlation of gold closing-price levels and aligned real-yield levels is classified as extreme positive at ≥ +0.80 and extreme negative at ≤ −0.80.",
    "正负相关各比较第 1–10 个后续交易日。所有期限使用信号后有完整十个交易日的同一批样本；信号后第一个交易日开盘进入，第 N 个后续交易日收盘退出。":
        "Each correlation group is compared at trading-day horizons 1–10. All horizons use the same signal cohort with ten complete subsequent trading days. Entry is the first subsequent trading-day open; exit is the Nth subsequent trading-day close.",
    "退出收盘价高于入场开盘价记为上涨。历史上涨概率 = 上涨次数 ÷ 样本数；年均出现次数 = 独立信号次数 ÷ 样本跨度（天数 / 365.2425）。不是“每年上涨的概率”。":
        "Up means the exit closing price exceeds the entry opening price. Historical up rate = up outcomes / sample count. Average annual frequency = unique signals / sample span in years (days / 365.2425). This is not a yearly probability of gains.",
    "仅当相关类别、信号日期和上涨比例均相同才合并展示。相同概率不表示每次结果相同，逐次结果按各期限保留。":
        "Horizons are grouped only when their correlation category, signal dates and historical up rate all match. Equal rates do not imply identical individual outcomes; event results are retained separately for each horizon.",
    "数据源：2026-10-02 前黄金与利率保留原历史数据，相关系数恢复为 TradingView 原指标导出值；衔接日及之后黄金使用 IBKR XAUUSD MIDPOINT 日线、利率使用 FRED DFII10。相关性取完整 FRED 日历中严格早于黄金日线日期的最近正式观测，再计算五日原始数值；不是把同日两列直接配对，也不是简单移动一行。CSV分别记录利率实际观测日期与相关性配对观测日期。IBKR与原图OANDA黄金来源不同，衔接后的数值不承诺与OANDA图表相同。":
        "Data sources: before 2026-10-02, original historical gold and yield data are retained and correlations use the original TradingView indicator export. From that boundary onward, gold uses IBKR XAUUSD MIDPOINT daily bars and real yields use FRED DFII10. Correlation alignment takes the latest formal observation strictly before each gold-bar date from the full FRED calendar, then calculates five-point level correlation. This is neither same-date column pairing nor a simple one-row shift. The CSV records the actual yield observation date and the correlation-paired observation date separately. IBKR and the original OANDA chart use different gold sources; post-boundary values are not guaranteed to match OANDA.",
}


LABELS = {
    "历史样本：覆盖": "Historical sample: ",
    "二十余年": "20+ years", "十余年": "10+ years", "数十年": "Several decades",
    "一年多": "Over a year", "不足一年": "Under a year", "多年": "Several years",
    "近三千个交易日": "Nearly 3,000 trading days", "约三千个交易日": "Around 3,000 trading days",
    "两千余个交易日": "Over 2,000 trading days", "千余个交易日": "Over 1,000 trading days",
    "数百个交易日": "Hundreds of trading days", "数十个交易日": "Dozens of trading days",
    "少量交易日": "A small trading-day sample", "部分年份样本": "Partial-year sample", "约 ": "Around ",
    "黄金与实际利率 · 历史信号研究": "Gold & Real Yields · Historical Signal Research",
    "历史上涨概率 ≥70% 的方案 · 按同批信号与相同胜率归类": "Horizons with historical up rates ≥70% · Grouped by signal cohort and matching rates",
    "同一份研究，两种清晰入口": "One study. Two clear views.",
    "让黄金信号，": "Gold signals.", "一眼看清。": "Clearly in view.",
    "有信号时提醒，": "Alerts when signals appear.", "没有信号时不打扰。": "Quiet when they do not.",
    "SIGNAL DATES & OUTCOMES / 信号日期与后续结果": "SIGNAL DATES & OUTCOMES",
    "GOLD × REAL YIELD / 信号观察": "GOLD × REAL YIELD / SIGNAL RESEARCH",
    "RESEARCH COVERAGE / 历史样本": "RESEARCH COVERAGE",
    "HISTORICAL PERFORMANCE / 历史表现": "HISTORICAL PERFORMANCE",
    "SIGNAL ALERTS / 提醒服务": "SIGNAL ALERTS",
    "GOLD SIGNAL V2 · 商业化展示原型": "GOLD SIGNAL V2 · Commercial presentation prototype",
    "GOLD SIGNAL V2 · 黄金与美国十年期实际利率": "GOLD SIGNAL V2 · Gold & U.S. 10-year real yields",
    "历史样本统计 · 只读展示，不执行交易": "Historical statistics · Read-only presentation; no trading",
    "当前没有达到历史上涨比例 ≥70% 的完整样本方案。": "No complete-sample horizons currently meet the ≥70% historical up-rate threshold.",
    "当前没有达到历史上涨概率 ≥70% 的完整样本方案。": "No complete-sample horizons currently meet the ≥70% historical up-rate threshold.",
    "订阅登记 · 本地演示原型": "SUBSCRIPTIONS / LOCAL DEMO",
    "信号提醒服务筹备中": "Public signal alerts are in preparation",
    "查看订阅演示": "View subscription demo",
    "查看历史表现": "View historical performance", "查看信号日历": "View signal calendar",
    "进入校内研究版": "Open research view", "进入商业化版": "Open commercial view",
    "V2 · 双入口": "V2 · Two views", "校内研究版": "Research view", "校内研究": "Research",
    "商业化版": "Commercial view", "黄金信号研究": "Gold Signal Research", "黄金信号 V2": "Gold Signal V2",
    "主导航": "Main navigation", "商业化页面导航": "Commercial page navigation", "版本入口": "View navigation",
    "网页入口": "Website entry", "返回入口": "Back to entry", "研究版": "Research view", "入口": "Home",
    "达到 ≥70% 的期限方案": "Horizon plans ≥70%", "独立历史信号": "Unique historical signals",
    "年均出现": "Annual average", "历史样本跨度": "Historical sample span",
    "按相同胜率与同批日期归类": "Grouped by matching rates and signal dates",
    "跨期限、跨展示组去重": "Deduplicated across horizons and groups",
    "次数 ÷ 完整样本跨度": "Count / full sample span", "不是每年固定出现次数": "Not a fixed annual count",
    "观察期限方案": "Observation horizons", "历史研究样本": "Historical research sample",
    "信号后的观察期限": "Trading-day horizons after the signal",
    "历史上涨比例": "Historical up rate", "历史上涨概率": "Historical up rate",
    "年份次数 = 信号次数": "Year count = signal occurrences",
    "信号后的第 N 个交易日：": "Nth trading day after the signal:",
    "未上涨（含持平）": "Not up (includes flat)", "未上涨": "Not up", "上涨": "Up",
    "信号出现日期": "Signal date", "信号日与后续结果": " signal dates and subsequent outcomes",
    "信号日": "Signal date", "后续结果": "Subsequent outcomes",
    "历史表现": "Historical performance", "信号日历": "Signal calendar", "提醒服务": "Alert service",
    "样本期内未出现信号": "No signals in the sample window", "样本期内无信号": "No signals in the sample window",
    "全年样本": "Full-year sample", "展开全部": "Expand all", "收起全部": "Collapse all",
    "展开日期": "View dates", "收起明细": "Hide details",
    "研究明细 · 按期限核对逐次结果": "Audit details · Per-event outcomes by horizon",
    "可展开的历史方案": "Expandable historical horizons",
    "这组方案的信号出现日期": "Signal dates for this group",
    "查看月历 ↓": "View calendar ↓", "收起月历": "Close calendar",
    "信号月历": " signal calendar", "周一至周日": "Monday through Sunday",
    "信号日期": "Signal date", "入场日期": "Entry date", "观察结束日期": "Exit date",
    "入场开盘价": "Entry open", "退出收盘价": "Exit close", "单次毛收益": "Gross return", "上涨结果": "Outcome",
    "暂无完整观察记录": "No fully observed events", "的历史日期明细": " historical event details",
    "研究口径与数据来源": "Methodology & data sources",
    "≥70% 方案 CSV": "Horizons ≥70% · CSV", "20 种完整概率表": "All 20 horizon comparisons · CSV",
    "逐次信号明细": "Per-event records · CSV", "研究数据 CSV": "Source research data · CSV",
    "正极端相关": "Extreme positive correlation", "负极端相关": "Extreme negative correlation",
    "历史方案": "Historical horizons", "该方案": "This horizon", "历史出现 / 次": "Historical signals",
    "年均 / 次": "Annual average", "独立信号年均出现": "Average unique signals",
    "年均信号": "Average signals", "年均": "Annual average", "历史": "Historical", "样本：": "Sample: ",
}


def _english(page: str) -> str:
    for source, target in sorted(SENTENCES.items(), key=lambda item: -len(item[0])):
        page = page.replace(source, target)

    # These patterns cover variable counts/dates without changing their values.
    patterns = (
        (r"共同 A\+B 样本 (\d+) 次：正极端 (\d+)，负极端 (\d+)，非极端 (\d+)，相关系数不可计算 (\d+)。",
         r"Common A+B sample: \1 events; extreme positive: \2; extreme negative: \3; non-extreme: \4; correlation unavailable: \5."),
        (r"这 (\d+) 种方案对应同一批 (\d+) 次信号，日期只计算一次。",
         r"These \1 horizons share the same \2 historical signals; each date is counted once. "),
        (r"(\d{4}) 年的样本覆盖区间（(\d{2}/\d{2})—(\d{2}/\d{2})）内没有出现这类信号。",
         r"No signals in the \1 sample window (\2–\3, MM/DD)."),
        (r"(\d+) 个信号出现日期，逐次结果看清。", r"\1 signal dates. Every outcome in view."),
        (r"(\d+) 种方案，逐项看清。", r"\1 observation horizons, individually shown."),
        (r"(\d+) 种 / (\d+) 组", r"\1 horizons / \2 groups"),
        (r"(\d{4}-\d{2}-\d{2})信号", r"\1 signal"),
        (r"(\d{4}) ?年 ?(\d{1,2}) ?月 ?(\d{1,2}) ?日",
         lambda m: f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"),
        (r"(\d{4})年(\d{1,2})月", lambda m: f"{calendar.month_name[int(m[2])]} {m[1]}"),
        (r"(\d{1,2})月(\d{1,2})日", lambda m: f"{calendar.month_abbr[int(m[1])]} {int(m[2])}"),
        (r"(\d{1,2}) 月", lambda m: calendar.month_name[int(m[1])]),
        (r"(\d{4}) ?年", r"\1"),
        (r"第\s*((?:\d+\s*[、,]\s*)*\d+)\s*个后续交易日",
         lambda m: ("Days " if "、" in m[1] or "," in m[1] else "Day ") + re.sub(r"\s*[、,]\s*", ", ", m[1]) + " after the signal"),
        (r"第\s*(\d+)\s*个交易日", r"Day \1"),
        (r"第(\d+)日", r"Day \1 ·"),
        (r"(\d+) 种期限", r"\1 horizons"),
        (r"(\d+) 种方案", r"\1 horizons"),
        (r"方案组 (\d+)", r"Group \1"),
        (r"覆盖 (\d{2}/\d{2})—(\d{2}/\d{2})", r"Coverage: \1–\2 (MM/DD)"),
        (r"([\d,.]+) 个交易日", r"\1 trading days"),
        (r"([\d,.]+) ?次信号", r"\1 signals"),
        (r"([\d,.]+) 次 / 年", r"\1 signals / year"),
        (r"([\d,.]+) 次", r"\1 signals"),
    )
    for pattern, replacement in patterns:
        page = re.sub(pattern, replacement, page)

    for source, target in sorted(LABELS.items(), key=lambda item: -len(item[0])):
        page = page.replace(source, target)
    for source, target in (
        (">年<", ">years<"), (">种<", ">plans<"), (">次<", ">signals<"),
        (">次信号<", ">signals<"), (">次 / 年<", ">signals / year<"),
        (" 次 / 年", " signals / year"), ("样本数", "sample count"),
        ("共 ", "Total: "), (" 种方案", " horizons"),
        ("入场为信号后第一个交易日，观察结束为", "Entry is the first trading day after the signal; exit is "),
        (" 年", " years"),
    ):
        page = page.replace(source, target)
    for source, target in zip("一二三四五六日", ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
        page = page.replace(f"<span>{source}</span>", f"<span>{target}</span>")
    page = page.replace('lang="zh-CN"', 'lang="en"')
    for name in PAGE_NAMES:
        page = page.replace(f'href="{name}"', f'href="{language_filename(name, "en")}"')
    for source, target in (("，", ", "), ("。", "."), ("：", ": "), ("、", ", "), ("／", "/"), ("　", " ")):
        page = page.replace(source, target)
    page = re.sub(r"(?<![\d.])1 (horizons|signals|plans)\b", lambda m: "1 " + m[1][:-1], page)
    return page


LANGUAGE_CSS = """
.topbar{flex-wrap:wrap}.topbar .nav,.topbar nav{flex-wrap:wrap}
.language-switch{display:flex;align-items:center;gap:4px;font-size:12px;flex-shrink:0;margin-left:auto}
.language-switch a{text-decoration:none;padding:5px 9px;border:1px solid var(--line);border-radius:6px;color:var(--muted);line-height:1.5}
.language-switch a[aria-current="true"]{color:var(--ink);border-color:var(--gold);background:var(--wash,#1b2d40)}
.language-switch a:hover{border-color:var(--gold)}
html[lang="en"]{font-family:'Segoe UI',Arial,sans-serif}
html[lang="en"] .hero h1{letter-spacing:-.5px}
html[lang="en"] .plan-frequency{white-space:normal}
html[lang="en"] .date-heading{flex-wrap:wrap}
@media(max-width:680px){.language-switch{font-size:11px;order:1}.language-switch a{padding:4px 8px}.topbar>.nav,.topbar>nav{order:2;width:100%}}
"""


def render_language_page(page: str, page_name: str, language: str = "zh") -> str:
    """Localize a rendered page while preserving all statistics and event data."""
    language_filename(page_name, language)  # validate before any transformation
    if language == "en":
        page = _english(page)
        # This is already an authored English view, not content that needs a
        # browser translation back to the reader's preferred language. The
        # standard inherited translate flag also covers calendar/a11y labels.
        page = page.replace('<html lang="en">',
                            '<html lang="en" translate="no" class="notranslate">', 1)
        page = page.replace('<head>', '<head><meta name="google" content="notranslate">', 1)
        page = re.sub(r'<body\b([^>]*)>',
                      lambda match: '<body' + match[1] + ' translate="no">', page, count=1)
    links = []
    for locale, label in (("zh", "中文" if language == "zh" else "Chinese"), ("en", "English")):
        selected = ' aria-current="true"' if locale == language else ""
        label_language = "zh" if language == "zh" and locale == "zh" else "en"
        links.append(f'<a href="{language_filename(page_name, locale)}" hreflang="{locale}" lang="{label_language}" data-language="{locale}"{selected}>{label}</a>')
    switch = '<div class="language-switch" role="navigation" aria-label="' + ("语言切换" if language == "zh" else "Language") + '">' + "".join(links) + "</div>"
    topbar = re.compile(r'(<(?P<tag>nav|header) class="topbar"[^>]*>.*?)(</(?P=tag)>)', re.DOTALL)
    page, count = topbar.subn(lambda match: match[1] + switch + match[3], page, count=1)
    if count != 1:
        raise ValueError("The V2 page is missing its language-switch location.")
    page = page.replace("</head>", f"<style>{LANGUAGE_CSS}</style></head>", 1)
    return page
