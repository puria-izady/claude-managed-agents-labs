# Lab 4 - A Data-Science Environment

**Section**: 6 - Cloud Environments
**Estimated time**: 15 minutes
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> **Run the notebook:** [`code/lab_04_data_science_env/lab04.ipynb`](code/lab_04_data_science_env/lab04.ipynb) - open it in Udemy Labs (nothing to install) and run top to bottom. The steps below mirror the notebook cell for cell.

---

## Goal: Goal
Build a reusable cloud environment with **pandas, numpy, and matplotlib** pre-installed, then run an agent that generates a small dataset and saves a chart PNG to `/mnt/session/outputs/`. You'll retrieve the PNG locally and confirm the package versions the agent reports.

**Estimated cost:** a few cents.

## Prereqs: Prerequisites
- Python SDK installed (`pip install anthropic`).
- A working API key exported as `ANTHROPIC_API_KEY`.

---

## Steps: Python path

Full runnable script: [`code/lab_04_data_science_env/lab04.py`](code/lab_04_data_science_env/lab04.py).

### Step 1 - Create the environment with pre-installed packages
Declare the packages **once** in the environment config. They are pre-installed at build time, so every session off this env starts ready. Pin what matters for reproducibility (pandas), let the rest float.

```python
from anthropic import Anthropic

client = Anthropic()

env = client.beta.environments.create(
 name="data-analysis",
 config={
 "type": "cloud",
 "packages": {
 # The data-science stack, pre-installed at build time.
 "pip": ["pandas==2.2.0", "numpy", "matplotlib"],
 },
 "networking": {"type": "unrestricted"},
 },
 betas=["managed-agents-2026-04-01"],
)
print(f"env.id = {env.id}")
```

### Step 2 - Create an agent on the built-in toolset
```python
agent = client.beta.agents.create(
 name="Data Analyst",
 model="claude-haiku-4-5-20251001",
 system=(
 "You are a data analyst. Use Python (pandas, numpy, matplotlib) via "
 "the bash tool. Always save chart images as PNG to "
 "/mnt/session/outputs/."
 ),
 tools=[{"type": "agent_toolset_20260401"}],
 betas=["managed-agents-2026-04-01"],
)
print(f"agent.id = {agent.id}")
```

### Step 3 - Start a session on the environment
```python
session = client.beta.sessions.create(
 agent=agent.id,
 environment_id=env.id,
 title="Generate a chart",
 betas=["managed-agents-2026-04-01"],
)
print(f"session.id = {session.id}")
```

### Step 4 - Ask it to generate a dataset and save a chart PNG
```python
with client.beta.sessions.events.stream(session.id) as stream:
 client.beta.sessions.events.send(session.id, events=[{
 "type": "user.message",
 "content": [{
 "type": "text",
 "text": (
 "First, print the installed pandas, numpy, and matplotlib "
 "versions. Then create a small DataFrame of 12 months of "
 "synthetic monthly revenue, plot it as a line chart with "
 "matplotlib, and save the figure to "
 "/mnt/session/outputs/revenue.png."
 ),
 }],
 }])
 for event in stream:
 if event.type == "agent.message":
 for b in event.content:
 if b.type == "text":
 print(b.text, end="", flush=True)
 elif event.type == "agent.tool_use":
 print(f"\n[tool: {event.name}]")
 elif event.type == "session.status_idle":
 print("\n--- session idle ---")
 break
```

### Step 5 - Retrieve the PNG
```python
from pathlib import Path

Path("outputs").mkdir(exist_ok=True)
for f in client.beta.files.list(scope_id=session.id,
 betas=["managed-agents-2026-04-01"]):
 print(f.id, f.filename)
 if f.filename.endswith(".png"):
 client.beta.files.download(f.id).write_to_file(f"./outputs/{f.filename}")
 print("saved:", f.filename)
```

## Claude Code: Bonus (optional): Claude Code
> Not required - the notebook is the whole lab. If you want to try agentic engineering, open this folder in Claude Code and say: "Create a Managed Agents **cloud environment** named `data-analysis` that pre-installs the pip packages pandas (pinned to 2.2.0), numpy, and matplotlib, with unrestricted networking. Then create an agent on `claude-haiku-4-5-20251001` with the full agent toolset and a system prompt telling it to use pandas/numpy/matplotlib and save charts as PNG to `/mnt/session/outputs/`. Start a session on that environment, ask it to print the installed package versions and to generate 12 months of synthetic revenue as a line chart saved to `/mnt/session/outputs/revenue.png`, stream the response, then download the PNG locally."

## Expected: Expected output
- The agent calls `bash` to run Python.
- It prints the installed versions: the **pinned pandas 2.2.0**, plus the latest numpy and matplotlib.
- A chart PNG (`revenue.png`) is written to `/mnt/session/outputs/` and downloaded into your local `outputs/` folder.
- Session status moves `running` → `idle`.

## Troubleshooting
- **`pip install` failed at build time** → check the package spec uses pip syntax (`pandas==2.2.0`, not `pandas:2.2.0`). The environment build fails as a whole if any package can't resolve; fix the offending pin and recreate the env.
- **Packages unreachable under limited networking** → if you switch `networking` to `limited`, the package managers can't reach PyPI unless you set `allow_package_managers: true`. Without it, the build can't fetch pandas/numpy/matplotlib.
- **`name already exists`** → environment names are unique per workspace. Archive the old env or pick a new name.
- **No output PNG** → confirm the agent saved to the exact path `/mnt/session/outputs/`. Files written elsewhere aren't collected by the Files API. If matplotlib opened an interactive backend, tell the agent to use `matplotlib.use("Agg")` before plotting.

## Stretch: Stretch
- Add `seaborn` to the pip list (`["pandas==2.2.0", "numpy", "matplotlib", "seaborn"]`) and ask the agent to restyle the chart with `seaborn`.
- Ask for **two charts**: the revenue line chart plus a bar chart of month-over-month growth; verify both PNGs land in outputs.
- **Verify reuse:** start a second session against the same env ID with a different prompt and confirm the packages are already present (no reinstall).

## What you've learned
- How to pre-install packages per manager in a cloud environment.
- That environments are reusable templates - one env, many isolated sessions.
- The mount-free output flow: agent writes to `/mnt/session/outputs/`, you pull the file via the Files API.
- Why `allow_package_managers` matters once you tighten networking.
