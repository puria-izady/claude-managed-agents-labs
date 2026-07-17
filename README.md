# Claude Managed Agents — Labs

Runnable reference code for the *Mastering Claude Managed Agents* Udemy
course. Each lab folder holds the code you end up with by the end of that
lab: the full narrated, step-by-step walkthrough is part of the course
itself.

<!-- TODO: add the Udemy course link once published -->

## Labs

| # | Lab |
|---|---|
| 1 | Console agent |
| 2 | First Python session |
| 3 | Research agent |
| 4 | Data-science environment |
| 5 | Streaming Agent Sessions |
| 6 | Linear + Slack MCP agent with Vaults |
| 7 | Human-in-the-loop |
| 8 | Financial analyst (`xlsx`) |
| 9 | DCF with outcome rubric |
| 10 | Customer-support memory |
| 11 | Research → Write → Fact-check |
| 12 | Bug-fixer that opens a PR |
| 13 | Capstone: personal research agent |

Each `lab_NN_*/` folder has its own `README.md` describing what the lab does,
what you'll end up with, and how to run it.

## Layout

```
README.md          ← you are here
.env.example        ← env vars every lab uses
pyproject.toml       ← shared uv project + Python deps
requirements.txt     ← pip-compatible dependency list
setup_uv.sh          ← creates .venv and registers the notebook kernel
shared/              ← prompts / rubrics reused across labs
lab_01_console_agent/    ← no Python (Console-only lab)
lab_02_first_python_session/
├── lab02.py
├── lab02.ipynb
└── README.md
…
lab_13_capstone/
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
| 06 - Linear + Slack MCP agent | `LINEAR_VAULT_ID` (contains both credentials), `SLACK_CHANNEL` |
| 12 - Bug-fixer + PR | `GITHUB_TOKEN`, `GITHUB_REPO_URL`, `GITHUB_VAULT_ID` |
| 13 - Capstone | `GOOGLE_DOCS_VAULT_ID`, `SLACK_VAULT_ID`, `SLACK_CHANNEL` |

## Running a lab

```bash
cd lab_02_first_python_session
uv run --project .. --env-file ../.env python lab02.py
```

No shell activation is required. `uv run --project ..` uses the shared
`.venv` environment from inside any lab folder, while keeping the current
working directory local to that lab.

## Running notebooks

Run `./setup_uv.sh` once, then open the notebook and select the Jupyter
kernel:

```text
Managed Agents Labs (.venv)
```

The notebooks check that they are running on that `.venv` kernel. If the
wrong kernel is selected, switch kernels and restart the notebook.

Each lab prints the IDs it creates (agent, environment, session) so you can
reuse them in later labs.

## Prompt caching and cost

Anthropic's [prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
describe two Messages API paths: automatic caching with
`cache_control={"type": "ephemeral"}` on `messages.create`, or with
block-level `cache_control` breakpoints on stable content. These labs use
Managed Agents sessions, whose current SDK surface does not expose
`cache_control` on `agents.create`, `sessions.create`, or
`sessions.events.send`.

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
one estimated price per session, then prints a total across those sessions.
It reads cumulative `session.usage` and adds Managed Agents active runtime
from `session.stats.active_seconds`. The estimate is useful for teaching and
budget awareness, but it is not an invoice: current Console billing is
authoritative and can include account-specific terms or billing adjustments.

## License

MIT, see [LICENSE](LICENSE). The lab code is reference material for learning
purposes: adapt it freely for your own projects.
