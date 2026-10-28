"""Static V2 entrances and expandable historical signal views.

Presentation only: no changes to signal selection, prices or ranking calculations.
"""

from __future__ import annotations

import calendar
import html
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from v2_commercial import commercial_page
from v2_i18n import PAGE_NAMES, language_filename, render_language_page
from v2_sample_summary import public_sample_summary
from v2_signal_calendar import SIGNAL_CALENDAR_CSS, signal_calendar


DAYS_PER_YEAR = 365.2425


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _rate(value: object) -> str:
    return "—" if value is None else f"{float(value):.1%}"


def _annual(value: object) -> str:
    return "—" if value is None else f"{float(value):.1f}"


def calendar_years(signal_dates: tuple[str, ...] | list[str], first: date, last: date) -> list[dict]:
    """Monday-first calendars, using unique signal dates and the actual sample coverage."""
    if last < first:
        raise ValueError("日历样本结束日期早于开始日期。")
    days = sorted({date.fromisoformat(day) for day in signal_dates})
    if any(day < first or day > last for day in days):
        raise ValueError("信号日期不在历史样本覆盖区间内。")
    result = []
    week_calendar = calendar.Calendar(firstweekday=0)
    for year in range(first.year, last.year + 1):
        year_days = [day for day in days if day.year == year]
        coverage_start = max(first, date(year, 1, 1))
        coverage_end = min(last, date(year, 12, 31))
        months = []
        for month in sorted({day.month for day in year_days}):
            month_days = [day for day in year_days if day.month == month]
            months.append({
                "month": month, "count": len(month_days),
                "signal_days": [day.day for day in month_days],
                "weeks": week_calendar.monthdayscalendar(year, month),
            })
        result.append({
            "year": year, "count": len(year_days), "dates": [day.isoformat() for day in year_days],
            "months": months, "coverage_start": coverage_start.isoformat(),
            "coverage_end": coverage_end.isoformat(),
            "partial": coverage_start != date(year, 1, 1) or coverage_end != date(year, 12, 31),
        })
    return result


def presentation_model(eligible: list[dict], details: list[dict], metadata: dict) -> dict:
    """Group equal-rate horizons only when their signal group and dates also match."""
    first = date.fromisoformat(str(metadata["first_date"]))
    last = date.fromisoformat(str(metadata["last_date"]))
    if last < first:
        raise ValueError("历史样本结束日期早于开始日期。")
    years = (last - first).days / DAYS_PER_YEAR
    events_by_plan: dict[tuple, list[dict]] = defaultdict(list)
    for event in details:
        events_by_plan[(str(event["group"]), int(event["horizon"]))].append(event)

    grouped: dict[tuple, dict] = {}
    all_dates: set[str] = set()
    signal_outcomes: dict[str, list[dict]] = defaultdict(list)
    for row in eligible:
        events = sorted(events_by_plan[(str(row["group"]), int(row["horizon"]))],
                        key=lambda event: str(event["signal_date"]))
        dates = tuple(str(event["signal_date"]) for event in events)
        count = int(row["sample_count"])
        wins = int(row["wins"])
        if len(dates) != count or len(set(dates)) != count:
            raise ValueError("方案样本数与独立信号日期不一致。")
        if sum(bool(event["win"]) for event in events) != wins:
            raise ValueError("方案上涨次数与逐次记录不一致。")
        probability = row["win_probability"]
        if count and (probability is None or abs(float(probability) - wins / count) > 1e-12):
            raise ValueError("方案上涨概率与样本数不一致。")
        annual_frequency = count / years if years > 0 else None
        plan = {**row, "dates": dates, "events": events, "annual_frequency": annual_frequency}
        for event in events:
            if not isinstance(event["win"], bool):
                raise ValueError("逐次上涨结果必须是明确的布尔值，不能用文本或缺失值代替。")
            signal_outcomes[str(event["signal_date"])].append({
                "group": str(row["group"]), "horizon": int(row["horizon"]),
                "win": event["win"],
            })
        key = (str(row["group"]), dates, wins, count, probability)
        if key not in grouped:
            grouped[key] = {
                "group": row["group"], "group_label": row["group_label"],
                "wins": wins, "sample_count": count, "win_probability": probability,
                "dates": dates, "annual_frequency": annual_frequency, "plans": [],
            }
        grouped[key]["plans"].append(plan)
        all_dates.update(dates)

    groups = sorted(grouped.values(), key=lambda group: (
        -float(group["win_probability"] if group["win_probability"] is not None else -1),
        str(group["group"]), min(int(plan["horizon"]) for plan in group["plans"]),
    ))
    for group in groups:
        group["plans"].sort(key=lambda plan: int(plan["horizon"]))
    signal_dates = tuple(sorted(all_dates))
    yearly_counts = Counter(day[:4] for day in signal_dates)
    return {
        "metadata": dict(metadata), "years": years, "groups": groups,
        "plan_count": len(eligible), "unique_signal_count": len(all_dates),
        "unique_annual_frequency": len(all_dates) / years if years > 0 else None,
        "signal_dates": signal_dates, "calendar_years": calendar_years(signal_dates, first, last),
        "signal_outcomes": {day: sorted(outcomes, key=lambda outcome: (outcome["horizon"], outcome["group"]))
                            for day, outcomes in signal_outcomes.items()},
        "year_counts": [(year, yearly_counts[str(year)])
                        for year in range(first.year, last.year + 1)],
    }


