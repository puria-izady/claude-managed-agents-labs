# Lab 12 - Bug-Fixer Agent That Opens a Pull Request

**Section**: E - Orchestration, Integration & Production
**Chapter**: 14 - Files & GitHub Workflows
**Path**: Jupyter Notebook (Python) + optional Claude Code bonus

> Run the notebook **`code/lab_12_bugfixer_pr/lab12.ipynb`** top to bottom (in Udemy Labs or locally). This page mirrors the notebook and adds an optional Claude Code path at the end. Requires a GitHub repo you own.

---

## Goal: Overview

In this lab you build a bug-fixer agent that runs the full clone-edit-branch-PR loop in a single session. You attach a GitHub repository as a session resource with a fine-grained token, the agent reproduces a planted bug, edits the minimum code to fix it, creates a new branch, and opens a pull request. You then retrieve the PR URL from the run.

The repo attaches as a first-class resource: the token clones the repo once and wires into the local git remote. The token never reaches the sandbox where Claude's code runs. To push and open a PR, you pair the repo with the GitHub MCP server authenticated through a Claude Managed Agents vault. For this lab, create that vault credential with **Bearer Token** auth backed by the fine-grained PAT.

**Estimated cost:** a few cents. Runs on your own machine and API key.

---

## Prereqs: Prereqs

