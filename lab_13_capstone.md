# Lab 13 - Capstone: Personal Research Agent

**Section**: F - Capstone and Next Steps
**Chapter**: 17 - Capstone: Personal Research Agent
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> Run the notebook `labs/code/lab_13_capstone/lab13.ipynb` top to bottom (in Udemy Labs or your own machine). The steps below mirror its cells; the committed `lab13.py` is the same pipeline as a single script.

---

## Overview

This is the capstone. You build a Personal Research Agent that takes a topic,
coordinates a Researcher, a Writer, and a Fact-Checker, remembers your
preferences across sessions, and iterates against an outcome rubric until the
brief is genuinely good enough. When the rubric is satisfied, the coordinator
files the cited brief to a new Google Doc and posts concise updates to Slack.

Nothing here is new on its own. The capstone is the assembly: one coordinator
routes the job and three specialists do the work; one environment runs them
and vault-backed credentials hold the Google Docs and Slack connections; two
memory stores ride along (your
preferences read-only, the per-topic history read-write); one rubric decides
when the brief is done; the Google Docs MCP files it; and the Slack MCP lets
the coordinator post its own status updates. The whole thing runs from a
single script, `lab13.py`.

Estimated cost: a few cents to a couple dollars. This is the biggest lab in
the course; a low spend cap keeps the price ceiling concrete and safe.

---

## Prereqs

- A working setup from the earlier labs: multi-agent rosters, memory stores, outcome rubrics, and MCP via a vault all need to be familiar.
- Your own machine, an Anthropic API key, and Python with the `anthropic` SDK installed.
- A Google Docs Managed Agents vault with a Google Docs MCP OAuth credential. The
  agent files the brief here, so this connector must be reachable. The script
  can usually read the MCP URL from the vault; set `GOOGLE_DOCS_MCP_URL` only if
  the vault has multiple MCP credentials.
- A Slack Managed Agents vault with a Slack MCP credential. Set `SLACK_VAULT_ID`;
  set `SLACK_MCP_URL` only if the vault has multiple MCP credentials. Keep
  `SLACK_CHANNEL` as a simple non-secret channel setting, for example `#research`.

---

## Python path

Work through the script `labs/code/lab_13_capstone/lab13.py`. Each numbered
step below maps to one part of that file.

1. **Build the environment and resolve the vaults.** Create a cloud environment
	 with limited networking that explicitly allows the Google Docs endpoints and
	 MCP servers, then resolve the Google Docs and Slack connections from their
	 vaults. The vaults are what let the agent file the brief as you and post to
	 Slack as you: the tokens never reach the sandbox where Claude's code runs.

 ```python
 env = client.beta.environments.create(
 name="capstone-env",
 config={
 "type": "cloud",
 "packages": {"pip": ["beautifulsoup4", "markdownify"]},
 "networking": {
 "type": "limited",
 "allowed_hosts": [
 "docs.googleapis.com",
 "www.googleapis.com",
 ],
 "allow_mcp_servers": True,
 "allow_package_managers": True,
 },
 },
 )

 google_docs_vault_id, google_docs_mcp_url = resolve_google_docs_connection(client)
 slack_vault_id, slack_mcp_url = resolve_required_mcp_connection(
     client, provider="slack", vault_env="SLACK_VAULT_ID", url_env="SLACK_MCP_URL")
 ```

2. **Configure the `multiagent.agents` roster.** Create the three specialists,
 then create the coordinator with the roster listing them. All agents use
 `claude-haiku-4-5-20251001`; role differences come from prompts, tool scope,
 and the coordinator topology.

 ```python
 researcher = client.beta.agents.create(
 name="Capstone Researcher", model="claude-haiku-4-5-20251001", system=RESEARCHER,
 tools=[{"type": "agent_toolset_20260401",
 "default_config": {"enabled": False},
 "configs": [{"name": "web_search", "enabled": True},
 {"name": "web_fetch", "enabled": True},
 {"name": "read", "enabled": True},
 {"name": "write", "enabled": True}]}])
 writer = client.beta.agents.create(
 name="Capstone Writer", model="claude-haiku-4-5-20251001", system=WRITER,
 tools=[{"type": "agent_toolset_20260401"}])
 fact_checker = client.beta.agents.create(
 name="Capstone Fact-Checker", model="claude-haiku-4-5-20251001", system=FACT_CHECKER,
 tools=[{"type": "agent_toolset_20260401",
 "default_config": {"enabled": False},
 "configs": [{"name": "web_fetch", "enabled": True},
 {"name": "read", "enabled": True},
 {"name": "write", "enabled": True}]}])

 coordinator = client.beta.agents.create(
 name="Capstone Research Lead", model="claude-haiku-4-5-20251001", system=COORDINATOR,
 mcp_servers=[
 {"type": "url", "name": "google_docs", "url": google_docs_mcp_url},
 {"type": "url", "name": "slack", "url": slack_mcp_url}],
 tools=[{"type": "agent_toolset_20260401"},
 {"type": "mcp_toolset", "mcp_server_name": "google_docs"},
 {"type": "mcp_toolset", "mcp_server_name": "slack"}],
 multiagent={"type": "coordinator", "agents": [
 {"type": "agent", "id": researcher.id},
 {"type": "agent", "id": writer.id},
 {"type": "agent", "id": fact_checker.id}]})
 ```

