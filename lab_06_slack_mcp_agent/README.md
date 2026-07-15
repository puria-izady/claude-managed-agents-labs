# Lab 06 - Linear-aware MCP agent + vault

Wires an agent to the public Linear MCP server, attaches an existing Claude
Managed Agents vault credential, and asks the agent to triage issues and file a
new bug.

The folder keeps the old `slack` slug because earlier course links point here;
the current lab content is Linear.

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export LINEAR_VAULT_ID="vlt_..."                          # existing Linear vault
export LINEAR_MCP_URL=""                                  # optional override
export SLACK_VAULT_ID=""                                  # optional Slack vault
export SLACK_MCP_URL=""                                   # optional override
```

The script also keeps an advanced fallback that can create/register a Linear
vault from raw OAuth values, but the notebook path should use
`LINEAR_VAULT_ID` from Claude Console.

## Run

```bash
uv run --project .. --env-file ../.env python lab06.py
```

## Where to get the Linear vault

- In Claude Console, open the Managed Agents area and create or select a vault.
- Add/connect a Linear MCP OAuth credential to that vault.
- Copy the vault id that starts with `vlt_` into `LINEAR_VAULT_ID`.
- Leave `LINEAR_MCP_URL` blank unless the vault contains multiple MCP
  credentials and the code cannot choose the Linear one automatically.
- Optional: set `SLACK_VAULT_ID` too if you have a Slack MCP credential in a
  Managed Agents vault. The script/notebook will attach Slack alongside Linear.

The public Linear MCP URL is usually `https://mcp.linear.app/mcp`. It is a
hosted SaaS endpoint, so no local server or tunnel is required.

## Expected output

```
agent.id = agent_01...
vault.id = vlt_01... (existing Linear vault)
env.id   = env_01...
session.id = sesn_01...

I'll start by pulling your unassigned issues...
[mcp: linear_list_issues]
[mcp: linear_create_issue]

Filed ENG-142 "Login crashes on empty password".
--- session idle ---
```

If you see `session.error: mcp_auth_failed`, confirm the vault contains a Linear
MCP OAuth credential and that the credential URL matches the agent's MCP URL.
