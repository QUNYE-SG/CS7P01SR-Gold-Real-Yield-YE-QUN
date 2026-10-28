"""V1-inspired commercial presentation, with a static signal calendar.

Only renders the existing presentation model. No data updates, orders or enrolment.
"""

from __future__ import annotations

import html
from v2_sample_summary import public_sample_summary
from v2_signal_calendar import SIGNAL_CALENDAR_CSS, signal_calendar


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _annual(value: object) -> str:
    return "—" if value is None else f"{float(value):.1f}"


COMMERCIAL_CSS = """
:root{color-scheme:dark;--ink:#f4f0e8;--muted:#a5b3c0;--gold:#d7b36a;--gold-light:#f1d79c;--line:#2b3b4d;--bg:#09121c;font-family:'Microsoft YaHei','PingFang SC',Arial,sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(ellipse at 82% 0,#20354b 0,transparent 34%),radial-gradient(ellipse at 4% 30%,#152637 0,transparent 32%),var(--bg);color:var(--ink);line-height:1.65}a{color:inherit}button{font:inherit}a:focus-visible,button:focus-visible{outline:3px solid var(--gold);outline-offset:5px;border-radius:6px}main{max-width:1160px;margin:auto;padding:0 32px 44px}
.topbar{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:27px 0}.brand{display:flex;align-items:center;gap:11px;text-decoration:none;font-size:15px;font-weight:700;letter-spacing:1px}.brand-mark{display:grid;place-items:center;width:36px;height:36px;border:1px solid #d7b36a88;border-radius:50%;color:var(--gold-light);font-size:12px}.brand small{color:var(--gold);font-size:12px}.topbar nav{display:flex;gap:22px;font-size:13px;color:#c1ccd6}.topbar nav a{text-decoration:none}.topbar nav a:hover{color:var(--gold-light)}
.hero{display:grid;grid-template-columns:1.35fr .8fr;align-items:center;gap:58px;padding:47px 0 54px}.eyebrow{font-size:11px;letter-spacing:2px;color:var(--gold);font-weight:600}.hero h1{font-size:clamp(37px,4.8vw,58px);line-height:1.22;letter-spacing:-1.5px;margin:18px 0}.hero h1 span{color:var(--gold-light)}.hero p{font-size:15px;color:#bbc7d1;max-width:590px;margin:0;line-height:1.9}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:27px}.button{display:inline-flex;align-items:center;justify-content:center;text-decoration:none;padding:10px 18px;border:1px solid var(--gold);border-radius:7px;background:linear-gradient(130deg,#e6c982,#c9a655);color:#152433;font-weight:600;font-size:13px}.button.ghost{background:transparent;color:#e6edf3;border-color:#526779}.hero-panel{padding:26px;border:1px solid #d7b36a38;border-radius:14px;background:linear-gradient(145deg,#20344ad9,#0d1926);position:relative;overflow:hidden}.hero-panel:after{content:'';position:absolute;right:-50px;top:-65px;width:150px;height:150px;border:1px solid #d7b36a26;border-radius:50%;pointer-events:none}.panel-caption{font-size:11px;color:var(--muted);letter-spacing:1px}.hero-stat{font-size:43px;color:var(--gold-light);font-weight:600;line-height:1.25;margin:13px 0 7px}.hero-stat small{font-size:16px;margin-left:7px;font-weight:400}.hero-range{font-size:11px;color:#a6b7c8}.hero-metrics{display:grid;grid-template-columns:1fr 1fr;gap:15px;border-top:1px solid var(--line);margin-top:24px;padding-top:20px}.hero-metrics strong{display:block;font-size:25px;color:#e9eef3;font-weight:600}.hero-metrics strong small{font-size:11px;font-weight:400;margin-left:5px}.hero-metrics span{color:var(--muted);font-size:11px}
.section{border:1px solid #ffffff13;border-radius:14px;background:#101c29c9;padding:28px;margin-top:20px}.section-head{display:flex;justify-content:space-between;align-items:end;gap:18px;margin-bottom:20px}.section-head h2{font-size:24px;font-weight:600;margin:5px 0 0;line-height:1.45}.section-head p{margin:0;font-size:12px;color:var(--muted)}.result-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.result-card{border:1px solid #d7b36a49;border-radius:11px;background:linear-gradient(135deg,#223349,#152230);padding:25px}.result-card.featured{border-color:#d7b36a94;background:linear-gradient(135deg,#2a394b,#192838)}.result-index{font-size:10px;color:var(--gold);letter-spacing:2px}.result-heading{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-top:14px}.rate{font-size:52px;font-weight:600;line-height:1.1;color:var(--gold-light);letter-spacing:-2px}.rate-label{font-size:11px;color:var(--muted);margin-top:5px}.plan-count{font-size:12px;color:#c9d4de}.horizons{display:flex;gap:7px;flex-wrap:wrap;margin:21px 0 19px}.horizon{font-size:12px;color:#dbe3ea;border:1px solid #526174;border-radius:5px;padding:5px 9px}.meter{height:4px;background:#34485c;border-radius:4px;overflow:hidden}.meter span{height:100%;display:block;background:linear-gradient(90deg,#ad8942,#f1d79c);border-radius:4px}.card-foot{display:flex;justify-content:space-between;gap:10px;font-size:11px;color:var(--muted);margin-top:15px}.card-foot strong{color:#eef2f5;font-weight:600}.section-note{font-size:11px;color:var(--muted);margin:17px 0 0;line-height:1.8}
.calendar-legend{display:flex;align-items:center;gap:7px;color:#b8c7d6;font-size:11px}.calendar-legend:before{content:'';width:8px;height:8px;background:var(--gold);border-radius:2px}.calendar-years{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px}.calendar-year-card{min-width:0;padding:16px;border-radius:9px;border:1px solid #283746;min-height:145px;display:flex;flex-direction:column;gap:13px;background:#0d1824;color:#92a3b3}.calendar-year-card.has-signals{background:linear-gradient(140deg,#294259,#1b3044);border-color:#b99a6266;color:#f0f3f6;box-shadow:inset 0 2px 0 #d7b36a7a}.calendar-year-top{display:flex;align-items:center;justify-content:space-between;gap:10px}.calendar-year-top h3{font-size:16px;font-weight:600;margin:0;white-space:nowrap}.calendar-count{display:flex;align-items:baseline;gap:5px;white-space:nowrap}.calendar-count strong{font-size:34px;color:var(--gold-light);font-weight:600;line-height:1}.calendar-count small{font-size:11px;color:#c1d0dc}.no-signals .calendar-count strong{font-size:25px;color:#91a2b2;font-weight:400}.no-signals .calendar-count small{color:#91a2b2}.calendar-date-list{display:flex;flex-wrap:wrap;gap:6px}.calendar-date-list time{font-size:12px;color:#ecdfc3;font-variant-numeric:tabular-nums;border:1px solid #6a7d8d;border-radius:4px;background:#15283b;padding:3px 6px}.calendar-empty{font-size:11px;color:#92a3b3}.calendar-coverage{margin-top:auto;font-size:10px;color:#b4c3d0}.no-signals .calendar-coverage{color:#92a3b3}
.subscribe{display:grid;grid-template-columns:1.05fr .95fr;gap:38px;align-items:center;background:linear-gradient(120deg,#1a2d40,#101c2a)}.subscribe h2{margin:8px 0 12px;font-size:25px;font-weight:600}.subscribe p{font-size:13px;color:#bac7d3;margin:0;line-height:1.9}.subscribe .promise{margin-top:16px;border-left:2px solid var(--gold);padding-left:12px;color:#d9cba9;font-size:12px}.prototype{padding:21px;border:1px solid #40566b;border-radius:10px;background:#0d1926}.prototype small{display:block;font-size:11px;color:var(--gold)}.prototype h3{font-size:17px;margin:9px 0;font-weight:600}.prototype p{font-size:11px;color:#9eafbf;margin-bottom:15px}.prototype button{cursor:pointer}.prototype .demo-status{margin:12px 0 0;color:#bcd6c9;font-size:11px;min-height:18px}.footer{display:flex;justify-content:space-between;gap:20px;align-items:start;font-size:10px;line-height:1.8;color:#8e9faf;margin-top:26px;border-top:1px solid #263647;padding-top:18px}.footer-links{display:flex;gap:15px;white-space:nowrap}.footer a{text-decoration:none}.local-note{font-size:10px;color:#8e9faf;margin:10px 0 0}.empty{font-size:13px;color:var(--muted);padding:18px}
.result-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.result-card{min-width:0;padding:22px}.rate{font-size:46px}.horizon{font-size:14px}.card-foot{flex-wrap:wrap;row-gap:5px}.plan-count{font-size:11px}
@media(max-width:950px){.hero{gap:30px}.hero h1{font-size:45px}.calendar-years{grid-template-columns:repeat(3,minmax(0,1fr))}.subscribe{gap:22px}.result-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:680px){main{padding:0 16px 30px}.topbar{flex-wrap:wrap;gap:13px;padding:20px 0}.brand{font-size:13px}.topbar nav{font-size:11px;gap:20px}.hero{grid-template-columns:1fr;gap:26px;padding:24px 0 26px}.hero h1{font-size:38px;letter-spacing:-1px}.hero p{font-size:13px}.hero-panel{padding:21px}.hero-stat{font-size:34px}.hero-metrics{margin-top:18px;padding-top:15px}.section{padding:20px 16px}.section-head{align-items:start;flex-wrap:wrap;gap:10px}.section-head h2{font-size:21px}.result-grid{grid-template-columns:1fr;gap:12px}.result-card{padding:20px}.rate{font-size:45px}.horizons{margin:17px 0}.calendar-years{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.calendar-year-card{padding:12px;min-height:142px;gap:13px}.calendar-year-top{gap:5px}.calendar-year-top h3{font-size:13px}.calendar-count strong{font-size:29px}.no-signals .calendar-count strong{font-size:22px}.calendar-count{gap:3px}.calendar-count small{font-size:10px}.calendar-date-list time{font-size:10px;padding:3px 5px}.calendar-coverage{font-size:9px}.subscribe{grid-template-columns:1fr;gap:20px}.footer{flex-direction:column;gap:7px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""

COMMERCIAL_CSS += """
.calendar-list-header{display:flex;justify-content:space-between;gap:8px;padding-bottom:6px;margin-bottom:-8px;border-bottom:1px solid #ffffff20;font-size:10px;line-height:1.6;color:#b8c7d6;letter-spacing:.5px}
.calendar-date-list{display:flex;flex-direction:column;gap:0;list-style:none;margin:0;padding:0}.calendar-signal{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #ffffff12}.calendar-signal:last-child{border-bottom:0}.calendar-date-list time{flex-shrink:0;border:0;background:transparent;padding:0;color:#f0e3c7;font-size:12px}.calendar-outcomes{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:4px;min-width:0;max-width:160px}.calendar-outcome{font-size:10px;line-height:1.6;white-space:nowrap;border-radius:4px;padding:2px 5px;border:1px solid #536478;color:#d1dce5;background:#142739}.calendar-outcome.is-up{color:#b9e3cd;border-color:#59987988;background:#193b33}.calendar-outcome.is-not-up{color:#d1dce5;border-color:#72829388;background:#273b4b}.calendar-result-legend{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 15px;font-size:11px;color:#b8c7d6;align-items:center}.calendar-result-legend .legend-label{margin-right:4px}.calendar-definition{font-size:12px;color:#bac9d6;margin:0 0 17px;line-height:1.8}.calendar-signal-summary{font-size:10px;color:#b4c3d0}.calendar-empty{padding:10px 0}
@media(max-width:680px){.calendar-outcome{font-size:10px;padding:2px 4px}.calendar-signal{align-items:flex-start;gap:5px}.calendar-date-list time{font-size:11px}.calendar-outcomes{max-width:150px}.calendar-definition{font-size:11px}.calendar-year-card{gap:10px}}
@media(max-width:480px){.calendar-years{grid-template-columns:1fr}.calendar-year-card{padding:15px}.calendar-year-top h3{font-size:15px}.calendar-date-list time{font-size:12px}.calendar-outcomes{max-width:180px}.calendar-outcome{font-size:11px}.calendar-signal{align-items:center}}
"""


def _result_cards(model: dict) -> str:
    cards = []
    plans = [(group_index, plan) for group_index, group in enumerate(model["groups"], start=1)
             for plan in group["plans"]]
    for index, (group_index, plan) in enumerate(plans, start=1):
        probability = plan["win_probability"]
        rate = "—" if probability is None else f"{float(probability):.1%}"
        width = 0 if probability is None else max(0, min(100, float(probability) * 100))
        horizon = int(plan["horizon"])
        horizons = f'<span class="horizon" data-horizon="{horizon}">第 {horizon} 个后续交易日</span>'
        featured = " featured" if index == 1 else ""
        cards.append(f'''<article class="result-card{featured}" data-group="{group_index}" data-plan-horizon="{horizon}" aria-label="第{horizon}个后续交易日，历史上涨比例{rate}">
<div class="result-index">OBSERVATION {index:02d}</div><div class="result-heading"><div><div class="rate">{rate}</div>
<div class="rate-label">历史上涨比例</div></div></div>
<div class="horizons" aria-label="信号后的观察期限">{horizons}</div><div class="meter" aria-hidden="true"><span style="width:{width:.4f}%"></span></div>
<div class="card-foot"><span>上涨 <strong>{int(plan['wins'])}</strong> · 未上涨 <strong>{int(plan['sample_count']) - int(plan['wins'])}</strong> / {int(plan['sample_count'])} 次信号</span>
<span>年均信号 <strong>{_annual(plan['annual_frequency'])}</strong> 次 / 年</span></div></article>''')
    return "".join(cards) if cards else '<p class="empty">当前没有达到历史上涨比例 ≥70% 的完整样本方案。</p>'


def commercial_page(model: dict) -> str:
    """No research tables, hidden event payload, dropdowns or active subscriber collection."""
    sample = public_sample_summary(model)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>黄金信号 V2 | 商业化版</title><style>{COMMERCIAL_CSS}{SIGNAL_CALENDAR_CSS}</style></head><body><main>
<header class="topbar"><a class="brand" href="index.html"><span class="brand-mark" aria-hidden="true">GS</span>黄金信号研究 <small>V2</small></a>
<nav aria-label="商业化页面导航"><a href="#performance">历史表现</a><a href="#signal-calendar">信号日历</a><a href="#subscribe">提醒服务</a></nav></header>
<section class="hero"><div><div class="eyebrow">GOLD × REAL YIELD / 信号观察</div><h1>让黄金信号，<br><span>一眼看清。</span></h1>
<p>从黄金与实际利率的历史关系中，观察值得关注的时刻。精选历史上涨比例 ≥70% 的期限方案，让表现与发生日期清晰呈现。</p>
<div class="hero-actions"><a class="button" href="#performance">查看历史表现　→</a><a class="button ghost" href="#signal-calendar">查看信号日历</a></div></div>
<aside class="hero-panel" aria-label="历史研究样本"><div class="panel-caption">RESEARCH COVERAGE / 历史样本</div>
<div class="hero-stat">{sample['span']}</div><div class="hero-range">{sample['size']}</div>
<div class="hero-metrics"><div><strong>{model['plan_count']}<small>种</small></strong><span>观察期限方案</span></div>
<div><strong>{model['unique_signal_count']}<small>次</small></strong><span>独立历史信号</span></div></div></aside></section>
<section class="section" id="performance" aria-labelledby="performance-title"><div class="section-head"><div><div class="eyebrow">HISTORICAL PERFORMANCE / 历史表现</div>
<h2 id="performance-title">{model['plan_count']} 种方案，逐项看清。</h2></div><p>独立信号年均出现 {_annual(model['unique_annual_frequency'])} 次 / 年</p></div>
<div class="result-grid">{_result_cards(model)}</div><p class="section-note">每张卡片对应一个观察期限。同组期限共用同一批历史信号，次数不相加；日历按信号日期去重。历史上涨比例不是未来预测，年均次数也不是每年固定次数。</p></section>
{signal_calendar(model)}
<section class="section subscribe" id="subscribe" aria-labelledby="subscribe-title"><div><div class="eyebrow">SIGNAL ALERTS / 提醒服务</div>
<h2 id="subscribe-title">有信号时提醒，<br>没有信号时不打扰。</h2><p>提醒服务围绕研究定义的信号展开，帮助关注黄金市场的读者持续观察。研究信息不替代独立判断，也不执行交易。</p>
<div class="promise">正式开放前，将说明提醒方式、频率、隐私处理和取消方法，并由订阅者主动确认。</div></div>
<div class="prototype"><small>订阅登记 · 本地演示原型</small><h3>信号提醒服务筹备中</h3><p>目前尚未接入客户登记与通知服务。本页不收集联系方式，不保存或发送订阅信息。</p>
<button class="button" type="button" id="subscribe-demo">查看订阅演示</button><p class="demo-status" id="subscribe-status" role="status" aria-live="polite"></p></div></section>
<footer class="footer"><span>GOLD SIGNAL V2 · 商业化展示原型</span><span>历史统计不代表未来结果；小样本结果存在不确定性。</span>
<nav class="footer-links" aria-label="版本入口"><a href="index.html">返回入口</a><a href="research_dashboard.html">研究版</a><a href="commercial_dashboard.html" aria-current="page">商业化版</a></nav></footer>
<p class="local-note">两个本地入口用于展示区分，不构成访问权限隔离；本页尚未公开部署。</p></main>
<script>document.getElementById('subscribe-demo').addEventListener('click',function(){{document.getElementById('subscribe-status').textContent='这是本地演示，尚未开通正式订阅；没有保存或发送任何信息。';}});</script>
</body></html>'''
