# Lab 7 - Human-in-the-Loop Checkpoint

**Section**: 9 - Permission Policies & Safety
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> Run the notebook [`labs/code/lab_07_hitl/lab07.ipynb`](code/lab_07_hitl/lab07.ipynb) top to bottom in Udemy Labs or on your own machine. The steps below mirror it. The standalone script [`lab07.py`](code/lab_07_hitl/lab07.py) is the same flow as a CLI program.

---

## Goal: Overview

Build an agent that pauses for explicit human approval before every `bash`
command and before any `write` to a path outside `/tmp/`. You will set a
toolset default of `always_allow` so read-only tools run freely, then override
`bash` and `write` to `always_ask`. In your client you handle the server-side
confirmation flow: the session pauses in a `requires_action` state, you prompt
the operator, and you reply with a `user.tool_confirmation` that either allows
the action or denies it with a message the model can learn from.

By the end you will have seen all three behaviors live: an approval prompt
before a gated action, an `allow` that resumes the run, and a `deny` whose
message reroutes the agent toward a safer approach.

**Estimated cost:** a few cents.

---

## Prereqs: Prerequisites

- **Python SDK** installed (`pip install anthropic`) and `ANTHROPIC_API_KEY` set.
- An existing agent ID is optional. Step 1 builds a fresh one.
- A terminal where you can type at `input()` prompts (this lab is interactive).

---

## Steps: Python path

The runnable script is [`labs/code/lab_07_hitl/lab07.py`](code/lab_07_hitl/lab07.py).
The steps below mirror it.

### Step 1 - Create the agent with a selective `always_ask` policy

Set the toolset `default_config` to `always_allow`, then use `configs` to
override `bash` and `write` to `always_ask`. This is the common production
shape: let safe tools run, gate the mutating ones.

```python
from anthropic import Anthropic

client = Anthropic()

agent = client.beta.agents.create(
 name="HITL Coding Assistant",
 model="claude-haiku-4-5-20251001",
 system=(
 "You are a careful coding assistant. Explain what you will do "
 "before doing it, then take one action at a time. Never assume "
 "approval: wait for the confirmation result. If an action is "
 "denied, read the reason and propose a safer alternative."
 ),
 tools=[{
 "type": "agent_toolset_20260401",
 "default_config": {"permission_policy": {"type": "always_allow"}},
 "configs": [
 {"name": "bash", "permission_policy": {"type": "always_ask"}},
 {"name": "write", "permission_policy": {"type": "always_ask"}},
 ],
 }],
)
```

### Step 2 - Write the policy: auto-allow `/tmp/`, ask otherwise

The policy decides what to do with each pending tool_use. Writes under `/tmp/`
are low-risk scratch space, so let them through. Everything else escalates to a
stdin prompt that returns `allow`, a bare `deny`, or a `deny` with a reason.

```python
def decide(event_id, recent_events):
 """Return ('allow' | 'deny', optional_deny_message)."""
 target = next(
 (e for e in recent_events if getattr(e, "id", None) == event_id),
 None,
 )
 if target is None:
 return "deny", "Internal error: missing tool_use event."

 # Auto-allow writes under /tmp/.
 if target.name == "write":
 path = (target.input or {}).get("path", "")
 if path.startswith("/tmp/"):
 return "allow", None

 print(f"\n[approval needed] {target.name} -> {target.input}")
 ans = input(" approve? [y / N / explain <reason>] ").strip().lower()
 if ans == "y":
 return "allow", None
 if ans.startswith("explain"):
 reason = ans[len("explain"):].strip()
 return "deny", reason or "I'd rather not, please try another way."
 return "deny", "Denied by the operator. Do not retry this exact action."
```

### Step 3 - Drive the session and handle `requires_action`

Stream the session. When you reach `session.status_idle` with a
`requires_action` stop reason, run `decide()` for each blocking event id and
send one `user.tool_confirmation` per id. Send a confirmation for *every* id,
or the session deadlocks. Keep a running `recent` list so `decide()` can look
up the tool_use behind each id.

```python
env = client.beta.environments.create(
 name="hitl-env",
 config={"type": "cloud", "networking": {"type": "unrestricted"}},
)
session = client.beta.sessions.create(
 agent={"type": "agent", "id": agent.id, "version": agent.version},
 environment_id=env.id,
 title="HITL demo",
)

recent = []
with client.beta.sessions.events.stream(session.id) as stream:
 client.beta.sessions.events.send(session.id, events=[{
 "type": "user.message",
 "content": [{"type": "text", "text":
 "Write a hello-world Python script to /workspace/hello.py "
 "and then run it with python."}],
 }])
 for event in stream:
 recent.append(event)
 if event.type == "agent.message":
 for b in event.content:
 if b.type == "text":
 print(b.text, end="", flush=True)
 elif event.type == "agent.tool_use":
 print(f"\n[tool requested: {event.name}]")
 elif event.type == "session.status_idle":
 sr = getattr(event, "stop_reason", None)
 if sr and sr.type == "requires_action":
 for eid in sr.event_ids:
 choice, msg = decide(eid, recent)
 body = {"type": "user.tool_confirmation",
 "tool_use_id": eid, "result": choice}
 if choice == "deny" and msg:
 body["deny_message"] = msg
 client.beta.sessions.events.send(session.id, events=[body])
 else:
 break
```

