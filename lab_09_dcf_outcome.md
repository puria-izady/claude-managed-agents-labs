# Lab 9 - Meeting Notes Action Plan with an Outcome Rubric

**Section**: 11 - Outcomes
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> Run the notebook [`code/lab_09_outcome_rubric/lab09.ipynb`](code/lab_09_outcome_rubric/lab09.ipynb) top to bottom in Udemy Labs. The top-level handout keeps the old filename for slide compatibility, but the lab now uses a simpler meeting-notes action-plan case.

---

## Goal: Overview

Build an outcome-driven session that turns messy meeting notes into a structured
Markdown action plan. Instead of chatting with the agent and deciding for
yourself when the plan is good enough, you hand it a goal and a rubric and let a
separate grader score the work until it passes.

A conversational session is "you talk, it responds, you decide when to stop."
An outcome-driven session is "you define done, it iterates, and a separate
grader decides when it is done." You send a single `user.define_outcome` event
carrying a **description** of the goal and a **gradeable rubric**. A managed
grader scores each iteration against that rubric and feeds per-criterion gaps
back to the builder. The session loops build to grade to revise until the grader
returns `satisfied`, hits `max_iterations`, or is interrupted.

This lab is intentionally small and inexpensive. It creates a lightweight cloud
environment, mounts `meeting_notes.md`, and asks the agent to write
`/mnt/session/outputs/action_plan.md`.

**Estimated cost:** a few cents.

---

## Prereqs: Prerequisites

- **Python SDK** installed and `ANTHROPIC_API_KEY` set.
- The shared uv kernel `Managed Agents Labs (.venv)` if you run the notebook.
- The sample `meeting_notes.md` file in
  [`code/lab_09_outcome_rubric/`](code/lab_09_outcome_rubric/).

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Steps: Python path

The runnable script is
[`code/lab_09_outcome_rubric/lab09.py`](code/lab_09_outcome_rubric/lab09.py).
The steps below mirror it.

### Step 1 - Create the environment and agent

Create a lightweight cloud environment and a meeting action planner agent. No
package installs, internet egress, or prebuilt office skills are needed.

```python
from anthropic import Anthropic

client = Anthropic()
BETAS = ["managed-agents-2026-04-01"]

env = client.beta.environments.create(
 name="meeting-notes-outcome",
 config={
 "type": "cloud",
 "networking": {"type": "limited", "allowed_hosts": []},
 },
 betas=BETAS,
)
print(f"env.id = {env.id}")

agent = client.beta.agents.create(
 name="Meeting Action Planner",
 model="claude-haiku-4-5-20251001",
 system=(
 "You are an operations lead. Turn messy meeting notes into concise, "
 "source-grounded action plans. Do not invent owners, dates, or "
 "decisions. Write deliverables to /mnt/session/outputs/."
 ),
 tools=[{"type": "agent_toolset_20260401"}],
 betas=BETAS,
)
print(f"agent.id = {agent.id}")
```

### Step 2 - Upload and mount the meeting notes

Upload the source notes and mount them at a stable path inside the session.

```python
from pathlib import Path

notes = client.beta.files.upload(file=Path("meeting_notes.md"), betas=BETAS)
print(f"file.id = {notes.id}")

session = client.beta.sessions.create(
 agent={"type": "agent", "id": agent.id, "version": agent.version},
 environment_id=env.id,
 resources=[{
 "type": "file",
 "file_id": notes.id,
 "mount_path": "/workspace/meeting_notes.md",
 }],
 title="Meeting notes action plan",
 betas=BETAS,
)
print(f"session.id = {session.id}")
```

### Step 3 - Write a gradeable rubric

The rubric is a Markdown document the grader reads literally. Headings group
criteria into categories the grader scores independently; every bullet is one
pass/fail rule. Make each bullet testable.

```python
RUBRIC = """\
# Action Plan Rubric

## Decisions
- The output contains a "Decisions" section with at least 3 decisions from the notes
- The output does not invent decisions that are not supported by the notes

## Action Items
- The output contains an "Action Items" Markdown table with columns Owner, Task, Due Date, Priority, and Source Note
- The table contains at least 6 action items from the notes
- Each action item has a named owner when the notes provide one
- Missing due dates are written as "Needs date" instead of invented dates

## Risks and Open Questions
- The output contains a "Risks" section with at least 2 risks or blockers from the notes
- The output contains an "Open Questions" section with at least 2 unresolved questions from the notes

## Output Quality
- A single Markdown file is written to /mnt/session/outputs/action_plan.md
- The plan is concise, scannable, and uses only information from /workspace/meeting_notes.md
"""
```

### Step 4 - Send the outcome and stream grading

There is no `outcome` field on `sessions.create()`: an outcome is an **event**
you send next. Open the stream before sending so you do not miss the first
grader events. This lab uses `max_iterations=3` to keep cost predictable.

