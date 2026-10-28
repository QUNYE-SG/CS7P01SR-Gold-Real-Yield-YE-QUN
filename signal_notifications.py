"""Independent local chat and email outboxes for the existing daily automation.

No network requests, account settings or orders. The app's connected Gmail tool
sends email; only a verified Gmail message ID acknowledges it. Chat announcement
and email submission are separate, and neither is a recipient delivery receipt.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import os
import re
import tempfile
from pathlib import Path

from alerting import latest_completed_signal, message_for
from analysis import DailyObservation, load_data

ROOT = Path(__file__).resolve().parent
INPUT_PATH = ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv"
STATE_PATH = ROOT / "output" / "signal_notifications" / "state.json"
REPORT_PATH = STATE_PATH.with_name("latest_check.json")


def _mail_address(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value):
        raise ValueError("邮件地址格式不正确，未修改邮件提醒记录。")
    return value


def _status(state: dict) -> str:
    return "pending" if state["pending"] or state.get("email_pending") else "no_new_signal"


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="signal-", suffix=".tmp", delete=False) as output:
            name = output.name
            json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def _read_state(path: Path) -> dict:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("version") != 1:
            raise ValueError
        dt.date.fromisoformat(state["last_checked_date"])
        if not isinstance(state["pending"], list) or not isinstance(state["announced_event_ids"], list):
            raise ValueError
        ids = [event["event_id"] for event in state["pending"]]
        if len(ids) != len(set(ids)) or not all(isinstance(item, str) for item in ids):
            raise ValueError
        if not all(isinstance(item, str) for item in state["announced_event_ids"]):
            raise ValueError
        # Additive migration: existing chat records and baseline are never reset.
        state.setdefault("email_channel", None)
        state.setdefault("email_pending", [])
        state.setdefault("email_sent", [])
        # Keep the original ten-day outlook after either channel is acknowledged.
        state.setdefault("forecasts", {})
        if not isinstance(state["forecasts"], dict):
            raise ValueError
        for event_id, forecast in state["forecasts"].items():
            if not isinstance(forecast, dict) or forecast.get("event_id") != event_id:
                raise ValueError
        channel = state["email_channel"]
        if channel is not None:
            if channel["service"] != "gmail":
                raise ValueError
            _mail_address(channel["recipient"])
            _mail_address(channel["sender"])
            dt.date.fromisoformat(channel["enabled_after_date"])
        if not isinstance(state["email_pending"], list) or not isinstance(state["email_sent"], list):
            raise ValueError
        mail_ids = []
        for event in state["email_pending"]:
            if channel is None or event["recipient"] != channel["recipient"]:
                raise ValueError
            if event["status"] not in ("ready", "sending"):
                raise ValueError
            if not all(isinstance(event[key], str) and event[key] for key in ("event_id", "subject", "body", "marker")):
                raise ValueError
            mail_ids.append(event["event_id"])
        for receipt in state["email_sent"]:
            if channel is None or receipt["recipient"] != channel["recipient"]:
                raise ValueError
            if not all(isinstance(receipt[key], str) and receipt[key] for key in ("event_id", "message_id", "submitted_at")):
                raise ValueError
            mail_ids.append(receipt["event_id"])
        if len(mail_ids) != len(set(mail_ids)):
            raise ValueError
        return state
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("信号提醒记录无法读取，已停止提醒检查，未重置去重记录。") from exc


def _report(state: dict, status: str, last_date: str) -> dict:
    return {
        "status": status,
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "data_last_date": last_date,
        "notify": bool(state["pending"]),
        "pending": state["pending"],
        "announced_count": len(state["announced_event_ids"]),
        "email_channel": state.get("email_channel"),
        "email_notify": bool(state.get("email_pending")),
        "email_pending": state.get("email_pending", []),
        "email_sent_count": len(state.get("email_sent", [])),
        "forecast_count": len(state.get("forecasts", {})),
    }


def _save_report(state: dict, state_path: Path, report_path: Path) -> dict:
    _atomic_json(state_path, state)
    report = _report(state, _status(state), state["last_checked_date"])
    _atomic_json(report_path, report)
    return report


def configure_email(recipient: str, sender: str, state_path: Path = STATE_PATH,
                    report_path: Path = REPORT_PATH) -> dict:
    """Enable future alerts only; do not replay or re-route existing records."""
    _mail_address(recipient)
    _mail_address(sender)
    state = _read_state(state_path)
    current = state["email_channel"]
    if current is not None:
        if current["recipient"] != recipient or current["sender"] != sender:
            raise ValueError("已有邮件提醒地址不同，未转发或改写待发送邮件。")
    else:
        state["email_channel"] = {
            "service": "gmail", "recipient": recipient, "sender": sender,
            "enabled_after_date": state["last_checked_date"],
            "enabled_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    return _save_report(state, state_path, report_path)


def _email_event(signal: dict, recipient: str, data_last_date: str) -> dict:
    marker = "GSV2-" + signal["date"].replace("-", "") + "-" + signal["group"]
    notice = ("补更发现的历史信号，非即时入场提示。\n\n"
              if signal["date"] < data_last_date and not signal.get("is_catch_up") else "")
    return {
        "event_id": signal["event_id"], "date": signal["date"],
        "recipient": recipient, "status": "ready", "marker": marker,
        "subject": f"黄金信号提醒｜{signal['date']}｜{signal['label']} [{marker}]",
        "body": notice + signal["message"] + f"\n\n信号唯一标识：{marker}\n本邮件为历史统计观察提醒，不自动下单。",
    }


def prepare_notifications(rows: list[DailyObservation], state_path: Path = STATE_PATH,
                          report_path: Path = REPORT_PATH) -> dict:
    """Check newly completed rows, preserving unacknowledged signals across retries.

    First use establishes a baseline; historical dates never trigger a new alert.
    For a catch-up batch, each signal uses only its own date's available prefix.
    Historical references use the production ten-future-bar common sample, while
    detection itself uses no future bars. Both rules reuse production functions.
    """
    if not rows:
        raise ValueError("没有可检查的已完成黄金日线。")
    last_date = rows[-1].date.isoformat()
    if not state_path.exists():
        state = {"version": 1, "last_checked_date": last_date,
                 "pending": [], "announced_event_ids": [], "forecasts": {}}
        _atomic_json(state_path, state)
        report = _report(state, "initialized", last_date)
        _atomic_json(report_path, report)
        return report
    state = _read_state(state_path)
    if last_date < state["last_checked_date"]:
        raise ValueError("信号提醒输入日期早于已检查日期，未回退去重记录。")
    known = (set(state["announced_event_ids"]) | {event["event_id"] for event in state["pending"]}
             | set(state["forecasts"]))
    for index, row in enumerate(rows):
        if row.date.isoformat() <= state["last_checked_date"]:
            continue
        signal = latest_completed_signal(rows[:index + 1])
        if signal is None or signal["event_id"] in known:
            continue
        signal["historical_as_of"] = row.date.isoformat()
        signal["is_catch_up"] = signal["date"] < last_date
        signal["message"] = message_for(signal)
        state["forecasts"][signal["event_id"]] = copy.deepcopy(signal)
        state["pending"].append(signal)
        channel = state["email_channel"]
        if channel is not None and signal["date"] > channel["enabled_after_date"]:
            state["email_pending"].append(_email_event(signal, channel["recipient"], last_date))
        known.add(signal["event_id"])
    state["last_checked_date"] = last_date
    _atomic_json(state_path, state)
    report = _report(state, _status(state), last_date)
    _atomic_json(report_path, report)
    return report


def acknowledge(event_id: str, state_path: Path = STATE_PATH,
                report_path: Path = REPORT_PATH) -> dict:
    """Called by the chat automation immediately before announcing a real signal."""
    state = _read_state(state_path)
    if event_id not in {event["event_id"] for event in state["pending"]}:
        if event_id not in state["announced_event_ids"]:
            raise ValueError("待提醒记录中不存在该信号，未修改去重记录。")
    else:
        state["pending"] = [event for event in state["pending"] if event["event_id"] != event_id]
        if event_id not in state["announced_event_ids"]:
            state["announced_event_ids"].append(event_id)
        _atomic_json(state_path, state)
    report = _report(state, _status(state), state["last_checked_date"])
    _atomic_json(report_path, report)
    return report


def claim_email(event_id: str, state_path: Path = STATE_PATH,
                report_path: Path = REPORT_PATH) -> dict:
    """Persist sending before the external call; uncertain attempts cannot resend."""
    state = _read_state(state_path)
    matches = [event for event in state["email_pending"] if event["event_id"] == event_id]
    if not matches:
        raise ValueError("待发送邮件中不存在该信号，未创建或发送邮件。")
    event = matches[0]
    claimed = event["status"] == "ready"
    if claimed:
        event["status"] = "sending"
        event["attempt_started_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    report = _save_report(state, state_path, report_path)
    report["email_claimed"] = claimed
    report["email_event"] = event
    return report


def acknowledge_email(event_id: str, message_id: str, recipient: str,
                      state_path: Path = STATE_PATH, report_path: Path = REPORT_PATH) -> dict:
    """Only after Gmail success (or exact sent-message reconciliation), not delivery."""
    _mail_address(recipient)
    if not isinstance(message_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", message_id):
        raise ValueError("没有有效的 Gmail 邮件ID，未将邮件标记为已发送。")
    state = _read_state(state_path)
    matches = [event for event in state["email_pending"] if event["event_id"] == event_id]
    if not matches:
        prior = [item for item in state["email_sent"] if item["event_id"] == event_id]
        if not prior or prior[0]["message_id"] != message_id or prior[0]["recipient"] != recipient:
            raise ValueError("该信号没有匹配的待发送邮件或发送凭据，未修改邮件记录。")
    else:
        event = matches[0]
        if event["recipient"] != recipient or event["status"] != "sending":
            raise ValueError("邮件收件人或发送状态不匹配，未确认发送。")
        state["email_pending"] = [item for item in state["email_pending"] if item["event_id"] != event_id]
        state["email_sent"].append({
            "event_id": event_id, "recipient": recipient, "message_id": message_id,
            "submitted_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        })
    return _save_report(state, state_path, report_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="本地聊天及邮件信号提醒记录，不发送交易指令。")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--initialize", action="store_true")
    action.add_argument("--ack", metavar="EVENT_ID")
    action.add_argument("--enable-email", metavar="RECIPIENT")
    action.add_argument("--claim-email", metavar="EVENT_ID")
    action.add_argument("--ack-email", metavar="EVENT_ID")
    parser.add_argument("--sender")
    parser.add_argument("--message-id")
    parser.add_argument("--recipient")
    args = parser.parse_args()
    if args.enable_email and not args.sender:
        parser.error("--enable-email 需要 --sender")
    if args.ack_email and (not args.message_id or not args.recipient):
        parser.error("--ack-email 需要 --message-id 和 --recipient")
    try:
        if args.ack:
            report = acknowledge(args.ack)
        elif args.enable_email:
            report = configure_email(args.enable_email, args.sender)
        elif args.claim_email:
            report = claim_email(args.claim_email)
        elif args.ack_email:
            report = acknowledge_email(args.ack_email, args.message_id, args.recipient)
        else:
            report = prepare_notifications(load_data(INPUT_PATH))
    except (OSError, ValueError) as exc:
        print(f"信号提醒检查未完成：{exc}")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