3. **Attach the two memory stores.** Create a `user-prefs` store and seed it
 once with tone, length, and trusted sources. Create (or reuse) a per-topic
 `topic-context` store. You attach both to the session: `user-prefs` as
 `read_only` so preferences can never be overwritten, and `topic-context` as
 `read_write` so the coordinator can append a running log that accumulates
 across runs.

 ```python
 prefs = client.beta.memory_stores.create(name="capstone-user-prefs", ...)
 client.beta.memory_stores.memories.create(prefs.id, path="/style.md", content="...")
 client.beta.memory_stores.memories.create(prefs.id, path="/trusted_sources.md", content="...")

 topic_store = client.beta.memory_stores.create(name=f"capstone-topic-{slug}", ...)
 ```

4. **Declare the Google Docs and Slack MCP servers on the coordinator.** This
 was done in step 2 via `mcp_servers` plus the `mcp_toolset` entries. The MCP
 servers live on the coordinator only; the specialists never touch them. The
 coordinator authenticates to them through vault credentials at session time.

5. **Run an outcome-driven session with the rubric.** Create the session with
 both vaults and both memory stores attached, then send `user.define_outcome`
 with the rubric and a `max_iterations` safety rail. One call kicks off the
 whole pipeline: research, draft, fact-check, grade, and loop on a failed
 grade.

 ```python
 session = client.beta.sessions.create(
 agent={"type": "agent", "id": coordinator.id},
 environment_id=env.id, vault_ids=[google_docs_vault_id, slack_vault_id],
 resources=[
 {"type": "memory_store", "memory_store_id": prefs.id, "access": "read_only"},
 {"type": "memory_store", "memory_store_id": topic_store.id, "access": "read_write"}],
 title=topic)

 with client.beta.sessions.events.stream(session.id) as stream:
 client.beta.sessions.events.send(session.id, events=[{
 "type": "user.define_outcome",
 "description": f"Produce a research brief on: {topic}.",
 "rubric": {"type": "text", "content": RUBRIC},
 "max_iterations": 8}])
 for event in stream:
 if event.type == "session.thread_created":
 print(f"+ thread {event.agent_name}")
 elif event.type == "agent.thread_message_received":
 print(f" <- {event.from_agent_name} returned")
 elif event.type == "agent.mcp_tool_use":
 print(f" [mcp: {event.name}]")
 elif event.type == "span.outcome_evaluation_end":
 print(f" iter {event.iteration}: {event.result}")
 elif event.type == "session.status_idle":
 break
 ```

 The rubric is the loop's exit condition. It encodes both goals at once: the
 brief must be well-cited and within the length budget. It also points the
 grader at the trusted-sources memory file.

 ```markdown
 # Research Brief Rubric

 ## Content
 - Topic clearly defined in the opening paragraph.
 - 4-6 substantive claims, each supported by an inline citation.
 - No claim without a source. 500-600 words total.

 ## Sources
 - At least 5 distinct sources.
 - All from /mnt/memory/user-prefs/trusted_sources.md or comparable quality.
 - Each source linked by URL in an inline citation.

 ## Output
 - Saved as /mnt/session/outputs/brief.md.
 - Filed to a new Google Doc under "Research" via the google_docs MCP server.
 ```

6. **Retrieve the brief.** List the session's files, find `brief.md`, and
 download it locally so you have the cited brief next to the Google Doc.

 ```python
 for f in client.beta.files.list(scope_id=session.id, betas=["managed-agents-2026-04-01"]):
 if f.filename == "brief.md":
 client.beta.files.download(f.id).write_to_file(f"./outputs/{slug}.md")
 ```

---

## Bonus (optional): Claude Code

Not required. If you would rather drive this from Claude Code, paste these prompts in order.
Claude Code can author the script and then run it against your connectors.

1. Scaffold the agents and infrastructure:

