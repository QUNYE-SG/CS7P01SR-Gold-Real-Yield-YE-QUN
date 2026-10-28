"""Reproducible historical analysis for the selected gold/real-yield signals."""

from __future__ import annotations

import csv
import datetime as dt
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


YIELD_COLUMN = "10-Year Treasury Inflation-Indexed Security, Constant Maturity · Federal Reserve: close"
CORRELATION_COLUMN = "相关系数"
EXTREME_THRESHOLD = 0.80
MIN_SIGNAL_GAP = 5
SELECTED_HORIZONS = (("positive", 4), ("positive", 5), ("positive", 9), ("negative", 10))


@dataclass(frozen=True)
class DailyObservation:
    date: dt.date
    open: float
    close: float
    real_yield: float | None
    correlation: float | None
    high: float | None = None
    low: float | None = None


def _number(value: str | None, field: str, row_number: int) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"第 {row_number} 行的“{field}”不是有效数字。") from exc
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def load_data(path: Path) -> list[DailyObservation]:
    """Load and validate the daily OHLC/yield/correlation fields from the supplied CSV."""
    required = {"time", "open", "high", "low", "close", YIELD_COLUMN, CORRELATION_COLUMN}
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = set(reader.fieldnames or ())
        missing = sorted(required - columns)
        if missing:
            raise ValueError("CSV 缺少必需字段：" + "、".join(missing))

        rows: list[DailyObservation] = []
        latest_yield: float | None = None
        for row_number, row in enumerate(reader, start=2):
            try:
                day = dt.date.fromisoformat((row.get("time") or "").strip())
            except ValueError as exc:
                raise ValueError(f"第 {row_number} 行的日期格式错误，应为 YYYY-MM-DD。") from exc
            open_price = _number(row.get("open"), "open", row_number)
            high_price = _number(row.get("high"), "high", row_number)
            low_price = _number(row.get("low"), "low", row_number)
            close_price = _number(row.get("close"), "close", row_number)
            current_yield = _number(row.get(YIELD_COLUMN), YIELD_COLUMN, row_number)
            correlation = _number(row.get(CORRELATION_COLUMN), CORRELATION_COLUMN, row_number)
            if open_price is None or high_price is None or low_price is None or close_price is None:
                raise ValueError(f"第 {row_number} 行缺少完整的 OHLC 价格。")
            if high_price < max(open_price, close_price) or low_price > min(open_price, close_price) or low_price > high_price:
                raise ValueError(f"第 {row_number} 行 OHLC 价格关系不正确。")
            if correlation is not None and not -1.0 <= correlation <= 1.0:
                raise ValueError(f"第 {row_number} 行的相关系数超出 −1 至 +1 范围。")
            if current_yield is not None:
                latest_yield = current_yield
            rows.append(DailyObservation(day, open_price, close_price, latest_yield, correlation, high_price, low_price))

    if len(rows) < 20:
        raise ValueError("有效日线记录不足，至少需要 20 行。")
    if any(left.date >= right.date for left, right in zip(rows, rows[1:])):
        raise ValueError("日期必须按从早到晚排列且不能重复；程序不会擅自重排原始数据。")
    for index in range(5, len(rows)):
        if rows[index].real_yield is None:
            raise ValueError(f"第 {rows[index].date.isoformat()} 日缺少实际利率，无法判断信号。")
    return rows


def classify_correlation(value: float) -> str:
    if value >= EXTREME_THRESHOLD:
        return "positive"
    if value <= -EXTREME_THRESHOLD:
        return "negative"
    return "non_extreme"


def candidate_indices(rows: list[DailyObservation]) -> list[int]:
    """A+B: yield is above its value five sessions earlier; gold is above the
    lowest close in the five immediately preceding sessions.
    """
    candidates: list[int] = []
    for index in range(5, len(rows)):
        prior_yield = rows[index - 5].real_yield
        current_yield = rows[index].real_yield
        prior_closes = [rows[position].close for position in range(index - 5, index)]
        if prior_yield is None or current_yield is None:
            continue
        if current_yield > prior_yield and rows[index].close > min(prior_closes):
            candidates.append(index)
    return candidates


def deduplicate(indices: Iterable[int], minimum_gap: int = MIN_SIGNAL_GAP) -> list[int]:
    kept: list[int] = []
    for index in indices:
        if not kept or index - kept[-1] >= minimum_gap:
            kept.append(index)
    return kept