CSS = """
:root{color-scheme:light;--ink:#172c43;--muted:#607287;--bg:#f3f6f9;--paper:#fff;--line:#dce5ed;--navy:#142c43;--gold:#bd9354;--wash:#f4f7fa;--good:#1b725e;font-family:'Microsoft YaHei','PingFang SC',Arial,sans-serif}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--bg);line-height:1.65}a{color:inherit}button{font:inherit;cursor:pointer}a,button,summary{-webkit-tap-highlight-color:transparent}a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #ba914e;outline-offset:4px;border-radius:6px}
main{max-width:1160px;margin:auto;padding:0 32px 56px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:25px 0}.brand{font-size:15px;font-weight:700;letter-spacing:1px;text-decoration:none;display:flex;gap:11px;align-items:center}.brand-icon{width:27px;height:27px;border-radius:7px;background:var(--navy);position:relative}.brand-icon:after{content:'';position:absolute;width:10px;height:10px;left:8px;top:8px;background:var(--gold);transform:rotate(45deg)}.nav{display:flex;gap:8px;align-items:center;font-size:13px}.nav a{text-decoration:none;padding:7px 12px;border-radius:7px;color:var(--muted)}.nav a.active{background:var(--navy);color:white}.edition{font-size:12px;padding:5px 10px;border:1px solid var(--line);border-radius:6px;color:var(--muted)}
.hero{padding:35px 39px;background:var(--navy);color:#fff;border-radius:18px;position:relative;overflow:hidden}.hero:after{content:'';position:absolute;width:220px;height:220px;border:1px solid #456079;border-radius:50%;right:-65px;top:-75px;pointer-events:none}.eyebrow{font-size:11px;letter-spacing:3px;color:#d7b782;font-weight:700;margin:0 0 13px}.hero h1{margin:0 0 8px;font-size:32px;font-weight:600;letter-spacing:1px;line-height:1.4}.hero p{margin:0;color:#c6d3df;font-size:14px}.hero .range{margin-top:24px;color:#d9e2eb;font-size:12px;letter-spacing:.4px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;margin:20px 0 30px;background:var(--line);border:1px solid var(--line);border-radius:12px;overflow:hidden}.stat{background:var(--paper);padding:18px 24px}.stat-label{font-size:12px;color:var(--muted);margin-bottom:6px}.stat-value{font-size:26px;line-height:1.3;font-weight:600;letter-spacing:-.6px}.stat-value small{font-size:12px;font-weight:400;letter-spacing:0;margin-left:6px}.stat-sub{font-size:11px;color:var(--muted);margin-top:6px}
.section-heading{display:flex;justify-content:space-between;gap:16px;align-items:end;margin:25px 0 15px}.section-heading h2{font-size:21px;margin:0;font-weight:600}.section-heading p{font-size:12px;color:var(--muted);margin:5px 0 0}.actions{display:flex;gap:8px;flex-shrink:0}.actions button{border:1px solid var(--line);border-radius:6px;background:var(--paper);color:var(--muted);font-size:12px;padding:6px 11px}.actions button:hover{border-color:var(--gold);color:var(--ink)}
details>summary{list-style:none;cursor:pointer}details>summary::-webkit-details-marker{display:none}.strategy-group{background:var(--paper);border:1px solid var(--line);border-radius:13px;margin:12px 0;overflow:hidden}.group-summary{display:flex;align-items:center;gap:25px;padding:24px 28px}.probability{font-size:38px;font-weight:600;line-height:1.15;letter-spacing:-1px;width:148px;flex-shrink:0;color:var(--navy)}.probability small{display:block;color:var(--muted);font-size:11px;font-weight:400;letter-spacing:0;margin-top:7px}.group-title{flex:1;min-width:0}.group-title h3{font-size:16px;margin:0 0 6px;font-weight:600}.group-title p{margin:0;font-size:12px;color:var(--muted)}.mini-metrics{display:flex;gap:25px}.mini-metric{white-space:nowrap;font-size:21px;font-weight:600}.mini-metric small{display:block;font-size:11px;color:var(--muted);font-weight:400}.toggle{width:70px;flex-shrink:0;color:var(--muted);font-size:12px;text-align:right}.chevron{display:inline-block;border-right:1.5px solid currentColor;border-bottom:1.5px solid currentColor;width:7px;height:7px;transform:rotate(45deg);margin:0 2px 3px 8px;transition:transform .15s}.strategy-group[open]>.group-summary .chevron,.plan[open]>.plan-summary .chevron{transform:rotate(225deg);margin-bottom:-1px}.open-word{display:none}details[open]>summary .closed-word{display:none}details[open]>summary .open-word{display:inline}.group-body{border-top:1px solid var(--line);padding:22px 28px 25px;background:var(--paper)}.date-heading{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:12px}.date-heading h4{font-size:13px;margin:0;font-weight:600}.date-heading span{color:var(--muted);font-size:11px}.date-chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px}.date-chip{font-variant-numeric:tabular-nums;background:var(--wash);border:1px solid var(--line);border-radius:5px;padding:5px 10px;font-size:12px}
.plan{border:1px solid var(--line);border-radius:8px;margin:9px 0;background:var(--paper);overflow:hidden}.plan-summary{padding:15px 17px;display:flex;align-items:center;gap:16px;font-size:12px}.plan-name{font-size:13px;font-weight:600;flex:1}.plan-probability{color:var(--good);font-size:16px;font-weight:600;width:70px}.plan-frequency{color:var(--muted);min-width:200px;text-align:right}.plan-content{padding:0 17px 17px}.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:6px;scrollbar-width:thin}table{border-collapse:collapse;width:100%;font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap}th{background:var(--wash);color:var(--muted);font-size:11px;font-weight:500;text-align:left;padding:10px}td{border-top:1px solid var(--line);padding:10px}tbody tr:hover{background:var(--wash)}.up{color:var(--good)}.down{color:var(--muted)}.table-note{font-size:11px;color:var(--muted);margin:10px 0 0}.info{color:var(--muted);font-size:12px;border-left:2px solid var(--gold);padding:1px 0 1px 12px;margin:18px 0}
.panel{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:23px 28px;margin-top:24px}.panel h2{font-size:17px;font-weight:600;margin:0 0 14px}.year-grid{display:grid;grid-template-columns:repeat(12,1fr);gap:7px}.year-item{background:var(--wash);border-radius:5px;text-align:center;padding:9px 2px}.year-item span{display:block;color:var(--muted);font-size:10px}.year-item strong{font-size:18px;font-weight:600}.method summary{font-size:13px;font-weight:600;display:flex;justify-content:space-between}.method-content{font-size:12px;color:var(--muted);padding-top:14px;line-height:1.9}.method-content ol{padding-left:18px;margin-top:0}.downloads{display:flex;flex-wrap:wrap;gap:8px;margin-top:15px}.downloads a{border:1px solid var(--line);border-radius:6px;padding:7px 12px;text-decoration:none;font-size:11px}.downloads a:hover{border-color:var(--gold)}footer{display:flex;justify-content:space-between;gap:20px;color:var(--muted);font-size:11px;margin-top:30px;padding-top:17px;border-top:1px solid var(--line)}.empty{padding:35px;text-align:center;color:var(--muted)}
.entrances{display:grid;grid-template-columns:1fr 1fr;gap:19px;margin-top:24px}.entrance{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:28px;position:relative;display:flex;flex-direction:column}.entrance .number{font-size:11px;letter-spacing:2px;color:var(--gold)}.entrance h2{font-size:24px;font-weight:600;margin:15px 0 8px}.entrance p{font-size:13px;color:var(--muted);margin:0 0 19px}.entrance ul{padding:0;list-style:none;font-size:12px;color:var(--muted);margin:0 0 25px}.entrance li{padding:5px 0;border-bottom:1px solid var(--line)}.button{display:inline-block;background:var(--navy);color:white;border-radius:7px;padding:11px 18px;text-decoration:none;font-size:13px;align-self:flex-start;margin-top:auto}.button:hover{background:#234762}.entrance.public-card{background:#182f45;color:#f3f5f8;border-color:#182f45}.public-card p,.public-card ul{color:#c0ccd7}.public-card li{border-color:#354b60}.public-card .button{background:#d3b079;color:#172c43}
body.commercial{--ink:#e6edf4;--muted:#a8b8c8;--bg:#0d1e2e;--paper:#172c40;--line:#30465b;--navy:#e2c494;--wash:#1d3449;--good:#9bcab9;--gold:#d3b079;color-scheme:dark}.commercial .brand-icon{background:#263e54}.commercial .nav a.active{background:#d3b079;color:#142c43}.commercial .hero{background:linear-gradient(115deg,#1b354c,#162b40);border:1px solid var(--line)}.commercial .hero:after{border-color:#486079}.commercial .hero h1{color:#f7f4ee}.commercial .stat-value{color:#e6cca3}.commercial .group-summary{padding-top:26px;padding-bottom:26px}.commercial footer{color:#8da1b5}
@media(max-width:950px){.group-summary{gap:18px;padding:22px}.probability{width:110px;font-size:32px}.mini-metrics{gap:16px}.mini-metric{font-size:18px}.year-grid{grid-template-columns:repeat(6,1fr)}.plan-frequency{min-width:170px}}
@media(max-width:680px){main{padding:0 16px 35px}.topbar{padding:17px 0;flex-wrap:wrap;gap:10px}.brand{font-size:13px}.nav{font-size:11px;gap:2px}.nav a{padding:5px 8px}.edition{display:none}.hero{padding:26px 24px;border-radius:13px}.hero h1{font-size:25px}.hero p{font-size:12px}.hero .range{margin-top:18px;font-size:11px}.stats{grid-template-columns:1fr 1fr;margin:15px 0 24px}.stat{padding:15px 18px}.stat-value{font-size:23px}.stat-label{font-size:11px}.section-heading{align-items:start;flex-wrap:wrap}.section-heading h2{font-size:19px}.group-summary{display:grid;grid-template-columns:90px 1fr;gap:16px;padding:20px}.probability{width:auto;font-size:28px}.group-title h3{font-size:14px}.mini-metrics{grid-column:1/2;display:flex;gap:15px}.mini-metric{font-size:16px}.mini-metric small{font-size:10px}.toggle{grid-column:2/3;width:auto}.group-body{padding:18px 16px}.date-heading{flex-wrap:wrap;gap:3px}.date-chip{font-size:11px;padding:4px 7px}.plan-summary{display:grid;grid-template-columns:1fr 65px 12px;gap:7px;padding:13px}.plan-name{font-size:12px}.plan-frequency{grid-row:2;grid-column:1/4;min-width:0;text-align:left;font-size:11px}.plan-summary>.chevron{grid-column:3;grid-row:1}.plan-probability{font-size:14px;width:auto}.plan-content{padding:0 10px 12px}.panel{padding:20px 16px}.entrances{grid-template-columns:1fr;gap:15px}.entrance{padding:24px}.entrance h2{font-size:22px}.year-grid{gap:5px}footer{flex-direction:column;gap:4px}.commercial .group-summary{padding:20px}}
@media(prefers-reduced-motion:reduce){.chevron{transition:none}}
"""

