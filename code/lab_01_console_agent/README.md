# Lab 01 - Your First Console Agent

This lab is **Console-only** - no Python required. There's no code to run in this
folder; the full walkthrough lives in
[`../../lab_01_console_agent.md`](../../lab_01_console_agent.md).

💲 **Estimated cost:** a few cents.

## What you'll do

In the Anthropic Console you'll:

1. Create a coding-assistant agent on the **course default** model with the
   built-in agent toolset enabled.
2. Create (or select) a **cloud environment** with unrestricted networking.
3. Start a session titled `Fibonacci`.
4. Send: **"Write fib.py printing the first 20 Fibonacci numbers, then run it"**.
5. Watch the agent's `write` → `bash` → `read` tool calls and the session status
   move `running` → `idle`.

## You'll end up with

- A `My First Agent` agent in your workspace.
- A `quickstart-env` cloud environment.
- A `Fibonacci` session that wrote `/workspace/fib.py`, ran it, and printed the
  first 20 Fibonacci numbers.

## Prefer the API?

There's also a **Claude Code path** in the spec: 2–3 plain-English prompts you can
paste into Claude Code to do the exact same thing via the Managed Agents beta SDK
(the SDK adds the required beta header for you). If you show code, the captioned
current values are model `claude-haiku-4-5-20251001` and toolset `agent_toolset_20260401`.

Carry forward the **agent id** and **environment id** - Lab 02 reuses the same
shape from Python.