### Step 4 - Exercise both paths

Run it with `python lab07.py`. The default task writes to `/workspace/hello.py`
(outside `/tmp/`) and then runs it, so both gated tools fire. First try
approving both with `y`. Then run again and `deny` the `bash` step (or use
`explain not on prod`) and watch the agent adapt.

To see the auto-allow rule, change the task to write to `/tmp/hello.py`. That
write passes with no prompt; only the `bash` run pauses.

---

## Bonus (optional): Claude Code

Not required - the notebook is the whole lab. To try driving it agentically, open this folder in Claude Code and use plain-English prompts:

> "Build me a Managed Agents agent called 'HITL Coding Assistant' on
> `claude-haiku-4-5-20251001`. Use the `agent_toolset_20260401` toolset with a
> `default_config` of `always_allow`, but override `bash` and `write` to
> `always_ask` via `configs`. Give it a system prompt telling it to explain
> before acting, take one action at a time, never assume approval, and propose
> a safer alternative when an action is denied."

Then:

> "Create an unrestricted cloud environment and start a session. Stream it,
> and whenever the session hits `session.status_idle` with a `requires_action`
> stop reason, for each blocking event id either auto-allow `write` when the
> path starts with `/tmp/`, or prompt me at stdin. Send one
> `user.tool_confirmation` per id, using `deny_message` when I deny. Ask it to
> write `/workspace/hello.py` and run it."

Then drive it interactively:

> "Run it. Approve the write but deny the bash step with the message 'not on
> prod', and show me how the agent reroutes."

---

## Expected: Expected output

- `session.id = ...` printed at the start.
- A `[tool requested: write]` line, then an approval prompt for the write to
 `/workspace/hello.py` (because it is outside `/tmp/`).
- A `[tool requested: bash]` line, then an approval prompt before the run.
- If you `allow` both: the script is written, runs, and prints hello-world; the
 session goes idle and exits cleanly.
- If you `deny` the `bash` step with a message: the next `agent.message`
 acknowledges the denial and proposes another approach instead of retrying the
 same command.
- If the task targets `/tmp/`: an `[auto-allow]` line appears for the write with
 no prompt; only `bash` pauses.

---

## Troubleshooting

- **No prompt appears.** Check the policy config shape in Step 1. The override
 lives in `configs` as `{"name": "bash", "permission_policy": {"type":
 "always_ask"}}`, and the `default_config` must be `always_allow`. If the
 task never needs `bash` or `write`, the model will not invoke them. Use a
 task that clearly requires both, or sharpen the instruction.
- **Session hangs after a confirmation.** You must send a
 `user.tool_confirmation` for *every* id in `requires_action.event_ids`. Miss
 one and the session stays paused. Loop over all the ids before continuing.
- **`requires_action` never fires.** Make sure you read `stop_reason` off the
 `session.status_idle` event (`getattr(event, "stop_reason", None)`) and check
 `sr.type == "requires_action"`. An idle event with no such stop reason means
 the turn finished; that is your signal to `break`.
- **`deny_message` looks ignored.** It is delivered to the model as context for
 the next turn, not echoed back to you. Read the following `agent.message` to
 see the adaptation. Only attach `deny_message` on the `deny` path.

---

## Stretch: Stretch

- **Path-aware write rule.** Already wired in the sample: auto-allow `write`
 when the path starts with `/tmp/`, otherwise ask. Extend it to a small
 allowlist of safe prefixes (for example `/tmp/` and `/workspace/scratch/`).
- **Denylist risky bash.** Before prompting, auto-deny any `bash` input matching
 `rm -rf`, `curl ... | sh`, or writes to system paths, with a clear
 `deny_message`.
- **Route approvals to Slack.** Replace the stdin prompt with a Slack message
 and button, and log every allow/deny decision to a CSV for audit.

---

## What you've learned

- Setting a toolset `default_config` and overriding individual tools via
 `configs`.
- Handling the `requires_action` confirmation flow end to end.
- Using `deny_message` as a soft constraint that steers the agent's next move.
- Layering your own policy (auto-allow `/tmp/`) on top of the platform's
 permission system.