CSS += """
.signal-calendar [hidden]{display:none!important}.calendar-heading{display:flex;align-items:start;justify-content:space-between;gap:18px;margin-bottom:16px}.calendar-heading h2,.calendar-heading h4{margin:0;font-size:19px;font-weight:600}.calendar-heading p{margin:6px 0 0;font-size:12px;color:var(--muted)}.calendar-total{color:var(--gold);font-size:12px;white-space:nowrap;border:1px solid var(--line);border-radius:20px;padding:5px 12px}.calendar-years{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.calendar-year-card{text-align:left;min-width:0;border:1px solid var(--line);border-radius:9px;background:var(--paper);color:var(--ink);padding:13px 14px;display:flex;flex-direction:column;gap:10px;min-height:118px;transition:border-color .15s,background .15s}.calendar-year-card:hover,.calendar-year-card[aria-expanded="true"]{border-color:var(--gold);background:var(--wash)}.calendar-year-card.no-signals{background:var(--wash)}.calendar-year-top{display:flex;justify-content:space-between;align-items:center;gap:7px}.calendar-year-top strong{font-size:16px;font-weight:600}.calendar-count{font-size:11px;font-weight:600;color:var(--good)}.no-signals .calendar-count{color:var(--muted)}.calendar-date-list{display:flex;flex-wrap:wrap;gap:5px;min-height:25px;align-items:center}.calendar-date-list time{font-size:11px;font-variant-numeric:tabular-nums;padding:3px 6px;border-radius:4px;color:var(--ink);background:var(--wash);border:1px solid var(--line)}.calendar-no-signal{font-size:11px;color:var(--muted)}.calendar-year-bottom{display:flex;justify-content:space-between;gap:6px;margin-top:auto;font-size:10px;color:var(--muted)}.calendar-year-bottom i{font-style:normal;color:var(--gold)}.calendar-hint{font-size:11px;color:var(--muted);margin:13px 0 0}.calendar-year-panel{margin-top:18px;border-top:1px solid var(--line);padding-top:18px}.calendar-panel-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:14px}.calendar-panel-head h3{font-size:17px;font-weight:600;margin:0}.calendar-panel-head p{font-size:11px;color:var(--muted);margin:3px 0 0}.calendar-close{border:1px solid var(--line);border-radius:5px;background:var(--paper);color:var(--muted);font-size:11px;padding:5px 10px;white-space:nowrap}.calendar-months{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:13px}.calendar-month{border:1px solid var(--line);border-radius:9px;padding:15px;background:var(--paper)}.calendar-month-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}.calendar-month-heading h4{font-size:15px;font-weight:600;margin:0}.calendar-month-heading span{font-size:11px;color:var(--muted)}.calendar-weekdays,.calendar-days{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:4px}.calendar-weekdays span{font-size:10px;color:var(--muted);text-align:center;padding-bottom:6px}.calendar-day{aspect-ratio:1/1;display:flex;align-items:center;justify-content:center;min-width:0;border:1px solid transparent;background:none;color:var(--ink);border-radius:6px;font-size:12px;font-variant-numeric:tabular-nums;padding:0}.calendar-day.weekend{color:var(--muted)}.calendar-day.outside{opacity:.3}.signal-day{background:#d9b77e;color:#142c43;font-weight:700;cursor:pointer}.signal-day:hover,.signal-day[aria-pressed="true"]{background:#f1d7a5;border-color:#987137;box-shadow:0 0 0 2px var(--paper),0 0 0 3px var(--gold)}.calendar-event{margin-top:15px;padding:16px 18px;background:var(--wash);border:1px solid var(--line);border-left:3px solid var(--gold);border-radius:7px}.calendar-event h4{font-size:14px;font-weight:600;margin:0 0 5px}.calendar-event p{font-size:11px;color:var(--muted);margin:0 0 9px}.calendar-event-group{display:flex;align-items:center;gap:12px;padding:7px 0;font-size:12px}.calendar-event-rate{font-size:15px;color:var(--good);font-weight:600;min-width:54px}.calendar-empty-year{padding:20px;border-radius:8px;background:var(--wash);font-size:13px;color:var(--muted)}.calendar-compact{margin:0 0 22px}.calendar-compact .calendar-heading h4{font-size:14px}.calendar-compact .calendar-heading p{font-size:11px}.calendar-compact .calendar-year-card{min-height:108px}.commercial .signal-day{background:#d6b680;color:#13283b}
@media(max-width:950px){.calendar-years{grid-template-columns:repeat(3,minmax(0,1fr))}.calendar-months{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:680px){.calendar-years{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.calendar-heading{gap:10px;flex-wrap:wrap}.calendar-heading h2{font-size:18px}.calendar-year-card{padding:12px;min-height:120px}.calendar-year-top strong{font-size:14px}.calendar-year-bottom{font-size:9px}.calendar-months{grid-template-columns:1fr}.calendar-day{font-size:13px}.calendar-month{padding:15px 18px}.calendar-event-group{align-items:start;gap:9px}.calendar-event{padding:14px}.calendar-panel-head h3{font-size:15px}.calendar-date-list time{font-size:10px}}
@media(prefers-reduced-motion:reduce){.calendar-year-card{transition:none}}
"""