```python
with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
 client.beta.sessions.events.send(session.id, events=[{
 "type": "user.define_outcome",
 "description": (
 "Read /workspace/meeting_notes.md and create a concise action "
 "plan as Markdown. Include decisions, action items, risks, and "
 "open questions. Write the final file to "
 "/mnt/session/outputs/action_plan.md."
 ),
 "rubric": {"type": "text", "content": RUBRIC},
 "max_iterations": 3,
 }], betas=BETAS)

 for event in stream:
 if event.type == "span.outcome_evaluation_start":
 print(f"\n--- grading iteration {event.iteration} ---")
 elif event.type == "span.outcome_evaluation_end":
 print(f" result: {event.result}")
 if event.result == "needs_revision":
 print(f" feedback: {event.explanation[:240]}...")
 elif event.type == "agent.tool_use":
 print(f" [tool: {event.name}]")
 elif event.type == "session.status_idle":
 print("\n--- session idle ---")
 break
```

### Step 5 - Confirm the result and pull the deliverable

Read the final outcome result, then list the files written to
`/mnt/session/outputs/` and download the Markdown action plan.

```python
session = client.beta.sessions.retrieve(session.id, betas=BETAS)
for ev in session.outcome_evaluations:
 print(f"outcome {ev.outcome_id}: {ev.result}")

out_dir = Path("outputs")
out_dir.mkdir(exist_ok=True)
downloaded = False
for f in client.beta.files.list(scope_id=session.id, betas=BETAS):
 print(f.id, f.filename)
 if f.filename == "action_plan.md":
 client.beta.files.download(f.id).write_to_file(str(out_dir / f.filename))
 print(f"saved: {out_dir / f.filename}")
 downloaded = True

if not downloaded:
 raise RuntimeError("Could not find downloadable action_plan.md in session outputs.")
```

---

## Bonus (optional): Claude Code

Not required - the notebook above is the whole lab. If you want to try agentic
engineering, open this folder in Claude Code and paste the prompts in order.

**Prompt 1 - run the outcome-driven session:**

> "Using the Managed Agents SDK, create a lightweight cloud environment named
> `meeting-notes-outcome` with limited networking and no allowed hosts. Create a
> Managed Agents agent named `Meeting Action Planner` on
> `claude-haiku-4-5-20251001` with the full agent toolset. System prompt: it is
> an operations lead that turns messy meeting notes into concise,
> source-grounded action plans, never invents owners, dates, or decisions, and
> writes deliverables to `/mnt/session/outputs/`. Upload `meeting_notes.md` and
> mount it at `/workspace/meeting_notes.md`. Start a session on that
> environment. Then send a single `user.define_outcome` event - not a
> `user.message` - asking it to create `/mnt/session/outputs/action_plan.md`.
> Use the rubric in `rubric.md`, set `max_iterations` to 3, open the event
> stream before sending, and print grading iterations, results, feedback, and
> tool calls."

**Prompt 2 - confirm the result and retrieve the file:**

> "Retrieve the session and print each `outcome_evaluations` result. Then list
> the files this session produced with `scope_id=session.id` and download the
> `.md` action plan into a local `outputs/` folder."

---

## Expected: Expected output

- The first build runs at **iteration 0**.
- Tool calls stream by, usually `read` and `write`.
- The grader emits `span.outcome_evaluation_end` per iteration. You may see an
  early `needs_revision` if a section or table column is missing.
- The final result is usually `satisfied`, and the session moves to `idle`.
- `action_plan.md` downloads into your local `outputs/` folder.

---

## Troubleshooting

- **Writing a gradeable rubric.** Every bullet must be a single, testable
  pass/fail rule. Replace adjectives with measurable specifics.
- **`max_iterations` behavior.** It bounds the build-grade-revise loop. This lab
  uses 3 to keep cost low.
- **The result taxonomy.** `span.outcome_evaluation_end.result` is one of:
  `satisfied`, `needs_revision`, `max_iterations_reached`, `failed`, or
  `interrupted`.
- **`result: failed` immediately.** The rubric and description disagree.
  Reconcile them and re-send `user.define_outcome` once the session is idle.
- **No `action_plan.md` downloads.** Only files written to
  `/mnt/session/outputs/` are collected. The session file list can also include
  the mounted source file `meeting_notes.md`, which is not always downloadable
  as an output artifact. Filter for `action_plan.md` exactly.

---

## Stretch: Stretch

- Tighten the rubric with a stricter action table, such as "all high-priority
  items must appear before medium-priority items."
- Chain a second outcome after the first one is terminal: ask for a one-page
  executive summary of the action plan with its own short rubric.
- Ask the agent to produce a second file, `owner_followups.md`, grouped by owner.

---

## What you've learned

- The mental shift from a conversational session ("you decide when to stop") to
  an outcome-driven one ("a grader decides when it's done").
- The `user.define_outcome` event flow: a description plus a gradeable rubric,
  sent as an event, never a field on `sessions.create()`.
- How to write a rubric the grader can score literally, criterion by criterion.
- How `span.outcome_evaluation_*` events surface the iterate-until-satisfied
  loop.
- How to pull the deliverable from `/mnt/session/outputs/` with the Files API.
