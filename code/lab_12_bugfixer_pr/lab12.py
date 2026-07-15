"""Lab 12 - Bug-fixer agent that opens a PR.

Attaches your GitHub repo to a session as a resource, asks the agent to
fix a failing test, opens a pull request via the GitHub MCP, and prints
the PR URL.

The repo's authorization token clones the repo and wires the git remote;
it never reaches the sandbox where Claude's code runs. Pushing and PR
operations go through the GitHub MCP server.

Env vars (see ../.env.example):
    GITHUB_TOKEN      fine-grained PAT for the repo resource
    GITHUB_REPO_URL   https://github.com/your-org/your-repo
    GITHUB_VAULT_ID   Managed Agents vault with GitHub MCP bearer-token credential
    GITHUB_MCP_URL    optional override; otherwise read from vault

Run:
    python lab12.py
"""

import os
import sys
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_session_cost  # noqa: E402

BETAS = ["managed-agents-2026-04-01"]
MODEL = "claude-haiku-4-5-20251001"
REQUIRED_REPO_FILES = ["tests/test_math.py", "src/math.py"]


def validate_vault_id(vault_id: str) -> None:
    """Catch common copy/paste mistakes before sessions.create."""
    if not vault_id or vault_id.startswith("vlt_REPLACE"):
        raise RuntimeError("Set GITHUB_VAULT_ID to your Claude Managed Agents vault id.")
    if vault_id.startswith("sk-ant-"):
        raise RuntimeError(
            "GITHUB_VAULT_ID currently contains an Anthropic API key. Paste the "
            "GitHub vault id from Claude Console instead; it should start with 'vlt_'."
        )
    if not vault_id.startswith("vlt_"):
        raise RuntimeError(f"GITHUB_VAULT_ID should start with 'vlt_'. Got: {vault_id!r}")


def validate_mcp_url(url: str) -> None:
    """Catch missing or placeholder MCP URLs before agent creation."""
    parsed = urlparse(url)
    if not url or "REPLACE-ME" in url or parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(
            "Set GITHUB_MCP_URL to a valid https MCP endpoint, or use a "
            "GITHUB_VAULT_ID whose credential contains an MCP server URL."
        )


def mcp_url_from_vault(client: Anthropic, vault_id: str) -> str:
    """Read the GitHub MCP URL from an existing vault credential."""
    credentials = list(client.beta.vaults.credentials.list(vault_id, betas=BETAS))
    mcp_credentials = [
        credential for credential in credentials
        if getattr(getattr(credential, "auth", None), "type", None) == "mcp_oauth"
    ]
    github_credentials = [
        credential for credential in mcp_credentials
        if "github" in (
            f"{getattr(credential, 'display_name', '') or ''} "
            f"{getattr(getattr(credential, 'auth', None), 'mcp_server_url', '')}"
        ).lower()
    ]

    if len(github_credentials) == 1:
        return github_credentials[0].auth.mcp_server_url
    if len(mcp_credentials) == 1:
        return mcp_credentials[0].auth.mcp_server_url

    names = [
        f"{getattr(credential, 'display_name', '') or credential.id}: "
        f"{getattr(getattr(credential, 'auth', None), 'mcp_server_url', '<no mcp url>')}"
        for credential in mcp_credentials
    ]
    raise RuntimeError(
        "Could not uniquely identify the GitHub MCP credential in "
        f"vault {vault_id}. Set GITHUB_MCP_URL explicitly. "
        f"Found MCP credentials: {names or 'none'}"
    )


def resolve_github_connection(client: Anthropic) -> tuple[str, str]:
    """Return (vault_id, mcp_url), deriving the URL from the vault when possible."""
    vault_id = os.environ.get("GITHUB_VAULT_ID", "").strip()
    validate_vault_id(vault_id)

    mcp_url = os.environ.get("GITHUB_MCP_URL", "").strip() or mcp_url_from_vault(
        client, vault_id
    )
    validate_mcp_url(mcp_url)
    print(f"github vault.id = {vault_id} (existing vault)")
    print(f"github MCP URL = {mcp_url}")
    return vault_id, mcp_url


