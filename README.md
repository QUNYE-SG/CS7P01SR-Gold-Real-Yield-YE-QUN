# Gold and US Ten-Year Real Yield Signal System

CS7P01SR dissertation project, YE QUN.

**Design and Historical Evaluation of a Gold and US Ten-Year Real Yield Signal System**

## Repository status

This repository provides a source-only review snapshot of the existing V2 system.
The author has chosen public source-code access. Public access to this repository
does not mean that a live dashboard or trading service has been deployed.
This is not the completed dissertation or a self-contained historical-data package.
The separate CS7003SR XGBoost coursework is not included.

The application Python files and Windows launchers are unchanged copies of V2.
Email literals in two test files were consistently replaced with example.invalid
addresses. No signal rules or thresholds were changed. The live V2 installation
and its market history were not modified during preparation or verification.

Excluded from this repository:

- Real credentials, `.env`, account records and private notification settings.
- Market-data CSV files, the historical regression fixture and generated results.
- Notification state, logs and backups.

Never upload the live V2 folder or a real `.env` file. The `.env.example` file is
an empty configuration template, not a usable API key. The `.gitignore` file is
a precaution, not a substitute for inspecting files selected for browser upload.

## Main entry points

| File | Purpose |
| --- | --- |
| `analysis.py` | CSV validation, A+B candidates, deduplication and correlation classification |
| `build_top2_package.py` | Current offline evaluation: all 20 group/horizon comparisons |
| `v2_pages.py`, `v2_commercial.py` | Research and demonstration page generation |
| `v2_i18n.py` | English and Chinese page support |
| `v2_signal_calendar.py`, `v2_sample_summary.py` | Calendar and sample summaries |
| `update_v2_data.py` | Optional live IBKR/FRED data update |
| `signal_notifications.py`, `alerting.py` | Forecast and notification helpers |
| `app.py` | Earlier application interface; not the current 20-comparison entry point |
| `tests/` | Original test source, with test email addresses anonymised where needed |

## Method

1. A: the actual real yield exceeds its value five gold sessions earlier.
2. B: the current gold close exceeds the minimum close in the preceding five sessions.
3. Deduplicate A+B candidates with a minimum five-session gap, then classify the
   five-session raw-level Pearson correlation: positive >= +0.80 or negative <= -0.80.

Evaluate horizons 1 to 10 separately for each extreme group, producing 20
comparisons. Historical comparisons use common samples with all ten subsequent
sessions observed. An outcome is up when the Nth subsequent session close exceeds
the first subsequent session open. These are historical gross outcomes, not
guaranteed future probabilities or returns after transaction costs. Horizons in
the same group share events and their sample counts must not be added together.

Before 2 October 2026, V2 preserves the original TradingView/OANDA history and
exported correlation values. From that boundary, gold uses IBKR XAUUSD MIDPOINT
daily bars and yields use FRED DFII10. For correlation, each gold date is paired
with the latest formal FRED observation strictly earlier than that gold date,
using the full FRED observation calendar. Carried values retain their observation dates.

## Offline reproduction

Use Python 3.10 or newer. Verification described below used Python 3.14.
Offline analysis uses the standard library and does not require TWS or credentials.

**The data are not included. Downloading this repository alone is insufficient
to reproduce the full historical results or run the entire test suite.**
Obtain an authorised copy through an agreed assessment channel and place these
files under the repository root:

```text
data/market_data.csv
data/market_data_pine5_raw_recalc_preview.csv
tests/fixtures/v2_legacy_same_day_20261002.csv
```

The first file is the preserved original export. The second is the current
analysis input. The third is a frozen legacy layout-regression fixture, not the
corrected current ranking. No redistribution rights for third-party data are
implied. Do not describe synthetic replacements as the project's historical evidence.

From the repository root, with the authorised data in place:

```text
python -B build_top2_package.py
python -B -m unittest discover -s tests -v
```

Build before testing because some tests inspect generated pages.
Open `output/top2_pine5_20261004/index_en.html` for the English entry page, or
`output/top2_pine5_20261004/index.html` for Chinese. The build also produces
`ranking_20.csv`, `eligible_70_plus.csv`, `signal_details.csv` and a result ZIP.

## Local verification on 28 October 2026

The distributed source ZIP was extracted into an independent local folder and
supplied with the existing authorised local data. No live update was performed.

- Dataset: 2,858 daily rows, 2 October 2015 to 27 October 2026.
- Build completed successfully and generated all six Chinese/English pages.
- All **100 tests passed**, with no failures, errors or skipped tests.
- All 20 comparison rows matched the existing V2 result table.
- The packaged input CSV matched the local analysis input byte for byte.
- All six pages loaded in an isolated browser without JavaScript exceptions,
  broken images or missing local file links in the checks performed.
- V2 source files and historical data remained unchanged.

The successful test run used a temporary directory inside the verification
workspace. Network connections were blocked during Python verification and
external HTTP requests were blocked during browser checks. This was local
offline verification, not GitHub Actions, a live brokerage test or a mail-delivery test.
These results apply to the stated source/data snapshot, not all future updates.

## Optional live updates and alerts

Live updates additionally require the official IBKR TWS API Python package
(`ibapi`), an already logged-in TWS kept in API read-only mode, the required data
permissions and a personal FRED key stored only in a local `.env`.
The default endpoint is `127.0.0.1:7496`. The program does not place trading orders.
Do not run live updates merely to review source code or evaluate offline results.

Notification delivery is not configured in this source snapshot. Preparing,
uploading or offline-testing these files does not send live alerts.

## Academic scope

The dissertation must distinguish existing V2 implementation from subsequent
evaluation work, acknowledge external sources and describe development assistance
accurately. Public code access does not replace the dissertation, its historical
data access arrangements or any other assessment requirements.
