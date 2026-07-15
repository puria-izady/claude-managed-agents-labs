# Lab 08 - Financial analyst with the `xlsx` skill

A financial-analyst agent that turns `revenue.csv` into a polished Excel
workbook (formatted sheets, totals, live formulas, charts) using the prebuilt
**`xlsx`** skill. The workbook is written to `/mnt/session/outputs/` and
downloaded into `./outputs/`.

This lab creates its own `financial-analyst-data` cloud environment with pandas,
numpy, and matplotlib, so it does not depend on Lab 04.

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Files

- `lab08.py` - main script (creates the env, attaches the `xlsx` skill)
- `revenue.csv` - 12 rows of synthetic monthly revenue + cost data

## Run

```bash
uv run --project .. --env-file ../.env python lab08.py
```

## Expected output

```
env.id = env_01...
agent.id = agnt_01...
file.id  = file_01...
session.id = sesn_01...

[tool: read]
[tool: bash]
I've built revenue_summary.xlsx with a Summary sheet, totals, growth %, and two charts.
--- session idle ---
file_01... revenue.csv
file_02... revenue_summary.xlsx
saved: outputs/revenue_summary.xlsx
```

A `revenue_summary.xlsx` appears in `./outputs/`. Open it in Excel and verify:

- Revenue, cost, margin, and margin % columns, formatted cleanly
- A "Totals" row and month-over-month growth %
- A revenue column chart and a margin % line chart
- Computed columns use live Excel formulas, not literals

Stretch: add the `docx` skill in `lab08.py` and ask for a one-page summary too
(stay under the 20-skill ceiling).
