# Gold and US Ten-Year Real Yield Signal System

**CS7P01SR dissertation code review snapshot**  
Author: YE QUN  
Prepared: 28 October 2026

## Status and scope

This is a source-only review copy of the existing V2 system. The application Python
files and Windows launchers are byte-for-byte copies of V2. Email address literals
in two test files are replaced consistently with example.invalid addresses.
All other test source is unchanged.
The live V2 installation, rules, thresholds and market history have not been changed.
This is not the final dissertation submission or a complete reproducibility package.
The separate CS7003SR XGBoost coursework is not included.

Credentials, personal notification settings, trading-account records, logs,
notification state, backups, generated pages and market-data CSV files are omitted.
Do not upload the live V2 directory or copy a real .env file into this repository.
No licence grant for third-party market data is implied.

## Main files

| File | Purpose |
| --- | --- |
| analysis.py | Data validation, A+B candidates, deduplication and correlation groups |
| build_top2_package.py | Current evaluation entry point: all 20 group/horizon comparisons |
| v2_pages.py and v2_commercial.py | Research and demonstration pages |
| v2_i18n.py | English/Chinese presentation support |
| v2_signal_calendar.py and v2_sample_summary.py | Calendar and sample summaries |
| update_v2_data.py | Optional IBKR/FRED data update |
| signal_notifications.py and alerting.py | Forecast and notification helpers |
| app.py | Retained earlier application interface; not the current 20-comparison entry point |
| tests/ | Original test source; most tests require the omitted local data |

## Method

1. A: actual real yield exceeds its value five gold sessions earlier.
2. B: current gold close exceeds the minimum close of the preceding five sessions.
3. Deduplicate A+B candidates with a minimum five-session gap, then classify
   five-session raw-level Pearson correlation: positive >= +0.80, negative <= -0.80.

Evaluate horizons 1 through 10 for each extreme group, using common historical
samples with all ten future sessions observed. A result is up when the Nth
subsequent session close exceeds the first subsequent session open.
Proportions are historical gross outcomes, not guaranteed future probabilities
or returns after trading costs. Shared samples must not be counted twice.

Before 2 October 2026, V2 preserves the original TradingView/OANDA history and
exported correlation values. From that boundary, gold uses IBKR XAUUSD MIDPOINT
daily bars and yields use FRED DFII10. Correlation pairs each gold date with the
latest formal FRED observation strictly earlier than that gold date, using the
full FRED observation calendar. Carried values retain their actual observation dates.

## Offline use with authorised data

Python 3.10 or newer is required; this review snapshot is checked with Python 3.14.
Offline analysis uses the Python standard library and does not need TWS or credentials.

The historical data are **not in this upload**. To reproduce actual V2 rankings,
obtain a permitted copy through an agreed assessment channel and place:

- `data/market_data.csv` (preserved original export)
- `data/market_data_pine5_raw_recalc_preview.csv` (current analysis input)
- `tests/fixtures/v2_legacy_same_day_20261002.csv` (frozen legacy regression fixture,
  required by selected layout tests; not the corrected current ranking)

Do not substitute random or synthetic data and describe it as the project's
historical evidence. No full historical reproduction is claimed without these files.

From the repository root, after providing the authorised data:

```text
python -B build_top2_package.py
```

Open `output/top2_pine5_20261004/index_en.html` for the English entry page.
The build also creates the Chinese pages and CSV result tables.

Original tests can then be run with:

```text
python -B -m unittest discover -s tests -v
```

Tests that check generated pages also require a successful build first. Running
the entire test suite in this source-only repository without data will fail.

## Optional live updates

Live updating additionally requires an authorised IBKR TWS API installation
(`ibapi`), an already logged-in TWS with its API kept read-only, appropriate
data permissions and a personal FRED API key stored only in a local `.env`.
The default endpoint is 127.0.0.1:7496. The code does not place trading orders.
Do not run live updates merely to view the source or evaluate offline results.
Notification delivery is not configured in this review copy. No messages are
sent by preparing or uploading these source files.

## Assessment access

Keep the GitHub repository private and grant the designated assessors access.
Uploading code alone does not grant a teacher access to a private repository.
The dissertation should describe existing V2 work, subsequent evaluation work,
external sources and any development assistance accurately.
