# Lab 6 - Linear-Aware Agent via MCP + Vault

**Section**: 8 - Custom Tools & MCP
**Estimated time**: 30 to 40 minutes
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus (requires a Linear workspace you control)
**Cost: Estimated cost:** a few cents

> Run the lab as a notebook: [`labs/code/lab_06_slack_mcp_agent/lab06.ipynb`](code/lab_06_slack_mcp_agent/lab06.ipynb). The steps below mirror the notebook cell by cell; the `lab06.py` script is the same flow as a single runnable file.

---

## Goal: Goal
Build an agent that connects to Linear through the public Linear MCP server, authenticated per end user with a vault credential, and uses it to triage open issues and file a new bug.

## Prereqs: Prereqs
- A Linear account and a workspace where you can create issues.
- A Linear connection configured in Claude Managed Agents Vaults. Copy the resulting vault id that starts with `vlt_`.
- Optional: a Slack connection configured in Claude Managed Agents Vaults. Set `SLACK_VAULT_ID` if you want this lab to attach Slack tools too.
- The public Linear MCP URL: `https://mcp.linear.app/mcp`. This is a hosted SaaS connector, so you do not run a local server or a tunnel.
- Run on your own machine with your own `ANTHROPIC_API_KEY`.

> The Managed Agents harness reaches MCP servers over the public internet. Always point at a public, remote, or SaaS MCP endpoint like the one above. Local MCP tunnels are a research preview and are not used in this course.

---

## Python: Python path

The runnable version of every step lives in [`labs/code/lab_06_slack_mcp_agent/lab06.py`](code/lab_06_slack_mcp_agent/lab06.py). The filename keeps the old `slack` slug only because the decks link to it; the content is Linear. Work through the steps below, then run the script.

### Step 1 - Resolve the Linear vault and declare MCP servers
The existing vault supplies auth at session time. The code reads the Linear MCP URL from the vault credential when `LINEAR_MCP_URL` is unset, then declares that MCP server on the agent. If `SLACK_VAULT_ID` is set, the code uses the same pattern to attach Slack as a second MCP server. The `mcp_toolset` entries expose those tools.

```python
# lab06.py
import os
from anthropic import Anthropic
client = Anthropic()

LINEAR_VAULT_ID = os.environ["LINEAR_VAULT_ID"] # vlt_...
LINEAR_MCP_URL = os.environ.get("LINEAR_MCP_URL") or mcp_url_from_vault(
 client,
 LINEAR_VAULT_ID,
 "linear",
)

agent = client.beta.agents.create(
 name="Linear Triage Agent",
 model="claude-haiku-4-5-20251001",
 system=("You are a Linear assistant. You triage issues and file new ones"
 " via the linear MCP. When asked to file a bug, create a clear,"
 " well-titled issue with reproduction steps. Always confirm the"
 " issue identifier (e.g. ENG-123) of anything you create."),
 mcp_servers=[{
 "type": "url",
 "name": "linear",
 "url": LINEAR_MCP_URL,
 }],
 tools=[
 {"type": "agent_toolset_20260401"},
 {"type": "mcp_toolset", "mcp_server_name": "linear",
 "default_config": {"permission_policy": {"type": "always_allow"}}},
 ],
)
```

### Step 2 - Use the existing Linear vault
One agent definition serves many users. Each user's Linear or Slack credential lives in its own vault. In the course path, create/connect that credential in Claude Console, then paste the vault id in the setup cell or set `LINEAR_VAULT_ID` / `SLACK_VAULT_ID` in `labs/code/.env`.

```python
print("Using existing Linear vault:", LINEAR_VAULT_ID)
print("Credential MCP URL:", LINEAR_MCP_URL)
vault_ids = [LINEAR_VAULT_ID]
if os.environ.get("SLACK_VAULT_ID"):
 vault_ids.append(os.environ["SLACK_VAULT_ID"])
```

### Step 3 - Keep raw OAuth out of the notebook
Do not paste Linear or Slack access tokens into the notebook. Configure SaaS connections in Claude Managed Agents Vaults, then attach the vault ids to the session. The script keeps a Linear token-based fallback for automation, but the notebook demonstrates the safer vault-first path.

```python
# No raw OAuth token is needed in the notebook path.
# The session below attaches the prepared vault_ids list.
```

### Step 4 - Create an environment and a session that references the vault
The environment uses limited networking but allows MCP servers, so the harness can reach the public Linear endpoint. The session references the vault via `vault_ids`; auth wires up server-side.

```python
env = client.beta.environments.create(
 name="linear-env",
 config={"type": "cloud", "networking": {"type": "limited",
 "allow_mcp_servers": True,
 "allowed_hosts": []}},
)
session = client.beta.sessions.create(
 agent={"type": "agent", "id": agent.id, "version": agent.version},
 environment_id=env.id,
 vault_ids=vault_ids,
 title="Linear triage + file a bug",
)
```

