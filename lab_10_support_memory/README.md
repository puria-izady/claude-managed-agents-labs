# Lab 10 - Customer-support agent with persistent memory

A support agent that remembers each customer across separate calls using a
memory store mounted at `/mnt/memory/`. The script seeds a per-customer store
plus a shared `read_only` policies store, runs two separate sessions for Alice,
and shows the second session recalling the first.

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Run

```bash
python3 lab10.py
```

## Expected output

```
created cust-alice: memstore_...
created cust-bob: memstore_...
customer stores: {'alice': 'memstore_...', 'bob': 'memstore_...'}
created policies store: memstore_...
agent.id: agent_...
env.id: env_...

=== session sesn_01... (alice) ===
Watch in Console: https://platform.claude.com/workspaces/default/sessions/sesn_01...
Hi Alice! I see you're on the Pro plan. Let me check our refund policy...
Yes, I can approve that refund for the broken widget purchased 7 days ago.
I've noted it on your record.

--- after first call /profile.md ---
Name: Alice Cooper
Plan: pro
Notes: ...

=== session sesn_02... (alice) ===
Watch in Console: https://platform.claude.com/workspaces/default/sessions/sesn_02...
Welcome back, Alice. Last time we approved a refund for a broken widget...

Alice memory versions (newest first):
  memver_02...  modified  2026-...
  memver_01...  created   2026-...
```

The second session **referencing the first** without you saying anything is the
lab's core demonstration.

On reruns, the setup reuses existing stores by name and prefers a `cust-alice`
store whose `/profile.md` already has notes. This avoids accidentally attaching
a fresh duplicate store before the second call.

## Carry forward

Save `stores['alice']` and at least one `session.id` for **Lab 11** (run a
dream over these).