def _period_bounds(rows: list[DailyObservation], common: list[int], last_common: int) -> dict[str, tuple[dt.date, dt.date]]:
    first_date = rows[common[0]].date
    last_date = rows[last_common].date
    raw_start = rows[0].date
    raw_end = rows[-1].date
    midpoint = raw_start + dt.timedelta(days=(raw_end - raw_start).days // 2)
    try:
        recent_start = raw_end.replace(year=raw_end.year - 5) + dt.timedelta(days=1)
    except ValueError:
        recent_start = raw_end.replace(year=raw_end.year - 5, day=28) + dt.timedelta(days=1)
    return {
        "全样本": (first_date, last_date),
        "前半段": (first_date, midpoint),
        "后半段": (midpoint + dt.timedelta(days=1), last_date),
        "最近五年": (recent_start, last_date),
    }


def _gross_return(rows: list[DailyObservation], signal_index: int, horizon: int) -> float:
    entry_index = signal_index + 1
    exit_index = signal_index + horizon
    return rows[exit_index].close / rows[entry_index].open - 1.0


def _result(rows: list[DailyObservation], indices: list[int], horizon: int) -> dict[str, float | int | None]:
    returns = [_gross_return(rows, index, horizon) for index in indices]
    wins = sum(value > 0 for value in returns)
    return {
        "wins": wins,
        "n": len(indices),
        "win_rate": wins / len(indices) if indices else None,
        "mean_gross_return": statistics.mean(returns) if returns else None,
    }


def analyze(rows: list[DailyObservation], source_name: str = "") -> dict[str, object]:
    candidates = deduplicate(candidate_indices(rows))
    last_common = len(rows) - 11  # every included signal has ten later sessions
    last_d5 = len(rows) - 6
    if last_common < 5 or not candidates:
        raise ValueError("没有足够的完整信号样本。")

    main = [index for index in candidates if index <= last_d5]
    common = [index for index in candidates if index <= last_common]
    if not common:
        raise ValueError("没有可完整观察信号后十个交易日的共同样本。")

    groups = {
        index: (
            classify_correlation(rows[index].correlation)
            if rows[index].correlation is not None
            else "unavailable"
        )
        for index in common
    }
    selected = [
        (group, horizon, [index for index in common if groups[index] == group])
        for group, horizon in SELECTED_HORIZONS
    ]
    bounds = _period_bounds(rows, common, last_common)

    stats: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    for group, horizon, indices in selected:
        label = "A+B+C（正极端相关）" if group == "positive" else "A+B+D（负极端相关）"
        period_results: dict[str, object] = {}
        for period, (start, end) in bounds.items():
            subset = [index for index in indices if start <= rows[index].date <= end]
            period_results[period] = _result(rows, subset, horizon)
        stats.append(
            {
                "group": group,
                "horizon": horizon,
                "label": label,
                "full": period_results["全样本"],
                "periods": period_results,
            }
        )

        for index in indices:
            entry_index = index + 1
            exit_index = index + horizon
            gross_return = _gross_return(rows, index, horizon)
            details.append(
                {
                    "signal_date": rows[index].date.isoformat(),
                    "label": label,
                    "group": group,
                    "horizon": horizon,
                    "correlation": rows[index].correlation,
                    "signal_close": rows[index].close,
                    "entry_date": rows[entry_index].date.isoformat(),
                    "entry_open": rows[entry_index].open,
                    "exit_date": rows[exit_index].date.isoformat(),
                    "exit_close": rows[exit_index].close,
                    "gross_return": gross_return,
                    "success": gross_return > 0,
                }
            )

    probability_ranking = sorted(stats, key=lambda item: (item["full"]["win_rate"] or 0, item["full"]["n"]), reverse=True)
    return_ranking = sorted(stats, key=lambda item: (item["full"]["mean_gross_return"] or 0, item["full"]["n"]), reverse=True)

    return {
        "source_name": source_name,
        "data": {
            "first_date": rows[0].date.isoformat(),
            "last_date": rows[-1].date.isoformat(),
            "row_count": len(rows),
            "d5_signal_start": rows[main[0]].date.isoformat() if main else None,
            "d5_signal_end": rows[last_d5].date.isoformat(),
            "d5_ab_count": len(main),
            "common_signal_start": rows[common[0]].date.isoformat(),
            "common_signal_end": rows[last_common].date.isoformat(),
            "common_ab_count": len(common),
            "positive_count": sum(value == "positive" for value in groups.values()),
            "negative_count": sum(value == "negative" for value in groups.values()),
            "non_extreme_count": sum(value == "non_extreme" for value in groups.values()),
            "correlation_unavailable_count": sum(value == "unavailable" for value in groups.values()),
            "midpoint": (rows[0].date + dt.timedelta(days=(rows[-1].date - rows[0].date).days // 2)).isoformat(),
            "recent_start": bounds["最近五年"][0].isoformat(),
            "period_ranges": {
                name: f"{start.isoformat()} 至 {end.isoformat()}"
                for name, (start, end) in bounds.items()
            },
        },
        "strategies": stats,
        "probability_ranking": [
            {"group": item["group"], "horizon": item["horizon"]} for item in probability_ranking
        ],
        "return_ranking": [
            {"group": item["group"], "horizon": item["horizon"]} for item in return_ranking
        ],
        "candles": [
            {
                "date": item.date.isoformat(),
                "open": item.open,
                "high": item.high if item.high is not None else max(item.open, item.close),
                "low": item.low if item.low is not None else min(item.open, item.close),
                "close": item.close,
            }
            for item in rows
        ],
        "details": details,
    }
