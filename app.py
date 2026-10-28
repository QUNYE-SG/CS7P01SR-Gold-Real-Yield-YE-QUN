"""Build a self-contained, local HTML research dashboard from the daily CSV."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from analysis import analyze, load_data
from alerting import dispatch_once, latest_completed_signal, load_local_env


PAGE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>黄金与美国十年期实际利率信号研究</title>
<style>
:root{--navy:#193b62;--blue:#2877b7;--ink:#1f2937;--muted:#64748b;--line:#d8e1eb;--pale:#f1f6fb;--green:#12805c;--red:#b54747}
*{box-sizing:border-box}body{margin:0;background:#f5f7fa;color:var(--ink);font:16px/1.6 "Microsoft YaHei",Arial,sans-serif}
main{max-width:1200px;margin:32px auto;padding:0 22px}h1{margin:0;color:var(--navy);font-size:30px}h2{color:var(--navy);font-size:21px;margin:0 0 14px}h3{margin:0 0 8px;color:var(--navy)}
.subtitle{color:var(--muted);margin:5px 0 26px}.panel{background:white;border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:16px 0;box-shadow:0 2px 8px #16324f0a}
.defs{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 24px}.def{padding:8px 0;border-bottom:1px solid #edf1f5}.tag{font-weight:700;color:var(--blue)}
.meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.metric{background:var(--pale);padding:14px;border-radius:9px}.metric small{display:block;color:var(--muted)}.metric strong{font-size:19px;color:var(--navy)}
.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:760px}th{background:var(--navy);color:white;text-align:left;padding:11px 12px;font-weight:650}td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}tbody tr:nth-child(even){background:#f8fafc}.num{text-align:right;white-space:nowrap}.good{color:var(--green);font-weight:700}.bad{color:var(--red);font-weight:700}.note{color:var(--muted);font-size:14px}
.rankings{display:grid;grid-template-columns:1fr 1fr;gap:16px}.badge{display:inline-block;border-radius:999px;background:#e8f1fa;color:var(--navy);padding:2px 9px;font-size:13px}.filters{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:8px 0 14px}select{padding:8px 10px;border:1px solid var(--line);border-radius:7px;background:white;font:inherit}.footer{color:var(--muted);font-size:13px;margin:20px 0 40px}
.rankings{grid-template-columns:repeat(2,minmax(0,1fr))}.rankings>div{min-width:0}.table-wrap{max-width:100%;overflow-x:auto}
.strategy-list{display:grid;gap:10px}.strategy-item{border:1px solid var(--line);border-radius:9px;overflow:hidden}.strategy-item[open]{border-color:#b7cce0}.strategy-item summary{display:grid;grid-template-columns:42px minmax(200px,1.2fr) repeat(3,minmax(100px,.65fr));align-items:center;gap:12px;padding:13px 15px;cursor:pointer;list-style:none;background:#f8fafc}.strategy-item summary::-webkit-details-marker{display:none}.strategy-item summary::after{content:'展开 ＋';color:var(--blue);font-weight:650;text-align:right}.strategy-item[open] summary::after{content:'收起 −'}.strategy-index{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#e8f1fa;color:var(--navy);font-weight:700}.strategy-title{font-weight:700;color:var(--navy)}.strategy-metric small{display:block;color:var(--muted);font-size:12px}.strategy-metric strong{white-space:nowrap}.strategy-events{padding:8px 14px 14px}.strategy-events .note{margin:4px 0 10px}.signup-intro{max-width:760px;color:var(--muted);margin:0 0 16px}.signup-form{display:grid;grid-template-columns:1.3fr 1fr;gap:14px;max-width:780px}.signup-field{display:grid;gap:5px}.signup-field label{font-weight:650;color:var(--navy)}.signup-field input,.signup-field select{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:7px;background:#fff;font:inherit}.signup-consent{grid-column:1/-1;display:flex;align-items:flex-start;gap:9px;font-size:14px}.signup-consent input{margin-top:6px}.signup-form button{justify-self:start;padding:10px 18px;border:0;border-radius:7px;background:var(--navy);color:#fff;font:inherit;font-weight:650;cursor:pointer}.signup-form button:hover{background:#245383}.signup-status{grid-column:1/-1;min-height:24px;color:var(--green);font-size:14px}.prototype-note{padding:10px 12px;border-radius:7px;background:#fff8e6;color:#755b16;font-size:13px}
@media(max-width:760px){main{margin:18px auto;padding:0 12px}h1{font-size:24px}.defs,.rankings{grid-template-columns:1fr}.meta{grid-template-columns:repeat(2,minmax(0,1fr))}.panel{padding:16px}}
@media(max-width:760px){.strategy-item summary{grid-template-columns:34px 1fr;gap:8px}.strategy-metric{grid-column:2}.strategy-item summary::after{grid-column:2}.signup-form{grid-template-columns:1fr}.signup-consent,.signup-status{grid-column:1}}
/* School edition: polished editorial report styling. */
body{background:radial-gradient(ellipse at 88% 0%,#eaf1fa 0,transparent 34%),#f5f7fa;color:#17283c;font-family:"Microsoft YaHei",Arial,sans-serif}
main{max-width:1160px;margin:34px auto;padding:0 26px}.hero{position:relative;overflow:hidden;padding:38px 42px 28px;border-radius:18px;background:linear-gradient(120deg,#102943,#1d4262 68%,#285a78);color:#fff;box-shadow:0 14px 34px #193b6226}
.hero:after{content:"";position:absolute;right:-55px;top:-150px;width:420px;height:420px;border:1px solid #ffffff20;border-radius:50%;box-shadow:0 0 0 42px #ffffff08,0 0 0 86px #ffffff06;pointer-events:none}.eyebrow{font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#dcb96e;font-weight:700}.hero h1{position:relative;z-index:1;margin:12px 0 7px;color:white;font-size:34px;line-height:1.3}.hero .subtitle{position:relative;z-index:1;margin:0;color:#d5e1ec;font-size:15px}.hero-nav{position:relative;z-index:1;display:flex;gap:9px;flex-wrap:wrap;margin-top:24px}.hero-nav a{padding:6px 11px;border:1px solid #ffffff3d;border-radius:999px;color:#eef5fb;text-decoration:none;font-size:13px}.hero-nav a:hover{background:#ffffff17}
.panel{padding:23px 26px;margin:18px 0;border-radius:14px;box-shadow:0 5px 18px #1834520b}.panel h2{display:flex;align-items:center;gap:10px;margin-bottom:16px;font-size:20px}.panel h2:before{content:"";width:4px;height:21px;border-radius:4px;background:#c7a65b}.strategy-item summary{background:linear-gradient(100deg,#f5f8fb,#fbfcfe)}.strategy-item[open] summary{background:#edf4fa}.strategy-index{background:#193b62;color:#fff}.strategy-events{background:#fff}.metric{border:1px solid #e9eff5}.note{line-height:1.7}.footer{padding:10px 2px;border-top:1px solid var(--line)}
.stability-table td:not(:first-child){min-width:150px}.stability-cell strong{display:block;color:var(--navy)}.stability-cell small{color:var(--muted)}
</style>
</head>
<body><main>
<header class="hero"><div class="eyebrow">研究报告 · 校内评审版</div><h1>黄金与美国十年期实际利率<br>信号研究</h1><p class="subtitle">全样本历史统计、逐次记录与分段稳定性比较</p><nav class="hero-nav"><a href="#conditions">01 条件与口径</a><a href="#scope">02 数据范围</a><a href="#results">03 全样本结果</a><a href="#stability">04 分段比较</a></nav></header>

<section id="conditions" class="panel"><h2>一、条件与统计口径</h2>
<div class="defs">
<div class="def"><span class="tag">A：</span>信号日美国十年期实际利率，高于五个交易日前。</div>
<div class="def"><span class="tag">B：</span>信号日黄金收盘价，高于此前五个交易日中的最低收盘价。</div>
<div class="def"><span class="tag">C：正极端相关：</span>信号日五日相关系数 ≥ +0.80。</div>
<div class="def"><span class="tag">D：负极端相关：</span>信号日五日相关系数 ≤ −0.80。</div>
<div class="def"><span class="tag">信号去重：</span>按日期顺序保留信号，两个入选信号至少相隔五个交易日。</div>
<div class="def"><span class="tag">成功与毛收益：</span>下一交易日开盘买入，在指定观察日收盘退出；毛收益大于零记为上涨。</div>
</div>
<p class="note">相关系数读取数据文件中的日线字段。四种期限统一使用具有完整十个后续交易日的共同样本。毛收益不扣交易费用。</p>
</section>

<section id="scope" class="panel"><h2>二、研究数据范围与分段日期</h2><div id="meta" class="meta"></div></section>
<section id="results" class="panel"><h2>三、四种研究对象的全样本结果</h2><p class="note">点击每项可展开查看该组合的逐次信号、入场与退出数据。</p><div id="summary" class="strategy-list"></div></section>
<section id="stability" class="panel"><h2>四、分段稳定性比较</h2><p class="note">按全样本、前半段、后半段和最近五年分别呈现上涨比例与平均毛收益；分段用于观察结果随时期的变化。</p><div id="stability-table" class="table-wrap"></div></section>
<p class="footer">本页面由本地程序根据随附日线 CSV 生成。结果可通过同一计算程序和原始数据复算。</p>
</main>
<script id="research-data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('research-data').textContent);
const pct=x=>x==null?'—':(x*100).toFixed(1)+'%';
const ret=x=>x==null?'—':(x>=0?'+':'')+(x*100).toFixed(2)+'%';
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function table(headers,rows){return '<table><thead><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('')+'</tbody></table>'}
const m=D.data;
document.getElementById('meta').innerHTML=[['原始数据范围',m.first_date+' 至 '+m.last_date+'（'+m.row_count+' 行）'],['第5个交易日主样本',m.d5_signal_start+' 至 '+m.d5_signal_end+'（A+B '+m.d5_ab_count+' 个）'],['第1至第10个交易日共同样本',m.common_signal_start+' 至 '+m.common_signal_end+'（A+B '+m.common_ab_count+' 个）'],['共同样本相关分组','正极端 '+m.positive_count+' 个；负极端 '+m.negative_count+' 个；非极端 '+m.non_extreme_count+' 个；无法计算 '+m.correlation_unavailable_count+' 个'],...Object.entries(m.period_ranges).filter(([k])=>k!=='全样本')].map(([a,b])=>'<div class="metric"><small>'+esc(a)+'</small><strong>'+esc(b)+'</strong></div>').join('');
const summary=document.getElementById('summary');
summary.innerHTML=D.strategies.map((s,i)=>{const events=D.details.filter(x=>x.group===s.group&&x.horizon===s.horizon);const rows=events.map(e=>[
 esc(e.signal_date),Number(e.correlation).toFixed(3),esc(e.entry_date)+'<br>'+Number(e.entry_open).toFixed(3),esc(e.exit_date)+'<br>'+Number(e.exit_close).toFixed(3),ret(e.gross_return),e.success?'<span class="good">上涨</span>':'<span class="bad">未上涨</span>'
 ]);return '<details class="strategy-item"><summary><span class="strategy-index">'+(i+1)+'</span><span class="strategy-title">'+esc(s.label)+'｜信号后第'+s.horizon+'个交易日</span><span class="strategy-metric"><small>上涨数 / 样本数</small><strong>'+s.full.wins+' / '+s.full.n+'</strong></span><span class="strategy-metric"><small>上涨概率</small><strong>'+pct(s.full.win_rate)+'</strong></span><span class="strategy-metric"><small>平均毛收益</small><strong>'+ret(s.full.mean_gross_return)+'</strong></span></summary><div class="strategy-events"><p class="note">逐次记录：信号日相关系数、下一交易日开盘入场、指定观察日收盘退出；毛收益为未扣费用的价格变动比例。</p>'+table(['信号日','相关系数','入场日 / 开盘价','退出日 / 收盘价','毛收益','结果'],rows)+'</div></details>'}).join('');
const periods=['全样本','前半段','后半段','最近五年'];
document.getElementById('stability-table').innerHTML='<table class="stability-table"><thead><tr>'+['研究对象与期限',...periods].map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+D.strategies.map(s=>'<tr><td><strong>'+esc(s.label)+'</strong><br><span class="note">信号后第'+s.horizon+'个交易日</span></td>'+periods.map(p=>{const v=s.periods[p];return '<td><div class="stability-cell"><strong>'+v.wins+'/'+v.n+'（'+pct(v.win_rate)+'）</strong><small>平均毛收益 '+ret(v.mean_gross_return)+'</small></div></td>'}).join('')+'</tr>').join('')+'</tbody></table>';
</script></body></html>'''


COMMERCIAL_PAGE = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>黄金信号提醒｜研究展示</title><style>
:root{--ink:#f5f0e7;--muted:#b0b7c0;--gold:#d7b36a;--gold2:#f1d79c;--panel:#141f2c;--line:#2a3949;--green:#83d6ad;--bg:#09121c}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:radial-gradient(ellipse at 78% 4%,#203248 0,transparent 30%),radial-gradient(ellipse at 8% 28%,#1a2838 0,transparent 28%),var(--bg);color:var(--ink);font:16px/1.65 "Microsoft YaHei",Arial,sans-serif}
a{color:inherit}main{max-width:1120px;margin:auto;padding:28px 24px 56px}.topbar{display:flex;align-items:center;justify-content:space-between;padding:8px 0 28px}.brand{display:flex;align-items:center;gap:11px;font-weight:700;letter-spacing:.04em}.brand-mark{display:grid;place-items:center;width:38px;height:38px;border:1px solid #d7b36a88;border-radius:50%;color:var(--gold2);font-size:13px}.topbar nav{display:flex;gap:22px;color:#cbd2da;font-size:14px}.topbar nav a{text-decoration:none}.topbar nav a:hover{color:var(--gold2)}
.hero{display:grid;grid-template-columns:1.4fr .8fr;gap:50px;align-items:center;padding:54px 0 66px}.eyebrow{display:inline-flex;align-items:center;gap:8px;color:var(--gold2);font-size:12px;font-weight:700;letter-spacing:.15em}.eyebrow:before{content:"";width:23px;height:1px;background:var(--gold)}.hero h1{max-width:720px;margin:18px 0 14px;font-size:clamp(38px,5.4vw,64px);line-height:1.16;letter-spacing:-.035em}.hero h1 span{color:var(--gold2)}.hero p{max-width:590px;margin:0;color:#c0c9d2;font-size:17px}.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:27px}.button{display:inline-flex;align-items:center;justify-content:center;padding:11px 18px;border:1px solid #d7b36a;border-radius:7px;background:linear-gradient(135deg,#e4c77e,#c7a252);color:#14202b;text-decoration:none;font-weight:750}.button.ghost{background:transparent;color:#f5f0e7;border-color:#607184}.hero-panel{position:relative;padding:24px;border:1px solid #ffffff14;border-radius:14px;background:linear-gradient(145deg,#172534df,#0c1723e8);box-shadow:0 22px 70px #0005}.hero-panel:before{content:"";position:absolute;inset:0;border-radius:inherit;background:linear-gradient(135deg,#e4c77e13,transparent 45%);pointer-events:none}.panel-caption{color:var(--muted);font-size:12px;letter-spacing:.09em}.hero-stat{margin:8px 0 14px;color:var(--gold2);font-size:31px;font-weight:750}.spark{display:flex;align-items:end;gap:7px;height:76px;padding-top:9px;border-bottom:1px solid #607184}.spark i{display:block;flex:1;border-radius:4px 4px 0 0;background:linear-gradient(180deg,#e3c371,#a17d39);opacity:.85}.spark-note{display:flex;justify-content:space-between;margin-top:8px;color:#98a5b2;font-size:11px}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:20px;margin:0 0 18px}.section-head h2{margin:0;font-size:27px;letter-spacing:-.02em}.section-head p{margin:0;color:var(--muted);font-size:13px}.results{padding:30px;border:1px solid #ffffff14;border-radius:14px;background:#101b27d9;box-shadow:0 18px 60px #0003}.result-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.result-card{padding:18px 16px 16px;border:1px solid var(--line);border-radius:10px;background:linear-gradient(155deg,#192736,#111b27)}.result-card.featured{border-color:#d7b36a88;background:linear-gradient(155deg,#243043,#151e29)}.result-index{color:var(--gold);font-size:11px;font-weight:750;letter-spacing:.12em}.result-card h3{margin:9px 0 2px;font-size:15px;color:#e8edf1}.horizon{color:#aab4bf;font-size:13px}.rate{margin:16px 0 1px;color:var(--gold2);font-size:39px;line-height:1.1;font-weight:780;letter-spacing:-.04em}.rate-label{color:#abb6c0;font-size:12px}.meter{height:5px;margin:13px 0 13px;border-radius:99px;background:#304153;overflow:hidden}.meter i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#b18b42,#f1d79c)}.card-foot{display:flex;justify-content:space-between;gap:6px;padding-top:12px;border-top:1px solid #ffffff12;color:#c5ccd3;font-size:12px}.card-foot strong{color:#fff}.section-note{margin:15px 0 0;color:#97a4b2;font-size:12px;line-height:1.7}
.subscribe{display:grid;grid-template-columns:.85fr 1.15fr;gap:38px;margin-top:22px;padding:31px;border:1px solid #ffffff14;border-radius:14px;background:linear-gradient(110deg,#182737,#101a25)}.subscribe h2{margin:0 0 9px;font-size:25px}.subscribe-copy{color:#b7c2cc;font-size:14px}.subscribe-copy p{margin:0 0 11px}.promise{padding-left:13px;border-left:2px solid var(--gold);color:#e6d6b2;font-size:13px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.field{display:grid;gap:5px}.field label{font-size:13px;color:#d7dfe7}.field input,.field select{width:100%;padding:11px 12px;border:1px solid #3a4a5b;border-radius:6px;background:#0b141e;color:#fff;font:inherit}.field input::placeholder{color:#778492}.consent{grid-column:1/-1;display:flex;align-items:start;gap:9px;color:#c5cdd5;font-size:12px;line-height:1.6}.consent input{margin-top:5px;accent-color:#d7b36a}.form-grid button{justify-self:start;padding:10px 17px;border:0;border-radius:6px;background:var(--gold);color:#14202b;font:inherit;font-weight:750;cursor:pointer}.status{grid-column:1/-1;min-height:22px;color:var(--green);font-size:13px}.privacy{grid-column:1/-1;color:#8492a0;font-size:11px;line-height:1.6}.footer{display:flex;justify-content:space-between;gap:16px;margin-top:24px;padding-top:17px;border-top:1px solid #ffffff18;color:#7f8c99;font-size:11px}
@media(max-width:850px){.hero{grid-template-columns:1fr;gap:28px;padding:32px 0 42px}.hero-panel{max-width:460px}.result-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.subscribe{grid-template-columns:1fr;gap:20px}}
@media(max-width:560px){main{padding:18px 15px 38px}.topbar{align-items:start}.topbar nav{gap:12px;font-size:12px}.hero h1{font-size:39px}.results,.subscribe{padding:19px}.section-head{align-items:start;flex-direction:column}.result-grid{grid-template-columns:1fr 1fr;gap:8px}.result-card{padding:14px 12px}.rate{font-size:32px}.card-foot{font-size:11px}.form-grid{grid-template-columns:1fr}.consent,.privacy,.status{grid-column:1}.footer{flex-direction:column}}
</style></head><body><main>
<header class="topbar"><div class="brand"><span class="brand-mark">GS</span><span>黄金信号研究</span></div><nav><a href="#performance">历史表现</a><a href="#subscribe">订阅提醒</a></nav></header>
<section class="hero"><div><div class="eyebrow">市场观察 · 信号提醒</div><h1>把研究成果，<br><span>变成及时提醒。</span></h1><p>一套基于黄金与实际利率历史关系的信号观察服务。查看历史样本表现，并自愿登记你希望接收提醒的方式。</p><div class="hero-actions"><a class="button" href="#performance">查看历史表现</a><a class="button ghost" href="#subscribe">申请信号提醒</a></div></div><aside class="hero-panel"><div class="panel-caption">研究覆盖 · 历史样本</div><div class="hero-stat">十余年</div><div class="spark" aria-label="装饰性数据波形"><i style="height:31%"></i><i style="height:43%"></i><i style="height:37%"></i><i style="height:57%"></i><i style="height:49%"></i><i style="height:67%"></i><i style="height:55%"></i><i style="height:78%"></i><i style="height:64%"></i><i style="height:87%"></i><i style="height:72%"></i><i style="height:95%"></i></div><div class="spark-note"><span>历史研究样本</span><span>非实时行情图</span></div></aside></section>
<section id="performance" class="results"><div class="section-head"><div><div class="eyebrow">历史样本统计</div><h2>四个观察方案</h2></div><p>以历史样本呈现概率与平均毛收益</p></div><div id="result-grid" class="result-grid"></div><p class="section-note" id="period-note"></p></section>
<section id="subscribe" class="subscribe"><div class="subscribe-copy"><div class="eyebrow">自愿订阅</div><h2>有信号时，及时收到提醒。</h2><p>留下偏好的联系方式，仅用于发送你主动申请的研究信号报警，不用于广告或其他用途。登记与否不影响浏览本页。</p><div class="promise">正式启用前会明确告知信息处理方、用途、收集内容、保存期限、发送方式与频率、取消和删除方法，并请你再次确认。</div></div><div><div class="panel-caption" style="margin-bottom:10px">订阅登记 · 本地演示原型</div><form id="signup-form" class="form-grid" autocomplete="off"><div class="field"><label for="contact-value">联系方式</label><input id="contact-value" type="text" placeholder="演示版请勿填写真实信息" required></div><div class="field"><label for="contact-channel">偏好的提醒方式</label><select id="contact-channel"><option value="email">电子邮件</option><option value="wechat">企业微信</option><option value="sms">手机短信</option></select></div><label class="consent"><input id="signup-consent" type="checkbox" required><span>我自愿申请接收本研究定义的信号报警，并同意联系方式仅用于此报警服务。</span></label><button type="submit">申请订阅提醒</button><div id="signup-status" class="status" role="status" aria-live="polite"></div><div class="privacy">演示版尚未连接后台或通知服务，不会提交、保存或发送填写内容，请勿输入真实联系方式。点击按钮仅显示演示提示。</div></form></div></section>
<footer class="footer"><span>黄金信号研究 · 商业展示原型</span><span id="result-period"></span><span>历史统计不代表未来结果；平均毛收益未扣交易费用。</span></footer>
</main><script id="public-data" type="application/json">__DATA__</script><script>
const P=JSON.parse(document.getElementById('public-data').textContent);const percent=x=>(x*100).toFixed(1)+'%';const money=x=>(x>=0?'+':'')+(x*100).toFixed(2)+'%';
document.getElementById('result-grid').innerHTML=P.strategies.map((s,i)=>'<article class="result-card '+(i===0?'featured':'')+'"><div class="result-index">OBSERVATION '+String(i+1).padStart(2,'0')+'</div><h3>信号观察方案 '+(i+1)+'</h3><div class="horizon">信号后第 '+s.horizon+' 个交易日</div><div class="rate">'+percent(s.win_rate)+'</div><div class="rate-label">历史上涨比例</div><div class="meter"><i style="width:'+Math.max(0,Math.min(100,s.win_rate*100))+'%"></i></div><div class="card-foot"><span>上涨 <strong>'+s.wins+'/'+s.n+'</strong></span><span>平均毛收益 <strong>'+money(s.mean_gross_return)+'</strong></span></div></article>').join('');
document.getElementById('period-note').textContent='样本覆盖 '+P.years_label+'。各方案以“上涨次数 / 有效样本数”计算历史上涨比例；平均毛收益未扣交易费用。此商业展示页不展开具体筛选条件、逐次信号记录或原始行情。';document.getElementById('result-period').textContent='历史样本：'+P.years_label;
document.getElementById('signup-form').addEventListener('submit',event=>{event.preventDefault();document.getElementById('signup-status').textContent='本地演示版未连接登记服务：没有保存或发送任何信息。';event.currentTarget.reset()});
</script></body></html>'''


def write_dashboard(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    output.write_text(PAGE.replace("__DATA__", data), encoding="utf-8")


def public_summary(payload: dict[str, object]) -> dict[str, object]:
    """Keep only aggregate metrics in the public-facing HTML payload."""
    raw_data = payload["data"]
    first = dt.date.fromisoformat(raw_data["first_date"])
    last = dt.date.fromisoformat(raw_data["last_date"])
    years = round((last - first).days / 365.25)
    strategies = []
    for item in payload["strategies"]:
        full = item["full"]
        strategies.append(
            {
                "horizon": item["horizon"],
                "wins": full["wins"],
                "n": full["n"],
                "win_rate": full["win_rate"],
                "mean_gross_return": full["mean_gross_return"],
            }
        )
    return {"years_label": f"约{years}年历史样本", "strategies": strategies}


def write_commercial_dashboard(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(public_summary(payload), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    output.write_text(COMMERCIAL_PAGE.replace("__DATA__", data), encoding="utf-8")


def write_launch_page(school_output: Path, commercial_output: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    school_name = json.dumps(school_output.name, ensure_ascii=False)
    commercial_name = json.dumps(commercial_output.name, ensure_ascii=False)
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>黄金信号研究｜选择页面</title><style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;background:radial-gradient(ellipse at 80% 0,#e8eef6,transparent 35%),#f3f6f9;color:#17314c;font:16px/1.6 "Microsoft YaHei",Arial,sans-serif}}main{{width:min(920px,100%)}}.eyebrow{{color:#aa8846;letter-spacing:.16em;font-size:12px;font-weight:700}}h1{{margin:8px 0 5px;font-size:34px}}p{{color:#657588}}.cards{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:27px}}a{{display:block;padding:24px;border:1px solid #d9e2eb;border-radius:14px;background:#fff;box-shadow:0 9px 25px #1a3c5b0c;color:inherit;text-decoration:none;transition:transform .2s,box-shadow .2s}}a:hover{{transform:translateY(-3px);box-shadow:0 14px 32px #1a3c5b18}}.tag{{color:#b09251;font-size:12px;font-weight:700}}h2{{margin:8px 0;font-size:22px}}.desc{{font-size:14px;color:#68798a}}.go{{display:inline-block;margin-top:12px;color:#24567f;font-weight:700}}@media(max-width:620px){{h1{{font-size:27px}}.cards{{grid-template-columns:1fr}}}}</style></head><body><main><div class="eyebrow">GOLD SIGNAL RESEARCH</div><h1>黄金信号研究</h1><p>请选择要查看的版本。</p><div class="cards"><a href={school_name}><span class="tag">01 · 校内评审</span><h2>完整研究版</h2><div class="desc">包含条件定义、样本范围、逐次记录和分段统计，供课程评审与复核。</div><span class="go">打开研究版 →</span></a><a href={commercial_name}><span class="tag">02 · 对外展示</span><h2>信号提醒版</h2><div class="desc">展示汇总表现与自愿订阅入口，不在页面中展开算法条件和逐条样本。</div><span class="go">打开展示版 →</span></a></div></main></body></html>'''
    output.write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="根据日线 CSV 生成黄金/实际利率信号研究网页。")
    parser.add_argument("--input", type=Path, default=Path("data") / "market_data.csv", help="日线 CSV 文件")
    parser.add_argument("--output", type=Path, default=Path("output") / "research_dashboard.html", help="网页输出位置")
    parser.add_argument("--commercial-output", type=Path, default=None, help="商业展示页输出位置（默认与研究页同目录）")
    parser.add_argument("--index-output", type=Path, default=None, help="版本选择页输出位置（默认与研究页同目录）")
    parser.add_argument("--send-alert", action="store_true", help="若最新一行触发已选极端相关信号，则发送邮件/企业微信提醒")
    args = parser.parse_args()
    rows = load_data(args.input)
    payload = analyze(rows, args.input.name)
    commercial_output = args.commercial_output or args.output.with_name("commercial_dashboard.html")
    index_output = args.index_output or args.output.with_name("index.html")
    write_dashboard(payload, args.output)
    write_commercial_dashboard(payload, commercial_output)
    write_launch_page(args.output, commercial_output, index_output)
    print(f"数据范围：{payload['data']['first_date']} 至 {payload['data']['last_date']}，共 {payload['data']['row_count']} 行")
    print(f"共同样本：A+B {payload['data']['common_ab_count']} 个；正极端 {payload['data']['positive_count']} 个；负极端 {payload['data']['negative_count']} 个；非极端 {payload['data']['non_extreme_count']} 个；无法计算 {payload['data']['correlation_unavailable_count']} 个")
    for item in payload["strategies"]:
        full = item["full"]
        print(f"{item['label']}｜信号后第 {item['horizon']} 日：{full['wins']}/{full['n']}（{full['win_rate']:.1%}），平均毛收益 {full['mean_gross_return']:+.2%}")
    print(f"已生成校内研究版：{args.output.resolve()}")
    print(f"已生成商业展示版：{commercial_output.resolve()}")
    print(f"版本选择页：{index_output.resolve()}")
    if args.send_alert:
        load_local_env(Path(".env"))
        signal = latest_completed_signal(rows)
        if signal is None:
            print("最新一行没有触发正/负极端相关研究信号，未发送提醒。")
        else:
            for status in dispatch_once(signal, Path("output") / "notification_state.json"):
                print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
