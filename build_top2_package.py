"""Rank the positive/negative extreme-correlation strategies across horizons 1-10."""

from __future__ import annotations

import argparse
import csv
import shutil
import zipfile
from pathlib import Path

from v2_pages import write_pages

from analysis import (
    EXTREME_THRESHOLD,
    DailyObservation,
    candidate_indices,
    classify_correlation,
    deduplicate,
    load_data,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "market_data_pine5_raw_recalc_preview.csv"
DEFAULT_OUTPUT = ROOT / "output" / "top2_pine5_20261004"
GROUP_ORDER = {"positive": 0, "negative": 1}
GROUP_LABELS = {"positive": "正极端相关", "negative": "负极端相关"}
MIN_WIN_PROBABILITY = 0.70


def _gross_return(rows: list[DailyObservation], signal_index: int, horizon: int) -> float:
    entry = rows[signal_index + 1].open
    exit_price = rows[signal_index + horizon].close
    return exit_price / entry - 1.0


def calculate_rankings(rows: list[DailyObservation]) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    """Use the existing A+B signals and compare both correlation groups at horizons 1-10."""
    if len(rows) < 21:
        raise ValueError("有效日线记录不足，至少需要 21 行，才能检验第十个后续交易日。")

    last_common = len(rows) - 11
    common = [index for index in deduplicate(candidate_indices(rows)) if index <= last_common]
    if not common:
        raise ValueError("没有可完整观察后十个交易日的共同 A+B 信号样本。")

    counts = {"positive": 0, "negative": 0, "non_extreme": 0, "unavailable": 0}
    for index in common:
        value = rows[index].correlation
        group = "unavailable" if value is None else classify_correlation(value)
        counts[group] += 1

    combinations: list[dict[str, object]] = []
    details: list[dict[str, object]] = []
    for group in ("positive", "negative"):
        indices = [
            index
            for index in common
            if rows[index].correlation is not None
            and classify_correlation(rows[index].correlation) == group
        ]
        for horizon in range(1, 11):
            returns = [_gross_return(rows, index, horizon) for index in indices]
            wins = sum(value > 0 for value in returns)
            row: dict[str, object] = {
                "group": group,
                "group_label": GROUP_LABELS[group],
                "horizon": horizon,
                "wins": wins,
                "sample_count": len(indices),
                "win_probability": wins / len(indices) if indices else None,
            }
            combinations.append(row)
            for index, gross_return in zip(indices, returns):
                entry_index = index + 1
                exit_index = index + horizon
                details.append(
                    {
                        "group": group,
                        "group_label": GROUP_LABELS[group],
                        "horizon": horizon,
                        "signal_date": rows[index].date.isoformat(),
                        "correlation": rows[index].correlation,
                        "entry_date": rows[entry_index].date.isoformat(),
                        "entry_open": rows[entry_index].open,
                        "exit_date": rows[exit_index].date.isoformat(),
                        "exit_close": rows[exit_index].close,
                        "gross_return": gross_return,
                        "win": gross_return > 0,
                    }
                )

    ranked = sorted(
        combinations,
        key=lambda row: (
            -(row["win_probability"] if row["win_probability"] is not None else -1.0),
            GROUP_ORDER[str(row["group"])],
            int(row["horizon"]),
        ),
    )
    metadata = {
        "first_date": rows[0].date.isoformat(),
        "last_date": rows[-1].date.isoformat(),
        "row_count": len(rows),
        "common_ab_count": len(common),
        "group_counts": counts,
    }
    return ranked, details, metadata


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _percentage(value: object) -> str:
    return "—" if value is None else f"{float(value):.1%}"


def qualifying_rankings(ranked: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        row
        for row in ranked
        if row["win_probability"] is not None
        and float(row["win_probability"]) >= MIN_WIN_PROBABILITY
    ]




def build_package(input_path: Path, output_dir: Path) -> tuple[list[dict[str, object]], Path]:
    rows = load_data(input_path)
    ranked, details, metadata = calculate_rankings(rows)
    eligible = qualifying_rankings(ranked)
    output_dir.mkdir(parents=True, exist_ok=True)

    packaged_csv = output_dir / "market_data_pine5_raw_recalc.csv"
    shutil.copyfile(input_path, packaged_csv)
    _write_csv(
        output_dir / "ranking_20.csv",
        ranked,
        ["group", "group_label", "horizon", "wins", "sample_count", "win_probability"],
    )
    _write_csv(
        output_dir / "eligible_70_plus.csv",
        eligible,
        ["group", "group_label", "horizon", "wins", "sample_count", "win_probability"],
    )
    _write_csv(
        output_dir / "signal_details.csv",
        details,
        ["group", "group_label", "horizon", "signal_date", "correlation", "entry_date", "entry_open", "exit_date", "exit_close", "gross_return", "win"],
    )
    presentation = write_pages(output_dir, eligible, details, metadata)
    if output_dir.resolve() == DEFAULT_OUTPUT.resolve():
        write_pages(output_dir.parent, eligible, details, metadata,
                    download_prefix=output_dir.name + "/")

    eligible_text = "\n".join(
        f"- {row['group_label']}，第 {row['horizon']} 个后续交易日：{_percentage(row['win_probability'])}（{row['wins']}/{row['sample_count']}）"
        for row in eligible
    )
    readme = f"""# 黄金与实际利率：历史上涨概率不低于70%的方案

共 {len(eligible)} 种方案达到历史上涨概率 ≥70%：

{eligible_text}

## 口径

- 网页：`index.html` 是双入口；`research_dashboard.html` 为校内研究版，`commercial_dashboard.html` 为 V1 深蓝金色风格的商业化版。商业化版直接显示概率卡片和年份日历，没有下拉明细；提醒服务仅为本地演示，不收集或发送订阅信息。研究版保留互动月历、次级折叠研究明细、价格、算法和 CSV 下载。本地双入口仅为展示区分，并非访问权限隔离。
- 英文入口：`index_en.html`、`research_dashboard_en.html`、`commercial_dashboard_en.html`；中文原入口保留，各页顶部可切换对应语言。两种语言共享同一统计模型，每次构建同时生成，算法与 CSV 口径不变。
- 信号日历：商业化版直接显示各年份次数和月日；零次年份淡化，有信号的年份突出并放大次数。研究版可点开年份查看周一至周日月历和对应方案。首尾年份按实际覆盖区间统计。日历日期是信号日，不是入场日或退出日。
- 历史频率：样本跨度为 {presentation['years']:.2f} 年；这些方案共对应 {presentation['unique_signal_count']} 个独立信号日期。年均出现 = 信号次数 ÷ 完整样本跨度，不是年度上涨概率。
- 归类：仅合并相同相关类别、相同信号日期与相同上涨比例的期限；各期限的逐次结果保留，不重复累加信号次数。

- 输入：本包中的 `market_data_pine5_raw_recalc.csv`。2026-10-02 前的相关系数恢复为 TradingView 原指标导出值，价格和利率原始数据不变。衔接日及之后黄金 OHLC 使用 IBKR XAUUSD MIDPOINT，实际利率使用 FRED DFII10；相关性取完整 FRED 日历中严格早于黄金日线日期的最近正式观测，再计算五日原始数值 Pearson。黄金休市但 FRED 有值的日期不能丢弃。利率实际观测日期与相关性配对观测日期分别记录。IBKR与OANDA黄金来源不同，衔接后不承诺与原OANDA图表数值相同。
- 信号：沿用原项目 A+B 候选条件、相关阈值（±0.80）及至少五个交易日的信号间隔。
- 比较：正极端和负极端相关各检验第 1 至第 10 个后续交易日，共 20 种方案。为公平比较，所有期限使用信号后有完整十个交易日的同一批候选样本。
- 上涨判定：信号后第一个交易日开盘进入，在第 N 个后续交易日收盘退出；退出收盘价高于入场开盘价记为上涨。
- 上涨概率：上涨次数除以样本数。

`eligible_70_plus.csv` 含全部达到阈值的方案，`ranking_20.csv` 含 20 种组合的历史上涨概率，`signal_details.csv` 含逐次入场价、退出价、单次毛收益和上涨记录。CSV 口径不变；页面上的年均次数按当次数据自动计算。
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    zip_path = output_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ("index.html", "research_dashboard.html", "commercial_dashboard.html",
                     "index_en.html", "research_dashboard_en.html", "commercial_dashboard_en.html",
                     "eligible_70_plus.csv", "ranking_20.csv", "signal_details.csv", "market_data_pine5_raw_recalc.csv", "README.md"):
            archive.write(output_dir / name, arcname=f"{output_dir.name}/{name}")
    return ranked, zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description="比较正负极端相关的第1至第10日历史上涨概率并列出所有不低于70%的方案。")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="五日原始数值重算后的 CSV")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="独立结果包文件夹")
    args = parser.parse_args()
    ranked, zip_path = build_package(args.input, args.output_dir)
    print(f"结果包已生成：{args.output_dir.resolve()}")
    for row in qualifying_rankings(ranked):
        print(
            f"{row['group_label']}，第 {row['horizon']} 个后续交易日："
            f"上涨 {row['wins']}/{row['sample_count']}，历史上涨概率 {_percentage(row['win_probability'])}"
        )
    print(f"ZIP：{zip_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
