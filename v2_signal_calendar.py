"""One read-only signal/outcome calendar shared by both dashboard views."""

from __future__ import annotations

import html
from datetime import date


# Scoped rules leave the research-only interactive audit calendars untouched.
SIGNAL_CALENDAR_CSS = """
.outcome-calendar{border:1px solid var(--line);border-radius:14px;background:var(--paper,#101c29c9);padding:28px;margin-top:24px}
.outcome-calendar .section-head{display:flex;justify-content:space-between;align-items:end;gap:18px;margin-bottom:20px}
.outcome-calendar .section-head h2{font-size:24px;font-weight:600;margin:5px 0 0;line-height:1.45}
.outcome-calendar .eyebrow{font-size:11px;letter-spacing:2px;color:var(--gold);font-weight:600;margin:0}
.outcome-calendar .calendar-legend{display:flex;align-items:center;gap:7px;color:var(--muted);font-size:11px}
.outcome-calendar .calendar-legend:before{content:'';width:8px;height:8px;background:var(--gold);border-radius:2px}
.outcome-calendar .calendar-definition{font-size:12px;color:var(--muted);margin:0 0 17px;line-height:1.8}
.outcome-calendar .calendar-result-legend{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 15px;font-size:11px;color:var(--muted);align-items:center}
.outcome-calendar .legend-label{margin-right:4px}
.outcome-calendar .calendar-years{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px}
.outcome-calendar .calendar-year-card{min-width:0;text-align:left;padding:16px;border-radius:9px;border:1px solid #283746;min-height:145px;display:flex;flex-direction:column;gap:13px;background:var(--wash,#0d1824);color:var(--muted);cursor:default}
.outcome-calendar .calendar-year-card.has-signals{background:linear-gradient(140deg,#294259,#1b3044);border-color:#b99a6266;color:#f0f3f6;box-shadow:inset 0 2px 0 #d7b36a7a}
.outcome-calendar .calendar-year-card.no-signals{background:var(--wash,#0d1824);border-color:var(--line);color:var(--muted);box-shadow:none}
.outcome-calendar .calendar-year-top{display:flex;align-items:center;justify-content:space-between;gap:10px}
.outcome-calendar .calendar-year-top h3{font-size:16px;font-weight:600;margin:0;white-space:nowrap}
.outcome-calendar .calendar-count{display:flex;align-items:baseline;gap:5px;white-space:nowrap;color:#f1d79c}
.outcome-calendar .calendar-count strong{font-size:34px;color:#f1d79c;font-weight:600;line-height:1}
.outcome-calendar .calendar-count small{font-size:11px;color:#c1d0dc;font-weight:400;margin:0}
.outcome-calendar .no-signals .calendar-count strong{font-size:25px;color:var(--muted);font-weight:400}
.outcome-calendar .no-signals .calendar-count small{color:var(--muted)}
.outcome-calendar .calendar-list-header{display:flex;justify-content:space-between;gap:8px;padding-bottom:6px;margin-bottom:-8px;border-bottom:1px solid #ffffff20;font-size:10px;line-height:1.6;color:#b8c7d6;letter-spacing:.5px}
.outcome-calendar .no-signals .calendar-list-header{color:var(--muted);border-color:var(--line)}
.outcome-calendar .calendar-date-list{display:flex;flex-direction:column;align-items:stretch;gap:0;list-style:none;min-height:0;margin:0;padding:0}
.outcome-calendar .calendar-signal{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #ffffff12}
.outcome-calendar .calendar-signal:last-child{border-bottom:0}
.outcome-calendar .calendar-date-list time{flex-shrink:0;border:0;border-radius:0;background:transparent;padding:0;color:#f0e3c7;font-size:12px;font-variant-numeric:tabular-nums}
.outcome-calendar .calendar-outcomes{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:4px;min-width:0;max-width:160px}
.outcome-calendar .calendar-outcome{font-size:10px;line-height:1.6;white-space:nowrap;border-radius:4px;padding:2px 5px;border:1px solid #536478;color:#d1dce5;background:#142739}
.outcome-calendar .calendar-outcome.is-up{color:#b9e3cd;border-color:#59987988;background:#193b33}
.outcome-calendar .calendar-outcome.is-not-up{color:#d1dce5;border-color:#72829388;background:#273b4b}
.outcome-calendar .calendar-empty{font-size:11px;color:var(--muted);padding:10px 0}
.outcome-calendar .calendar-coverage{margin-top:auto;font-size:10px;color:#b4c3d0}
.outcome-calendar .no-signals .calendar-coverage{color:var(--muted)}
.outcome-calendar .section-note{font-size:11px;color:var(--muted);margin:17px 0 0;line-height:1.8}
@media(max-width:950px){.outcome-calendar .calendar-years{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:680px){.outcome-calendar{padding:20px 16px}.outcome-calendar .section-head{align-items:start;flex-wrap:wrap;gap:10px}.outcome-calendar .section-head h2{font-size:21px}.outcome-calendar .calendar-years{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.outcome-calendar .calendar-year-card{padding:12px;min-height:142px;gap:10px}.outcome-calendar .calendar-year-top{gap:5px}.outcome-calendar .calendar-year-top h3{font-size:13px}.outcome-calendar .calendar-count{gap:3px}.outcome-calendar .calendar-count strong{font-size:29px}.outcome-calendar .no-signals .calendar-count strong{font-size:22px}.outcome-calendar .calendar-count small{font-size:10px}.outcome-calendar .calendar-date-list time{font-size:11px}.outcome-calendar .calendar-coverage{font-size:9px}.outcome-calendar .calendar-outcome{font-size:10px;padding:2px 4px}.outcome-calendar .calendar-signal{align-items:flex-start;gap:5px}.outcome-calendar .calendar-outcomes{max-width:150px}.outcome-calendar .calendar-definition{font-size:11px}}
@media(max-width:480px){.outcome-calendar .calendar-years{grid-template-columns:1fr}.outcome-calendar .calendar-year-card{padding:15px}.outcome-calendar .calendar-year-top h3{font-size:15px}.outcome-calendar .calendar-date-list time{font-size:12px}.outcome-calendar .calendar-outcomes{max-width:180px}.outcome-calendar .calendar-outcome{font-size:11px}.outcome-calendar .calendar-signal{align-items:center}}
"""