> Write a Python script `lab13.py` using the Anthropic SDK `client.beta.*` Agents APIs. Create a cloud environment with limited networking that allows `docs.googleapis.com` and `www.googleapis.com` plus MCP servers and package managers. Use existing Managed Agents vaults from `GOOGLE_DOCS_VAULT_ID` and `SLACK_VAULT_ID`; read each MCP URL from the vault when possible, with `GOOGLE_DOCS_MCP_URL` and `SLACK_MCP_URL` as optional overrides. Create three specialist agents (a Researcher and a Writer on `claude-haiku-4-5-20251001`, a Fact-Checker on `claude-haiku-4-5-20251001`) each with the `agent_toolset_20260401` toolset scoped to the tools that role needs.

2. Wire the coordinator, memory, and outcome loop:

> In the same script, create a coordinator agent named "Capstone Research Lead" on `claude-haiku-4-5-20251001` with a `multiagent.agents` roster of the three specialists, `mcp_toolset` entries for `google_docs` and `slack`, and a system prompt that delegates research, drafting, and fact-checking, loops on fact-check failures, files the final brief to a new Google Doc under "Research", posts at most two concise Slack updates to `SLACK_CHANNEL`, and logs a one-line summary to the topic memory store. Create a `user-prefs` memory store (seed it with tone, length, and trusted sources) and a per-topic `topic-context` store. Create a session attaching both vaults, `user-prefs` as read_only, and `topic-context` as read_write. Send `user.define_outcome` with a rubric requiring a well-cited 500-600 word brief filed to Google Docs, with `max_iterations=8`. Stream the run and print thread, MCP, and outcome-evaluation events.

3. Retrieve and run:

 > After the run, download the session's `brief.md` to `./outputs/<topic-slug>.md`. Run `python lab13.py "small modular reactors"` with my env vars set and show me the streamed events, the Google Doc that was filed, and the Slack MCP update. If either external action did not appear, read the error and tell me whether the vault credential or the MCP URL is the problem.

---

## Expected output

The stream shows the specialists spawn and return, the grader's iteration
count climb toward `satisfied`, and the coordinator's MCP calls into Google
Docs and Slack. The run ends with a cited brief filed to a new Google Doc and
short Slack updates posted by the agent.

```
session.id = sesn_01...

+ thread Capstone Researcher
 <- Capstone Researcher returned
+ thread Capstone Writer
 <- Capstone Writer returned
+ thread Capstone Fact-Checker
 <- Capstone Fact-Checker returned
 iter 1: not_satisfied
+ thread Capstone Writer
 <- Capstone Writer returned
 iter 2: satisfied
 [mcp: create_document]
--- session idle ---

Slack notified on #research.
saved: outputs/small-modular-reactors.md
```

- A new Google Doc under "Research" with the cited brief as its content.
- A Slack message in your channel: "Brief ready: small modular reactors ...".
- `outputs/<topic-slug>.md` saved locally.

---

## Troubleshooting

- **No Google Doc filed.** Confirm the vault has a Google Docs MCP OAuth credential and that the resolved MCP URL is the one declared on the coordinator. Also confirm `docs.googleapis.com` is in the environment's `allowed_hosts`.
- **No Slack update.** Confirm the vault has a Slack MCP credential, `SLACK_CHANNEL`
 points to a channel the connected Slack account can post to, and the run reached
 the Slack step. If the channel is private, invite the connected Slack app/user.
- **`failed` or stuck outcome.** Re-read the rubric against the topic description; if they contradict, the grader can never pass. The Fact-Checker may also be failing on weak sources, so the loop never goes clean. Soften the rubric or strengthen the Researcher's trusted-sources preferences.
- **MCP auth errors.** If you see `mcp_auth_failed`, the Google Docs or Slack
 credential in the vault is missing, expired, scoped without the required
 permission, or registered for a different MCP URL. Reconnect the credential in
 the vault. Refresh fields are optional hardening for longer-lived Google runs.

---

## Stretch

- **Run a second topic.** Run the script on a new topic, then on the first topic again, and confirm the `topic-context` store recalls the earlier run while `user-prefs` is reused unchanged.
- **Add another MCP target.** Attach a third vault-backed MCP server, such as
 Linear or GitHub, and ask the coordinator to file follow-up work after the
 brief is complete.
- **Cost-optimize.** Lower `max_iterations`, tighten the rubric, or scope specialist tools more narrowly and measure quality on a few briefs.
- **Consolidate memory.** After several briefs, run a consolidation pass over the `topic-context` stores so retrieval stays cheap, then point the next run at the consolidated store.

---

## What you've shipped

A real, end-to-end agentic system that coordinates multiple Claude specialists,
remembers and improves across sessions, reaches into a real third-party service
securely through a vault, drives itself to a quality bar with an outcome rubric,
and announces its own results. This is the portfolio piece.
