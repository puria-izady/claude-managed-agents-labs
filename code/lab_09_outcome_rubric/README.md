# Lab 09 - Meeting notes action plan with an outcome rubric

An outcome-driven session that turns a small set of messy meeting notes into a
structured Markdown action plan. You send one `user.define_outcome` event with a
goal and a gradeable rubric; a managed grader scores each iteration and feeds
gaps back to the builder until the result is `satisfied`. Produces
`action_plan.md` in `/mnt/session/outputs/`.

**Spec:** [`../../lab_09_dcf_outcome.md`](../../lab_09_dcf_outcome.md)

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

Lab 09 creates its own lightweight `meeting-notes-outcome` environment and
`Meeting Action Planner` agent. No prior lab IDs are required.

## Files

- `lab09.py` - main script (inlines the rubric as text)
- `meeting_notes.md` - the source notes the agent turns into an action plan
- `rubric.md` - the same rubric as a standalone file, for the upload-and-reuse
  variant shown in the spec

## Run

```bash
uv run --project .. --env-file ../.env python lab09.py
```

## What you'll see

```
env.id = env_01...
agent.id = agent_01...
file.id = file_01...
session.id = sesn_01...

--- grading iteration 0 ---
  [tool: read]
  [tool: write]
  result: needs_revision
  feedback: The action table is missing Source Note values...

--- grading iteration 1 ---
  [tool: write]
  result: satisfied

--- session idle ---
outcome outc_01...: satisfied
file_02... action_plan.md
saved: outputs/action_plan.md
```

The action plan should include decisions, an owner/date/priority action table,
risks, and open questions grounded only in `meeting_notes.md`.

The download step intentionally filters for `action_plan.md` exactly. The
session file list can also include the mounted source file `meeting_notes.md`,
which is not always downloadable as an output artifact.

## Result taxonomy

`span.outcome_evaluation_end.result` is one of: `satisfied`, `needs_revision`,
`max_iterations_reached`, `failed`, `interrupted`. The first build runs at
iteration 0; the grader exits the moment a result is `satisfied`.
