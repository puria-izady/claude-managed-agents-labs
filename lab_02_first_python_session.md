# Lab 2 - Your First Python Session

**Section**: 2 - Setting Up Your Workspace
**Estimated time**: 15-20 minutes
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> Run this lab as the notebook [`code/lab_02_first_python_session/lab02.ipynb`](code/lab_02_first_python_session/lab02.ipynb) in Udemy Labs.

---

## Overview

In Lab 1 you built a coding-assistant agent in the Console: it wrote a Fibonacci script and ran it. In this lab you recreate that exact agent in about a dozen lines of Python and stream a turn from your terminal. By the end you will have created an agent, a cloud environment, and a session entirely from code, and watched the agent write and run `fib.py` live.

This is the bridge between the no-code Console and the API you will use for the rest of the course.

**Estimated cost:** a few cents.

## Prerequisites

- The Anthropic Python SDK installed (`pip install -U anthropic`) - see Chapter 2 for the full setup.
- `ANTHROPIC_API_KEY` set in your shell - also covered in Chapter 2.
- Lab 1 finished, so you know what the agent should do.

Quick check that both are in place:

```bash
echo $ANTHROPIC_API_KEY # should print sk-ant-...
python -c "import anthropic; print('ok')"
```

> The Managed Agents endpoints need a beta header. You do not set it by hand: every call under `client.beta.*` adds it for you. That is the whole reason the code uses `client.beta.agents`, `client.beta.environments`, and `client.beta.sessions`.

---

## Python path

The full runnable script is in [`code/lab_02_first_python_session/lab02.py`](code/lab_02_first_python_session/lab02.py). Follow these steps to understand each piece, then run it.

### Step 1 - Create the working folder

```bash
mkdir -p ~/ma-labs/lab02 && cd ~/ma-labs/lab02
```

Copy `lab02.py` here, or write it yourself following the steps below.

### Step 2 - Create the client

`Anthropic()` reads `ANTHROPIC_API_KEY` from your environment. The `.beta` namespace you will use next adds the Managed Agents beta header automatically.

```python
from anthropic import Anthropic

client = Anthropic()
```

### Step 3 - Create the agent

The model, system prompt, and toolset live on the **agent**, not the session. Use the course default model and the prebuilt agent toolset.

```python
agent = client.beta.agents.create(
 name="Coding Assistant",
 model="claude-haiku-4-5-20251001", # course default; swap as models update
 system="You are a helpful coding assistant. Write clean code and verify it runs.",
 tools=[{"type": "agent_toolset_20260401"}], # date-stamped toolset; may update
)
print(f"agent.id = {agent.id}")
```

> Both the model id (`claude-haiku-4-5-20251001`) and the toolset id (`agent_toolset_20260401`) are current values. They are versioned on purpose, so a newer model or a newer dated toolset may exist by the time you watch this. The flow does not change.

### Step 4 - Create the cloud environment

The environment is a template for the container the agent's tools run in. A cloud environment with unrestricted networking is the simplest choice for a lab.

```python
env = client.beta.environments.create(
 name="lab02-env",
 config={"type": "cloud", "networking": {"type": "unrestricted"}},
)
print(f"env.id = {env.id}")
```

### Step 5 - Create the session

The session ties the agent to the environment. Pin it to the exact agent version you just created.

```python
session = client.beta.sessions.create(
 agent={"type": "agent", "id": agent.id, "version": agent.version},
 environment_id=env.id,
 title="Lab 2 first session",
)
print(f"session.id = {session.id}")
```

### Step 6 - Send a message and stream events

Open the stream **first**, then send the user message, so you do not miss any early events. Print the agent's text as it arrives, print a line for each tool use, and stop when the session goes idle.

```python
with client.beta.sessions.events.stream(session_id=session.id) as stream:
 client.beta.sessions.events.send(
 session_id=session.id,
 events=[{
 "type": "user.message",
 "content": [{
 "type": "text",
 "text": "Create /workspace/fib.py that prints the first 20 "
 "Fibonacci numbers. Then run it.",
 }],
 }],
 )

 for event in stream:
 if event.type == "agent.message":
 for block in event.content:
 if block.type == "text":
 print(block.text, end="", flush=True)
 elif event.type == "agent.tool_use":
 print(f"\n[tool: {event.name}]")
 elif event.type == "session.status_idle":
 print("\n--- session idle ---")
 break
```

### Step 7 - Run it

```bash
python lab02.py
```

---

## Bonus (optional): Claude Code

Prefer to generate the script instead of typing it? Open Claude Code in your lab folder and use these prompts in order:

1. > Using the Anthropic Python SDK, write a minimal script that creates a Managed Agent named "Coding Assistant" with model `claude-haiku-4-5-20251001` and the `agent_toolset_20260401` toolset, then creates a cloud environment with unrestricted networking, then a session that references the agent. Use the `client.beta.*` namespace so the beta header is added automatically.

2. > Now add a streamed turn: open the session event stream, send a user message asking the agent to create `/workspace/fib.py` that prints the first 20 Fibonacci numbers and run it, then print the agent's text and each tool use, stopping when the session goes idle.

3. > Run the script and show me the output.

---

## Expected output

You should see, in order:

- Three printed IDs: `agent.id`, `env.id`, `session.id`.
- Streamed `[tool: ...]` lines as the agent works - typically `write` (creating `fib.py`), then `bash` (running it), and maybe `read`.
- The agent's chat text explaining what it created and the output it observed (the first 20 Fibonacci numbers).
- A final `--- session idle ---` line.

The agent has now written `/workspace/fib.py` and executed it inside the cloud container, exactly like Lab 1 but driven from your terminal.

---

## Troubleshooting

- **`AuthenticationError` / 401** - your key is missing or wrong. Run `echo $ANTHROPIC_API_KEY` and confirm it prints `sk-ant-...`. Re-export it if not (see Chapter 2).
- **400 "missing beta header"** - you called a non-beta path. Managed Agents lives under `client.beta.*`. Use `client.beta.agents`, `client.beta.environments`, `client.beta.sessions` - the beta header is added for you there.
- **`ModuleNotFoundError: No module named 'anthropic'`** - the SDK is not installed in this interpreter. Run `pip install -U anthropic`, and make sure you are using the same Python you installed it into.
- **`AttributeError` on `client.beta.agents`** - your SDK is too old for Managed Agents. Upgrade with `pip install -U anthropic`.
- **Wrong interpreter / venv** - if you set up a virtual environment in Chapter 2, activate it first: `source .venv/bin/activate`. Then `python lab02.py`.

---

## Stretch

- **Ask a follow-up in the same session.** After the session goes idle, send another `user.message` (for example, "Now make it print the first 30 numbers and rerun it") and stream again. The session keeps the container and its files, so the agent edits the existing `fib.py`.
- **Print a running token count.** The `span.model_request_end` event carries `model_usage`. Add a branch that accumulates `input_tokens` and `output_tokens` and prints a running total as the turn progresses:

 ```python
 total_in = total_out = 0
 # inside the for-loop:
 elif event.type == "span.model_request_end":
 u = event.model_usage
 total_in += u.input_tokens
 total_out += u.output_tokens
 print(f"\n[tokens so far: in={total_in} out={total_out}]")
 ```

---

## What you've learned

- How to create an agent, an environment, and a session from Python.
- That the model, system prompt, and toolset live on the agent - the session just points at it.
- How to stream a turn end-to-end and read the basic event types (`agent.message`, `agent.tool_use`, `session.status_idle`) you will see in every future lab.
- That the `client.beta.*` namespace adds the Managed Agents beta header for you.
