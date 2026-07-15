# Lab 8 - Financial Analyst with the `xlsx` Skill

**Section**: 10 - Skills
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> Run the notebook [`code/lab_08_financial_analyst/lab08.ipynb`](code/lab_08_financial_analyst/lab08.ipynb) top to bottom in Udemy Labs (nothing to install). It is the whole lab; the sections below mirror it, and the Claude Code path at the end is an optional bonus.

---

## Goal: Overview

Build a financial-analyst agent that turns a CSV of monthly revenue into a
polished Excel workbook: formatted sheets, live formulas, totals, and charts.
The work is done by attaching the prebuilt **`xlsx`** skill, which loads
reactively the moment the task is about spreadsheets, so your system prompt
stays lean.

This lab creates its **own dedicated data-science environment** with pandas,
numpy, and matplotlib. That keeps Lab 8 independent: you can run it without
first completing Lab 4 or copying an environment id between notebooks.

By the end you will have a real `.xlsx` on disk that opens in Excel with a
chart and working formulas, retrieved from the session via the Files API.

**Estimated cost:** a few cents.

---

## Prereqs: Prerequisites

- **Python SDK** installed and `ANTHROPIC_API_KEY` set.
- A Managed Agents cloud environment will be created by this lab with pandas,
 numpy, and matplotlib.
- **The prebuilt `xlsx` skill** (an Anthropic-maintained office skill). You
 attach it by `skill_id`; nothing to install.
- The sample `revenue.csv` lives next to the script in
 [`code/lab_08_financial_analyst/`](code/lab_08_financial_analyst/).

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Steps: Python path

The runnable script is
[`code/lab_08_financial_analyst/lab08.py`](code/lab_08_financial_analyst/lab08.py).
The steps below mirror it.

### Step 1 - Create a dedicated data-science environment

Create a Lab 8-specific cloud environment with pandas, numpy, and matplotlib.
This avoids a hard dependency on Lab 4 while keeping the same analysis stack.

```python
from anthropic import Anthropic

client = Anthropic()
BETAS = ["managed-agents-2026-04-01"]

env = client.beta.environments.create(
 name="financial-analyst-data",
 config={
 "type": "cloud",
 "packages": {
 "pip": ["pandas==2.2.0", "numpy", "matplotlib"],
 },
 "networking": {"type": "unrestricted"},
 },
 betas=BETAS,
)
print(f"env.id = {env.id}")
```

### Step 2 - Attach the prebuilt `xlsx` skill to the agent

Create the agent with the full toolset and attach the `xlsx` skill by ID. The
skill is loaded on demand, so it costs nothing on turns that are not about
spreadsheets.

```python
agent = client.beta.agents.create(
 name="Financial Analyst",
 model="claude-haiku-4-5-20251001",
 system=(
 "You are a financial analyst. Produce clean, professional Excel "
 "workbooks. Always use the xlsx skill for spreadsheet output. "
 "Place all deliverables in /mnt/session/outputs/."
 ),
 tools=[{"type": "agent_toolset_20260401"}],
 skills=[{"type": "anthropic", "skill_id": "xlsx"}],
 betas=BETAS,
)
print(f"agent.id = {agent.id}")
```

### Step 3 - Upload and mount `revenue.csv`

Upload the CSV, then mount it into the session at a known path so the agent can
read it.

```python
from pathlib import Path

csv = client.beta.files.upload(file=Path("revenue.csv"), betas=BETAS)
print(f"file.id = {csv.id}")

session = client.beta.sessions.create(
 agent={"type": "agent", "id": agent.id, "version": agent.version},
 environment_id=env.id,
 resources=[{
 "type": "file",
 "file_id": csv.id,
 "mount_path": "/workspace/revenue.csv",
 }],
 title="Revenue summary workbook",
 betas=BETAS,
)
print(f"session.id = {session.id}")
```

### Step 4 - Ask the agent to analyze the CSV and produce a formatted `.xlsx`

Be explicit about the sheets, formulas, charts, and the output path. The agent
loads the `xlsx` skill the moment it sees an Excel request and writes the file
to `/mnt/session/outputs/`.

```python
with client.beta.sessions.events.stream(session.id) as stream:
 client.beta.sessions.events.send(session.id, events=[{
 "type": "user.message",
 "content": [{
 "type": "text",
 "text": (
 "Analyze /workspace/revenue.csv and build a polished Excel "
 "workbook. Include a 'Summary' sheet with monthly revenue, "
 "cost, margin, and margin % columns, a 'Totals' row, and "
 "month-over-month growth %. Add a column chart of revenue "
 "by month and a line chart of margin %. Format headers, "
 "currency, and percentages cleanly. Save the workbook to "
 "/mnt/session/outputs/revenue_summary.xlsx."
 ),
 }],
 }])
 for event in stream:
 if event.type == "agent.tool_use":
 print(f"\n[tool: {event.name}]")
 elif event.type == "agent.message":
 for b in event.content:
 if b.type == "text":
 print(b.text, end="", flush=True)
 elif event.type == "session.status_idle":
 print("\n--- session idle ---")
 break
```

