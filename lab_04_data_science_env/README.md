# Lab 04 - Data-science environment

Builds a reusable `data-analysis` cloud environment with **pandas + numpy + matplotlib** pre-installed, creates a Data Analyst agent on the built-in toolset, and runs a session that prints the package versions and saves a chart PNG to `/mnt/session/outputs/`. The PNG is downloaded into `./outputs/`.

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Run

```bash
python lab04.py
```

## Expected output

```
env.id = env_01...
agent.id = agnt_01...
session.id = sesn_01...

The installed versions are pandas 2.2.0, numpy 1.26..., matplotlib 3.9...
[tool: bash]
I've saved the line chart to /mnt/session/outputs/revenue.png.
--- session idle ---
file_01... revenue.png
saved: revenue.png
```

A `revenue.png` line chart appears in `./outputs/`, and the agent confirms the pinned pandas 2.2.0 plus the latest numpy and matplotlib.
