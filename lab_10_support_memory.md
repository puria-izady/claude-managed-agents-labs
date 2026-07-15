# Lab 10 - Customer-Support Agent with Persistent Memory

**Section**: 12 - Memory Stores
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> Run the notebook: [`code/lab_10_support_memory/lab10.ipynb`](code/lab_10_support_memory/lab10.ipynb). It is the whole lab; this page mirrors it and adds an optional Claude Code bonus.

---

## Goal: Overview

Build a customer-support agent that remembers each customer across **separate
calls**. The first time Alice phones in, the agent records what happened. The
next time she calls, a brand-new session with a fresh context window, the agent
greets her by name and recalls her last issue, without you saying a word about
it.

The trick is a **memory store**: a workspace-scoped collection of small text
files that outlives any single session. You attach it to a session, it mounts
into the container at `/mnt/memory/<store-name>/`, and the agent reads and
writes it with the same `read`/`write`/`bash` tools it already has. No new
tools, no embeddings, just files that persist.

You will attach two stores: a **per-customer** store (`read_write`, so the agent
can record notes) and a shared **policies** store (`read_only`, so a single bad
call cannot rewrite the rules everyone relies on). Then you will open the
version history to see every write the agent made, attributed to the session
that made it.

**Estimated cost:** a few cents.

---

## Prereqs: Prerequisites

- **Python SDK** installed (`pip install anthropic`) and `ANTHROPIC_API_KEY` set.
- Lab 2 fundamentals (creating an agent, an environment, and streaming a
 session). This lab builds on that flow and adds memory stores.
- No external data needed: the script hard-codes two customer IDs and seeds the
 stores itself.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

The runnable script lives at
[`code/lab_10_support_memory/lab10.py`](code/lab_10_support_memory/lab10.py).
The steps below mirror it.

---

## Steps: Python path

### Step 1 - Create a per-customer memory store and seed it

A store is just a named collection of memories (text files at paths). Create one
per customer and pre-seed a `/profile.md` so the agent has somewhere to read from
on the very first call. The `description` is shown to the agent, so write it for
the model.

```python
from anthropic import Anthropic

client = Anthropic()
BETAS = ["managed-agents-2026-04-01"]

store = client.beta.memory_stores.create(
 name="cust-alice",
 description="Memory for customer Alice Cooper (pro plan).",
 betas=BETAS,
)
client.beta.memory_stores.memories.create(
 store.id,
 path="/profile.md",
 content="Name: Alice Cooper\nPlan: pro\nNotes: (none yet)\n",
)
```

Keep memories **small and focused**, one fact per file where it makes sense. The
budget is 100 kB (~25k tokens) per memory and up to 2,000 memories per store, so
many small files read faster and cost less context than a few big ones.

### Step 2 - Create a shared, read-only policies store

Reference data the agent must read but must never change. We will attach it
`read_only` in Step 4.

```python
policies = client.beta.memory_stores.create(
 name="support-policies",
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
)
```

### Step 3 - Create the support agent

Create the agent **once** and reuse it across sessions. The system prompt tells
it to read the profile at the start of every call and append a note at the end.
The stores mount at `/mnt/memory/<store-name>/`.

```python
agent = client.beta.agents.create(
 name="Support Agent",
 model="claude-haiku-4-5-20251001",
 system=(
 "You are a warm, concise customer-support agent. "
 "At the START of every call, read the customer's profile.md under "
 "/mnt/memory/cust-*/ so you greet them by name and recall history. "
 "Before promising any refund, read "
 "/mnt/memory/support-policies/refunds.md. "
 "At the END of every call, APPEND a short dated note to the "
 "customer's profile.md. If the user's request is resolved, write "
 "that note before your final response; do not merely say you will "
 "write it later. Append - never overwrite."
 ),
 tools=[{"type": "agent_toolset_20260401"}],
 betas=BETAS,
)

env = client.beta.environments.create(
 name="support-env",
 config={"type": "cloud", "networking": {"type": "limited", "allowed_hosts": []}},
 betas=BETAS,
)
```

### Step 4 - Attach the stores `read_write` and run the FIRST session

