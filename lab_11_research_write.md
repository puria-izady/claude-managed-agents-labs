# Lab 11 - Research, Write & Fact-Check Multi-Agent Pipeline

**Section**: 13 - Multi-Agent Orchestration
**Estimated time**: 35–45 minutes
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> Run the notebook [`code/lab_11_research_write/lab11.ipynb`](code/lab_11_research_write/lab11.ipynb) top to bottom in Udemy Labs or on your own machine. This page walks the same Python path step by step; the Claude Code prompts at the end are an optional bonus.

---

## Goal: Overview

You will build a coordinator that delegates to three specialists and produces a verified, well-cited brief on any topic:

- **Researcher** - uses web tools (web_search + web_fetch) to gather sources.
- **Writer** - drafts a brief from the researcher's citations.
- **Fact-Checker** - validates every claim against its linked source.

The coordinator owns the session, fans work out to the roster, and assembles the final brief. You will watch the primary thread to see who did what, and learn how primary and session threads differ.

**Estimated cost**: a few cents. You run this on your own machine with your own API key.

---

## Prereqs: Prereqs

- Multi-agent enabled on your account (request access if your key cannot create a coordinator).
- The Anthropic SDK installed: `pip install anthropic`.
- `ANTHROPIC_API_KEY` exported in your shell.
- Comfort with the single-agent session loop from earlier labs.

---

## Python: Python path

The full runnable script lives in [`code/lab_11_research_write/lab11.py`](code/lab_11_research_write/lab11.py). Walk these steps to understand each piece.

1. **Write the specialist prompts.** Each specialist gets a tight job description. The researcher writes citations to a shared file, the writer reads them and drafts, the fact-checker validates the draft. All three share the same container filesystem, so they hand off artifacts via files in `/workspace`.

 ```python
 RESEARCHER = """You research a topic. Use web_search for breadth and
 web_fetch on the most promising results. Write a JSON array of citations
 to /workspace/citations.json: each item {url, title, snippet, why_relevant}."""

 WRITER = """You draft a brief from the researcher's citations.
 Read /workspace/citations.json. Produce /workspace/draft.md (<=600 words)
 with inline citation links. Do not invent claims."""

 FACT_CHECKER = """For every claim in /workspace/draft.md, verify it against
 the linked source via web_fetch. Write /workspace/check.md with one of:
 [verified] - quote the source
 [partial] - quote the source and explain
 [unverified] - explain why it failed."""

 COORDINATOR = """You coordinate a research team. Given a topic:
 1) Delegate to the researcher (return when /workspace/citations.json exists).
 2) Delegate to the writer (return when /workspace/draft.md exists).
 3) Delegate to the fact-checker (return when /workspace/check.md exists).
 4) If check.md has any [unverified] claim, loop steps 2-3 with the writer
 fixing those claims.
 5) When the draft is clean, save the final brief to
 /mnt/session/outputs/brief.md."""
 ```

2. **Create the three specialists.** The researcher and fact-checker need web tools, so they enable a focused subset of `agent_toolset_20260401`. All agents use the course default Haiku model; role differences come from prompts and tool scope.

 ```python
 researcher = client.beta.agents.create(
 name="Researcher", model="claude-haiku-4-5-20251001", system=RESEARCHER,
 tools=[{
 "type": "agent_toolset_20260401",
 "default_config": {"enabled": False},
 "configs": [
 {"name": "web_search", "enabled": True},
 {"name": "web_fetch", "enabled": True},
 {"name": "write", "enabled": True},
 {"name": "read", "enabled": True},
 ],
 }],
 )
 writer = client.beta.agents.create(
 name="Writer", model="claude-haiku-4-5-20251001", system=WRITER,
 tools=[{"type": "agent_toolset_20260401"}],
 )
 fact_checker = client.beta.agents.create(
 name="Fact-Checker", model="claude-haiku-4-5-20251001", system=FACT_CHECKER,
 tools=[{
 "type": "agent_toolset_20260401",
 "default_config": {"enabled": False},
 "configs": [
 {"name": "web_fetch", "enabled": True},
 {"name": "read", "enabled": True},
 {"name": "write", "enabled": True},
 ],
 }],
 )
 ```

3. **Configure `multiagent.agents` on the coordinator.** The coordinator is the only agent your code talks to. It runs on the course default model because routing decisions matter most. Its roster lists the three specialists by id.

 ```python
 coordinator = client.beta.agents.create(
 name="Research Lead", model="claude-haiku-4-5-20251001", system=COORDINATOR,
 tools=[{"type": "agent_toolset_20260401"}],
 multiagent={
 "type": "coordinator",
 "agents": [
 {"type": "agent", "id": researcher.id},
 {"type": "agent", "id": writer.id},
 {"type": "agent", "id": fact_checker.id},
 ],
 },
 )
 ```

4. **Start a multiagent session.** Create a cloud environment with networking so the web tools work, then open a session on the coordinator and send the topic.

 ```python
 env = client.beta.environments.create(
 name="multiagent-env",
 config={"type": "cloud", "networking": {"type": "unrestricted"}},
 )
 session = client.beta.sessions.create(
 agent={"type": "agent", "id": coordinator.id, "version": coordinator.version},
 environment_id=env.id,
 title="Brief: agentic AI state of the art",
 )
 ```

