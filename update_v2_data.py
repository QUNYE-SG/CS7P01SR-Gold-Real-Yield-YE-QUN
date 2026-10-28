"""Update V2 gold bars from IBKR and real yields from FRED DFII10."""

from __future__ import annotations

import csv
import datetime as dt
import json
import logging
import math
import os
import shutil
import tempfile
import threading
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from analysis import CORRELATION_COLUMN, YIELD_COLUMN, load_data
from build_top2_package import DEFAULT_OUTPUT, build_package


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv"
SOURCE_START_DATE = "2026-10-02"
YIELD_DATE_COLUMN = "实际利率观测日期"
CORRELATION_YIELD_COLUMN = "相关性配对实际利率"
CORRELATION_YIELD_DATE_COLUMN = "相关性配对利率观测日期"
CORRELATION_SOURCE_COLUMN = "相关性来源"
FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
IBKR_STATUS_CODES = {2104, 2106, 2107, 2108, 2158}
LOG_PATH = ROOT / "output" / "update_logs" / "v2_data_update.log"


class UpdateError(RuntimeError):
    """A safe-to-display update failure with no embedded credentials."""


@dataclass(frozen=True)
class HistoricalBar:
    date: str
    open: float
    high: float
    low: float
    close: float


def _format_number(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return repr(float(value))


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        fields = list(reader.fieldnames or [])
        if not fields:
            raise UpdateError(f"数据文件没有表头：{path.name}")
        rows = [dict(row) for row in reader]
    required = {"time", "open", "high", "low", "close", YIELD_COLUMN, "正相关", "负相关", CORRELATION_COLUMN}
    missing = sorted(required.difference(fields))
    if missing:
        raise UpdateError("V2 数据文件缺少字段：" + "、".join(missing))
    if not rows:
        raise UpdateError("V2 数据文件没有日线记录。")
    dates = [row.get("time", "").strip() for row in rows]
    try:
        parsed_dates = [dt.date.fromisoformat(day) for day in dates]
    except ValueError as exc:
        raise UpdateError("V2 数据中存在无法识别的日期；没有改写数据。") from exc
    if any(left >= right for left, right in zip(parsed_dates, parsed_dates[1:])):
        raise UpdateError("V2 数据日期重复或未按先后排列；没有改写数据。")
    return fields, rows


def _fred_api_key() -> str:
    key = os.environ.get("FRED_API_KEY", "").strip()
    if key:
        return key
    env_path = ROOT / ".env"
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() == "FRED_API_KEY":
                key = value.strip().strip("\"'")
                break
    if not key:
        raise UpdateError("尚未设置 FRED_API_KEY。请在 V2 文件夹的 .env 中填写个人 FRED API 密钥。")
    return key


def _parse_fred_payload(payload: str | bytes) -> dict[str, float | None]:
    try:
        decoded = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        data = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UpdateError("FRED 返回的数据格式无法识别。") from exc
    if data.get("error_code"):
        raise UpdateError("FRED 拒绝了数据请求；请检查 API 密钥与请求权限。")
    observations = data.get("observations")
    if not isinstance(observations, list) or not observations:
        raise UpdateError("FRED 没有返回 DFII10 观测值。")
    values: dict[str, float | None] = {}
    for item in observations:
        day = str(item.get("date", ""))
        try:
            dt.date.fromisoformat(day)
        except ValueError as exc:
            raise UpdateError("FRED 返回了无法识别的日期。") from exc
        raw = str(item.get("value", ".")).strip()
        if raw in ("", "."):
            values[day] = None
            continue
        try:
            value = float(raw)
        except ValueError as exc:
            raise UpdateError(f"FRED 在 {day} 返回了非数字实际利率。") from exc
        if not math.isfinite(value):
            raise UpdateError(f"FRED 在 {day} 返回了无效实际利率。")
        values[day] = value
    return values


def fetch_fred_values(api_key: str, observation_start: str) -> dict[str, float | None]:
    params = urlencode(
        {
            "series_id": "DFII10",
            "api_key": api_key,
            "file_type": "json",
            "observation_start": observation_start,
            "sort_order": "asc",
            "limit": "100000",
        }
    )
    request = Request(
        f"{FRED_OBSERVATIONS_URL}?{params}",
        headers={"User-Agent": "GoldSignalDashboardV2/1.0"},
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
    except (URLError, TimeoutError, OSError) as exc:
        # Do not surface the request URL: it contains the private API key.
        raise UpdateError("连接 FRED 失败；请检查网络后重试。") from None
    values = _parse_fred_payload(payload)
    if not values:
        raise UpdateError("FRED 没有返回 DFII10 数据。")
    return values


def _ibkr_error_details(args: tuple[object, ...]) -> tuple[object, int, str] | None:
    """Normalize both legacy and current EWrapper.error callback signatures."""
    if len(args) >= 5:
        req_id, code, message = args[0], args[2], args[3]
    elif len(args) >= 3:
        req_id, code, message = args[0], args[1], args[2]
    else:
        return None
    try:
        numeric_code = int(code)
    except (TypeError, ValueError):
        numeric_code = -1
    return req_id, numeric_code, str(message)


def completed_gold_bars(
    bars: Iterable[HistoricalBar], *, now: dt.datetime | None = None,
) -> list[HistoricalBar]:
    # Daily updates run after 00:00 UTC. Exclude today's UTC date even if IBKR
    # supplies a forming bar; a delayed daytime run must not save intraday OHLC.
    current = now or dt.datetime.now(dt.timezone.utc)
    cutoff = current.astimezone(dt.timezone.utc).date().isoformat()
    return [bar for bar in bars if bar.date < cutoff]


def fetch_ibkr_bars(host: str = "127.0.0.1", port: int = 7496, client_id: int = 688) -> list[HistoricalBar]:
    try:
        from ibapi.client import EClient
        from ibapi.contract import Contract
        from ibapi.wrapper import EWrapper
    except ImportError as exc:
        raise UpdateError("当前 Python 环境没有安装 IBKR 的 ibapi；请使用已安装 TWS API 的 Python。") from exc

    class HistoricalClient(EWrapper, EClient):
        def __init__(self) -> None:
            EClient.__init__(self, self)
            self.connected_event = threading.Event()
            self.finished_event = threading.Event()
            self.bars: list[HistoricalBar] = []
            self.request_errors: list[str] = []

        def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IBKR callback name
            self.connected_event.set()

        def historicalData(self, reqId: int, bar: object) -> None:  # noqa: N802
            if reqId != 1:
                return
            raw_date = str(getattr(bar, "date", "")).split(" ", 1)[0]
            try:
                day = dt.datetime.strptime(raw_date, "%Y%m%d").date().isoformat()
                values = tuple(float(getattr(bar, field)) for field in ("open", "high", "low", "close"))
            except (ValueError, TypeError, AttributeError):
                self.request_errors.append("IBKR 返回了无法识别的日线数据。")
                return
            if not all(math.isfinite(value) for value in values):
                self.request_errors.append(f"IBKR 在 {day} 返回了无效 OHLC。")
                return
            self.bars.append(HistoricalBar(day, *values))

        def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802
            if reqId == 1:
                self.finished_event.set()

        def error(self, *args: object) -> None:
            details = _ibkr_error_details(args)
            if details is None:
                return
            req_id, numeric_code, message = details
            if numeric_code in IBKR_STATUS_CODES:
                return
            if req_id == 1 or numeric_code in (502, 504):
                self.request_errors.append(f"IBKR API 错误 {numeric_code}：{message}")
                if req_id == 1:
                    self.finished_event.set()

    app = HistoricalClient()
    thread: threading.Thread | None = None
    try:
        app.connect(host, port, client_id)
        thread = threading.Thread(target=app.run, name="ibkr-historical-data", daemon=True)
        thread.start()
        if not app.connected_event.wait(timeout=15):
            raise UpdateError(f"无法通过 {host}:{port} 完成 IBKR API 握手；请确认 TWS 已登录且 API 端口开启。")

        contract = Contract()
        contract.symbol = "XAUUSD"
        contract.secType = "CMDTY"
        contract.exchange = "SMART"
        contract.currency = "USD"
        app.reqHistoricalData(1, contract, "", "1 Y", "1 day", "MIDPOINT", 0, 1, False, [])
        if not app.finished_event.wait(timeout=120):
            raise UpdateError("等待 IBKR 黄金日线超时；没有改写 V2 数据。")
        if app.request_errors:
            raise UpdateError("；".join(dict.fromkeys(app.request_errors)))
        bars = completed_gold_bars(
            sorted({bar.date: bar for bar in app.bars}.values(), key=lambda bar: bar.date),
        )
        if not bars:
            raise UpdateError("IBKR 没有返回 XAUUSD 日线；请检查合约和行情权限。")
        return bars
    except UpdateError:
        raise
    except Exception as exc:
        raise UpdateError("IBKR 连接或历史行情请求失败；请确认 TWS 已登录且 API 端口为 7496。") from exc
    finally:
        if app.isConnected():
            app.disconnect()
        if thread is not None:
            thread.join(timeout=3)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    x_mean = math.fsum(xs) / len(xs)
    y_mean = math.fsum(ys) / len(ys)
    x_delta = [value - x_mean for value in xs]
    y_delta = [value - y_mean for value in ys]
    x_sum = math.fsum(value * value for value in x_delta)
    y_sum = math.fsum(value * value for value in y_delta)
    if x_sum == 0 or y_sum == 0:
        return None
    result = math.fsum(x * y for x, y in zip(x_delta, y_delta)) / math.sqrt(x_sum * y_sum)
    return max(-1.0, min(1.0, result))


def restore_tradingview_history(
    existing_rows: Iterable[dict[str, str]],
    original_rows: Iterable[dict[str, str]],
    boundary: str = SOURCE_START_DATE,
) -> list[dict[str, str]]:
    """Restore exported indicator values, never raw OHLC or yield observations.

    This also preserves holiday alignment, leading windows and a degenerate
    window reported as zero by the original Pine export.
    """
    original = {row["time"]: row for row in original_rows}
    result = []
    for item in existing_rows:
        row = dict(item)
        if row["time"] < boundary:
            source = original.get(row["time"])
            if source is None:
                raise UpdateError(f"原始导出缺少 {row['time']}，不能恢复历史相关性。")
            for field in ("open", "high", "low", "close", YIELD_COLUMN):
                left, right = row.get(field, "").strip(), source.get(field, "").strip()
                if left != right and (not left or not right or float(left) != float(right)):
                    raise UpdateError(f"{row['time']} 的历史 {field} 与原始导出不一致；没有覆盖历史价格或利率。")
            for field in ("正相关", "负相关", CORRELATION_COLUMN):
                row[field] = source.get(field, "")
            row[CORRELATION_SOURCE_COLUMN] = "TradingView原始导出"
        result.append(row)
    return result


def merge_and_recalculate(
    fieldnames: list[str],
    existing_rows: Iterable[dict[str, str]],
    bars: Iterable[HistoricalBar],
    fred_values: dict[str, float | None],
    *,
    source_start_date: str | None = None,
) -> list[dict[str, str]]:
    if source_start_date is not None:
        dt.date.fromisoformat(source_start_date)
    rows_by_date = {row["time"]: dict(row) for row in existing_rows}
    # Keep the complete FRED calendar, including observations on days when
    # gold has no bar. Shifting the gold-row yield column loses those dates.
    observations: dict[str, float] = {}
    for row in rows_by_date.values():
        raw = row.get(YIELD_COLUMN, "").strip()
        if raw:
            observation_day = row.get(YIELD_DATE_COLUMN, "").strip() or row["time"]
            value = float(raw)
            if math.isfinite(value):
                observations[observation_day] = value
    for day, value in fred_values.items():
        if value is None:
            observations.pop(day, None)
        else:
            observations[day] = value
    observation_days = sorted(observations)
    for bar in bars:
        if source_start_date is not None and bar.date < source_start_date:
            continue
        try:
            dt.date.fromisoformat(bar.date)
            prices = (float(bar.open), float(bar.high), float(bar.low), float(bar.close))
        except (TypeError, ValueError) as exc:
            raise UpdateError("IBKR 日线日期或 OHLC 格式错误；没有写入数据。") from exc
        open_price, high, low, close = prices
        if (
            not all(math.isfinite(value) for value in prices)
            or high < max(open_price, close)
            or low > min(open_price, close)
            or low > high
        ):
            raise UpdateError(f"IBKR 的 {bar.date} OHLC 关系不正确；没有写入数据。")
        row = rows_by_date.setdefault(bar.date, {field: "" for field in fieldnames})
        row.update(
            {
                "time": bar.date,
                "open": _format_number(open_price),
                "high": _format_number(high),
                "low": _format_number(low),
                "close": _format_number(close),
            }
        )

    for day, value in fred_values.items():
        if source_start_date is not None and day < source_start_date:
            continue
        row = rows_by_date.get(day)
        if row is not None:
            row[YIELD_COLUMN] = _format_number(value)

    rows = [rows_by_date[day] for day in sorted(rows_by_date)]
    if source_start_date is not None:
        available_days = sorted(day for day, value in fred_values.items() if value is not None)
        for row in rows:
            if row["time"] < source_start_date:
                continue
            position = bisect_right(available_days, row["time"]) - 1
            if position < 0:
                raise UpdateError(f"FRED 尚未提供 {row['time']} 或之前可用的实际利率；没有写入数据。")
            observation_day = available_days[position]
            row[YIELD_COLUMN] = _format_number(fred_values[observation_day])
            row[YIELD_DATE_COLUMN] = observation_day
    aligned_yields: list[float | None] = []
    aligned_dates: list[str | None] = []
    for row in rows:
        # Reproduce the verified historical request.security(D, close,
        # gaps_off, lookahead_off) mapping for the gold daily time axis:
        # use the latest FRED observation strictly before the gold bar date.
        # This is calendar/date-asof selection, not an unconditional row shift.
        position = bisect_left(observation_days, row["time"]) - 1
        day = observation_days[position] if position >= 0 else None
        aligned_dates.append(day)
        aligned_yields.append(observations[day] if day is not None else None)

    for index, row in enumerate(rows):
        if source_start_date is not None and row["time"] < source_start_date:
            continue
        correlation: float | None = None
        if index >= 4:
            start = index - 4
            yields = aligned_yields[start : index + 1]
            if any(value is None for value in yields):
                raise UpdateError(f"{row['time']} 缺少原图时序对齐所需的历史FRED观测；没有改写数据。")
            if all(value is not None for value in yields):
                try:
                    closes = [float(rows[position]["close"]) for position in range(start, index + 1)]
                    correlation = _pearson(closes, [float(value) for value in yields if value is not None])
                except (ValueError, TypeError) as exc:
                    raise UpdateError(f"{row['time']} 的五日相关系数无法重算。") from exc
        row[CORRELATION_COLUMN] = _format_number(correlation)
        if "正相关" in row:
            row["正相关"] = _format_number(max(0.0, correlation)) if correlation is not None else ""
        if "负相关" in row:
            row["负相关"] = _format_number(min(0.0, correlation)) if correlation is not None else ""
        row[CORRELATION_YIELD_COLUMN] = _format_number(aligned_yields[index])
        row[CORRELATION_YIELD_DATE_COLUMN] = aligned_dates[index] or ""
        row[CORRELATION_SOURCE_COLUMN] = "IBKR/FRED日线时序对齐"
    return rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)


def run_update(
    input_path: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT,
    *,
    api_key: str | None = None,
    bars: list[HistoricalBar] | None = None,
    fred_values: dict[str, float | None] | None = None,
    source_start_date: str | None = SOURCE_START_DATE,
) -> dict[str, object]:
    fieldnames, existing_rows = _read_rows(input_path)
    restored_rows = existing_rows
    if input_path.resolve() == DEFAULT_INPUT.resolve() and source_start_date is not None:
        _, original_rows = _read_rows(ROOT / "data" / "market_data.csv")
        restored_rows = restore_tradingview_history(existing_rows, original_rows, source_start_date)
    if fred_values is None:
        if api_key is None:
            api_key = _fred_api_key()
        observation_start = existing_rows[0]["time"]
        if source_start_date is not None:
            observation_start = (dt.date.fromisoformat(source_start_date) - dt.timedelta(days=14)).isoformat()
        fred_values = fetch_fred_values(api_key, observation_start)
    if bars is None:
        host = os.environ.get("IBKR_HOST", "127.0.0.1")
        port = int(os.environ.get("IBKR_PORT", "7496"))
        client_id = int(os.environ.get("IBKR_CLIENT_ID", "688"))
        bars = fetch_ibkr_bars(host, port, client_id)

    for field in (YIELD_DATE_COLUMN, CORRELATION_YIELD_COLUMN,
                  CORRELATION_YIELD_DATE_COLUMN, CORRELATION_SOURCE_COLUMN):
        if field not in fieldnames:
            fieldnames.append(field)
    updated_rows = merge_and_recalculate(
        fieldnames, restored_rows, bars, fred_values, source_start_date=source_start_date,
    )
    data_changed = len(existing_rows) != len(updated_rows) or any(
        old.get(field, "") != new.get(field, "")
        for old, new in zip(existing_rows, updated_rows)
        for field in fieldnames
    )
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8-sig", newline="", suffix=".csv", prefix="v2-update-",
        dir=input_path.parent, delete=False,
    ) as temporary:
        temporary_path = Path(temporary.name)
        writer = csv.DictWriter(temporary, fieldnames=fieldnames, extrasaction="ignore", quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(updated_rows)
        temporary.flush()
        os.fsync(temporary.fileno())
    backup_dir: Path | None = None
    try:
        # Reuse the existing production validator before replacing the input.
        load_data(temporary_path)
        if data_changed:
            backup_root = output_dir.parent / "update_backups"
            backup_root.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-")
            backup_dir = Path(tempfile.mkdtemp(prefix=stamp, dir=backup_root))
            shutil.copy2(input_path, backup_dir / input_path.name)
            prior_zip = output_dir.with_suffix(".zip")
            if prior_zip.is_file():
                shutil.copy2(prior_zip, backup_dir / prior_zip.name)
        ranked, zip_path = build_package(temporary_path, output_dir)
        os.replace(temporary_path, input_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    result: dict[str, object] = {
        "row_count": len(updated_rows),
        "first_date": updated_rows[0]["time"],
        "last_date": updated_rows[-1]["time"],
        "ibkr_bars": len(bars),
        "fred_observations": len(fred_values),
        "gold_last_date": max((bar.date for bar in bars), default=None),
        "fred_last_date": max((day for day, value in fred_values.items() if value is not None), default=None),
        "source_start_date": source_start_date,
        "correlation_method": "TradingView原始历史导出；衔接后使用完整FRED日历、严格早于黄金日线日期的正式观测，五日原始数值Pearson",
        "data_changed": data_changed,
        "backup_dir": str(backup_dir) if backup_dir is not None else None,
        "eligible_count": sum(row["win_probability"] is not None and row["win_probability"] >= 0.70 for row in ranked),
        "package_zip": str(zip_path),
    }
    return result


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    try:
        result = run_update()
    except UpdateError as exc:
        logging.error("数据更新失败：%s", exc)
        print(f"数据更新未完成：{exc}")
        return 1
    except (OSError, ValueError) as exc:
        logging.exception("数据更新失败")
        print(f"数据更新未完成：{exc}")
        return 1

    # Run only after both source checks and the production package succeed.
    # The application automation reads this outbox and delivers the notification.
    from signal_notifications import prepare_notifications

    try:
        result["signal_notification"] = prepare_notifications(load_data(DEFAULT_INPUT))
    except (OSError, ValueError) as exc:
        result["signal_notification"] = {"status": "failed", "notify": False, "error": str(exc)}
        logging.error("信号提醒检查失败：%s", exc)

    message = (
        f"V2 更新完成：{result['first_date']} 至 {result['last_date']}，"
        f"IBKR 最新日线 {result['gold_last_date']}，FRED 最新观测 {result['fred_last_date']}；"
        f"达到 70% 的方案 {result['eligible_count']} 种。结果包：{result['package_zip']}"
    )
    logging.info(message)
    (LOG_PATH.parent / "latest_update.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
