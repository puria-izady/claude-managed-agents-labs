# Lab 13 - Capstone: Personal Research Agent

The full integration in one runnable script: multi-agent (coordinator plus
three specialists) + two memory stores + an outcome rubric + Google Docs and
Slack MCP servers, both authenticated through Managed Agents vaults.

## Files

| File | Purpose |
|--|--|
| `lab13.py` | Builds the whole system and runs one brief end to end |
| `README.md` | This file |

## What `lab13.py` does

1. Builds the cloud environment and resolves the Google Docs and Slack vault credentials.
2. Creates three specialists (Researcher / Writer / Fact-Checker) and a coordinator with a `multiagent.agents` roster.
3. Attaches two memory stores to the session: `user-prefs` (read_only) and `topic-context` (read_write).
4. Declares the Google Docs and Slack MCP servers on the coordinator only.
5. Sends `user.define_outcome` with the rubric and `max_iterations`, then streams the run while the coordinator files the Google Doc and posts concise Slack updates.
6. Downloads the finished brief to `./outputs/<topic-slug>.md`.

Model choice: all agents run on `claude-haiku-4-5-20251001`; role differences
come from prompts, tool scope, and the coordinator topology.

## Environment variables

```bash
# Always required
export ANTHROPIC_API_KEY="sk-ant-..."

# Google Docs MCP (the brief is filed here, NOT to any other doc store)
export GOOGLE_DOCS_VAULT_ID="vlt_..."
# Optional only if the vault has multiple MCP credentials:
export GOOGLE_DOCS_MCP_URL="https://mcp.example.com/google-docs"

# Slack MCP (the agent posts its own updates here)
export SLACK_VAULT_ID="vlt_..."
# Optional only if the vault has multiple MCP credentials:
export SLACK_MCP_URL="https://mcp.example.com/slack"
export SLACK_CHANNEL="#research"

```

Preferred setup: create/connect the Google Docs MCP credential in Claude
Managed Agents Vaults, then paste the resulting vault id into
`GOOGLE_DOCS_VAULT_ID`. The notebook/script reads the MCP URL from that vault
credential when possible.

Create/connect the Slack MCP credential the same way and paste its vault id into
`SLACK_VAULT_ID`. `SLACK_CHANNEL` is not a secret; it only tells the coordinator
where to post. Authentication stays in the vault.

## Run

```bash
uv run --project .. --env-file ../.env python lab13.py "small modular reactors"
```

Run a second topic to see `user-prefs` reused while a fresh `topic-context`
store is created (and recalled on later runs of the same topic):

```bash
uv run --project .. --env-file ../.env python lab13.py "advances in solid-state batteries"
```

## Slack updates

The coordinator has the Slack MCP toolset and may post at most two short
messages: one progress update after research starts and one final completion
message after the Google Doc is filed. This keeps the capstone vault-first and
avoids any extra public server.

## Estimated cost

A few cents to a couple dollars. This is the biggest lab; a low spend cap
keeps the ceiling safe.
