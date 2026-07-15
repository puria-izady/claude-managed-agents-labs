"""Lab 04 - Build a data-science environment and produce a chart.

Creates a reusable `data-analysis` cloud environment with pandas / numpy /
matplotlib pre-installed, creates a Data Analyst agent on the built-in toolset,
then runs a session that:
  1. prints the installed package versions, and
  2. generates a small synthetic dataset and saves a line chart PNG to
     /mnt/session/outputs/revenue.png.

The PNG is downloaded into ./outputs/.

Run:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python lab04.py
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

    # 1. Cloud environment with the data-science stack pre-installed at build
    #    time. pandas is pinned for reproducibility; numpy/matplotlib float.
    env = client.beta.environments.create(
        name="data-analysis",
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

    # 2. Agent on the built-in toolset. Haiku drives the analysis via bash.
    agent = client.beta.agents.create(
        name="Data Analyst",
        model=MODEL,
        system=(
            "You are a data analyst. Use Python (pandas, numpy, matplotlib) "
            "via the bash tool. Always save chart images as PNG to "
            "/mnt/session/outputs/."
        ),
        tools=[{"type": "agent_toolset_20260401"}],
        betas=BETAS,
    )
    print(f"agent.id = {agent.id}")

    # 3. Session bound to the environment above.
    session = client.beta.sessions.create(
        agent=agent.id,
        environment_id=env.id,
        title="Generate a chart",
        betas=BETAS,
    )
    print(f"session.id = {session.id}\n")

    # 4. Ask for versions + a saved chart PNG, streaming the response.
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

    # 5. Retrieve the chart PNG produced in the session outputs.
    Path("outputs").mkdir(exist_ok=True)
    for f in client.beta.files.list(scope_id=session.id, betas=BETAS):
        print(f.id, f.filename)
        if f.filename.endswith(".png"):
            client.beta.files.download(f.id).write_to_file(
                f"./outputs/{f.filename}"
            )
            print("saved:", f.filename)

    print_session_cost(client, session.id, MODEL, betas=BETAS)


if __name__ == "__main__":
    main()