CSS += """
.calendar-count{display:inline-flex;align-items:baseline;gap:4px}.calendar-count strong{font-size:31px;font-weight:600;line-height:1}.calendar-count small{font-size:11px;font-weight:400}.calendar-year-card.has-signals{background:#19374f;border-color:#35546e;color:#f0f4f7}.has-signals .calendar-count{color:#f0d298}.has-signals .calendar-date-list time{background:#29495f;color:#f4e9d3;border-color:#638095}.has-signals .calendar-year-bottom{color:#c0ced9}.has-signals .calendar-year-bottom i{color:#e7c582}.calendar-year-card.has-signals:hover,.calendar-year-card.has-signals[aria-expanded="true"]{background:#23465f;border-color:#b48f52}.calendar-year-card.no-signals{background:#f8fafc;border-color:#e5ebf1;color:#607287}.no-signals .calendar-count strong{font-size:23px;font-weight:400}.calendar-year-card.no-signals:hover,.calendar-year-card.no-signals[aria-expanded="true"]{background:#f3f6f9;border-color:#a3b0bf}.audit-details{border-top:1px solid var(--line);padding-top:16px;margin-top:18px}.audit-details>summary{font-size:12px;color:var(--muted);display:flex;justify-content:space-between;align-items:center}.audit-details[open]>summary{margin-bottom:15px}.audit-details[open]>summary .chevron{transform:rotate(225deg)}
@media(max-width:680px){.calendar-count strong{font-size:27px}.no-signals .calendar-count strong{font-size:21px}.calendar-count small{font-size:10px}}
"""

