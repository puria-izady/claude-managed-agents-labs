# Lab 3 - A Research Agent that Files to Google Docs

**Section**: 5 - Designing Effective Agents
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> **Run the notebook:** [`code/lab_03_research_agent/lab03.ipynb`](code/lab_03_research_agent/lab03.ipynb).
> Open it in Udemy Labs (nothing to install) or your own JupyterLab and run top to
> bottom. The steps below mirror the notebook cells.

---

## Goal: Overview

Build a `Research Brief` agent that web-searches a topic, writes a concise,
well-cited brief, then files that brief into **Google Docs** through a remote
MCP server. This is your first agent that combines the built-in toolset
(`web_search`, `web_fetch`, `write`) with an external **MCP connector** that
takes real action in another product.

By the end you will have: a finished brief, a brand-new Google Doc containing
it, and citations carried through to the doc.

**Estimated cost:** a few cents.

---

## Prereqs: Prerequisites

- **Python SDK** installed (`pip install anthropic`) and `ANTHROPIC_API_KEY` set.
- A Google Docs connection configured in Claude Managed Agents Vaults. Paste
  `GOOGLE_DOCS_VAULT_ID` in the setup cell. `GOOGLE_DOCS_MCP_URL` is only needed
  as an override if the vault has multiple MCP credentials or the URL cannot be
  inferred.
- Internet access for the agent (it needs `web_search` + `web_fetch`).

> **Note on credentials:** This lab uses Claude Managed Agents Vaults for Google
> OAuth. The token stays in the vault; the session only receives the vault id.

---

## Steps: Python path

The runnable script is [`labs/code/lab_03_research_agent/lab03.py`](code/lab_03_research_agent/lab03.py).
The steps below mirror it.

### Step 1 - Write a four-ingredient system prompt

The prompt lives in `labs/code/shared/prompts.py` as `RESEARCH_BRIEF_GDOCS_SYSTEM`.
It follows the role / constraints / tools / deliverable structure and tells the
agent to research, write a cited brief, **then create a Google Doc** with it:

```python
RESEARCH_BRIEF_GDOCS_SYSTEM = """\
ROLE
You are a research analyst. Your job is to research a topic the user
provides, write a concise, well-cited brief, then file that brief into
Google Docs.

CONSTRAINTS
- Always cite sources by URL inline, e.g. ([anthropic.com](https://anthropic.com)).
- Never invent numbers. If you can't verify a number, flag it as unverified.
- Keep the final brief concise.

TOOLS
You have web_search, web_fetch, write, and a "google_docs" MCP server.
Use web_search to discover sources, web_fetch to read them, write to draft
the brief, then call the google_docs MCP to create a new document.

DELIVERABLE
End every session by creating ONE Google Doc whose body is the finished
brief (exec summary, 3-5 cited paragraphs, a 'Sources' section). Report the
URL of the created Google Doc in your final message.
"""
```

### Step 2 - Declare the Google Docs MCP server on the agent

Create the agent with the **built-in toolset** plus an `mcp_servers` entry for
Google Docs, and expose those MCP tools via an `mcp_toolset`. Auth comes from
the Managed Agents vault attached to the session. If `GOOGLE_DOCS_MCP_URL` is
not set, read it from the vault credential before `agents.create`:

```python
GOOGLE_DOCS_VAULT_ID = os.environ["GOOGLE_DOCS_VAULT_ID"]
GOOGLE_DOCS_MCP_URL = os.environ.get("GOOGLE_DOCS_MCP_URL", "")

if not GOOGLE_DOCS_MCP_URL:
 credentials = client.beta.vaults.credentials.list(
  GOOGLE_DOCS_VAULT_ID,
  betas=["managed-agents-2026-04-01"],
 )
 mcp_credentials = [
  c for c in credentials if getattr(c.auth, "type", None) == "mcp_oauth"
 ]
 GOOGLE_DOCS_MCP_URL = mcp_credentials[0].auth.mcp_server_url

agent = client.beta.agents.create(
 name="Research Brief (Google Docs)",
 model="claude-haiku-4-5-20251001",
 system=RESEARCH_BRIEF_GDOCS_SYSTEM,
 mcp_servers=[{
 "type": "url",
 "name": "google_docs",
 "url": GOOGLE_DOCS_MCP_URL,
 }],
 tools=[
 {"type": "agent_toolset_20260401"}, # web_search, web_fetch, write...
 {"type": "mcp_toolset", # the Google Docs tools
 "mcp_server_name": "google_docs",
 "default_config": {"permission_policy": {"type": "always_allow"}}},
 ],
 betas=["managed-agents-2026-04-01"],
)
```

### Step 3 - Create a cloud environment that allows MCP + web

The agent needs to reach both the public web (for research) and the MCP server:

