"""Lab 10 - Customer-support agent with persistent memory.

A support agent remembers each customer across separate calls using a memory
store mounted at /mnt/memory/. The script:

  1. Creates a per-customer memory store and seeds a profile.
  2. Creates a shared, read-only policies store.
  3. Creates the support agent (model claude-haiku-4-5-20251001, agent_toolset_20260401).
  4. Runs a FIRST session for Alice - the agent records facts about the call.
  5. Runs a SECOND, separate session for Alice - the agent recalls them.
  6. Inspects the memory version history (the audit trail).

Budgets to remember: max 8 stores/session, 100 kB (~25k tokens) per memory,
up to 2,000 memories/store, 30-day version audit trail.

Run:
    export ANTHROPIC_API_KEY="sk-ant-..."
    python3 lab10.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_sessions_cost  # noqa: E402

# Beta header for all Managed Agents calls. The SDK sets this automatically on
# client.beta.{agents,environments,sessions,memory_stores}.* calls; we pass it
# explicitly here so the intent is obvious in the lab.
BETAS = ["managed-agents-2026-04-01"]
MODEL = "claude-haiku-4-5-20251001"

# Pick the workspace slug you create sessions in ("default" unless you changed it).
WORKSPACE = "default"

CUSTOMERS = [
    {"id": "alice", "name": "Alice Cooper", "plan": "pro"},
    {"id": "bob",   "name": "Bob Ross",     "plan": "team"},
]


def seed_profile(customer: dict[str, str]) -> str:
    return (
        f"Name: {customer['name']}\n"
        f"Plan: {customer['plan']}\n"
        f"Notes: (none yet)\n"
    )


def get_memory_by_path(client: Anthropic, store_id: str, path: str):
    matches = list(
        client.beta.memory_stores.memories.list(
            store_id,
            path_prefix=path,
            view="full",
            betas=BETAS,
        )
    )
    for memory in matches:
        if getattr(memory, "type", None) == "memory" and memory.path == path:
            if memory.content is not None:
                return memory
            return client.beta.memory_stores.memories.retrieve(
                memory.id,
                memory_store_id=store_id,
                view="full",
                betas=BETAS,
            )
    return None


def profile_has_notes(content: str | None) -> bool:
    if not content:
        return False
    lines = [line for line in content.splitlines() if line.strip()]
    return len(lines) > 3 or "Notes: (none yet)" not in content


def get_or_create_customer_store(client: Anthropic, customer: dict[str, str]) -> str:
    """Reuse a customer store across notebook reruns.

    Memory store names are not unique. If duplicates exist, prefer the one whose
    profile already has notes, otherwise use the newest seed store.
    """
    name = f"cust-{customer['id']}"
    candidates = [
        store for store in client.beta.memory_stores.list(betas=BETAS)
        if store.name == name
    ]
    if candidates:
        profiles = [
            (store, get_memory_by_path(client, store.id, "/profile.md"))
            for store in candidates
        ]
        with_notes = [
            (store, profile) for store, profile in profiles
            if profile_has_notes(getattr(profile, "content", None))
        ]
        store, profile = sorted(
            with_notes or profiles,
            key=lambda item: item[0].updated_at,
            reverse=True,
        )[0]
        if profile is None:
            client.beta.memory_stores.memories.create(
                store.id,
                path="/profile.md",
                content=seed_profile(customer),
                betas=BETAS,
            )
        print(f"reusing {name}: {store.id}")
        return store.id

    store = client.beta.memory_stores.create(
        name=name,
        description=f"Memory for customer {customer['name']} ({customer['plan']} plan).",
        betas=BETAS,
    )
    client.beta.memory_stores.memories.create(
        store.id,
        path="/profile.md",
        content=seed_profile(customer),
        betas=BETAS,
    )
    print(f"created {name}: {store.id}")
    return store.id


def get_or_create_policy_store(client: Anthropic) -> str:
    name = "support-policies"
    existing = [
        store for store in client.beta.memory_stores.list(betas=BETAS)
        if store.name == name
    ]
    if existing:
        store = sorted(existing, key=lambda item: item.updated_at, reverse=True)[0]
        print(f"reusing policies store: {store.id}")
        return store.id

    policies = client.beta.memory_stores.create(
        name=name,
        description="Customer support policies. Read before promising anything.",
        betas=BETAS,
    )
    client.beta.memory_stores.memories.create(
        policies.id,
        path="/refunds.md",
        content=(
            "Refund policy:\n"
            "- Refunds allowed within 14 days of purchase.\n"
            "- Pro plan: unconditional within the window.\n"
            "- Team plan: requires manager approval.\n"
        ),
        betas=BETAS,
    )
    print(f"created policies store: {policies.id}")
    return policies.id


def print_profile(client: Anthropic, store_id: str, label: str) -> None:
    profile = get_memory_by_path(client, store_id, "/profile.md")
    content = getattr(profile, "content", None) if profile else None
    print(f"\n--- {label} /profile.md ---")
    print(content or "<missing profile>")


def main() -> None:
    client = Anthropic()

    # 1. Per-customer stores, each seeded with a starter profile. Reuse an
    #    existing store on notebook/script reruns so Step 5 does not attach an
    #    empty duplicate.
    stores: dict[str, str] = {}
    for c in CUSTOMERS:
        stores[c["id"]] = get_or_create_customer_store(client, c)
    print("customer stores:", stores)

    # 2. Shared, read-only policies store. Reference data the agent must read
    #    but must never overwrite - so we will attach it read_only below.
    policies_id = get_or_create_policy_store(client)

    # 3. The support agent. Create it ONCE and reuse across sessions.
    agent = client.beta.agents.create(
        name="Support Agent",
        model=MODEL,
        system=(
            "You are a warm, concise customer-support agent. "
            "Each session mounts the customer's memory under /mnt/memory/cust-*/ "
            "and a shared policy store under /mnt/memory/support-policies/. "
            "At the START of every call, read the customer's profile.md so you "
            "greet them by name and recall their history. "
            "Before promising any refund or escalation, read "
            "/mnt/memory/support-policies/refunds.md. "
            "At the END of every call, APPEND a short dated note to the "
            "customer's profile.md describing the issue and outcome. "
            "If the user's request is resolved, write that note before your "
            "final response; do not merely say you will write it later. "
            "Append - never overwrite existing notes."
        ),
        tools=[{"type": "agent_toolset_20260401"}],
        betas=BETAS,
    )
    print("agent.id:", agent.id)

    # An isolated cloud environment with no outbound network is plenty here -
    # the agent only touches its mounted memory stores.
    env = client.beta.environments.create(
        name="support-env",
        config={
            "type": "cloud",
            "networking": {"type": "limited", "allowed_hosts": []},
        },
        betas=BETAS,
    )
    print("env.id:", env.id)

    # 4 + 5. One helper, reused for both calls. Each call is a SEPARATE session,
    #        so the only thing carried between them is the memory store.
    session_ids: list[str] = []

    def run_session(customer_id: str, message: str) -> None:
        session = client.beta.sessions.create(
            agent={"type": "agent", "id": agent.id, "version": agent.version},
            environment_id=env.id,
            resources=[
                {
                    # Per-customer memory: the agent reads AND writes here.
                    "type": "memory_store",
                    "memory_store_id": stores[customer_id],
                    "access": "read_write",
                    "instructions": (
                        "This is the customer's own memory. Read profile.md "
                        "first; append a note about this call at the end."
                    ),
                },
                {
                    # Shared policies: read_only so a poisoned call cannot
                    # rewrite the rules every other customer relies on.
                    "type": "memory_store",
                    "memory_store_id": policies_id,
                    "access": "read_only",
                    "instructions": "Read before promising any refund or escalation.",
                },
            ],
            title=f"Call with {customer_id}",
            betas=BETAS,
        )
        print(f"\n=== session {session.id} ({customer_id}) ===")
        print(
            "Watch in Console: "
            f"https://platform.claude.com/workspaces/{WORKSPACE}/sessions/{session.id}"
        )

        # Stream-first: open the stream, then send the message.
        with client.beta.sessions.events.stream(session_id=session.id) as stream:
            client.beta.sessions.events.send(
                session_id=session.id,
                events=[{
                    "type": "user.message",
                    "content": [{"type": "text", "text": message}],
                }],
            )
            for event in stream:
                if event.type == "agent.message":
                    for block in event.content:
                        if block.type == "text":
                            print(block.text, end="", flush=True)
                elif event.type == "session.status_idle":
                    # Break only on a terminal stop reason; keep waiting if the
                    # agent is mid-task (e.g. between tool calls).
                    if getattr(event.stop_reason, "type", None) == "requires_action":
                        continue
                    break
                elif event.type == "session.status_terminated":
                    break
        session_ids.append(session.id)
        print()

    # FIRST call: Alice reports an issue. The agent reads policy and records it.
    run_session(
        "alice",
        "Hi, my widget is broken. I bought it 7 days ago. Can I get a refund? "
        "If I am eligible, approve the refund and append a note about this "
        "issue and outcome to my customer profile before you finish.",
    )

    print_profile(client, stores["alice"], "after first call")

    # SECOND call: a brand-new session. The agent should recall the first call
    # purely from the memory store - we say nothing about the broken widget.
    run_session("alice", "Hi again, it's me. What was my last issue with you?")

    # 6. Inspect the memory version history - the audit trail. Every write the
    #    agent made produced an immutable memver_* attributed to its session.
    print("\nAlice memory versions (newest first):")
    versions = client.beta.memory_stores.memory_versions.list(stores["alice"])
    for v in versions.data[:5]:
        print(f"  {v.id}  {v.operation}  {v.created_at}")

    print_sessions_cost(client, session_ids, MODEL, betas=BETAS)


if __name__ == "__main__":
    main()