def parse_github_repo(repo_url: str) -> tuple[str, str]:
    """Return (owner, repo) from a GitHub HTTPS URL."""
    parsed = urlparse(repo_url)
    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.netloc != "github.com" or len(path_parts) < 2:
        raise RuntimeError(
            "GITHUB_REPO_URL must look like https://github.com/owner/repo. "
            f"Got: {repo_url!r}"
        )
    owner, repo = path_parts[:2]
    return owner, repo.removesuffix(".git")


def github_api_get(path: str, token: str) -> dict | list:
    """Small GitHub API helper for local preflight checks."""
    request = Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        hint = (
            "Check that GITHUB_REPO_URL points to your copy of the repo and "
            "GITHUB_TOKEN is a fine-grained PAT with Contents read/write on that repo."
        )
        if exc.code == 404 and path.startswith("/repos/") and "/contents" not in path:
            hint = (
                "GitHub returns 404 when the repo does not exist, and also when "
                "the repo is private but this token is not authorized for it. "
                "Open GITHUB_REPO_URL in your browser while signed in, then edit "
                "the fine-grained PAT so Repository access includes exactly this repo."
            )
        elif exc.code == 404 and "/contents" in path:
            hint = (
                "The repo is visible to the token, but the expected lab file was "
                "not found on the selected branch. Confirm you used the course "
                "template repo or pushed the template_repo files, and check GITHUB_BRANCH."
            )
        raise RuntimeError(
            f"GitHub API preflight failed for {path}: HTTP {exc.code}. "
            f"{hint} "
            f"Details: {detail[:500]}"
        ) from exc


def preflight_github_repo(repo_url: str, token: str) -> tuple[str, str, str]:
    """Verify the repo token can read the target repo and expected lab files."""
    owner, repo = parse_github_repo(repo_url)
    repo_info = github_api_get(f"/repos/{owner}/{repo}", token)
    default_branch = os.environ.get("GITHUB_BRANCH", "").strip() or repo_info.get(
        "default_branch", "main"
    )

    root = github_api_get(f"/repos/{owner}/{repo}/contents?ref={default_branch}", token)
    if not isinstance(root, list) or not root:
        raise RuntimeError(
            f"GitHub repo {owner}/{repo} is empty on branch {default_branch!r}. "
            "Use the course template to create a populated repo, or push the "
            "template_repo files before running this lab."
        )

    root_names = ", ".join(sorted(item.get("name", "") for item in root if item.get("name")))
    print(f"GitHub preflight: {owner}/{repo}@{default_branch} root contains: {root_names}")

    for file_path in REQUIRED_REPO_FILES:
        github_api_get(
            f"/repos/{owner}/{repo}/contents/{file_path}?ref={default_branch}",
            token,
        )
    print("GitHub preflight: required lab files are present.")
    return owner, repo, default_branch


