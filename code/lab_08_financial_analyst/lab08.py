"""Lab 08 - Financial analyst that ships an Excel deck via the xlsx skill.

Creates its own data-science environment with pandas / numpy / matplotlib,
attaches the prebuilt `xlsx` skill, reads a mounted revenue CSV, and produces
a polished, formatted .xlsx workbook with charts in /mnt/session/outputs/. The
workbook is then retrieved via the Files API.

Prereqs:
  - Export ANTHROPIC_API_KEY before running:

      export ANTHROPIC_API_KEY="sk-ant-..."
      uv run --project .. --env-file ../.env python lab08.py
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_session_cost  # noqa: E402

BETAS = ["managed-agents-2026-04-01"]
MODEL = "claude-haiku-4-5-20251001"


def main() -> None:
    client = Anthropic()

    # 1. Dedicated cloud environment for this lab. This removes the hard
    #    dependency on Lab 04 while keeping the same data-science stack.
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

    # 2. Create the agent and ATTACH the prebuilt xlsx skill. The skill is
    #    loaded reactively: it only enters context once the task is about Excel.
    #    Remember the ceiling is 20 skills per session, counted across agents.
    agent = client.beta.agents.create(
        name="Financial Analyst",
        model=MODEL,
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

    # 3. Upload the CSV so it can be mounted into the session filesystem.
    csv = client.beta.files.upload(file=Path("revenue.csv"), betas=BETAS)
    print(f"file.id  = {csv.id}")

    # 4. Start a session on the dedicated env and mount the CSV at a known path.
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
    print(f"session.id = {session.id}\n")

    # 5. Ask for the formatted workbook. Be explicit about sheets, formulas,
    #    charts, and the output path so the deliverable is reproducible.
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

    # 6. Retrieve the .xlsx the agent wrote to the session outputs.
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    for f in client.beta.files.list(scope_id=session.id, betas=BETAS):
        print(f.id, f.filename)
        if f.filename.endswith(".xlsx"):
            client.beta.files.download(f.id).write_to_file(
                str(out_dir / f.filename)
            )
            print(f"saved: {out_dir / f.filename}")

    print_session_cost(client, session.id, MODEL, betas=BETAS)


if __name__ == "__main__":
    main()
