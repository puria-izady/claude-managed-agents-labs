# Lab 11 - Research, write & fact-check multi-agent pipeline

Three specialists (Researcher / Writer / Fact-Checker) coordinated by a Research Lead. Produces a verified, well-cited brief.

**Spec:** [`../../lab_11_research_write.md`](../../lab_11_research_write.md)

## Prerequisites

- Multi-agent enabled on your account (request access if your key cannot create a coordinator).

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Files

- `lab11.py` - main script (creates 4 agents + env + session, streams the primary thread, downloads the brief). System prompts are inlined at the top.

## Run

```bash
python lab11.py
```

## What you'll see

```
session.id = sesn_01...

+ thread Researcher
  <- Researcher returned
+ thread Writer
  <- Writer returned
+ thread Fact-Checker
  <- Fact-Checker returned
+ thread Writer       # second pass if the fact-checker flagged anything
  <- Writer returned
+ thread Fact-Checker
  <- Fact-Checker returned
--- session idle ---
saved: outputs/brief.md
```

`outputs/brief.md` is the verified, inline-cited brief.

## Model Choice

| Agent | Model | Why |
|--|--|--|
| Coordinator | claude-haiku-4-5-20251001 | routing decisions matter most |
| Researcher | claude-haiku-4-5-20251001 | focused web research |
| Writer | claude-haiku-4-5-20251001 | drafting from cited sources |
| Fact-Checker | claude-haiku-4-5-20251001 | verification with scoped tools |

## Thread budget

A session allows 25 concurrent threads: 1 primary + 24 child. This roster uses three specialists, well under the cap. Archive finished threads to return their slots to the budget.
