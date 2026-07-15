"""Lab 07 - Human-in-the-loop checkpoint for bash and write.

This script builds an agent whose toolset defaults to always_allow, but
overrides `bash` and `write` to always_ask. It then drives a session and
handles the server-side confirmation flow:

  1. The agent emits a tool_use the policy must approve.
  2. The session pauses in a `requires_action` state and hands back the
     blocking event ids.
  3. For each id we run our local policy:
       - auto-allow `write` when the path starts with /tmp/
       - otherwise prompt the human at stdin (y / N / explain <reason>)
  4. We send one `user.tool_confirmation` per id (allow, or deny with a
     deny_message), and the session resumes.

A deny with a message is fed back to the model so it can adapt and try a
different approach. Watch the next agent.message after a deny to see the
recovery.

Run:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python lab07.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_session_cost  # noqa: E402

MODEL = "claude-haiku-4-5-20251001"
TOOLSET = "agent_toolset_20260401"
BETAS = ["managed-agents-2026-04-01"]


def decide(event_id: str, recent_events: list) -> tuple[str, str | None]:
    """Decide whether to allow a pending tool_use.

    Returns a ('allow' | 'deny', optional_deny_message) tuple. The
    deny_message is only used on the deny path; it is handed to the model so
    it can reroute.
    """
    # Find the agent.tool_use event the session is blocking on.
    target = next(
        (e for e in recent_events if getattr(e, "id", None) == event_id),
        None,
    )
    if target is None:
        # Defensive: if we cannot identify the tool, refuse rather than
        # blindly approve.
        return "deny", "Internal error: missing tool_use event."

    # Policy rule: writes under /tmp/ are low-risk scratch space, so let them
    # through without bothering the human. Everything else is escalated.
    if target.name == "write":
        path = (target.input or {}).get("path", "")
        if path.startswith("/tmp/"):
            print(f"\n[auto-allow] write to {path} (under /tmp/)")
            return "allow", None

    # Escalate to the human for bash and for writes outside /tmp/.
    print(f"\n[approval needed] {target.name} -> {target.input}")
    ans = input("  approve? [y / N / explain <reason>] ").strip().lower()
    if ans == "y":
        return "allow", None
    if ans.startswith("explain"):
        reason = ans[len("explain"):].strip()
        # The reason becomes the deny_message the agent sees next turn.
        return "deny", reason or "I'd rather not, please try another way."
    # Any other input (N, blank, garbage) is a hard deny.
    return "deny", "Denied by the operator. Do not retry this exact action."


def main() -> None:
    client = Anthropic()

    # Toolset default is always_allow so read-only tools (read, grep, ...)
    # run freely. We tighten only the two mutating tools to always_ask.
    agent = client.beta.agents.create(
        name="HITL Coding Assistant",
        model=MODEL,
        system=(
            "You are a careful coding assistant. Explain what you will do "
            "before doing it, then take one action at a time. Never assume "
            "approval: wait for the confirmation result. If an action is "
            "denied, read the reason and propose a safer alternative."
        ),
        tools=[{
            "type": TOOLSET,
            "default_config": {"permission_policy": {"type": "always_allow"}},
            "configs": [
                {"name": "bash", "permission_policy": {"type": "always_ask"}},
                {"name": "write", "permission_policy": {"type": "always_ask"}},
            ],
        }],
    )

    env = client.beta.environments.create(
        name="hitl-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )

    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent.id, "version": agent.version},
        environment_id=env.id,
        title="HITL demo",
    )
    print(f"session.id = {session.id}\n")

    # We keep a running list of streamed events so decide() can look up the
    # tool_use referenced by each requires_action event id.
    recent: list = []

    with client.beta.sessions.events.stream(session.id) as stream:
        # A task that forces both gated tools: a write outside /tmp/, then a
        # bash run. Each should pause for confirmation.
        client.beta.sessions.events.send(session.id, events=[{
            "type": "user.message",
            "content": [{
                "type": "text",
                "text": (
                    "Write a hello-world Python script to "
                    "/workspace/hello.py and then run it with python."
                ),
            }],
        }])

        for event in stream:
            recent.append(event)

            if event.type == "agent.message":
                # Stream the model's narration as it arrives.
                for b in event.content:
                    if b.type == "text":
                        print(b.text, end="", flush=True)

            elif event.type == "agent.tool_use":
                print(f"\n[tool requested: {event.name}]")

            elif event.type == "session.status_idle":
                sr = getattr(event, "stop_reason", None)
                if sr and sr.type == "requires_action":
                    # The session is paused waiting on confirmations. Answer
                    # every blocking id, or the session deadlocks.
                    for eid in sr.event_ids:
                        choice, msg = decide(eid, recent)
                        body = {
                            "type": "user.tool_confirmation",
                            "tool_use_id": eid,
                            "result": choice,
                        }
                        if choice == "deny" and msg:
                            body["deny_message"] = msg
                        client.beta.sessions.events.send(
                            session.id, events=[body],
                        )
                    # Loop continues: the session resumes and streams more.
                else:
                    # Idle with no pending action means the turn is done.
                    break

    print("\n\nDone.")
    print_session_cost(client, session.id, MODEL, betas=BETAS)


if __name__ == "__main__":
    main()