### Step 5 - Retrieve the workbook via the Files API

List the files the session produced and download the `.xlsx` locally.

```python
out_dir = Path("outputs")
out_dir.mkdir(exist_ok=True)
for f in client.beta.files.list(scope_id=session.id, betas=BETAS):
 print(f.id, f.filename)
 if f.filename.endswith(".xlsx"):
 client.beta.files.download(f.id).write_to_file(str(out_dir / f.filename))
 print(f"saved: {out_dir / f.filename}")
```

---

## Bonus (optional): Claude Code

Not required: the notebook above is the whole lab. If you want to try agentic engineering, open this folder in Claude Code and paste the prompts in order.

**Prompt 1 - build and run the analyst with its own environment:**

> "Create a Managed Agents cloud environment named `financial-analyst-data` that
> pre-installs pandas pinned to 2.2.0, numpy, and matplotlib, with unrestricted
> networking. Then create a Managed Agents agent named `Financial Analyst` on
> `claude-haiku-4-5-20251001` with the full agent toolset and the prebuilt
> **`xlsx`** skill attached (`skill_id` `xlsx`). System prompt: it is a financial
> analyst that always uses the xlsx skill and writes deliverables to
> `/mnt/session/outputs/`. Upload `revenue.csv` and mount it at
> `/workspace/revenue.csv`. Start a session on that environment, then ask the
> agent to analyze the CSV and build a polished `.xlsx` with a Summary sheet
> (revenue, cost, margin, margin %, a Totals row, month-over-month growth %), a
> column chart of revenue, and a line chart of margin %, saved to
> `/mnt/session/outputs/revenue_summary.xlsx`. Stream the response."

**Prompt 2 - retrieve the file:**

> "List the files this session produced and download the `.xlsx` into a local
> `outputs/` folder."

**Prompt 3 (optional) - sharpen the deliverable:**

> "If the workbook is missing a chart or the formulas are static values, send a
> follow-up asking the agent to add a column chart of revenue by month and use
> live Excel formulas for the Totals row."

---

## Expected: Expected output

- The agent loads the `xlsx` skill reactively once the task mentions Excel.
- Tool calls stream by: `read` the CSV, `bash` to build the workbook, `write`
 the output.
- A polished `revenue_summary.xlsx` lands in `/mnt/session/outputs/` with:
 formatted headers, revenue / cost / margin / margin % columns, a Totals row,
 month-over-month growth, and a column chart plus a line chart.
- The workbook downloads into your local `outputs/` folder and opens cleanly in
 Excel with live formulas and charts.
- Session status moves `running` → `idle`.

---

## Troubleshooting

- **Skill not loaded / no Excel output** → confirm
 `skills=[{"type": "anthropic", "skill_id": "xlsx"}]` is on the agent. The
 skill only loads when the task reads as a spreadsheet request, so make the
 prompt clearly about an `.xlsx` workbook.
- **The 20-skill ceiling** → a session may attach at most **20 skills**, counted
 across all agents in the session. This lab uses one (`xlsx`); if you also add
 `docx` or `pptx` in the stretch, stay well under the limit and only attach
 what the agent actually uses.
- **Environment creation fails** → confirm your Anthropic API key has Managed
 Agents access and rerun the environment creation step. This lab creates its own
 `financial-analyst-data` environment, so no Lab 4 `ENV_ID` is required.
- **File not in outputs** → only files written to the exact path
 `/mnt/session/outputs/` are collected by the Files API. If nothing downloads,
 tell the agent explicitly to save to that directory.
- **Retrieval returns nothing** → list with the same `betas` and use
 `scope_id=session.id`. Filter on `.xlsx` so you skip the mounted input CSV.

---

## Stretch: Stretch

- **Add a Word summary.** Attach the `docx` skill alongside `xlsx` and ask for a
 one-page `.docx` executive summary of the workbook (headline numbers, trend,
 one chart image). Two office skills, still well under the 20-skill ceiling.
- **Pivot tables.** Ask the agent to add a pivot-table sheet that breaks revenue
 and margin out by quarter, with a quarter-over-quarter comparison.
- **Generalize it.** Wrap the flow in a function that takes any CSV path and
 output name, then run it against a second CSV to confirm it generalizes
 without code changes.

---

## What you've learned

- How to attach an Anthropic prebuilt skill (`xlsx`) by `skill_id` and rely on
 reactive, on-demand loading to keep system prompts lean.
- That skills produce real binary artifacts: a formatted Excel workbook, not
 just text.
- How to create a dedicated cloud environment for a skill-backed workflow.
- The upload → mount → outputs → Files API flow for working with user files end
 to end.
