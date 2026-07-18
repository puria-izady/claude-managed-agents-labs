# Lab 06 - Linear + Slack MCP agent with Vaults

Wires an agent to the public Linear and Slack MCP servers. Both MCP OAuth
credentials live in the same Claude Managed Agents vault. After creating the
Linear ticket, the agent posts a completion update to Slack with the ticket
title and issue identifier.

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export LINEAR_VAULT_ID="vlt_..."  # vault containing Linear and Slack
export SLACK_CHANNEL="#research"  # completion-update destination
```

## Run

```bash
uv run --project .. --env-file ../.env python lab06.py
```

## Configure the shared vault

- In Claude Console, open the Managed Agents area and create or select a vault.
- Add/connect both Linear and Slack MCP OAuth credentials to that same vault.
- Copy the vault id that starts with `vlt_` into `LINEAR_VAULT_ID`.

The script reads both MCP server URLs directly from the vault credentials. No
manual Linear or Slack MCP URL configuration is used.

## Expected output

```
agent.id = agent_01...
vault.id = vlt_01... (Linear + Slack)
env.id   = env_01...
session.id = sesn_01...

I'll start by pulling your unassigned issues...
[mcp: linear_list_issues]
[mcp: linear_create_issue]
[mcp: slack_post_message]

Filed ENG-142 "Login crashes on empty password".
Posted the completion update to #research.
--- session idle ---
```

If you see `session.error: mcp_auth_failed`, confirm the shared vault contains
valid Linear and Slack MCP OAuth credentials.