SCRIPT = """<script>
document.querySelectorAll('[data-expand]').forEach(function(button){
  button.addEventListener('click',function(){
    var expand = button.dataset.expand === 'true';
    document.querySelectorAll('#strategies details').forEach(function(item){item.open=expand;});
  });
});
document.querySelectorAll('.signal-calendar:not(.outcome-calendar)').forEach(function(calendar){
  function resetEvents(){
    calendar.querySelectorAll('.calendar-event').forEach(function(event){event.hidden=true;});
    calendar.querySelectorAll('.signal-day').forEach(function(day){day.setAttribute('aria-pressed','false');});
  }
  function closeYears(){
    calendar.querySelectorAll('.calendar-year-panel').forEach(function(panel){panel.hidden=true;});
    calendar.querySelectorAll('.calendar-year-card').forEach(function(card){card.setAttribute('aria-expanded','false');});
    resetEvents();
  }
  calendar.querySelectorAll('.calendar-year-card').forEach(function(card){
    card.addEventListener('click',function(){
      var reopen=card.getAttribute('aria-expanded')!=='true';
      closeYears();
      if(reopen){
        var panel=calendar.querySelector('#'+card.getAttribute('aria-controls'));
        panel.hidden=false;
        card.setAttribute('aria-expanded','true');
        panel.scrollIntoView({block:'nearest'});
      }
    });
  });
  calendar.querySelectorAll('.calendar-close').forEach(function(button){
    button.addEventListener('click',function(){
      var card=calendar.querySelector('.calendar-year-card[aria-expanded="true"]');
      closeYears();
      if(card){card.focus();}
    });
  });
  calendar.querySelectorAll('.signal-day').forEach(function(day){
    day.addEventListener('click',function(){
      resetEvents();
      var event=calendar.querySelector('#'+day.getAttribute('aria-controls'));
      event.hidden=false;
      day.setAttribute('aria-pressed','true');
      event.scrollIntoView({block:'nearest'});
    });
  });
});
</script>"""


def _shell(title: str, body: str, *, commercial: bool = False, active: str = "") -> str:
    def link(name: str, label: str) -> str:
        selected = ' class="active" aria-current="page"' if active == name else ""
        return f'<a href="{name}"{selected}>{label}</a>'

    navigation = link("index.html", "入口") + link("research_dashboard.html", "校内研究") + link("commercial_dashboard.html", "商业化版")
    edition = "商业化版" if commercial else "校内研究版" if active == "research_dashboard.html" else "V2 · 双入口"
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="{'dark' if commercial else 'light'}"><title>{_escape(title)}</title>
<style>{CSS}{SIGNAL_CALENDAR_CSS}</style></head><body class="{'commercial' if commercial else 'research'}"><main>
<nav class="topbar" aria-label="主导航"><a class="brand" href="index.html"><span class="brand-icon" aria-hidden="true"></span>GOLD SIGNAL <span style="color:var(--gold)">V2</span></a>
<div class="nav">{navigation}<span class="edition">{edition}</span></div></nav>
{body}<footer><span>GOLD SIGNAL V2 · 黄金与美国十年期实际利率</span><span>历史样本统计 · 只读展示，不执行交易</span></footer>
</main>{SCRIPT}</body></html>'''


def _stats(model: dict, *, public: bool = False) -> str:
    items = [
        ("达到 ≥70% 的期限方案", str(model["plan_count"]), "种", "按相同胜率与同批日期归类"),
        ("独立历史信号", str(model["unique_signal_count"]), "次", "跨期限、跨展示组去重"),
        ("年均出现", _annual(model["unique_annual_frequency"]), "次 / 年", "次数 ÷ 完整样本跨度"),
        ("历史样本跨度", public_sample_summary(model)["span"] if public else f'{model["years"]:.1f}',
         "" if public else "年", "不是每年固定出现次数"),
    ]
    return '<div class="stats">' + "".join(
        f'<div class="stat"><div class="stat-label">{label}</div><div class="stat-value">{value}<small>{unit}</small></div><div class="stat-sub">{sub}</div></div>'
        for label, value, unit, sub in items
    ) + "</div>"


def _hero(model: dict, title: str, subtitle: str, *, public: bool = False) -> str:
    meta = model["metadata"]
    sample = (public_sample_summary(model)["summary"] if public else
              f"样本：{_escape(meta['first_date'])} — {_escape(meta['last_date'])}　·　{int(meta['row_count']):,} 个交易日")
    return f'''<header class="hero"><div class="eyebrow">GOLD × REAL YIELD / HISTORICAL RESEARCH</div>
