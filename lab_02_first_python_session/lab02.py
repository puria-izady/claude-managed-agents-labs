"""Lab 02 - Recreate the Lab 1 coding-assistant agent in ~12 lines of Python.

Mirrors the Console flow from Lab 1, but from code:
  1. create a client (Anthropic)
  2. create an Agent  (model + agent toolset)
  3. create a cloud Environment
  4. create a Session that references the agent + environment
  5. send a user.message and stream the events back

Everything under client.beta.* sends the Managed Agents beta header for you.

Run:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python lab02.py

Expected:
  - Streamed [tool: ...] lines (write, bash, read) as the agent works
  - The agent's chat text explaining what it did
  - The agent writing /workspace/fib.py and running it
  - "--- session idle ---" at the end

Note on IDs that may update:
  - model="claude-haiku-4-5-20251001" is the course default; swap as models update.
  - the "agent_toolset_20260401" toolset id is date-stamped; a newer dated
    toolset may exist later. Both are current as of this lab.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_session_cost  # noqa: E402

BETAS = ["managed-agents-2026-04-01"]
MODEL = "claude-haiku-4-5-20251001"


def main() -> None:
    # 1. Client - reads ANTHROPIC_API_KEY from the environment.
    #    The .beta namespace adds the managed-agents beta header automatically.
    client = Anthropic()

    # 2. Agent - the model, persona, and toolset live here (not on the session).
    agent = client.beta.agents.create(
        name="Coding Assistant",
        model=MODEL,  # course default; swap as models update
        system="You are a helpful coding assistant. Write clean code and verify it runs.",
        tools=[{"type": "agent_toolset_20260401"}],  # date-stamped; may update
    )
    print(f"agent.id   = {agent.id}")

    # 3. Environment - a cloud container template with open networking.
    env = client.beta.environments.create(
        name="lab02-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )
    print(f"env.id     = {env.id}")

    # 4. Session - references the agent (pinned to this version) + the environment.
    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent.id, "version": agent.version},
        environment_id=env.id,
        title="Lab 2 first session",
    )
    print(f"session.id = {session.id}\n")

    # 5. Stream a turn. Open the stream FIRST, then send the message, so we
    #    don't miss any early events.
    with client.beta.sessions.events.stream(session_id=session.id) as stream:
        client.beta.sessions.events.send(
            session_id=session.id,
            events=[{
                "type": "user.message",
                "content": [{
                    "type": "text",
                    "text": (
                        "Create /workspace/fib.py that prints the first 20 "
                        "Fibonacci numbers. Then run it."
                    ),
                }],
            }],
        )

        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="", flush=True)
            elif event.type == "agent.tool_use":
                print(f"\n[tool: {event.name}]")
            elif event.type == "session.status_idle":
                print("\n--- session idle ---")
                break

    print_session_cost(client, session.id, MODEL, betas=BETAS)


if __name__ == "__main__":
    main()
