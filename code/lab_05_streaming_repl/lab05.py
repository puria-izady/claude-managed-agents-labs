"""Lab 05 - Streaming REPL with a live cost meter.

A tiny terminal console that talks to one persistent session. It:
  1. creates an agent + environment + session,
  2. streams events as the agent works,
  3. prints the agent's text (agent.message) and tool calls (agent.tool_use)
     live, in band, and
  4. reads usage off the session after each turn and shows a running
     estimated cost.

The cost figure is a list-price estimate. Check Claude Console billing for
authoritative cost.

Run:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python lab05.py

Optionally reuse an agent/env you already built (e.g. Lab 02/04) instead of
creating fresh ones:
    export AGENT_ID="agent_..."
    export ENV_ID="env_..."

Commands inside the REPL:
    quit / exit   end the REPL and print the final total
    interrupt     send user.interrupt to halt the agent cleanly
"""

import os
import sys
from pathlib import Path

from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
from cost_meter import print_session_cost  # noqa: E402

BETAS = ["managed-agents-2026-04-01"]
MODEL = os.environ.get("MODEL", "claude-haiku-4-5-20251001")


def get_or_create_agent(client: Anthropic) -> str:
    """Reuse AGENT_ID if set, otherwise create a small console agent."""
    if os.environ.get("AGENT_ID"):
        return os.environ["AGENT_ID"]
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
    print(f"agent.id = {agent.id}")
    return agent.id


def get_or_create_env(client: Anthropic) -> str:
    """Reuse ENV_ID if set, otherwise create a plain cloud environment."""
    if os.environ.get("ENV_ID"):
        return os.environ["ENV_ID"]
    env = client.beta.environments.create(
        name="streaming-repl",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
        betas=BETAS,
    )
    print(f"env.id = {env.id}")
    return env.id


def show_cost(client: Anthropic, session_id: str) -> None:
    """Re-fetch the session, then print an estimated running cost ticker.

    Usage on a session is cumulative across the whole session, so this total
    grows turn over turn.
    """
    print_session_cost(client, session_id, MODEL, betas=BETAS)


def main() -> None:
    client = Anthropic()

    # 1. Agent + environment + session. Reuse via AGENT_ID / ENV_ID if present.
    agent_id = get_or_create_agent(client)
    env_id = get_or_create_env(client)
    session = client.beta.sessions.create(
        agent=agent_id,
        environment_id=env_id,
        title="Lab 5 streaming REPL",
        betas=BETAS,
    )
    print(f"session.id = {session.id}")
    print("Type a prompt. 'quit' to exit, 'interrupt' to halt the agent.\n")

    while True:
        user = input("you> ").strip()
        if not user:
            continue
        if user.lower() in {"quit", "exit"}:
            break
        if user.lower() == "interrupt":
            # Halt the agent immediately; session state is preserved.
            client.beta.sessions.events.send(
                session.id,
                events=[{"type": "user.interrupt"}],
                betas=BETAS,
            )
            continue

        # 2. Open the stream, then 3. send the turn and print events live.
        with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
            client.beta.sessions.events.send(
                session.id,
                events=[{
                    "type": "user.message",
                    "content": [{"type": "text", "text": user}],
                }],
                betas=BETAS,
            )
            sys.stdout.write("agent> ")
            sys.stdout.flush()
            for event in stream:
                if event.type == "agent.message":
                    # Streamed model text: print each text block as it arrives.
                    for block in event.content:
                        if block.type == "text":
                            sys.stdout.write(block.text)
                            sys.stdout.flush()
                elif event.type == "agent.tool_use":
                    # Built-in tool call: show it in band so the user sees the
                    # agent reach for a tool while it works.
                    sys.stdout.write(f"\n  [tool: {event.name}]\n  ")
                    sys.stdout.flush()
                elif event.type == "session.status_idle":
                    # 4. Turn finished: read usage off the session and tick the
                    #    running cost meter.
                    show_cost(client, session.id)
                    break

    # Final total when the user quits.
    print("\nFinal total:")
    show_cost(client, session.id)
    print("Goodbye.")


if __name__ == "__main__":
    main()