<h1>{title}</h1><p>{subtitle}</p><div class="range">{sample}</div></header>'''


def _plan(plan: dict, commercial: bool) -> str:
    columns = ["信号日期", "入场日期", "观察结束日期"]
    if not commercial:
        columns += ["入场开盘价", "退出收盘价", "单次毛收益"]
    columns += ["上涨结果"]
    rows = []
    for event in plan["events"]:
        cells = [_escape(event[name]) for name in ("signal_date", "entry_date", "exit_date")]
        if not commercial:
            cells += [f'{float(event["entry_open"]):,.2f}', f'{float(event["exit_close"]):,.2f}',
                      f'{float(event["gross_return"]):+.2%}']
        result = '<span class="up">上涨</span>' if event["win"] else '<span class="down">未上涨</span>'
        cells.append(result)
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    if not rows:
        rows.append(f'<tr><td colspan="{len(columns)}">暂无完整观察记录</td></tr>')
    return f'''<details class="plan" data-horizon="{int(plan['horizon'])}"><summary class="plan-summary">
<span class="plan-name">第 {int(plan['horizon'])} 个后续交易日</span><span class="plan-probability">{_rate(plan['win_probability'])}</span>
<span class="plan-frequency">历史 {int(plan['sample_count'])} 次　·　年均 {_annual(plan['annual_frequency'])} 次 / 年</span><i class="chevron" aria-hidden="true"></i></summary>
<div class="plan-content"><div class="table-wrap" role="region" aria-label="第 {int(plan['horizon'])} 个交易日的历史日期明细" tabindex="0"><table>
<thead><tr>{''.join(f'<th scope="col">{column}</th>' for column in columns)}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="table-note">上涨 {int(plan['wins'])} / {int(plan['sample_count'])} 次。入场为信号后第一个交易日，观察结束为第 {int(plan['horizon'])} 个后续交易日。</p></div></details>'''


def _groups(model: dict, commercial: bool) -> str:
    cards = []
    for index, group in enumerate(model["groups"], start=1):
        horizons = "、".join(str(int(plan["horizon"])) for plan in group["plans"])
        label = f"方案组 {index:02d}" if commercial else _escape(group["group_label"])
        signal_calendar = _signal_calendar(model, commercial=commercial,
                                           uid=f"group-calendar-{index}", group_index=index)
        cards.append(f'''<details class="strategy-group" data-group="{index}"><summary class="group-summary">
<div class="probability">{_rate(group['win_probability'])}<small>历史上涨概率 · {int(group['wins'])}/{int(group['sample_count'])}</small></div>
<div class="group-title"><h3>{label} · {len(group['plans'])} 种期限</h3><p>第 {horizons} 个后续交易日</p></div>
<div class="mini-metrics"><div class="mini-metric">{int(group['sample_count'])}<small>历史出现 / 次</small></div><div class="mini-metric">{_annual(group['annual_frequency'])}<small>年均 / 次</small></div></div>
<div class="toggle"><span class="closed-word">展开日期</span><span class="open-word">收起明细</span><i class="chevron" aria-hidden="true"></i></div></summary>
<div class="group-body">{signal_calendar}<details class="audit-details"><summary>研究明细 · 按期限核对逐次结果 <i class="chevron" aria-hidden="true"></i></summary>
{''.join(_plan(plan, commercial) for plan in group['plans'])}</details></div></details>''')
    if not cards:
        return '<div class="panel empty">当前没有达到历史上涨概率 ≥70% 的完整样本方案。</div>'
    return "".join(cards)


def _calendar_event(day: str, indexed_groups: list[tuple[int, dict]], uid: str,
                    commercial: bool) -> str:
    matches = [(index, group) for index, group in indexed_groups if day in group["dates"]]
    plan_count = sum(len(group["plans"]) for _, group in matches)
    event_date = date.fromisoformat(day)
    lines = []
    for index, group in matches:
        label = f"方案组 {index:02d}" if commercial else _escape(group["group_label"])
        for plan in group["plans"]:
            event = next(event for event in plan["events"] if str(event["signal_date"]) == day)
            result = "上涨" if event["win"] else "未上涨"
            state = "up" if event["win"] else "down"
            lines.append(f'<div class="calendar-event-group"><strong class="{state}">{result}</strong>'
                         f'<span>{label} · 第 {int(plan["horizon"])} 个后续交易日'
                         f' · 该方案历史上涨比例 {_rate(plan["win_probability"])}</span></div>')
    return f'''<aside class="calendar-event" id="{uid}-event-{day}" data-signal-date="{day}" role="status" hidden>
<h4><time datetime="{day}">{event_date.year} 年 {event_date.month} 月 {event_date.day} 日</time> · 信号出现日期 · {plan_count} 种方案</h4>
<p>同一次信号，各期限结果分别判断；上涨指对应期限收盘价高于信号后首个交易日开盘价，未上涨包括持平。百分比是该方案全样本历史比例，不是当天预测。</p>{''.join(lines)}</aside>'''


def _calendar_month(year: dict, month: dict, uid: str) -> str:
    cells = []
    first = date.fromisoformat(year["coverage_start"])
    last = date.fromisoformat(year["coverage_end"])
    for week in month["weeks"]:
        for weekday, day in enumerate(week):
            if not day:
                cells.append('<span class="calendar-day" aria-hidden="true"></span>')
                continue
            current = date(year["year"], month["month"], day)
            stamp = current.isoformat()
            if day in month["signal_days"]:
                cells.append(f'<button type="button" class="calendar-day signal-day" data-date="{stamp}" '
                             f'aria-label="{year["year"]}年{month["month"]}月{day}日，信号日" '
                             f'aria-controls="{uid}-event-{stamp}" aria-pressed="false">{day}</button>')
            else:
                state = " outside" if current < first or current > last else " weekend" if weekday >= 5 else ""
                cells.append(f'<span class="calendar-day{state}">{day}</span>')
    weekday_names = "".join(f"<span>{day}</span>" for day in "一二三四五六日")
    return f'''<section class="calendar-month" data-month="{year['year']}-{month['month']:02d}" aria-label="{year['year']}年{month['month']}月">
