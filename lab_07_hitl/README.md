# Lab 07 - Human-in-the-loop checkpoint

An agent that pauses for explicit approval before every `bash` command and
before any `write` outside `/tmp/`. The toolset default is `always_allow`, with
`bash` and `write` overridden to `always_ask`. A stdin policy decides per call:
auto-allow writes to `/tmp/`, prompt for everything else.

Model: `claude-haiku-4-5-20251001`. Toolset: `agent_toolset_20260401`.

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Run

```bash
python lab07.py
```

This lab is interactive: it stops at `input()` prompts, so run it in a real
terminal.

## Interactive prompts

```
[tool requested: write]
[approval needed] write -> {'path': '/workspace/hello.py', ...}
  approve? [y / N / explain <reason>] y

[tool requested: bash]
[approval needed] bash -> {'command': 'python /workspace/hello.py'}
  approve? [y / N / explain <reason>] explain not on prod
```

- `y` -> allow, the action runs and the session resumes.
- `N`, blank, or anything else -> deny with a default message.
- `explain <reason>` -> deny, and the reason is sent as `deny_message` so the
  model adapts on its next turn.

Writes to `/tmp/...` are auto-allowed by the policy with no prompt. Point the
task at `/workspace/...` to see the write approval prompt; point it at `/tmp/...`
to see the auto-allow path.