### Step 5 - Ask the agent to triage and file an issue, then stream
```python
with client.beta.sessions.events.stream(session.id) as stream:
 client.beta.sessions.events.send(session.id, events=[{
 "type": "user.message",
 "content": [{"type": "text",
 "text": "Triage my unassigned Linear issues and tell me"
 " the top three by likely priority. Then file a"
 " new bug titled 'Login crashes on empty password'"
 " with short reproduction steps. Report the new"
 " issue identifier when done."}],
 }])
 for event in stream:
 if event.type == "agent.message":
 for b in event.content:
 if b.type == "text": print(b.text, end="", flush=True)
 elif event.type == "agent.mcp_tool_use":
 print(f"\n[mcp: {event.name}]")
 elif event.type == "session.error":
 print(f"\n[ERROR] {event.error}")
 elif event.type == "session.status_idle":
 break
```

---

## Bonus (optional): Claude Code

Prefer to drive this from Claude Code instead of writing the script yourself? Paste these prompts in order. Have your Linear vault id ready.

1. > Create a Managed Agents agent named "Linear Triage Agent" on model `claude-haiku-4-5-20251001`. Declare a single MCP server named `linear` with URL `https://mcp.linear.app/mcp`. Give it the toolset `agent_toolset_20260401` plus an `mcp_toolset` for `linear` with permission policy `always_allow`. The system prompt should tell it to triage and file Linear issues and always confirm the issue identifier it creates.

2. > Use my existing Linear Managed Agents vault from `LINEAR_VAULT_ID`. Read the Linear MCP URL from the vault credential when `LINEAR_MCP_URL` is unset, then declare that URL on the agent.

3. > Create a cloud environment named `linear-env` with limited networking but `allow_mcp_servers` true. Then start a session for the agent on that environment, passing the Linear vault id, plus Slack if configured, in `vault_ids`. Title it "Linear triage + file a bug".

4. > In that session, send this user message and stream the response, printing each `agent.mcp_tool_use` name as it happens: "Triage my unassigned Linear issues and tell me the top three by likely priority. Then file a new bug titled 'Login crashes on empty password' with short reproduction steps. Report the new issue identifier when done." Stop when the session goes idle.

---

## Expected: Expected output
- `[mcp: linear_list_issues]` (or similar) as the agent reads your workspace.
- `[mcp: linear_create_issue]` as it files the new bug.
- The agent's final turn names the new issue identifier (for example `ENG-142`).
- A new issue titled "Login crashes on empty password" visible in your Linear workspace.
- No `session.error` events about MCP auth.

---

## Troubleshooting
- **`invalid vault_id`** -> `LINEAR_VAULT_ID` must be the vault id from Claude Console and should start with `vlt_`. Do not paste your `sk-ant-...` API key into this field.
- **`session.error: mcp_auth_failed` or "missing credential"** -> the vault credential is wrong, expired, or was not registered for the exact `mcp_server_url`. Confirm `LINEAR_VAULT_ID` points to the vault with the Linear MCP OAuth credential and that the credential URL matches the agent's `LINEAR_MCP_URL`.
- **Could not uniquely identify the Linear MCP credential** -> the vault has multiple MCP credentials. Set `LINEAR_MCP_URL=https://mcp.linear.app/mcp` explicitly.
- **No MCP tool calls appear** -> the agent did not discover the server. Confirm all three pieces are wired: the `mcp_servers` array on the agent, the `mcp_toolset` entry in `tools`, and `vault_ids` passed at session creation.
- **OAuth scope errors when creating issues** -> the Linear connection in the vault lacks write scope. Reconnect or rotate the Linear credential in Claude Console with issue write access.
- **Tool calls pause for confirmation** -> the MCP default permission policy is `always_ask`. Either set `always_allow` on the `mcp_toolset` (Step 1) or implement the confirmation flow to approve each call. Leaving it as `always_ask` is the safer default in production.
- **Networking blocked** -> make sure the environment has `allow_mcp_servers: true`; with strict networking the harness cannot reach the public Linear endpoint.

---

## Stretch: Stretch
- Have the agent **label and assign** the issue it files (for example label `bug`, assign to yourself), then confirm the change with another MCP tool call.
- Ask it to **query existing issues** by team or status and produce a short triage report before filing anything.
- Reconnect or rotate the Linear credential in Claude Console and confirm a new session picks up the refreshed secret.
- Switch the `mcp_toolset` policy to `always_ask` and implement the approval flow so a human confirms each write to Linear.

## What you've learned
- The two-step MCP wiring: declare the server on the agent, supply auth on the session via a vault.
- How to attach per-user SaaS credentials from Claude Managed Agents Vaults.
- Why public, remote MCP endpoints are the only supported surface (no tunnels).
- How MCP auth failures surface as non-fatal `session.error` events.