<div class="calendar-month-heading"><h4>{month['month']} 月</h4><span>{month['count']} 次</span></div>
<div class="calendar-weekdays" aria-label="周一至周日">{weekday_names}</div><div class="calendar-days">{''.join(cells)}</div></section>'''


def _signal_calendar(model: dict, *, commercial: bool, uid: str = "signal-calendar",
                     group_index: int | None = None) -> str:
    indexed_groups = [(index, group) for index, group in enumerate(model["groups"], start=1)
                      if group_index is None or index == group_index]
    dates = tuple(sorted({day for _, group in indexed_groups for day in group["dates"]}))
    first = date.fromisoformat(str(model["metadata"]["first_date"]))
    last = date.fromisoformat(str(model["metadata"]["last_date"]))
    years = model["calendar_years"] if dates == model["signal_dates"] else calendar_years(dates, first, last)
    plans = [plan for _, group in indexed_groups for plan in group["plans"]]
    same_dates = bool(plans) and all(tuple(plan["dates"]) == dates for plan in plans)
    explanation = f"这 {len(plans)} 种方案对应同一批 {len(dates)} 次信号，日期只计算一次。" if same_dates else "按独立信号日期去重；点开信号日查看当日对应方案。"
    cards, panels = [], []
    for year in years:
        number = year["year"]
        panel_id = f"{uid}-year-{number}"
        times = "".join(f'<time datetime="{day}">{date.fromisoformat(day).month}月{date.fromisoformat(day).day}日</time>'
                        for day in year["dates"])
        if not times:
            times = '<span class="calendar-no-signal">样本期内无信号</span>'
        coverage = f'{year["coverage_start"][5:].replace("-", "/")}—{year["coverage_end"][5:].replace("-", "/")}'
        bottom = "覆盖 " + coverage if year["partial"] else "全年样本"
        classes = "calendar-year-card" + (" no-signals" if not year["count"] else " has-signals")
        cards.append(f'''<button type="button" class="{classes}" data-calendar-year="{number}" aria-expanded="false" aria-controls="{panel_id}">
<span class="calendar-year-top"><strong>{number} 年</strong><span class="calendar-count"><strong>{year['count']}</strong><small>次信号</small></span></span>
<span class="calendar-date-list">{times}</span><span class="calendar-year-bottom"><span>{bottom}</span><i>查看月历 ↓</i></span></button>''')
        months = "".join(_calendar_month(year, month, uid) for month in year["months"])
        events = "".join(_calendar_event(day, indexed_groups, uid, commercial) for day in year["dates"])
        if months:
            month_body = f'<div class="calendar-months">{months}</div>{events}'
            month_hint = "只展示发生信号的月份；金色日期可点击查看对应方案。"
        else:
            month_body = f'<div class="calendar-empty-year">{number} 年的样本覆盖区间（{coverage}）内没有出现这类信号。</div>'
            month_hint = "0 次表示样本覆盖区间内无信号，不代表未覆盖日期。"
        panels.append(f'''<section class="calendar-year-panel" id="{panel_id}" aria-label="{number}年信号月历" hidden>
<div class="calendar-panel-head"><div><h3>{number} 年 · {year['count']} 次信号</h3><p>{month_hint}</p></div>
<button class="calendar-close" type="button">收起月历</button></div>{month_body}</section>''')
    compact = group_index is not None
    title = f"这组方案的信号出现日期 · {len(dates)} 次" if compact else f"信号出现日期 · {len(dates)} 次"
    heading = "h4" if compact else "h2"
    classes = "signal-calendar calendar-compact" if compact else "panel signal-calendar"
    return f'''<section class="{classes}" id="{uid}" aria-label="{title}"><div class="calendar-heading"><div><{heading}>{title}</{heading}>
<p>次数统计信号出现，不是上涨成功；点击年份及信号日查看各期限的上涨／未上涨结果。</p></div><span class="calendar-total">共 {len(dates)} 次信号</span></div>
<div class="calendar-years">{''.join(cards)}</div><p class="calendar-hint">{explanation}首尾年份仅计入实际覆盖区间。</p>
{''.join(panels)}<noscript><p class="calendar-hint">具体日期已显示在年份卡片中；展开月历需要浏览器启用 JavaScript。</p></noscript></section>'''


def _method(model: dict, download_prefix: str) -> str:
    meta = model["metadata"]
    counts = meta["group_counts"]
    downloads = "".join(f'<a href="{_escape(download_prefix + name)}" download>{label}</a>' for name, label in (
        ("eligible_70_plus.csv", "≥70% 方案 CSV"), ("ranking_20.csv", "20 种完整概率表"),
        ("signal_details.csv", "逐次信号明细"), ("market_data_pine5_raw_recalc.csv", "研究数据 CSV"),
    ))
    return f'''<section class="panel"><details class="method"><summary>研究口径与数据来源 <i class="chevron" aria-hidden="true"></i></summary>
