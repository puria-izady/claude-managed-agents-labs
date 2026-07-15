# Lab 5 - Streaming REPL with a Live Cost Meter

**Section**: 7 - The Event Stream
**Estimated time**: 20–25 minutes
**Path**: Python + Claude Code

---

## Goal: Goal
Build a tiny streaming console. You chat with one persistent session, the agent's text and tool use stream into your terminal live, and a running cost ticker updates on the session after every turn. By the end you can read the streaming event loop, surface tool calls in band, and turn `session.usage` into a dollar figure on your own UI.

**Estimated cost:** a few cents.

> **About the cost number:** the meter prints a list-price estimate from `session.usage` plus Managed Agents active runtime. It is not an authoritative invoice. Check Claude Console billing for final cost.

## Prereqs: Prerequisites
- Python SDK installed (`pip install anthropic`).
- A working API key exported as `ANTHROPIC_API_KEY`.
- Optional: an agent ID and environment ID from an earlier lab (Lab 2 or Lab 4). If you do not set them, the script creates a fresh agent and a plain cloud environment for you.

---

## Steps: Python path

Full runnable script: [`code/lab_05_streaming_repl/lab05.py`](code/lab_05_streaming_repl/lab05.py) plus the shared cost helper [`code/shared/cost_meter.py`](code/shared/cost_meter.py).

### Step 1 - Create the agent, environment, and session
Reuse an agent and env if you have them, otherwise create them once. Then start a single session that the whole REPL will talk to.

```python
import os, sys
from pathlib import Path
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from cost_meter import print_session_cost

BETAS = ["managed-agents-2026-04-01"]
MODEL = os.environ.get("MODEL", "claude-haiku-4-5-20251001")

client = Anthropic()

agent = client.beta.agents.create(
 name="Streaming Console",
 model=MODEL,
 system=(
 "You are a concise console assistant. Use the bash tool to inspect "
 "the workspace when asked. Keep replies short."
 ),
 tools=[{"type": "agent_toolset_20260401"}],
 betas=BETAS,
)

env = client.beta.environments.create(
 name="streaming-repl",
 config={"type": "cloud", "networking": {"type": "unrestricted"}},
 betas=BETAS,
)

session = client.beta.sessions.create(
 agent=agent.id,
 environment_id=env.id,
 title="Lab 5 streaming REPL",
 betas=BETAS,
)
print(f"session.id = {session.id}")
```

### Step 2 - Read user input in a loop
A plain `input()` loop. Reserve two words: `quit` to leave, and `interrupt` to halt the agent mid-run while keeping the session alive.

```python
while True:
 user = input("you> ").strip()
 if not user:
 continue
 if user.lower() in {"quit", "exit"}:
 break
 if user.lower() == "interrupt":
 client.beta.sessions.events.send(
 session.id, events=[{"type": "user.interrupt"}], betas=BETAS,
 )
 continue
 # ... send + stream (Step 3)
```

### Step 3 - Stream events and print agent text + tool use live
Open the stream, send the turn, then iterate events as they arrive. Print `agent.message` text as it streams, and surface every `agent.tool_use` in band so the user watches the agent reach for a tool.

```python
 with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
 client.beta.sessions.events.send(
 session.id,
 events=[{
 "type": "user.message",
 "content": [{"type": "text", "text": user}],
 }],
 betas=BETAS,
 )
 sys.stdout.write("agent> "); sys.stdout.flush()
 for event in stream:
 if event.type == "agent.message":
 for block in event.content:
 if block.type == "text":
 sys.stdout.write(block.text); sys.stdout.flush()
 elif event.type == "agent.tool_use":
 sys.stdout.write(f"\n [tool: {event.name}]\n ")
 sys.stdout.flush()
 elif event.type == "session.status_idle":
 show_cost(client, session.id) # Step 4
 break
```

### Step 4 - Read usage off the session and show a running cost
Usage is cumulative across the whole session, so re-fetch the session after each `session.status_idle` and feed the retrieved session into the shared meter. The total climbs turn over turn.

```python
def show_cost(client, session_id):
 print_session_cost(client, session_id, MODEL, betas=BETAS)
```

The shared helper multiplies input, output, cache read/write tokens, and active runtime by current public list-price constants. It is still only a teaching estimate; billing in the Claude Console is authoritative.

### Step 5 - Run it and interact
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python lab05.py
```
Try:
- `What's in /workspace?`
- `Read /etc/os-release.`
- Type `interrupt` mid-run to halt the agent (state is preserved).
- Type `quit` to exit and print the final total.

## Claude Code: Claude Code path
> Open this folder in Claude Code and paste:

