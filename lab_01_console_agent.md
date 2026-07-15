# Lab 1 - Your First Managed Agent in the Console

Companion notebook: code/lab_01_console_agent/lab01.ipynb (run in Udemy Labs).

**Section**: Chapter 2 - Setting Up Your Workspace
**Path**: No-code (Console only)

In this lab you build a coding-assistant agent entirely in the Anthropic Console: no Python, no terminal, no API calls of your own. You give the agent a model and the built-in toolset, point it at a cloud environment, start a session, and ask it to write and run a small Python script. Watching the agent decide to *write* a file, *run* it with bash, and *read* the result back is the whole point: it makes the agent loop concrete before you ever touch code. By the end you will have seen a real session move from `running` to `idle` with the first 20 Fibonacci numbers in the output.

**Estimated cost:** a few cents.

---

## Prerequisites

You should already have these from Chapter 2 setup:

- An **Anthropic account** at `platform.claude.com`.
- A **workspace** selected (API keys and resources are workspace-scoped).
- An **API key** created. You won't paste it anywhere in this lab, but the Console needs your workspace to have one.
- The **Console open** in your browser.

> New here? Walk through the Chapter 2 setup lesson first (account, spend cap, key). It takes a couple of minutes and sets the low spend limit that makes labs like this stress-free.

---

## Console path (primary)

This is the recommended way through the lab. Every step is a click or a typed message in the browser.

### Step 1 - Create the agent

1. In the left nav, open **Agents → New agent** (or use **Agent Quickstart** from your workspace).
2. **Name:** `My First Agent`.
3. **Model:** pick the **course default** model from the dropdown.
4. **System prompt:**
 ```
 You are a helpful coding assistant. Write clean, well-documented code.
 When asked to create a file, write it under /workspace/, run it if
 appropriate, and verify the output.
 ```
5. **Tools:** leave the full **built-in agent toolset** enabled (this is the default and it includes `write`, `bash`, and `read`).
6. **MCP servers / Skills:** leave empty for now.
7. Save the agent.

> Tip: click **"Show equivalent API request"** if you want to peek at the code the Console is generating. That request is exactly what Lab 2 builds by hand.

### Step 2 - Create or select a cloud environment

1. When prompted for an environment, choose **Create environment** (or pick an existing one).
2. **Type:** cloud.
3. **Networking:** `unrestricted` is fine for this lab.
4. No package presets are needed; Python is already available in the default cloud image.
5. Give it a name like `quickstart-env` and save.

### Step 3 - Start a session

1. Click **Start session**.
2. Give the session a title: `Fibonacci`.
3. You'll land in the session viewer with an inline chat box.

### Step 4 - Send the first message

In the chat box, send exactly this:

> Write fib.py printing the first 20 Fibonacci numbers, then run it

### Step 5 - Watch the tool calls

Keep your eye on the event stream / session viewer. You should see, roughly in order:

- A short message where Claude explains what it's about to do.
- A **`write`** tool call creating `/workspace/fib.py`.
- A **`bash`** tool call running the script (e.g. `python /workspace/fib.py`).
- A **`read`** (or tool result) showing the script's output.
- A final message where Claude reports the numbers.

Watch the **session status** indicator: it moves from `running` while the agent works to `idle` when the turn is complete.

---

## Bonus (optional): Claude Code

Prefer to do the same thing through the API without writing the code yourself? Open Claude Code in this repo and paste these plain-English prompts one at a time. Claude Code will call the Managed Agents API for you (and the SDK adds the required beta header automatically).

1. **Create the agent and environment:**
 > Using the Anthropic Managed Agents beta SDK, create a coding-assistant agent on the course default model with the built-in agent toolset enabled, plus a cloud environment with unrestricted networking. Print the agent id and environment id.

2. **Start a session and send the task:**
 > Start a session against that agent and environment, then send the message "Write fib.py printing the first 20 Fibonacci numbers, then run it" and stream the agent's reply to my terminal.

3. **Confirm the result:**
 > Tell me whether the session reached idle, which tools the agent used, and show me the Fibonacci numbers it printed.

---

## Expected output

- `/workspace/fib.py` exists in the session's environment.
- The agent's output shows the **first 20 Fibonacci numbers**: `0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181`.
- The event stream shows `write`, `bash`, and `read` tool calls.
- The **session ends `idle`** (no errors, no stuck `running` state).

---

## Troubleshooting

- **"400: missing beta header" (Claude Code path only):** the Managed Agents endpoints require a beta header. The SDK adds it for you when you use the beta namespace, so let Claude Code use the SDK rather than raw curl. If you do hit this, ask Claude Code to switch to the beta SDK client.
- **Other 400 errors:** usually a typo in the model id or toolset id. In the Console, pick the model and toolset from the menus instead of typing them. In code, use the captioned current values (`claude-haiku-4-5-20251001`, toolset `agent_toolset_20260401`).
- **Agent replies but never runs the file:** make sure the **built-in toolset is enabled** on the agent (Step 1.5). Without `bash`, it can only write the file, not run it. You can also nudge it: "Now actually run /workspace/fib.py and paste the output."
- **Tool call asks for approval / "permission denied":** the toolset permission policy may be set to ask before each call. Approve the `write` and `bash` calls in the session panel.
- **Stuck on `running` for more than a minute or two:** click **Interrupt** and resend the message.
- **Worried about cost:** confirm the **spend cap** you set in Chapter 2 is in place. This lab is a few cents at most, and the cap is your safety net.

---

## Stretch

- **Verify the artifact:** ask the agent, "Run /workspace/fib.py again and read the file back to confirm it has exactly 20 numbers." Watch it chain `bash` and `read`.
- **Add a docstring:** ask, "Add a module-level docstring and a docstring on the function explaining what it does, then re-run it." Notice the agent edits, re-writes, and re-runs without you touching anything.

---

## What you've learned

- How to create an agent, environment, and session entirely from the Console.
- How to read the event stream and follow `write` → `bash` → `read` tool calls.
- That a managed agent can write, execute, and verify code on its own, with the status moving `running` → `idle`.
- That the same flow is one API request away (the Claude Code path and Lab 2 prove it).
