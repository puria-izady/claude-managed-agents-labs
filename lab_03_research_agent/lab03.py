"""Lab 03 - A research agent that web-searches and files a brief to Google Docs.

Creates a Haiku-backed agent with the built-in toolset (web_search, web_fetch,
write, ...) plus a Google Docs MCP server. The agent researches a topic, writes
a concise cited brief, then calls the Google Docs MCP to create a new document
containing the brief. We stream the run and print the created doc's URL.

The Google Docs connector is authenticated through a Claude Managed Agents
vault. Create/connect the Google Drive credential in the Console, then set the
vault id. The MCP URL can usually be read from the vault credential.

Env vars (see ../.env.example):
    ANTHROPIC_API_KEY     required
    GOOGLE_DOCS_VAULT_ID  vault containing the Google Docs MCP credential
    GOOGLE_DOCS_MCP_URL   optional override; otherwise read from the vault

Run:
    uv run --project .. --env-file ../.env python lab03.py
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Make `shared/` importable when running from this folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_session_cost  # noqa: E402
from prompts import RESEARCH_BRIEF_GDOCS_SYSTEM  # noqa: E402

BETAS = ["managed-agents-2026-04-01"]
MODEL = "claude-haiku-4-5-20251001"
GOOGLE_DOCS_VAULT_ID = os.environ.get("GOOGLE_DOCS_VAULT_ID", "").strip()
GOOGLE_DOCS_MCP_URL = os.environ.get("GOOGLE_DOCS_MCP_URL", "").strip()

TOPIC = "the state of small modular reactors in 2026"
RESEARCH_ALLOWED_HOSTS = [
    "*.com",
    "*.org",
    "*.net",
    "*.edu",
    "*.gov",
    "*.int",
    "*.io",
    "*.ai",
    "*.dev",
    "*.co",
    "*.de",
    "*.uk",
    "*.eu",
]


def validate_mcp_url(url: str) -> None:
    """Catch missing or placeholder URLs before the API returns a generic 400."""
    parsed = urlparse(url)
    if not url or "REPLACE-ME" in url or parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(
            "Set GOOGLE_DOCS_MCP_URL to a valid https MCP endpoint, or use a "
            "GOOGLE_DOCS_VAULT_ID whose credential contains an MCP server URL."
        )


def validate_vault_id(vault_id: str) -> None:
    """Catch common copy/paste mistakes before sessions.create."""
    if not vault_id or vault_id.startswith("vlt_REPLACE"):
        raise RuntimeError(
            "Set GOOGLE_DOCS_VAULT_ID to the Claude Managed Agents vault that "
            "contains your Google Docs credential."
        )
    if vault_id.startswith("sk-ant-"):
        raise RuntimeError(
            "GOOGLE_DOCS_VAULT_ID currently contains an Anthropic API key. "
            "Paste the Google Docs vault id from Claude Console instead; it "
            "should start with 'vlt_'."
        )
    if not vault_id.startswith("vlt_"):
        raise RuntimeError(
            f"GOOGLE_DOCS_VAULT_ID should start with 'vlt_'. Got: {vault_id!r}"
        )


def google_docs_mcp_url_from_vault(client: Anthropic, vault_id: str) -> str:
    """Read the MCP URL from the first Google Docs MCP OAuth credential."""
    credentials = list(client.beta.vaults.credentials.list(vault_id, betas=BETAS))
    mcp_credentials = [
        credential for credential in credentials
        if getattr(credential.auth, "type", None) == "mcp_oauth"
    ]
    google_credentials = [
        credential for credential in mcp_credentials
        if "google" in (
            f"{credential.display_name or ''} "
            f"{getattr(credential.auth, 'mcp_server_url', '')}"
        ).lower()
    ]

    if len(google_credentials) == 1:
        return google_credentials[0].auth.mcp_server_url
    if len(mcp_credentials) == 1:
        return mcp_credentials[0].auth.mcp_server_url

    names = [
        f"{credential.display_name or credential.id}: "
        f"{getattr(credential.auth, 'mcp_server_url', '<no mcp url>')}"
        for credential in mcp_credentials
    ]
    raise RuntimeError(
        "Could not uniquely identify the Google Docs MCP credential in "
        f"vault {vault_id}. Set GOOGLE_DOCS_MCP_URL explicitly. "
        f"Found MCP credentials: {names or 'none'}"
    )


def resolve_google_docs_config(client: Anthropic) -> tuple[str, str]:
    validate_vault_id(GOOGLE_DOCS_VAULT_ID)

    mcp_url = GOOGLE_DOCS_MCP_URL or google_docs_mcp_url_from_vault(
        client, GOOGLE_DOCS_VAULT_ID,
    )
    validate_mcp_url(mcp_url)
    return mcp_url, GOOGLE_DOCS_VAULT_ID


def build_mcp_server(mcp_url: str) -> dict:
    """Declare the remote Google Docs MCP server on the agent."""
    return {
        "type": "url",
        "name": "google_docs",
        "url": mcp_url,
    }


def main() -> None:
    client = Anthropic()
    google_docs_mcp_url, google_docs_vault_id = resolve_google_docs_config(client)
    print("Google Docs MCP URL =", google_docs_mcp_url)

    # 1. Create the agent: built-in toolset + the Google Docs MCP server.
    agent = client.beta.agents.create(
        name="Research Brief (Google Docs)",
        model=MODEL,
        system=RESEARCH_BRIEF_GDOCS_SYSTEM,
        mcp_servers=[build_mcp_server(google_docs_mcp_url)],
        tools=[
            # Built-in toolset: web_search, web_fetch, write, read, bash, ...
            {"type": "agent_toolset_20260401"},
            # Expose the Google Docs MCP tools to the agent.
            {
                "type": "mcp_toolset",
                "mcp_server_name": "google_docs",
                "default_config": {
                    "permission_policy": {"type": "always_allow"},
                },
            },
        ],
        betas=BETAS,
    )
    print(f"agent.id = {agent.id}")

    # 2. Cloud environment. Networking is limited: MCP servers allowed, plus
    #    the public web so web_search / web_fetch can reach the internet.
    env = client.beta.environments.create(
        name="research-gdocs-env",
        config={
            "type": "cloud",
            "networking": {
                "type": "limited",
                "allow_mcp_servers": True,
                # Common public-web TLDs for research. Tighten in production.
                "allowed_hosts": RESEARCH_ALLOWED_HOSTS,
            },
        },
        betas=BETAS,
    )
    print(f"env.id = {env.id}")

    # 3. Start a session pinned to this agent version.
    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent.id, "version": agent.version},
        environment_id=env.id,
        vault_ids=[google_docs_vault_id],
        title="SMRs 2026 -> Google Docs",
        betas=BETAS,
    )
    print(f"session.id = {session.id}\n")

    # 4. Ask for the brief, stream the run, watch tools fire.
    with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
        client.beta.sessions.events.send(session.id, events=[{
            "type": "user.message",
            "content": [{
                "type": "text",
                "text": (
                    f"Research {TOPIC}. Write a concise, cited brief, then "
                    "create a Google Doc containing it and tell me the URL."
                ),
            }],
        }], betas=BETAS)
        for event in stream:
            if event.type == "agent.message":
                for b in event.content:
                    if b.type == "text":
                        print(b.text, end="", flush=True)
            elif event.type == "agent.tool_use":
                q = (event.input or {}).get("query", "")
                print(f"\n[tool: {event.name}({q[:60]})]")
            elif event.type == "agent.mcp_tool_use":
                print(f"\n[mcp: {event.name}]")
            elif event.type == "session.error":
                print(f"\n[ERROR] {event.error}")
            elif event.type == "session.status_idle":
                print("\n--- session idle ---")
                break

    print_session_cost(client, session.id, MODEL, betas=BETAS)


if __name__ == "__main__":
    main()
