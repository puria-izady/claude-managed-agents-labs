# Lab 02 - First Python session

The ~12-line agent: create a client, then an Agent + Environment + Session, send a `user.message`, and stream the response. Recreates the Lab 1 coding assistant from code.

Uses model `claude-haiku-4-5-20251001` and toolset `agent_toolset_20260401` (both current; may update over time). Everything runs under `client.beta.*`, which adds the Managed Agents beta header for you.

## Run

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # if not already in your shell
python lab02.py
```

## What you'll see

```
agent.id   = agent_01...
env.id     = env_01...
session.id = sesn_01...

I'll create the Fibonacci script and run it...
[tool: write]
[tool: bash]
The first 20 Fibonacci numbers are: 0, 1, 1, 2, ...
--- session idle ---
```

## Carry forward

Save these for later labs:
- `agent.id` -> reused in later labs as `AGENT_ID`
- `env.id` -> reused in later labs as `ENV_ID`