def main() -> None:
    # Read config from the environment. The fine-grained token is scoped to
    # one repo with Contents and Pull Requests read/write. MCP auth comes
    # from the Managed Agents vault, not this token.
    token = os.environ["GITHUB_TOKEN"]
    repo_url = os.environ["GITHUB_REPO_URL"]

    client = Anthropic()
    github_vault_id, mcp_url = resolve_github_connection(client)
    repo_owner, repo_name, repo_branch = preflight_github_repo(repo_url, token)
    print(
        "GitHub MCP reminder: configure the vault credential as Bearer Token "
        "auth backed by the fine-grained PAT. If MCP repo or PR calls return "
        "404, update that vault credential so it uses the PAT for this same repo."
    )

    # The agent gets two toolsets: the built-in agent toolset for local
    # file ops (read, edit, write, bash) and an MCP toolset for the GitHub
    # operations (branch, commit, push, open PR).
    agent = client.beta.agents.create(
        name="Bug Fixer",
        model=MODEL,
        system=(
            "You are a bug-fixing agent. Steps:\n"
            "1) Read the repo at /workspace/repo.\n"
            "2) Run the tests to reproduce the failure.\n"
            "3) Fix the failing test by editing only the minimum code.\n"
            "4) Re-run tests to confirm green.\n"
            "5) Use the GitHub MCP against exactly this repository: "
            f"owner `{repo_owner}`, repo `{repo_name}`, base branch `{repo_branch}`. "
            "Never use any other owner, repo, or base branch.\n"
            "6) Use the GitHub MCP to: create a branch named "
            "`claude-fix-<short-issue>`, commit the change, push, and open "
            "a PR with a clear description of what changed and why. "
            "Do not run `git push` against the local origin; the mounted repo "
            "remote is an internal resource URL. If any GitHub MCP call returns "
            "404 for this owner/repo/base branch, stop and report that the vault "
            "GitHub credential cannot access the repo or branch; do not try "
            "`git push`. Report the PR URL when you are done."
        ),
        # Pair the mounted repo with the GitHub MCP so the agent can push
        # and open a pull request. Auth is supplied by vault_ids on the session.
        mcp_servers=[{
            "type": "url",
            "name": "github",
            "url": mcp_url,
        }],
        tools=[
            {"type": "agent_toolset_20260401"},
            {"type": "mcp_toolset", "mcp_server_name": "github"},
        ],
        betas=BETAS,
    )

    # A cloud environment with pytest and limited networking to GitHub and
    # the MCP server. allow_mcp_servers lets the GitHub MCP reach out.
    env = client.beta.environments.create(
        name="codefix-env",
        config={
            "type": "cloud",
            "packages": {"pip": ["pytest"]},
            "networking": {
                "type": "limited",
                "allowed_hosts": [
                    "api.github.com",
                    "github.com",
                ],
                "allow_mcp_servers": True,
                "allow_package_managers": True,
            },
        },
        betas=BETAS,
    )

    # Attach the GitHub repo as a session resource. The token clones the
    # repo and configures the remote; it stays outside the sandbox.
    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent.id, "version": agent.version},
        environment_id=env.id,
        resources=[{
            "type": "github_repository",
            "url": repo_url,
            "mount_path": "/workspace/repo",
            "checkout": {"type": "branch", "name": repo_branch},
            "authorization_token": token,
        }],
        vault_ids=[github_vault_id],
        title="Fix failing test",
        betas=BETAS,
    )
    print(f"session.id = {session.id}\n")

    pr_url = None

    # Send one user message describing the bug, then stream the run.
    with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
        client.beta.sessions.events.send(session.id, events=[{
            "type": "user.message",
            "content": [{
                "type": "text",
                "text": (
                    "There's a failing test in tests/test_math.py. First run "
                    "`pwd && ls -la /workspace /workspace/repo && git -C "
                    "/workspace/repo status --short && find /workspace/repo "
                    "-maxdepth 3 -type f | sort | head -100` to verify the "
                    "repo mounted. If /workspace/repo has no files, stop and "
                    "say the GitHub repository resource did not mount. "
                    f"Otherwise find the failure, fix it, and open a PR with the fix. "
                    f"Use the GitHub MCP with owner `{repo_owner}`, repo `{repo_name}`, "
                    f"and base branch `{repo_branch}`. Do not use `git push`. "
                    "If the GitHub MCP returns 404 for that repo or branch, stop "
                    "and explain that the vault GitHub credential needs repo access."
                ),
            }],
        }], betas=BETAS)
        for event in stream:
            if event.type == "agent.tool_use":
                print(f"\n[tool: {event.name}]")
            elif event.type == "agent.mcp_tool_use":
                print(f"\n[mcp: {event.name}]")
            elif event.type == "agent.mcp_tool_result":
                # The open-PR MCP call returns the new pull request URL in
                # its result. Capture the first GitHub URL we see.
                pr_url = _extract_pr_url(event) or pr_url
            elif event.type == "agent.message":
                for b in event.content:
                    if b.type == "text":
                        print(b.text, end="", flush=True)
            elif event.type == "session.status_idle":
                print("\n--- session idle ---")
                break

    if pr_url:
        print(f"\nPR: {pr_url}")
    else:
        print(
            "\nNo PR URL captured from MCP results. "
            "Check the agent's closing message for the link."
        )

    print_session_cost(client, session.id, MODEL, betas=BETAS)


def _extract_pr_url(event) -> str | None:
    """Best-effort scan of an MCP tool result for a pull request URL.

    MCP result shapes vary by server, so we walk the content blocks and
    return the first string that looks like a GitHub PR link.
    """
    content = getattr(event, "content", None) or []
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and "github.com" in text and "/pull/" in text:
            for token in text.split():
                if "github.com" in token and "/pull/" in token:
                    return token.strip().strip(".,)")
    return None


if __name__ == "__main__":
    main()
