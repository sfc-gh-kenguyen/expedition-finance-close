# Expedition 2026 — Day 3: Close Faster, Audit Smarter

Hands-on lab for the **finance operations** track. Land three messy financial exports in Snowflake-managed Apache Iceberg tables, use CoCo to clean and reconcile them, surface discrepancies on a live Streamlit dashboard, and ask close-cycle questions in Snowflake CoWork.

## What's in this repo

| File / folder | Purpose |
|---|---|
| `lab.ipynb` | The notebook you'll run — markdown prompts + SQL cells |
| `data/` | Three CSV exports: `payroll_register.csv`, `gl_journal_entries.csv`, `bank_statement.csv` |
| `reconciliation_dashboard/` | Pre-built Streamlit reconciliation dashboard |

## Get started

Follow the published [Snowflake Developer Guide](https://developers.snowflake.com/solution/guides/) for step-by-step instructions, or open `lab.ipynb` in a Git-backed Workspace and work top-to-bottom.

## Prerequisites

- A free [Snowflake trial account](https://signup.snowflake.com/?utm_source=snowflake-devrel&utm_medium=developer-guides&trial=student&cloud=aws&region=us-east-2&utm_campaign=introtosnowflake&utm_cta=developer-guides) (AWS, US East Ohio)
