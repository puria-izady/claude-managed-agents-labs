"""Lab 09 - Meeting notes action plan driven by an outcome rubric.

Turns a session from a conversation into work. Instead of sending a
user.message and deciding for yourself when the deliverable is good enough,
you send a single user.define_outcome event: a description of the goal plus a
gradeable rubric. A managed grader scores each iteration against that rubric
and feeds per-criterion gaps back to the builder, which revises and tries
again. The loop runs build -> grade -> revise until the grader returns
`satisfied`, hits max_iterations, or is interrupted.

This version keeps the task deliberately small and inexpensive: the agent reads
meeting_notes.md and writes one Markdown action plan to /mnt/session/outputs/.

Prereqs:
  - Export ANTHROPIC_API_KEY before running:

      export ANTHROPIC_API_KEY="sk-ant-..."
      uv run --project .. --env-file ../.env python lab09.py
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_session_cost  # noqa: E402

BETAS = ["managed-agents-2026-04-01"]
MODEL = "claude-haiku-4-5-20251001"

# The rubric is a markdown document the grader reads literally. Every bullet is
# a single pass/fail criterion - measurable, not "make it good".
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


def main() -> None:
    client = Anthropic()

    # 1. Dedicated lightweight environment. No package installs and no internet
    #    egress are needed for this notes-to-plan task.
    env = client.beta.environments.create(
        name="meeting-notes-outcome",
        config={
            "type": "cloud",
            "networking": {"type": "limited", "allowed_hosts": []},
        },
        betas=BETAS,
    )
    print(f"env.id = {env.id}")

    # 2. Dedicated agent for the writing task. No prebuilt skills are needed;
    #    the standard toolset is enough to read the mounted notes and write the
    #    Markdown deliverable.
    agent = client.beta.agents.create(
        name="Meeting Action Planner",
        model=MODEL,
        system=(
            "You are an operations lead. Turn messy meeting notes into concise, "
            "source-grounded action plans. Do not invent owners, dates, or "
            "decisions. Write deliverables to /mnt/session/outputs/."
        ),
        tools=[{"type": "agent_toolset_20260401"}],
        betas=BETAS,
    )
    print(f"agent.id = {agent.id}")

    # 3. Upload the meeting notes so the agent works from a fixed source file.
    notes = client.beta.files.upload(file=Path("meeting_notes.md"), betas=BETAS)
    print(f"file.id = {notes.id}")

    # 4. Start a plain session. There is no outcome field on sessions.create:
    #    an outcome is an event you send next.
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
    print(f"session.id = {session.id}\n")

    # 5. Send the outcome. Stream-first: open the stream BEFORE sending so we do
    #    not miss the first grader events. max_iterations is intentionally small
    #    because the artifact is simple and the lab should stay inexpensive.
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

        # 6. Watch the iterate-until-satisfied loop.
        for event in stream:
            if event.type == "span.outcome_evaluation_start":
                print(f"\n--- grading iteration {event.iteration} ---")
            elif event.type == "span.outcome_evaluation_end":
                print(f"  result: {event.result}")
                if event.result == "needs_revision":
                    print(f"  feedback: {event.explanation[:240]}...")
            elif event.type == "agent.tool_use":
                print(f"  [tool: {event.name}]")
            elif event.type == "session.status_idle":
                print("\n--- session idle ---")
                break

    # 7. Report the final result taxonomy from the session record.
    session = client.beta.sessions.retrieve(session.id, betas=BETAS)
    for ev in session.outcome_evaluations:
        print(f"outcome {ev.outcome_id}: {ev.result}")

    # 8. Pull the deliverable from /mnt/session/outputs/ via the Files API.
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    downloaded = False
    for f in client.beta.files.list(scope_id=session.id, betas=BETAS):
        print(f.id, f.filename)
        if f.filename == "action_plan.md":
            client.beta.files.download(f.id).write_to_file(
                str(out_dir / f.filename)
            )
            print(f"saved: {out_dir / f.filename}")
            downloaded = True

    if not downloaded:
        raise RuntimeError(
            "Could not find downloadable action_plan.md in session outputs. "
            "Confirm the agent wrote /mnt/session/outputs/action_plan.md."
        )

    print_session_cost(client, session.id, MODEL, betas=BETAS)


if __name__ == "__main__":
    main()