> "Write a small Python REPL `lab05.py` for the Claude Managed Agents beta (`betas=['managed-agents-2026-04-01']`, all calls on `client.beta.*`). Create an agent on `claude-haiku-4-5-20251001` with the full toolset `{'type': 'agent_toolset_20260401'}` and a short system prompt, create a plain cloud environment, and start one session. Then loop on `input()`: send each line as a `user.message` and open `client.beta.sessions.events.stream(...)`. In the stream, print `agent.message` text live and print every `agent.tool_use` as `[tool: <name>]` in band. On `session.status_idle`, re-fetch the session and print a running cost meter computed from `session.usage`. Support `interrupt` (send a `user.interrupt` event) and `quit`."

> Then paste:

> "Use the shared `code/shared/cost_meter.py` helper. On every `session.status_idle`, re-fetch the session id, print the per-session estimate, and print the total across all session ids passed to the helper. Label the number as an estimate and point students to Claude Console billing for authoritative cost."

## Expected: Expected output
- A `session.id` line, then a `you>` prompt.
- Agent text streaming character by character after `agent> `.
- A `[tool: bash]` (or similar) marker every time the agent invokes a tool.
- An `Estimated lab cost` block after each turn, with one row per session id and a total.
- `interrupt` halts the agent and returns you to the prompt; `quit` prints a final total and exits.

Example shape:
```
session.id = session_01ab...
you> What's in /workspace?
agent>
 [tool: bash]
 The workspace contains: README.md, data/, notebooks/.
Estimated lab cost (USD, list-price estimate):
  session sesn_01ab...: $0.0123 (4180 in / 96 out; 0 cache read / 0 cache write; 34.0s runtime)
  total across 1 session(s): $0.0123
  total tokens: 4180 input / 96 output; 0 cache read / 0 cache write
  total active runtime: 34.0s

you> quit

Final total:
Estimated lab cost (USD, list-price estimate):
  session sesn_01ab...: $0.0123 (4180 in / 96 out; 0 cache read / 0 cache write; 34.0s runtime)
  total across 1 session(s): $0.0123
  total tokens: 4180 input / 96 output; 0 cache read / 0 cache write
  total active runtime: 34.0s
Goodbye.
```

## Troubleshooting
- **The stream disconnects or hangs mid-turn** → SSE is one long-lived connection; a dropped network or proxy timeout closes it. The `with ... stream(...)` block re-opens cleanly on the next turn. To recover an in-flight turn after a hard drop, list past events (`client.beta.sessions.events.list(session.id, betas=BETAS)`) to catch up, then send your next message to resume. Never reuse a closed stream object.
- **Cost is always $0.00 or `usage` is `None`** → read usage only after `session.status_idle`; before that the totals may be empty. The helper uses `getattr(usage, ..., 0)` so a partial usage object will not crash, it just reads as zero. Re-fetch with `client.beta.sessions.retrieve(...)` rather than reading the stale create-time session object.
- **The cost number looks wrong** → it is a list-price estimate, not an invoice. The helper reads `session.usage` and `session.stats.active_seconds`; usage is cumulative for the session, so the total only ever grows within one session. For the authoritative figure, use Claude Console billing.
- **REPL never returns to the prompt** → make sure you `break` on `session.status_idle`. If the agent is waiting on a custom tool or human review (`requires_action`), this simple loop will sit waiting; that path is covered in Lab 7.
- **`agent.id` / `env.id` unknown** → if you set `AGENT_ID` or `ENV_ID`, confirm they exist in your workspace; otherwise leave them unset and let the script create fresh ones.

## Stretch: Stretch
- **Color the output** with the `rich` library: tool markers cyan, agent text default, the cost line green. A console that color-codes tool use reads far better in a screencast.
- **Per-tool counts:** keep a `collections.Counter` keyed on `event.name` and print a small `bash x3, str_replace x1` summary alongside the cost on each `session.status_idle`.
- **Budget cap:** stop accepting input once the estimated running total crosses a threshold (e.g. $0.50) and print a warning.
- **Resume across runs:** persist `session.id` to a dotfile and offer to reattach to it on the next launch instead of creating a new session.

## What you've learned
- The streaming event loop in detail: open a stream, send a turn, consume `agent.message`, `agent.tool_use`, and `session.status_idle`.
- How to surface tool use live so a user can watch the agent work.
- How to read `session.usage` off a re-fetched session and turn it into a running cost on your own UI.
- That any cost figure you compute client-side is only as good as your rate table and observable usage fields, so keep it labelled as an estimate and source final numbers from the Console.
