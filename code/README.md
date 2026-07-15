# Lab Code - Mastering Claude Managed Agents

Runnable reference implementations for the course labs. Each lab folder
contains the Python code that the matching `labs/lab_NN_*.md` spec walks you
through. The specs are the **authoritative** guide - these files are the
copy-paste artifact you end up with at the end of each lab.

## Layout

```
code/
├── README.md                ← you are here
├── .env.example             ← env vars every lab uses
├── pyproject.toml           ← shared uv project + Python deps
├── requirements.txt         ← pip-compatible dependency list
├── setup_uv.sh              ← creates .venv and registers the notebook kernel
├── shared/                  ← prompts / rubrics reused across labs
│   ├── cache_usage.py
│   ├── cost_meter.py
│   └── prompts.py
├── lab_01_console_agent/    ← no Python (Console-only lab)
├── lab_02_first_python_session/
│   └── lab02.py
├── lab_03_research_agent/
│   ├── lab03.py
│   └── prompts.py
├── …
└── lab_13_capstone/
    └── lab13.py
```

## Setup

```bash
./setup_uv.sh

cp .env.example .env
# Edit .env with your real keys
```

Required at minimum:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

For specific labs you'll also need:

| Lab | Extra env var |
|--|--|
| 03 - Research Agent | `GOOGLE_DOCS_VAULT_ID` |
| 06 - Linear/Slack MCP agent | `LINEAR_VAULT_ID`, optional `SLACK_VAULT_ID` |
| 12 - Bug-fixer + PR | `GITHUB_TOKEN`, `GITHUB_REPO_URL`, `GITHUB_VAULT_ID` |
| 13 - Capstone | `GOOGLE_DOCS_VAULT_ID`, `SLACK_VAULT_ID`, `SLACK_CHANNEL` |

## Running a lab

```bash
cd lab_02_first_python_session
uv run --project .. --env-file ../.env python lab02.py
```

No shell activation is required. `uv run --project ..` uses the shared
`code/.venv` environment from inside any lab folder, while keeping the
current working directory local to that lab.

## Running notebooks

Run `./setup_uv.sh` once, then open the notebook and select the Jupyter kernel:

```text
Managed Agents Labs (.venv)
```

The notebooks check that they are running on that `.venv` kernel. If the wrong
kernel is selected, switch kernels and restart the notebook.

Each lab prints the IDs it creates (agent, environment, session) so you can
reuse them in later labs.

## Prompt Caching And Cost

Anthropic's [prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
describe two Messages API paths: automatic caching with
`cache_control={"type": "ephemeral"}` on `messages.create`, or with block-level
`cache_control` breakpoints on stable content. These labs use Managed Agents
sessions, whose current SDK surface does not expose `cache_control` on
`agents.create`, `sessions.create`, or `sessions.events.send`.

For Managed Agents labs, verify cache behavior from the cumulative session
usage counters after the session goes idle:

```python
session = client.beta.sessions.retrieve(session.id, betas=BETAS)
usage = session.usage
print("cache read tokens:", getattr(usage, "cache_read_input_tokens", 0) or 0)
print("cache write tokens:", getattr(usage, "cache_creation_input_tokens", 0) or 0)
```

Lab 5's cost meter uses `shared/cache_usage.py` to print those counters after
each turn. For reliable cache hits, keep agent definitions, system prompts,
toolsets, and static mounted resources stable; put per-turn/user-specific
content in the user event, after the stable prefix.

Every session-based notebook also ends with a cost estimate cell backed by
`shared/cost_meter.py`. The helper re-fetches one or more session IDs, prints
one estimated price per session, then prints a total across those sessions. It
reads cumulative `session.usage` and adds Managed Agents active runtime from
`session.stats.active_seconds`. The estimate is useful for teaching and budget
awareness, but it is not an invoice: current Console billing is authoritative
and can include account-specific terms or billing adjustments.

## Course materials map

- **Lab specs** live in `../` (`lab_01_console_agent.md` etc.)
- **Lab code** lives here

When a spec says "Step 2 - Write the script" the code block in that step is
exactly the file in this folder.