def signal_calendar(model: dict) -> str:
    """Render each unique signal once, with all its selected horizon outcomes.

    The same markup is used in research and commercial views. Precise research
    coverage remains in the research header and audit detail, not this summary.
    """
    cards = []
    for year in model["calendar_years"]:
        dates = []
        for day in year["dates"]:
            outcomes = []
            for outcome in model["signal_outcomes"][day]:
                horizon = int(outcome["horizon"])
                status = "up" if outcome["win"] else "not-up"
                label = "上涨" if outcome["win"] else "未上涨"
                group = html.escape(str(outcome["group"]), quote=True)
                outcomes.append(f'<span class="calendar-outcome is-{status}" data-outcome-date="{day}" '
                                f'data-outcome-group="{group}" data-outcome-horizon="{horizon}" '
                                f'data-outcome="{status}" aria-label="{day}信号，第{horizon}个后续交易日，{label}">第{horizon}日 {label}</span>')
            event_date = date.fromisoformat(day)
            dates.append(f'<li class="calendar-signal"><time datetime="{day}" aria-label="信号出现日期{day}">{event_date.month}月{event_date.day}日</time>'
                         f'<span class="calendar-outcomes">{"".join(outcomes)}</span></li>')
        date_list = "".join(dates) or '<li class="calendar-empty">样本期内未出现信号</li>'
        coverage = "部分年份样本" if year["partial"] else "全年样本"
        state = "has-signals" if year["count"] else "no-signals"
        cards.append(f'''<article class="calendar-year-card {state}" data-calendar-year="{year['year']}" data-signal-count="{year['count']}" aria-label="{year['year']}年，{year['count']}次信号">
<div class="calendar-year-top"><h3>{year['year']} 年</h3><div class="calendar-count"><strong>{year['count']}</strong><small>次信号</small></div></div>
<div class="calendar-list-header"><span>信号日</span><span>后续结果</span></div>
<ul class="calendar-date-list" aria-label="{year['year']}年信号日与后续结果">{date_list}</ul><div class="calendar-coverage">{coverage}</div></article>''')
    return f'''<section class="section signal-calendar outcome-calendar" id="signal-calendar" aria-labelledby="calendar-title">
<div class="section-head"><div><div class="eyebrow">SIGNAL DATES & OUTCOMES / 信号日期与后续结果</div><h2 id="calendar-title">{model['unique_signal_count']} 个信号出现日期，逐次结果看清。</h2></div>
<span class="calendar-legend">年份次数 = 信号次数</span></div>
<p class="calendar-definition">日期标记信号出现，不代表当天上涨或后续一定上涨。每个日期旁分别标注对应期限的历史结果，无需展开。</p>
<div class="calendar-result-legend"><span class="legend-label">信号后的第 N 个交易日：</span><span class="calendar-outcome is-up">上涨</span><span class="calendar-outcome is-not-up">未上涨（含持平）</span></div>
<div class="calendar-years">{''.join(cards)}</div>
<p class="section-note">结果比较信号后首个交易日的开盘价与第 N 个交易日的收盘价；不是信号当天的涨跌，也不要求中间每天连续上涨。同一信号的不同期限可能结果不同。按信号日期去重，跨期限次数不相加；首尾年份仅计实际覆盖区间。历史统计不保证未来结果。</p></section>'''