<div class="method-content"><ol>
<li>A+B 候选条件：均使用已完成日线。
<p><strong>一、实际利率五日净上涨</strong><br>当天实际利率 ＞ 五个交易日前的实际利率。只比较两端，不要求每天连续上涨。中间四个交易日的利率可以上涨、下跌、持平，也可以高于当天，不设额外走势限制。两端利率相等时，不满足条件。</p>
<p><strong>二、黄金守住此前收盘低点</strong><br>当天黄金收盘价 ＞ 此前五个交易日中的最低收盘价。此前五个交易日不包含当天；比较的是收盘价，不是盘中最低价。当天收盘价等于该低点时，不满足条件。</p>
<p>“只比较两端”仅用于判断实际利率高于五个交易日前这一条件，不代表整个算法忽略中间数据；五日相关性仍按既定规则计算。入选信号至少间隔五个交易日。</p></li>
<li>黄金收盘价与实际利率的五日原始数值相关系数 ≥ +0.80 为正极端相关，≤ −0.80 为负极端相关。</li>
<li>正负相关各比较第 1–10 个后续交易日。所有期限使用信号后有完整十个交易日的同一批样本；信号后第一个交易日开盘进入，第 N 个后续交易日收盘退出。</li>
<li>退出收盘价高于入场开盘价记为上涨。历史上涨概率 = 上涨次数 ÷ 样本数；年均出现次数 = 独立信号次数 ÷ 样本跨度（天数 / 365.2425）。不是“每年上涨的概率”。</li>
<li>仅当相关类别、信号日期和上涨比例均相同才合并展示。相同概率不表示每次结果相同，逐次结果按各期限保留。</li></ol>
共同 A+B 样本 {int(meta['common_ab_count'])} 次：正极端 {int(counts['positive'])}，负极端 {int(counts['negative'])}，非极端 {int(counts['non_extreme'])}，相关系数不可计算 {int(counts['unavailable'])}。<br>
数据源：2026-10-02 前黄金与利率保留原历史数据，相关系数恢复为 TradingView 原指标导出值；衔接日及之后黄金使用 IBKR XAUUSD MIDPOINT 日线、利率使用 FRED DFII10。相关性取完整 FRED 日历中严格早于黄金日线日期的最近正式观测，再计算五日原始数值；不是把同日两列直接配对，也不是简单移动一行。CSV分别记录利率实际观测日期与相关性配对观测日期。IBKR与原图OANDA黄金来源不同，衔接后的数值不承诺与OANDA图表相同。
<div class="downloads">{downloads}</div></div></details></section>'''


def dashboard_page(model: dict, *, commercial: bool = False, download_prefix: str = "",
                   language: str = "zh") -> str:
    if commercial:
        return render_language_page(commercial_page(model), "commercial_dashboard.html", language)
    title = "黄金与实际利率 · 历史信号研究"
    subtitle = "历史上涨概率 ≥70% 的方案 · 按同批信号与相同胜率归类"
    body = _hero(model, title, subtitle) + _stats(model)
    body += signal_calendar(model)
    body += f'''<section id="strategies" aria-label="可展开的历史方案"><div class="section-heading"><div><h2>历史方案 · {model['plan_count']} 种 / {len(model['groups'])} 组</h2><p>点击方案组查看日历；需要核对时，再展开研究明细。</p></div>
<div class="actions"><button type="button" data-expand="true">展开全部</button><button type="button" data-expand="false">收起全部</button></div></div>'''
    body += _groups(model, False) + "</section>"
    body += '<p class="info">不同期限可能对应同一批历史信号，次数不相加。年均出现次数是历史频率，不是年度上涨概率，也不保证下一年出现同样次数。</p>'
    body += _method(model, download_prefix)
    return render_language_page(
        _shell(title + " | Gold Signal V2", body, active="research_dashboard.html"),
        "research_dashboard.html", language)


def launcher_page(model: dict, *, language: str = "zh") -> str:
    body = _hero(model, "同一份研究，两种清晰入口", "校内研究看完整过程，商业化版看精炼结果。", public=True) + _stats(model, public=True)
    body += '''<div class="entrances"><article class="entrance"><div class="number">01 / RESEARCH</div><h2>校内研究版</h2>
<p>面向课程、研讨与数据复核，保留完整研究口径。</p><ul><li>方案归类 · 历史概率 · 年均频率</li><li>年份日历、信号月日与每个期限的逐次记录</li><li>算法条件、原始价格及研究 CSV 下载</li></ul><a class="button" href="research_dashboard.html">进入校内研究版　→</a></article>
<article class="entrance public-card"><div class="number">02 / COMMERCIAL</div><h2>商业化版</h2>
<p>面向市场读者，以清晰的概率卡片与信号日历呈现研究成果。</p><ul><li>历史表现 · 年均频率 · 方案归类</li><li>年份、次数与具体月日直接显示，无需展开</li><li>提醒服务演示，不呈现研究明细与算法</li></ul><a class="button" href="commercial_dashboard.html">进入商业化版　→</a></article></div>
<p class="info">两个入口使用相同的 V2 统计结果；每次数据更新会同时重建。均为本地展示，不执行交易，也不代表公开部署或访问权限隔离。</p>'''
    return render_language_page(_shell("Gold Signal V2 | 网页入口", body, active="index.html"),
                                "index.html", language)


def write_pages(output_dir: Path, eligible: list[dict], details: list[dict], metadata: dict,
                *, download_prefix: str = "") -> dict:
    model = presentation_model(eligible, details, metadata)
    output_dir.mkdir(parents=True, exist_ok=True)
    for language in ("zh", "en"):
        pages = (
            launcher_page(model, language=language),
            dashboard_page(model, download_prefix=download_prefix, language=language),
            dashboard_page(model, commercial=True, language=language),
        )
        for name, page in zip(PAGE_NAMES, pages):
            (output_dir / language_filename(name, language)).write_text(page, encoding="utf-8")
    return model