5. **Observe primary vs session threads.** Stream the primary thread. It is a condensed view of all activity: one `session.thread_created` per specialist, an `agent.thread_message_received` each time a specialist returns, and the coordinator's own text. Drill into a specific session thread only when you need the full reasoning of one specialist.

 ```python
 with client.beta.sessions.events.stream(session.id) as stream:
 client.beta.sessions.events.send(session.id, events=[{
 "type": "user.message",
 "content": [{"type": "text",
 "text": "Topic: 'agentic AI, state of the art'. "
 "Produce a verified brief."}],
 }])
 for event in stream:
 if event.type == "session.thread_created":
 print(f"\n+ thread {event.agent_name}")
 elif event.type == "agent.thread_message_received":
 print(f" <- {event.from_agent_name} returned")
 elif event.type == "agent.message":
 for b in event.content:
 if b.type == "text":
 print(b.text, end="", flush=True)
 elif event.type == "session.status_idle":
 break
 ```

6. **Collect the final brief.** The coordinator saves `brief.md` into the session outputs. List the session files and download it.

 ```python
 for f in client.beta.files.list(
 scope_id=session.id, betas=["managed-agents-2026-04-01"],
 ):
 if f.filename == "brief.md":
 client.beta.files.download(f.id).write_to_file("outputs/brief.md")
 ```

Run it:

```bash
cd labs/code/lab_11_research_write
python lab11.py
```

---

## Bonus (optional): Claude Code

Not required: the notebook and Python path above are the whole lab. Prefer to build this conversationally? Paste these prompts into Claude Code one at a time.

**Prompt 1 - scaffold the specialists**

```
Using the Anthropic SDK (client.beta.*), create three agents with
agent_toolset_20260401:
- Researcher (claude-haiku-4-5-20251001): web_search + web_fetch + read + write only.
 System prompt: research a topic and write a JSON citation array to
 /workspace/citations.json.
- Writer (claude-haiku-4-5-20251001): full toolset. System prompt: read the citations
 and produce /workspace/draft.md, max 600 words, inline citations, no invented
 claims.
- Fact-Checker (claude-haiku-4-5-20251001): web_fetch + read + write only. System
 prompt: verify every claim in the draft against its linked source and write
 /workspace/check.md marking each claim verified, partial, or unverified.
Print each agent id.
```

**Prompt 2 - add the coordinator**

```
Create a coordinator agent "Research Lead" on claude-haiku-4-5-20251001 with
multiagent.type "coordinator" and a roster of the three specialist ids.
Its system prompt should delegate in order (researcher, writer, fact-checker),
loop the writer and fact-checker if any claim is unverified, then save the
final brief to /mnt/session/outputs/brief.md.
```

**Prompt 3 - run and watch**

```
Create a cloud environment with unrestricted networking, open a session on the
coordinator, and send the topic "agentic AI, state of the art. Produce a
verified brief." Stream the primary thread and print one line per
session.thread_created and per agent.thread_message_received so I can see which
specialist ran. Stop on session.status_idle.
```

**Prompt 4 - collect the brief**

```
List the session files and download brief.md into ./outputs/brief.md, then
print its contents.
```

---

## Expected: Expected output

- Three threads spawn on the primary stream: `+ thread Researcher`, `+ thread Writer`, `+ thread Fact-Checker`.
- One `<- ... returned` line per specialist as each finishes.
- Optionally a second Writer and Fact-Checker pass if the first check flagged an unverified claim.
- A `brief.md` file: a researched, written, fact-checked brief with inline citations that survive verification.

```
session.id = sesn_01...

+ thread Researcher
 <- Researcher returned
+ thread Writer
 <- Writer returned
+ thread Fact-Checker
 <- Fact-Checker returned
--- session idle ---
saved: outputs/brief.md
```

---

## Troubleshooting

- **Roster rejected as too large** → a coordinator roster holds at most **20 unique agents**. This lab uses three, so if you hit the cap you have duplicate or stray roster entries.
- **A specialist tries to delegate and fails** → the roster is **1 level deep**. Specialists cannot have their own rosters or call other agents; only the coordinator delegates.
- **New delegations seem to stall** → a session allows **25 concurrent threads = 1 primary + 24 child**. Parallel fan-out can hit the ceiling; new delegations queue until a slot frees.
- **Slots stay full after work is done** → **archive** finished threads to return their slots to the budget. Idle child threads keep holding a slot until archived.
- **A specialist blocks on a tool you did not expect** → an `always_ask` tool confirmation is **cross-posted to the primary thread** with its `session_thread_id`. Reply on the **primary thread** and the server routes the confirmation back to the right child thread. You never subscribe to specialist threads just for confirmations.
- **Coordinator skips a specialist** → tighten the coordinator prompt so each delegation step is explicit and names the file it should produce.

---

## Stretch: Stretch

- **Experiment with model routing.** Drafting is volume-heavy, so try a different model for the Writer and compare cost and quality against the brief you already produced.
- **Add a second fact-checker.** Create a fourth specialist that re-checks the brief with a different emphasis (for example, numbers and dates only), add it to the roster, and have the coordinator require both checkers to pass before saving.

---

## What you've learned

- The coordinator plus roster model end to end, configured through `multiagent.agents`.
- How the primary thread gives a condensed, readable view of multi-agent activity while session threads hold the full per-agent detail.
- Routing models by subtask: the course default for coordination, the same course default model with scoped specialist tools.
- The thread budget and how cross-posted confirmations keep your listener single-agent simple.