```python
RESEARCH_ALLOWED_HOSTS = [
 "*.com", "*.org", "*.net", "*.edu", "*.gov", "*.int",
 "*.io", "*.ai", "*.dev", "*.co", "*.de", "*.uk", "*.eu",
]

env = client.beta.environments.create(
 name="research-gdocs-env",
 config={"type": "cloud", "networking": {
 "type": "limited",
 "allow_mcp_servers": True,
 "allowed_hosts": RESEARCH_ALLOWED_HOSTS,
 }},
)
```

### Step 4 - Run a session and watch the tools fire

```python
session = client.beta.sessions.create(
 agent={"type": "agent", "id": agent.id, "version": agent.version},
 environment_id=env.id,
 vault_ids=[GOOGLE_DOCS_VAULT_ID],
 title="SMRs 2026 -> Google Docs",
)

with client.beta.sessions.events.stream(session.id) as stream:
 client.beta.sessions.events.send(session.id, events=[{
 "type": "user.message",
 "content": [{"type": "text", "text":
 "Research the state of small modular reactors in 2026. "
 "Write a concise, cited brief, then create a Google Doc "
 "containing it and tell me the URL."}],
 }])
 for event in stream:
 if event.type == "agent.message":
 for b in event.content:
 if b.type == "text":
 print(b.text, end="", flush=True)
 elif event.type == "agent.tool_use":
 print(f"\n[tool: {event.name}]")
 elif event.type == "agent.mcp_tool_use":
 print(f"\n[mcp: {event.name}]")
 elif event.type == "session.status_idle":
 break
```

### Step 5 - Pull the result

The deliverable is the **Google Doc itself**, not a local file. The agent reports
the new document's URL in its final `agent.message`. Open that URL to confirm the
brief landed with its citations intact.

> Run it end to end with `python lab03.py` from the lab folder.

---

## Bonus (optional): Claude Code

Not required - the notebook is the whole lab. If you want to try agentic
engineering, open this folder in Claude Code and use plain-English prompts:

> "Build me a Managed Agents agent called 'Research Brief (Google Docs)'. Use
> `claude-haiku-4-5-20251001` and a four-section system prompt (role / constraints / tools /
> deliverable). Enable the full agent toolset and declare a Google Docs MCP server
> from the `GOOGLE_DOCS_MCP_URL` env var. Tell the agent to research a topic, write
> a concise cited brief, then create a Google Doc with it and report the URL."

Then:

> "Create a limited-networking cloud environment that allows MCP servers and the
> open web, start a session, and ask for a brief on the state of small modular
> reactors in 2026. Stream the run and print the Google Doc URL it returns."

---

## Expected: Expected output

- Streamed `[tool: web_search]` and `[tool: web_fetch]` lines as it researches.
- A `[tool: write]` as it drafts the brief.
- An `[mcp: ...]` call that **creates the Google Doc**.
- A final message containing the **Google Doc URL**.
- Open the doc: a concise brief with an executive summary, cited analysis, and a
 Sources section listing the URLs actually consulted.

---

## Troubleshooting

- **MCP auth fails** (401/403 from the connector) → your `GOOGLE_DOCS_MCP_URL`
 or `GOOGLE_DOCS_VAULT_ID` is wrong, or the credential in the vault is expired
 or missing. Confirm the vault credential was created for the exact MCP server
 URL declared on the agent.
- **400 on environment creation** → `allowed_hosts` must contain hostnames or
 wildcard hostname patterns such as `"example.com"` or `"*.example.com"`. A
 bare `"*"` is rejected.
- **400 on session creation with `invalid vault_id`** → `GOOGLE_DOCS_VAULT_ID`
 is not the vault id. If it starts with `sk-ant-`, you pasted the Anthropic API
 key into the vault field. Clear it with
 `os.environ.pop("GOOGLE_DOCS_VAULT_ID", None)`, rerun the setup cell, and
 paste the `vlt_...` id from Claude Console.
- **Web tools can't reach the internet** → the environment networking blocked
 them. Make sure `networking.type` is `limited` with hostname patterns like
 `"*.com"` in `allowed_hosts`. Also set `allow_mcp_servers: True` so the
 connector is reachable.
- **Empty results / no brief** → the topic may be too narrow or the agent ran out
 of good sources. Broaden the topic, or add a follow-up turn: "Search more widely
 and try again." If the doc was never created, check the system prompt's
 deliverable section explicitly names the `google_docs` MCP.

---

## Stretch: Stretch

- **Add a length budget.** Add a constraint such as "Keep the brief under 500
 words" and a final `bash` word-count check before the doc is created.
- **List sources at the end.** Require a dedicated "Sources" section at the bottom
 of the Google Doc enumerating every URL the agent actually fetched, numbered.

---

## What you've learned

- Combining the built-in toolset with an external MCP connector in one agent.
- Declaring an `mcp_servers` entry and exposing it via an `mcp_toolset`.
- Driving a real side effect (a created Google Doc) from an agent session.
- Configuring environment networking so both web tools and MCP servers work.
