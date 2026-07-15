"""Lab 11 - Research, write & fact-check multi-agent pipeline.

Builds three specialists (Researcher / Writer / Fact-Checker) and a
Coordinator that delegates to them, runs a session on a topic, streams the
primary thread, and downloads the verified brief.

All agents use the course default Haiku model. Tool scoping and the coordinator
topology are the focus of this lab.

Run:
    python lab11.py
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_session_cost  # noqa: E402

BETAS = ["managed-agents-2026-04-01"]
MODEL = "claude-haiku-4-5-20251001"

# --- System prompts ---------------------------------------------------------
# All three specialists share the same container filesystem, so they hand off
# artifacts via files in /workspace.

RESEARCHER = """You research a topic. Use web_search for breadth and
web_fetch on the most promising results. Write a JSON array of citations
to /workspace/citations.json: each item {url, title, snippet, why_relevant}."""

WRITER = """You draft a brief from the researcher's citations.
Read /workspace/citations.json. Produce /workspace/draft.md (<=600 words)
with inline citation links. Do not invent claims."""

FACT_CHECKER = """For every claim in /workspace/draft.md, verify it against
the linked source via web_fetch. Write /workspace/check.md with one of:
  [verified]   - quote the source
  [partial]    - quote the source and explain
  [unverified] - explain why it failed."""

COORDINATOR = """You coordinate a research team. Given a topic:
1) Delegate to the researcher (return when /workspace/citations.json exists).
2) Delegate to the writer (return when /workspace/draft.md exists).
3) Delegate to the fact-checker (return when /workspace/check.md exists).
4) If check.md has any [unverified] claim, loop steps 2-3 with the writer
   fixing those claims.
5) When the draft is clean, save the final brief to
   /mnt/session/outputs/brief.md."""


def main() -> None:
    client = Anthropic()

    # --- Step 1: the three specialists --------------------------------------
    # The researcher needs the web tools to gather sources. We disable the
    # toolset by default and enable only the tools this role needs.
    researcher = client.beta.agents.create(
        name="Researcher", model=MODEL, system=RESEARCHER,
        tools=[{
            "type": "agent_toolset_20260401",
            "default_config": {"enabled": False},
            "configs": [
                {"name": "web_search", "enabled": True},
                {"name": "web_fetch",  "enabled": True},
                {"name": "write",      "enabled": True},
                {"name": "read",       "enabled": True},
            ],
        }],
    )

    # The writer only reads citations and writes a draft; the full toolset is
    # fine here since drafting is low risk.
    writer = client.beta.agents.create(
        name="Writer", model=MODEL, system=WRITER,
        tools=[{"type": "agent_toolset_20260401"}],
    )

    # The fact-checker re-fetches each source to verify claims.
    fact_checker = client.beta.agents.create(
        name="Fact-Checker", model=MODEL, system=FACT_CHECKER,
        tools=[{
            "type": "agent_toolset_20260401",
            "default_config": {"enabled": False},
            "configs": [
                {"name": "web_fetch", "enabled": True},
                {"name": "read",      "enabled": True},
                {"name": "write",     "enabled": True},
            ],
        }],
    )

    # --- Step 2: the coordinator --------------------------------------------
    # multiagent.agents lists the roster the coordinator can delegate to.
    # A roster holds up to 20 unique agents and is 1 level deep: specialists
    # cannot delegate further. The coordinator is the only agent we talk to.
    coordinator = client.beta.agents.create(
        name="Research Lead", model=MODEL, system=COORDINATOR,
        tools=[{"type": "agent_toolset_20260401"}],
        multiagent={
            "type": "coordinator",
            "agents": [
                {"type": "agent", "id": researcher.id},
                {"type": "agent", "id": writer.id},
                {"type": "agent", "id": fact_checker.id},
            ],
        },
    )

    # --- Step 3: environment + session --------------------------------------
    # Unrestricted networking lets the web tools reach the internet.
    env = client.beta.environments.create(
        name="multiagent-env",
        config={"type": "cloud", "networking": {"type": "unrestricted"}},
    )

    session = client.beta.sessions.create(
        agent={
            "type": "agent",
            "id": coordinator.id,
            "version": coordinator.version,
        },
        environment_id=env.id,
        title="Brief: agentic AI state of the art",
    )
    print(f"session.id = {session.id}\n")

    # --- Step 4: stream the primary thread ----------------------------------
    # The primary thread is a condensed view of all activity. We see one
    # thread_created per specialist and one message_received each time a
    # specialist returns. To inspect a specialist's full reasoning you would
    # open that session thread directly; here the primary view is enough.
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(session.id, events=[{
            "type": "user.message",
            "content": [{
                "type": "text",
                "text": (
                    "Topic: 'agentic AI, state of the art'. "
                    "Produce a verified brief."
                ),
            }],
        }])
        for event in stream:
            if event.type == "session.thread_created":
                # A new child thread spawned for a specialist.
                print(f"\n+ thread {event.agent_name}")
            elif event.type == "agent.thread_message_received":
                # A specialist returned a result to the coordinator.
                print(f"  <- {event.from_agent_name} returned")
            elif event.type == "agent.message":
                # The coordinator's own text, including the final brief.
                for b in event.content:
                    if b.type == "text":
                        print(b.text, end="", flush=True)
            elif event.type == "session.status_idle":
                print("\n--- session idle ---")
                break

    # --- Step 5: collect the final brief ------------------------------------
    out_dir = Path("./outputs")
    out_dir.mkdir(exist_ok=True)
    for f in client.beta.files.list(
        scope_id=session.id, betas=["managed-agents-2026-04-01"],
    ):
        if f.filename == "brief.md":
            client.beta.files.download(f.id).write_to_file(
                str(out_dir / "brief.md"),
            )
            print(f"saved: {out_dir / 'brief.md'}")

    print_session_cost(client, session.id, MODEL, betas=BETAS)


if __name__ == "__main__":
    main()