- A small Python repo you own with a planted bug and a failing test. The course ships a ready-made template at [github.com/puria-izady/managed-agents-bugfixer-sample](https://github.com/puria-izady/managed-agents-bugfixer-sample): an off-by-one in a `factorial` helper with a failing `test_factorial_five`. Click **Use this template** to create your own copy to run the lab against. (The same files also live at `code/lab_12_bugfixer_pr/template_repo/`. Building your own works too, but the template is the fast path.)
- A **fine-grained** GitHub personal access token for the lab repo. In GitHub, create a **Fine-grained token**, set **Repository access** to **Only select repositories**, select your lab repo, then grant these repository permissions: `Contents: Read and write` and `Pull requests: Read and write`. This is used only for the mounted repo resource.
- A GitHub MCP connection configured in Claude Managed Agents Vaults. In Claude Console, create the GitHub MCP credential with **Bearer Token** auth and paste the same fine-grained PAT as the bearer token. Paste the resulting vault id into `GITHUB_VAULT_ID`. Leave `GITHUB_MCP_URL` blank unless the vault contains multiple MCP credentials and the code cannot infer the GitHub one.

---

## Python: Python path

1. **Attach a GitHub repo as a resource with a fine-grained token.** Create the session with a `github_repository` resource. The `authorization_token` clones the repo and configures the git remote; it stays outside the sandbox.

 ```python
 import os
 from anthropic import Anthropic

 client = Anthropic()
 github_vault_id = os.environ["GITHUB_VAULT_ID"]
 github_owner, github_repo, github_branch = preflight_github_repo(
 os.environ["GITHUB_REPO_URL"], os.environ["GITHUB_TOKEN"])

 session = client.beta.sessions.create(
 agent={"type": "agent", "id": agent.id, "version": agent.version},
 environment_id=env.id,
 resources=[{
 "type": "github_repository",
 "url": os.environ["GITHUB_REPO_URL"],
 "mount_path": "/workspace/repo",
 "checkout": {"type": "branch", "name": github_branch},
 "authorization_token": os.environ["GITHUB_TOKEN"],
 }],
 vault_ids=[github_vault_id],
 title="Fix failing test",
 )
 ```

 Before creating the session, the notebook/script calls the GitHub API with
 `GITHUB_TOKEN` to verify that the repo exists, the selected branch is not
 empty, and `tests/test_math.py` plus `src/math.py` are present. This catches
 the common failure mode where a student created an empty repo instead of using
 the template, or scoped the token to the wrong repo. The GitHub MCP credential
 in `GITHUB_VAULT_ID` should be configured as Bearer Token auth using the same
 fine-grained PAT so it can access the same repository for branch and PR
 operations.

2. **Pair with the GitHub MCP through a vault.** Mounting the repo lets the agent read and edit. The GitHub MCP lets it push, branch, comment, and open PRs. Declare the MCP server on the agent, then pass the GitHub vault id on the session so auth is supplied server-side.

 ```python
 github_mcp_url = os.environ.get("GITHUB_MCP_URL") or mcp_url_from_vault(
 client, github_vault_id)

 agent = client.beta.agents.create(
 name="Bug Fixer",
 model="claude-haiku-4-5-20251001",
 system=(
 "You are a bug-fixing agent. Reproduce, fix, branch, and open a PR. "
 f"Use the GitHub MCP with owner {github_owner!r}, repo {github_repo!r}, "
 f"and base branch {github_branch!r}. Do not use git push."
 ),
 mcp_servers=[{
 "type": "url",
 "name": "github",
 "url": github_mcp_url,
 }],
 tools=[
 {"type": "agent_toolset_20260401"},
 {"type": "mcp_toolset", "mcp_server_name": "github"},
 ],
 )
 ```

3. **The agent reproduces a bug, edits, creates a branch, opens a PR.** Send one user message describing the failing test. The agent runs the tests to reproduce, edits the minimum code, re-runs to confirm green, then uses the MCP to create a branch, commit, push, and open the PR.

 ```python
 with client.beta.sessions.events.stream(session.id) as stream:
 client.beta.sessions.events.send(session.id, events=[{
 "type": "user.message",
 "content": [{
 "type": "text",
 "text": ("There's a failing test in tests/test_math.py. "
 "Find it, fix it, and open a PR with the fix."),
 }],
 }])
 for event in stream:
 if event.type == "agent.tool_use":
 print(f"\n[tool: {event.name}]")
 elif event.type == "agent.mcp_tool_use":
 print(f"\n[mcp: {event.name}]")
 elif event.type == "agent.message":
 for b in event.content:
 if b.type == "text":
 print(b.text, end="", flush=True)
 elif event.type == "session.status_idle":
 break
 ```

4. **Retrieve the PR URL.** The MCP open-PR call returns the new pull request URL in its result. Capture it from the `agent.mcp_tool_use` (or the matching result) event, or read it back from the agent's closing message. Print it so you have a direct link to the open PR.

---

## Bonus (optional): Claude Code

Not required - the notebook is the whole lab. If you would rather drive this from Claude Code, paste these prompts in order. Claude Code can author the script, then run it against your repo.

1. Scaffold the script:

 > Write a Python script `lab12.py` using the Anthropic SDK `client.beta.*` Agents APIs. It creates an agent named "Bug Fixer" on model `claude-haiku-4-5-20251001` with tools `agent_toolset_20260401` and an `mcp_toolset` for a GitHub MCP server. It creates a cloud environment with pytest installed and limited networking to GitHub and the MCP server. It uses my existing GitHub Managed Agents vault from `GITHUB_VAULT_ID`, reads the GitHub MCP URL from that vault when `GITHUB_MCP_URL` is unset, and attaches my repo as a `github_repository` resource mounted at `/workspace/repo` using a fine-grained token from `GITHUB_TOKEN`.

2. Wire the fix loop:

 > In the same script, send one user message: "There's a failing test in tests/test_math.py. Find it, fix it, and open a PR with the fix." Stream the session events and print each tool use, MCP tool use, and assistant text. Stop on session idle. After the run, print the pull request URL returned by the open-PR MCP call.

3. Run and report:

 > Run `python lab12.py` with my env vars set. Show me the streamed tool calls and the final PR URL. If the PR did not open, read the error and tell me which token scope or MCP auth step is missing.

---

## Expected: Expected output

A new branch on the repo (for example `claude-fix-math`) and an open pull request carrying the fix with a clean, minimal diff and a clear description. The stream shows the loop:

```
session.id = sesn_01...

[tool: bash] pytest -> 1 failing
[tool: read] tests/test_math.py
[tool: read] src/math.py
[tool: edit] fix the off-by-one
[tool: bash] pytest -> all green
[mcp: github_create_branch] claude-fix-math
[mcp: github_commit_file] src/math.py
[mcp: github_open_pr] Fix off-by-one in factorial
--- session idle ---

PR: https://github.com/your-org/your-repo/pull/42
```

---

## Troubleshooting

- **Fine-grained token scopes.** Use a fine-grained personal access token, not a classic one. In GitHub's token form, set **Repository access** to **Only select repositories**, select the single lab repo, then grant exactly two repository permissions: `Contents: Read and write` (to push the branch) and `Pull requests: Read and write` (to open the PR). A token missing either scope clones fine but fails at branch or PR time.
- **Repo caching.** Repos are cached across sessions, so a second run on the same repo starts faster. If you pushed changes outside the agent and the session still sees the old tree, start a fresh session to refresh the cache rather than expecting a mid-session re-clone.
- **Agent sees an empty `/workspace/repo`.** Check the GitHub preflight output first. If it failed, fix the repo URL, token scope, or push the template files. If preflight passed but the agent still sees no files, create a fresh session; the resource mount failed after validation.
- **Preflight 404 on `/repos/owner/repo`.** GitHub returns 404 both when the repo does not exist and when a private repo exists but the token is not authorized for it. Open `GITHUB_REPO_URL` in your browser while signed in, then edit the fine-grained PAT so **Repository access** includes exactly that repo.
- **The 100-file cap.** A session can hold up to 100 mounted files. A small repo is well under that, but if you mount a large repo as individual files you can hit it. Mount the repo as a `github_repository` resource (one clone) rather than uploading files one by one, and for very large trees mount a single archive and extract it in-session.
- **GitHub MCP auth.** If you see `session.error: mcp_auth_failed`, the MCP server could not authenticate. Confirm `GITHUB_VAULT_ID` points to the vault with the GitHub MCP bearer-token credential and that the credential URL matches the agent's `GITHUB_MCP_URL`.
- **MCP `GET /repos/...` returns 404.** The repo token preflight can pass while the MCP credential still cannot see the repo. Update the GitHub MCP credential in Claude Console to use **Bearer Token** auth with the fine-grained PAT for this repo.
- **MCP branch-ref 404.** If branch creation fails with `GET /repos/<owner>/<repo>/git/ref/heads/<branch>: 404`, the base branch was visible to `GITHUB_TOKEN` during preflight but not to the GitHub MCP credential in the vault. Use Bearer Token auth with the fine-grained PAT so the MCP credential has Contents access to the repo.
- **MCP targets the wrong owner/repo.** If an MCP tool call uses an owner like `anthropics` instead of your parsed repo owner, restart from the preflight cell and create a fresh agent/session. The lab passes `GITHUB_OWNER`, `GITHUB_REPO`, and `GITHUB_BRANCH` into the prompt and tells the agent not to use `git push` against the internal mount remote.

---

## Stretch: Stretch

- **Add tests.** Have the agent write a new regression test that fails before the fix and passes after, and include it in the same PR so reviewers see the bug captured.
- **Request review.** After opening the PR, use the GitHub MCP to request a reviewer (a teammate or a team) and post a summary comment explaining the root cause and the change.

---

## What you've learned

- Attaching GitHub repos as session resources with fine-grained tokens.
- The interplay between built-in tools (bash, read, edit, write) and the GitHub MCP (branch, commit, PR ops).
- Why fine-grained tokens and the resource-plus-MCP split matter for agents that touch real repos.
