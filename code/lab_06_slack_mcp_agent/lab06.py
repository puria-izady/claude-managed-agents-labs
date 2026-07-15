"""Lab 06 - Linear-aware MCP agent + vault credential.

Wires an agent to the PUBLIC Linear MCP server, attaches an existing per-user
vault credential, and asks the agent to triage issues and file a new one.

The Linear MCP is a remote (SaaS) connector. We never run a local MCP tunnel
(that surface is research preview). The harness reaches the public Linear
endpoint over the internet, and per-user auth lives in a vault, not on the
agent definition.

Env vars (see ../.env.example):
    ANTHROPIC_API_KEY               required
    LINEAR_VAULT_ID                 preferred: existing vault id for Linear
    LINEAR_MCP_URL                  optional override; otherwise read from vault
    SLACK_VAULT_ID                  optional: existing vault id for Slack
    SLACK_MCP_URL                   optional override; otherwise read from vault
    LINEAR_OAUTH_ACCESS_TOKEN       fallback: token to store in a new vault
    LINEAR_OAUTH_REFRESH_TOKEN      optional fallback refresh token
    LINEAR_OAUTH_CLIENT_ID          optional fallback OAuth app client id
    LINEAR_OAUTH_CLIENT_SECRET      optional fallback OAuth client secret
    LINEAR_TOKEN_ENDPOINT           optional fallback token endpoint

Run:
    uv run --project .. --env-file ../.env python lab06.py
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_session_cost  # noqa: E402

BETAS = ["managed-agents-2026-04-01"]
MODEL = "claude-haiku-4-5-20251001"

# Public, remote Linear MCP endpoint. This is a hosted SaaS connector, not a
# local tunnel. Override with LINEAR_MCP_URL only if Linear changes the path.
DEFAULT_LINEAR_MCP_URL = "https://mcp.linear.app/mcp"

# Linear's OAuth token endpoint, used by Anthropic to refresh the credential.
DEFAULT_TOKEN_ENDPOINT = "https://api.linear.app/oauth/token"


def validate_vault_id(
    vault_id: str,
    env_var: str = "LINEAR_VAULT_ID",
    provider: str = "Linear",
) -> None:
    """Catch common copy/paste mistakes before sessions.create."""
    if not vault_id or vault_id.startswith("vlt_REPLACE"):
        raise RuntimeError(f"Set {env_var} to the Claude Managed Agents vault id.")
    if vault_id.startswith("sk-ant-"):
        raise RuntimeError(
            f"{env_var} currently contains an Anthropic API key. Paste the "
            f"{provider} vault id from Claude Console instead; it should start with 'vlt_'."
        )
    if not vault_id.startswith("vlt_"):
        raise RuntimeError(f"{env_var} should start with 'vlt_'. Got: {vault_id!r}")


def validate_mcp_url(
    url: str,
    url_env: str = "LINEAR_MCP_URL",
    vault_env: str = "LINEAR_VAULT_ID",
) -> None:
    """Catch missing or placeholder MCP URLs before agent creation."""
    parsed = urlparse(url)
    if not url or "REPLACE-ME" in url or parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(
            f"Set {url_env} to a valid https MCP endpoint, or use a "
            f"{vault_env} whose credential contains an MCP server URL."
        )


def mcp_url_from_vault(client: Anthropic, vault_id: str, provider: str) -> str:
    """Read an MCP OAuth URL from an existing vault credential."""
    credentials = list(client.beta.vaults.credentials.list(vault_id, betas=BETAS))
    mcp_credentials = [
        credential for credential in credentials
        if getattr(getattr(credential, "auth", None), "type", None) == "mcp_oauth"
    ]
    provider_credentials = [
        credential for credential in mcp_credentials
        if provider.lower() in (
            f"{getattr(credential, 'display_name', '') or ''} "
            f"{getattr(getattr(credential, 'auth', None), 'mcp_server_url', '')}"
        ).lower()
    ]

    if len(provider_credentials) == 1:
        return provider_credentials[0].auth.mcp_server_url
    if len(mcp_credentials) == 1:
        return mcp_credentials[0].auth.mcp_server_url

    names = [
        f"{getattr(credential, 'display_name', '') or credential.id}: "
        f"{getattr(getattr(credential, 'auth', None), 'mcp_server_url', '<no mcp url>')}"
        for credential in mcp_credentials
    ]
    raise RuntimeError(
        f"Could not uniquely identify the {provider} MCP credential in "
        f"vault {vault_id}. Set LINEAR_MCP_URL explicitly. "
        f"Found MCP credentials: {names or 'none'}"
    )


def linear_mcp_oauth_auth(linear_mcp_url: str) -> dict:
    """Build a vault credential payload for the script-only OAuth fallback."""
    auth = {
        "type": "mcp_oauth",
        "mcp_server_url": linear_mcp_url,
        "access_token": os.environ["LINEAR_OAUTH_ACCESS_TOKEN"],
    }
    if os.environ.get("LINEAR_EXPIRES_AT"):
        auth["expires_at"] = os.environ["LINEAR_EXPIRES_AT"]

    refresh_token = os.environ.get("LINEAR_OAUTH_REFRESH_TOKEN")
    client_id = os.environ.get("LINEAR_OAUTH_CLIENT_ID")
    if refresh_token and client_id:
        refresh = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "token_endpoint": os.environ.get("LINEAR_TOKEN_ENDPOINT", DEFAULT_TOKEN_ENDPOINT),
            "token_endpoint_auth": {"type": "none"},
        }
        if os.environ.get("LINEAR_OAUTH_CLIENT_SECRET"):
            refresh["token_endpoint_auth"] = {
                "type": "client_secret_post",
                "client_secret": os.environ["LINEAR_OAUTH_CLIENT_SECRET"],
            }
        auth["refresh"] = refresh

    return auth


def resolve_linear_connection(client: Anthropic) -> tuple[str, str]:
    """Return (vault_id, mcp_url), deriving the URL from the vault when possible."""
    vault_id = os.environ.get("LINEAR_VAULT_ID", "").strip()
    mcp_url = os.environ.get("LINEAR_MCP_URL", "").strip()
    if vault_id:
        validate_vault_id(vault_id, provider="Linear")
        mcp_url = mcp_url or mcp_url_from_vault(client, vault_id, "linear")
        validate_mcp_url(mcp_url)
        print(f"vault.id = {vault_id} (existing Linear vault)")
        print(f"linear MCP URL = {mcp_url}")
        return vault_id, mcp_url

    if not os.environ.get("LINEAR_OAUTH_ACCESS_TOKEN"):
        raise RuntimeError(
            "Set LINEAR_VAULT_ID for the Claude Managed Agents vault that "
            "contains your Linear MCP credential. Script-only fallback: set "
            "LINEAR_OAUTH_ACCESS_TOKEN and optionally LINEAR_MCP_URL."
        )

    mcp_url = mcp_url or DEFAULT_LINEAR_MCP_URL
    validate_mcp_url(mcp_url)
    vault = client.beta.vaults.create(
        display_name=os.environ.get("LINEAR_USER_LABEL", "Linear user"),
        metadata={"external_user_id": os.environ.get("LINEAR_EXTERNAL_USER_ID", "usr_replace_me")},
        betas=BETAS,
    )
    credential = client.beta.vaults.credentials.create(
        vault.id,
        auth=linear_mcp_oauth_auth(mcp_url),
        display_name="Linear MCP OAuth",
        betas=BETAS,
    )
    print(f"vault.id = {vault.id}")
    try:
        validation = client.beta.vaults.credentials.mcp_oauth_validate(
            credential.id,
            vault_id=vault.id,
            betas=BETAS,
        )
        print(f"linear credential status = {validation.status}")
    except Exception as exc:
        print(f"WARNING: could not validate Linear MCP credential yet: {exc}")
    return vault.id, mcp_url


def resolve_optional_mcp_connection(
    client: Anthropic,
    provider: str,
    vault_env: str,
    url_env: str,
) -> tuple[str | None, str | None]:
    """Return an optional (vault_id, mcp_url) pair when a vault id is set."""
    vault_id = os.environ.get(vault_env, "").strip()
    mcp_url = os.environ.get(url_env, "").strip()
    if not vault_id:
        return None, None

    validate_vault_id(vault_id, vault_env, provider.title())
    mcp_url = mcp_url or mcp_url_from_vault(client, vault_id, provider)
    validate_mcp_url(mcp_url, url_env, vault_env)
    print(f"{provider} vault.id = {vault_id} (existing vault)")
    print(f"{provider} MCP URL = {mcp_url}")
    return vault_id, mcp_url


def main() -> None:
    client = Anthropic()
    vault_id, linear_mcp_url = resolve_linear_connection(client)
    slack_vault_id, slack_mcp_url = resolve_optional_mcp_connection(
        client,
        provider="slack",
        vault_env="SLACK_VAULT_ID",
        url_env="SLACK_MCP_URL",
    )

    # 1. Agent declares the public Linear MCP server (no auth on the agent).
    #    The mcp_toolset entry exposes Linear's tools to the model. We leave the
    #    default permission policy as-is here; see the troubleshooting notes in
    #    the lab markdown if MCP tool calls pause for confirmation.
    mcp_servers = [{
        "type": "url",
        "name": "linear",
        "url": linear_mcp_url,
    }]
    tools = [
        {"type": "agent_toolset_20260401"},
        {
            "type": "mcp_toolset",
            "mcp_server_name": "linear",
            # Auto-approve Linear tool calls so the lab runs end to end.
            # Drop this default_config to fall back to always_ask.
            "default_config": {"permission_policy": {"type": "always_allow"}},
        },
    ]
    vault_ids = [vault_id]

    if slack_vault_id and slack_mcp_url:
        mcp_servers.append({
            "type": "url",
            "name": "slack",
            "url": slack_mcp_url,
        })
        tools.append({
            "type": "mcp_toolset",
            "mcp_server_name": "slack",
        })
        vault_ids.append(slack_vault_id)

    agent = client.beta.agents.create(
        name="Linear Triage Agent",
        model=MODEL,
        system=(
            "You are a Linear assistant. You triage issues and file new ones "
            "via the linear MCP. When asked to file a bug, create a clear, "
            "well-titled issue with a concise description and reproduction "
            "steps. When asked to triage, list open or unassigned issues and "
            "suggest a priority for each. Always confirm the issue identifier "
            "(e.g. ENG-123) of anything you create or change. If a Slack MCP "
            "server is connected, use it only when the user explicitly asks "
            "for Slack context or Slack posting."
        ),
        mcp_servers=mcp_servers,
        tools=tools,
        betas=BETAS,
    )
    print(f"agent.id = {agent.id}")

    # 2. Limited-networking environment that permits MCP servers. The harness
    #    needs outbound access to the public Linear endpoint.
    env = client.beta.environments.create(
        name="linear-env",
        config={
            "type": "cloud",
            "networking": {
                "type": "limited",
                "allow_mcp_servers": True,
                "allowed_hosts": [],
            },
        },
        betas=BETAS,
    )
    print(f"env.id = {env.id}")

    # 3. Session references the vault via vault_ids; auth wires up server-side.
    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent.id, "version": agent.version},
        environment_id=env.id,
        vault_ids=vault_ids,
        title="Linear triage + file a bug",
        betas=BETAS,
    )
    print(f"session.id = {session.id}\n")

    # 4. Ask the agent to triage and file an issue, then stream the result.
    with client.beta.sessions.events.stream(session.id, betas=BETAS) as stream:
        client.beta.sessions.events.send(session.id, events=[{
            "type": "user.message",
            "content": [{
                "type": "text",
                "text": (
                    "Triage my unassigned Linear issues and tell me the top "
                    "three by likely priority. Then file a new bug titled "
                    "'Login crashes on empty password' with short reproduction "
                    "steps. Report the new issue identifier when done."
                ),
            }],
        }], betas=BETAS)
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="", flush=True)
            elif event.type == "agent.mcp_tool_use":
                # Each Linear tool call shows up here (list, create, comment).
                print(f"\n[mcp: {event.name}]")
            elif event.type == "session.error":
                print(f"\n[ERROR] {event.error}")
            elif event.type == "session.status_idle":
                print("\n--- session idle ---")
                break

    print_session_cost(client, session.id, MODEL, betas=BETAS)


if __name__ == "__main__":
    main()
