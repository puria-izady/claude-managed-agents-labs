# Lab 12 - Bug-fixer agent that opens a PR

Attaches your GitHub repo as a session resource, asks the agent to fix a failing test, opens a PR via the GitHub MCP, and prints the PR URL.

**Spec:** [`../../lab_12_bugfixer_pr.md`](../../lab_12_bugfixer_pr.md)

## Prerequisites

- A small Python repo you own with a planted bug and a failing test. The fastest path: go to [github.com/puria-izady/managed-agents-bugfixer-sample](https://github.com/puria-izady/managed-agents-bugfixer-sample) and click **Use this template** to create your own copy. (The same files live at [`template_repo/`](template_repo/) if you would rather inspect them locally.)
- A **fine-grained** GitHub PAT for the lab repo. In GitHub, create a
  **Fine-grained token**, set **Repository access** to **Only select
  repositories**, select your lab repo, then grant these repository
  permissions: `Contents: Read and write` and `Pull requests: Read and write`.
  This is only for attaching the repo resource.
- A GitHub MCP connection configured in Claude Managed Agents Vaults. In Claude
  Console, create the GitHub MCP credential with **Bearer Token** auth and paste
  the same fine-grained PAT as the bearer token. Copy the vault id that starts
  with `vlt_`.

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="github_pat_..."
export GITHUB_REPO_URL="https://github.com/your-org/your-repo"
export GITHUB_VAULT_ID="vlt_..."
export GITHUB_MCP_URL=""   # optional override if the vault has multiple MCP credentials
```

The code still references only the vault id at runtime: `GITHUB_TOKEN` lets
Managed Agents clone and push the mounted repo resource, while `GITHUB_VAULT_ID`
authenticates the GitHub MCP server used for branch, commit, and PR operations.
For this lab, configure that vault credential as a bearer token backed by the
same fine-grained PAT.
The notebook/script runs a GitHub API preflight before creating the session:
it checks that the token can read the repo, that the selected branch is not
empty, and that `tests/test_math.py` plus `src/math.py` are present.

## Run

```bash
python lab12.py
```

## What happens

```
session.id = sesn_01...

[tool: bash]                   pytest -> 1 failing
[tool: read]                   tests/test_math.py
[tool: read]                   src/math.py
[tool: edit]                   fix the off-by-one
[tool: bash]                   pytest -> all green
[mcp: github_create_branch]    claude-fix-math
[mcp: github_commit_file]      src/math.py
[mcp: github_open_pr]          Fix off-by-one in factorial
--- session idle ---

PR: https://github.com/your-org/your-repo/pull/42
```

Check GitHub: a new branch and an open PR with a clean, minimal diff and a clear description.

## Empty repo in the agent

If the agent says `/workspace/repo` is empty, first look at the preflight cell.
If preflight failed, fix the repo URL or token before starting a new session.
If preflight passed but the agent still sees no files, start a fresh session;
the resource mount failed after validation. The lab now pins `checkout` to the
repo's default branch so it does not depend on branch auto-detection.

If preflight fails with `HTTP 404` on `/repos/owner/repo`, GitHub either cannot
find that repo or the repo is private and the fine-grained token is not
authorized for it. Open the repo URL in your browser while signed in, then edit
the token so **Repository access** includes exactly that repo.

If the preflight passes but the GitHub MCP later returns `GET /repos/...: 404`,
the vault credential cannot access the repo. Update the GitHub MCP credential
in Claude Console to use **Bearer Token** auth with the fine-grained PAT for
this repo.

If branch creation fails with `GET /repos/<owner>/<repo>/git/ref/heads/<branch>:
404`, the base branch was visible to `GITHUB_TOKEN` during preflight but not to
the GitHub MCP credential in the vault. Use Bearer Token auth with the
fine-grained PAT so the MCP credential has Contents access to the repo.

If the MCP call targets the wrong owner or repo, for example `anthropics/testrepo`
instead of your `owner/repo`, restart from the preflight cell and create a fresh
agent/session. The lab now passes the parsed `GITHUB_OWNER`, `GITHUB_REPO`, and
`GITHUB_BRANCH` into the agent instructions and tells it not to use `git push`
against the internal mount remote.

## Claude Code path

Prefer to drive this from Claude Code? The spec has paste-able prompts that scaffold this same script, wire the fix loop, and run it against your repo. See [`../../lab_12_bugfixer_pr.md`](../../lab_12_bugfixer_pr.md).
