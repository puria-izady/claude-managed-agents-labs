# Lab 05 - Streaming Agent Sessions

A tiny terminal console: chat with one persistent session, watch the agent's
tool use stream by live, and track a running cost on the session.

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional: reuse an agent/env you already built. If unset, the script
# creates a fresh agent and a plain cloud environment for you.
export AGENT_ID="agent_..."        # e.g. from Lab 02
export ENV_ID="env_..."            # e.g. from Lab 02 or Lab 04
export MODEL="claude-haiku-4-5-20251001"     # optional, default claude-haiku-4-5-20251001
```

## Run

```bash
python lab05.py
```

## Commands inside the session console

| Input | Behavior |
|--|--|
| `<any prompt>` | Sends a `user.message`, streams the agent's reply and tool use |
| `interrupt` | Sends `user.interrupt`, halts the agent cleanly, preserves state |
| `quit` / `exit` | Ends the console and prints the final running total |

## Files

- `lab05.py`: the interactive session loop. Creates agent/env/session, streams events, prints
  `agent.message` text and `agent.tool_use` markers, ticks a running cost.
- `../shared/cost_meter.py`: shared list-price estimate helper used by all
  session-based labs.

## Cost

A few cents for a short session. The meter prints a list-price estimate per
session ID and a total across all session IDs passed to the helper. It uses
`session.usage` plus Managed Agents active runtime. Check Claude Console billing
for authoritative cost.

## Tip

Try `What's in /workspace?` then `Read /etc/os-release.` The cost meter is
cumulative, so the total climbs across turns within the same session.