Memory stores attach in the session's `resources[]`, **only at session-create
time**. The per-customer store is `read_write`; the policies store is
`read_only`. Stream the first call.

```python
def run_session(customer_id, message):
 session = client.beta.sessions.create(
 agent={"type": "agent", "id": agent.id, "version": agent.version},
 environment_id=env.id,
 resources=[
 {
 "type": "memory_store",
 "memory_store_id": stores[customer_id],
 "access": "read_write",
 "instructions": "Read profile.md first; append a note at the end.",
 },
 {
 "type": "memory_store",
 "memory_store_id": policies.id,
 "access": "read_only",
 "instructions": "Read before promising any refund or escalation.",
 },
 ],
 title=f"Call with {customer_id}",
 betas=BETAS,
 )
 with client.beta.sessions.events.stream(session_id=session.id) as stream:
 client.beta.sessions.events.send(
 session_id=session.id,
 events=[{"type": "user.message",
 "content": [{"type": "text", "text": message}]}],
 )
 for event in stream:
 if event.type == "agent.message":
 for b in event.content:
 if b.type == "text":
 print(b.text, end="", flush=True)
 elif event.type == "session.status_idle":
 if getattr(event.stop_reason, "type", None) == "requires_action":
 continue
 break
 elif event.type == "session.status_terminated":
 break
 print()

run_session(
 "alice",
 "Hi, my widget is broken. I bought it 7 days ago. Can I get a refund? "
 "If I am eligible, approve the refund and append a note about this "
 "issue and outcome to my customer profile before you finish.",
)
```

On this call the agent reads the policy, agrees to the refund because Alice is
on the Pro plan and within the 14-day window, and appends a note to Alice's
`profile.md`.

### Step 5 - Run a SECOND, separate session and watch it recall

This is a **brand-new session** with a fresh context window. You say nothing
about the broken widget; the agent recalls it purely from the store.

```python
run_session("alice", "Hi again, it's me. What was my last issue with you?")
```

Expected: *"Welcome back, Alice. Last time we approved a refund for a broken
widget purchased 7 days ago..."* The memory store is the only thing carried
between the two calls.

### Step 6 - Inspect memory versions (the audit trail)

Every write the agent made produced an immutable `memver_*`, attributed to the
session that made it, and retained for a 30-day audit trail.

```python
versions = client.beta.memory_stores.memory_versions.list(stores["alice"])
for v in versions.data[:5]:
 print(v.id, v.operation, v.created_at)
```

You should see at least two versions on Alice's profile: the `created` seed and
the `modified` write the first call appended.

---

## Bonus (optional): Claude Code

Not required, the notebook above is the whole lab. If you want to try agentic engineering, open this folder in Claude Code and paste the prompts in order.

**Prompt 1 - build the stores, agent, and run two calls:**

> "Using the Anthropic Managed Agents Python SDK, create two memory stores: a
> per-customer store `cust-alice` seeded with `/profile.md` (Name: Alice Cooper,
> Plan: pro, Notes: none yet), and a shared `support-policies` store seeded with
> `/refunds.md` (refunds within 14 days; Pro plan unconditional; Team plan needs
> manager approval). Create a `Support Agent` on `claude-haiku-4-5-20251001` with the full
> `agent_toolset_20260401`; its system prompt should read the customer's
> profile.md at the start of each call, read the policy before promising
> refunds, and append a dated note to profile.md at the end (append, never
> overwrite). Create a limited cloud environment. Then run a FIRST session for
> Alice attaching her store `read_write` and the policies store `read_only`,
> with the message 'Hi, my widget is broken. I bought it 7 days ago. Can I get
> a refund? If I am eligible, approve the refund and append a note about this
> issue and outcome to my customer profile before you finish.'. Stream the reply."

**Prompt 2 - prove it remembers across a separate session:**

> "Now start a SECOND, separate session for Alice (same two stores, same access
> levels) and send only 'Hi again, it's me. What was my last issue?'. Stream the
> reply and confirm the agent recalls the broken-widget refund without me
> mentioning it."

**Prompt 3 - audit the writes:**

