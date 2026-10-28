"""Optional email and Enterprise WeChat group notifications."""

from __future__ import annotations

import json
import os
import smtplib
from datetime import date, timedelta
from email.message import EmailMessage
from pathlib import Path
from urllib.request import Request, urlopen

from analysis import DailyObservation, candidate_indices, classify_correlation, deduplicate


def load_local_env(path: Path) -> None:
    """Read local KEY=VALUE settings without replacing process variables."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def observation_cycle(signal_date: str, historical: list[dict[str, object]]) -> list[dict[str, object]]:
    """Ten as-issued horizons; dates are weekday estimates, not an exchange calendar.

    Never read future bars to assign these dates, including during catch-up.
    Actual horizons remain counts of completed gold daily bars, not weekdays.
    """
    from build_top2_package import MIN_WIN_PROBABILITY

    by_horizon = {int(item["horizon"]): item for item in historical}
    expected_date = date.fromisoformat(signal_date)
    cycle = []
    for horizon in range(1, 11):
        expected_date += timedelta(days=1)
        while expected_date.weekday() >= 5:
            expected_date += timedelta(days=1)
        item = by_horizon.get(horizon, {})
        probability = item.get("win_probability")
        sample_count = int(item.get("sample_count", 0))
        cycle.append({
            "horizon": horizon,
            "expected_date": expected_date.isoformat(),
            "wins": int(item.get("wins", 0)),
            "sample_count": sample_count,
            "win_probability": probability if sample_count else None,
            "is_focus": (sample_count > 0 and probability is not None
                         and float(probability) >= MIN_WIN_PROBABILITY),
        })
    return cycle


def latest_completed_signal(rows: list[DailyObservation]) -> dict[str, object] | None:
    """Return an alert only when the newest CSV row itself is a selected signal."""
    if not rows:
        return None
    kept = deduplicate(candidate_indices(rows))
    last_index = len(rows) - 1
    if not kept or kept[-1] != last_index:
        return None
    observation = rows[last_index]
    if observation.correlation is None:
        return None
    group = classify_correlation(observation.correlation)
    if group not in ("positive", "negative"):
        return None
    # Reuse all 20 production comparisons, not the old hand-picked horizons.
    # This signal itself never needs future bars. Only historical estimates do.
    from build_top2_package import calculate_rankings, qualifying_rankings

    try:
        ranked, _, _ = calculate_rankings(rows)
        all_historical = [item for item in ranked if item["group"] == group]
        historical = [item for item in qualifying_rankings(ranked) if item["group"] == group]
    except ValueError:
        all_historical = []
        historical = []
    historical.sort(key=lambda item: int(item["horizon"]))
    horizons = [int(item["horizon"]) for item in historical]
    label = "正极端相关" if group == "positive" else "负极端相关"
    return {
        "event_id": f"{observation.date.isoformat()}:{group}",
        "date": observation.date.isoformat(),
        "group": group,
        "label": label,
        "correlation": observation.correlation,
        "horizons": horizons,
        "historical_results": historical,
        "forecast_version": 1,
        "historical_as_of": observation.date.isoformat(),
        "historical_sample_end": rows[-11].date.isoformat() if all_historical else None,
        "date_basis": "weekday_estimate",
        "cycle_results": observation_cycle(observation.date.isoformat(), all_historical),
    }


def message_for(signal: dict[str, object]) -> str:
    cycle = signal.get("cycle_results")
    if cycle is None:  # Compatibility for the optional legacy dispatcher.
        cycle = observation_cycle(str(signal["date"]), signal.get("historical_results", []))
    horizons = "、".join(f"第{item['horizon']}个交易日" for item in cycle if item["is_focus"])
    lines = []
    for item in cycle:
        probability = item["win_probability"]
        if probability is not None and item["sample_count"]:
            percentage = f"{float(probability):.1%}"
            # Do not display a rounded 70.0% as if it reached the threshold.
            if not item["is_focus"] and percentage == "70.0%":
                percentage = "<70%"
            estimate = f"{percentage}（{item['wins']}/{item['sample_count']}次）"
        else:
            estimate = "样本不足（0个完整同类历史样本）"
        focus = " ★重点观察（≥70%）" if item["is_focus"] else ""
        lines.append(f"第{item['horizon']}日｜预计 {item['expected_date']}｜历史上涨比例 {estimate}{focus}")
    history = "\n".join(lines)
    notice = "补更发现的历史信号，非即时入场提示。\n\n" if signal.get("is_catch_up") else ""
    return (
        notice + "黄金与美国十年期实际利率研究提醒\n"
        f"信号日：{signal['date']}\n"
        f"组合：A+B+{ 'C' if signal['group'] == 'positive' else 'D' }（{signal['label']}）\n"
        f"信号日五日相关系数：{signal['correlation']:+.3f}\n"
        f"历史统计截至信号日：{signal.get('historical_as_of', signal['date'])}（发出后固定，不用后来结果改写）\n"
        f"重点观察日：{horizons or '暂无达到70%的重点观察日'}\n"
        "后续第1—10个交易日完整观察表：\n"
        f"{history}\n"
        "日期仅按周一至周五预计，未核验黄金节假日休市；遇休市顺延，以实际黄金交易日计数为准。\n"
        "统计口径：同类历史信号共用已有完整后续10日的样本；均以信号后第1个交易日开盘为基准，"
        "比较对应第N日收盘是否更高，不是期间曾上涨或单日涨跌概率。\n"
        "信号确认即列全周期，不等待未来结果；历史上涨比例不保证未来上涨。不自动下单。"
    )


def _send_email(subject: str, body: str) -> tuple[bool, str]:
    required = ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_TO")
    if not all(os.getenv(key) for key in required):
        return False, "邮件设置不完整，未发送。"
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "465"))
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.getenv("SMTP_FROM") or username
    message["To"] = os.environ["SMTP_TO"]
    message.set_content(body)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20) as server:
                server.login(username, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(username, password)
                server.send_message(message)
    except Exception as exc:
        return False, f"邮件发送失败（{type(exc).__name__}），请检查本机邮件设置。"
    return True, "邮件已发送。"


def _send_wecom(body: str) -> tuple[bool, str]:
    webhook = os.getenv("WECHAT_WORK_WEBHOOK_URL", "").strip()
    if not webhook:
        return False, "企业微信机器人未配置，未发送。"
    payload = json.dumps({"msgtype": "text", "text": {"content": body}}, ensure_ascii=False).encode("utf-8")
    request = Request(webhook, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("errcode") != 0:
            return False, "企业微信机器人返回失败状态，请检查本机机器人设置。"
    except Exception as exc:
        return False, f"企业微信发送失败（{type(exc).__name__}），请检查本机机器人设置。"
    return True, "企业微信消息已发送。"


def dispatch_once(signal: dict[str, object], state_path: Path) -> list[str]:
    """Send each configured channel once per signal date; secrets never enter state/logs."""
    state = {"email": "", "wecom": ""}
    if state_path.exists():
        try:
            stored = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                state.update({key: str(stored.get(key, "")) for key in state})
        except (OSError, json.JSONDecodeError):
            return ["提醒去重记录无法读取，未发送，以免产生重复消息。"]

    subject = f"黄金与实际利率研究信号：{signal['date']}"
    body = message_for(signal)
    outcomes: list[str] = []
    configured = False
    if all(os.getenv(key) for key in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_TO")):
        configured = True
        if state["email"] == signal["event_id"]:
            outcomes.append("该信号的邮件已发送过，已跳过。")
        else:
            sent, result = _send_email(subject, body)
            outcomes.append(result)
            if sent:
                state["email"] = str(signal["event_id"])
    if os.getenv("WECHAT_WORK_WEBHOOK_URL", "").strip():
        configured = True
        if state["wecom"] == signal["event_id"]:
            outcomes.append("该信号的企业微信消息已发送过，已跳过。")
        else:
            sent, result = _send_wecom(body)
            outcomes.append(result)
            if sent:
                state["wecom"] = str(signal["event_id"])
    if not configured:
        outcomes.append("没有配置邮件或企业微信渠道，未发送。")
    if state["email"] == signal["event_id"] or state["wecom"] == signal["event_id"]:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return outcomes
