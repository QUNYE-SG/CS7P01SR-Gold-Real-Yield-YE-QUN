"""Coarse, truthful sample descriptions for public presentation only."""

from __future__ import annotations


def public_sample_summary(model: dict) -> dict[str, str]:
    """Keep precise dates/counts in the model, but do not render them publicly.

    Descriptions follow broad ranges so later daily updates do not leave a
    hardcoded 'nearly 3,000' claim on a materially larger or smaller sample.
    This is display minimisation, not an access-control or IP-protection layer.
    """
    years = float(model["years"])
    count = int(model["metadata"]["row_count"])
    if years >= 30:
        span = "数十年"
    elif years >= 20:
        span = "二十余年"
    elif years >= 10:
        span = "十余年"
    elif years >= 2:
        span = "多年"
    elif years >= 1:
        span = "一年多"
    else:
        span = "不足一年"

    if 2750 <= count < 3000:
        size = "近三千个交易日"
    elif 2500 <= count < 3500:
        size = "约三千个交易日"
    elif count >= 3500:
        rounded = ((count + 500) // 1000) * 1000
        size = f"约 {rounded:,} 个交易日"
    elif count >= 2000:
        size = "两千余个交易日"
    elif count >= 1000:
        size = "千余个交易日"
    elif count >= 100:
        size = "数百个交易日"
    elif count >= 10:
        size = "数十个交易日"
    else:
        size = "少量交易日"
    return {"span": span, "size": size, "summary": f"历史样本：覆盖{span} · {size}"}