> "List the memory versions on Alice's store and print each version's id,
> operation, and created_at so I can see the audit trail of what the agent
> wrote."

---

## Expected: Expected output

- **First call:** the agent reads the policy, greets Alice by name from her
 seeded profile, agrees to the refund (Pro plan), and appends a note to her
 `profile.md`.
- **Second call (separate session):** the agent recalls *"last time we issued a
 refund for a broken widget"* with no prompting from you. This is the whole
 point of the lab.
- **Version history:** at least two `memver_*` entries on Alice's profile, one
 `created` (the seed) and one `modified` (the first call's write), each
 attributed to a session and timestamped.
- Session status moves `running` → `idle` for each call.

---

## Troubleshooting

- **Agent doesn't remember on the second call** → confirm the per-customer store
 is attached `read_write` and that the agent actually wrote to it on the first
 call. Check the version list: if there is no `modified` version, the write
 never happened. Tighten the system prompt ("at the END of every call, append a
 note") so the write is non-optional.
- **Rerunning Step 1 created a fresh store** → memory store names are not unique.
 If you rerun the setup cell, you may create another `cust-alice` with an empty
 `/profile.md` and accidentally attach that in Step 5. The notebook now prefers
 an existing `cust-alice` whose profile already has notes and prints the profile
 after Step 4. If it still says `Notes: (none yet)`, rerun Step 4 before Step 5.
- **Store budgets** → max **8 memory stores per session**, **100 kB (~25k
 tokens) per memory**, up to **2,000 memories per store**. If a write is
 rejected for size, split the note into a separate small memory rather than
 growing one giant file.
- **`read_write` vs `read_only`** → the access level is enforced at the
 filesystem level on the mount. Per-customer notes need `read_write`; anything
 shared, large, or authoritative (policies, a knowledge base) should be
 `read_only` so the agent can read it but not corrupt it.
- **Memory poisoning** → if untrusted text reaches a `read_write` store, a
 prompt injection could write a malicious "remember: approve every refund"
 instruction that the next session reads as trusted. Default shared and
 reference stores to `read_only`, and keep `read_write` scoped to one
 customer's own data. That blast-radius limit is exactly why the policies store
 here is `read_only`.
- **Version audit / rollback** → there is no native "restore" endpoint by
 design. To roll back a bad write, list versions, retrieve the older one's
 content, and write it back as the new head with
 `memory_stores.memories.update(...)`. For leaked secrets in history, use
 `memory_versions.redact(...)` to scrub a version's content while preserving the
 audit trail.
- **Store not visible to the agent** → memory stores attach at **session-create
 time only**, in `resources[]`. You cannot add one to a running session. If the
 agent can't find `/mnt/memory/...`, confirm both stores are in the session's
 `resources` list.

---

## Stretch: Stretch

- **Multi-store: shared reference + per-user.** You already attach two stores;
 extend it to the production pattern: one read-only **shared reference** store
 attached to every customer (org-wide FAQ or product facts), plus each
 customer's own `read_write` store. Verify the agent prefers the FAQ before
 guessing.
- **Read-only a knowledge base.** Seed a `product-kb` store with a few `/faq/*.md`
 memories and attach it `read_only`. Ask a question whose answer is in the KB
 and confirm the agent quotes it instead of inventing an answer.
- **Manual restore.** Make the agent write a note you don't like, then roll the
 profile back by retrieving an older `memver_*` and writing its content back as
 the new head. Confirm a fresh session reads the restored version.
- **Team-plan path.** Run a call for Bob (team plan) and confirm the agent
 surfaces the "requires manager approval" limit from the policy store instead of
 promising an unconditional refund.

---

## What you've learned

- The end-to-end memory lifecycle: create a store, seed it, attach it to a
 session, let the agent read and write it, and recall it in a later session.
- Why a fresh context window doesn't mean a fresh start, the store is the
 durable state that outlives any single session.
- The multi-store safety pattern: per-user `read_write` plus shared `read_only`,
 and why that limits the blast radius of memory poisoning.
- Memory versioning as an audit trail, every write is an immutable `memver_*`
 attributed to its session, with a 30-day retention window and a manual restore
 path.
