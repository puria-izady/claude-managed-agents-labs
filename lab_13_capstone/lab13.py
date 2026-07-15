"""Lab 13 - Capstone: Personal Research Agent.

The full integration. One coordinator routes the job; three specialists do
the work (Researcher, Writer, Fact-Checker). Two memory stores ride along:
user preferences (read_only) and per-topic history (read_write). An outcome
rubric decides when the brief is good enough. When the rubric is satisfied,
the coordinator files the brief to Google Docs through an MCP server, and a
Slack MCP server posts concise progress and completion updates.

This single script wires the whole system and runs one brief end to end:

  1) build the environment and resolve per-user vaults
  2) create the three specialists and the coordinator (multiagent.agents)
  3) attach the two memory stores to the session
  4) declare the Google Docs and Slack MCPs on the coordinator
  5) run an outcome-driven session with the rubric; the coordinator files the
     brief to Google Docs and posts Slack updates through MCP
  6) retrieve the finished brief locally

Run:
    python lab13.py "small modular reactors"

Environment variables (see README.md for the full list):
    ANTHROPIC_API_KEY          your Anthropic API key
    GOOGLE_DOCS_VAULT_ID       preferred: existing Managed Agents vault id
    GOOGLE_DOCS_MCP_URL        optional override; otherwise read from the vault
    SLACK_VAULT_ID             existing Managed Agents vault id for Slack
    SLACK_MCP_URL              optional override; otherwise read from the vault
    SLACK_CHANNEL              channel to post to (default: #research)
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from anthropic import Anthropic  # noqa: E402
from cost_meter import print_session_cost  # noqa: E402

# The managed-agents beta header is required for files.list / files.download.
MANAGED_AGENTS_BETA = "managed-agents-2026-04-01"
MODEL = "claude-haiku-4-5-20251001"

# --- System prompts ---------------------------------------------------------
# The three specialists share one container filesystem, so they hand off
# artifacts as files under /workspace. The coordinator reads user preferences
# from the read_only memory store and appends to the read_write topic store.

RESEARCHER = """You research a topic. Use web_search for breadth and
web_fetch on the most promising results. Prefer the sources listed in
/mnt/memory/user-prefs/trusted_sources.md. Write a JSON array of citations
to /workspace/citations.json: each item {url, title, snippet, why_relevant}.
Aim for at least 5 distinct, high-quality sources."""

WRITER = """You draft a research brief from the researcher's citations.
Read /workspace/citations.json for sources and
/mnt/memory/user-prefs/style.md for tone and length. Produce
/workspace/draft.md: 500-600 words, every non-trivial claim carrying an
inline citation link. Do not invent claims or sources."""

FACT_CHECKER = """For every claim in /workspace/draft.md, verify it against
the linked source with web_fetch. Write /workspace/check.md, marking each
claim:
  [verified]   - quote the supporting line from the source
  [partial]    - quote the source and explain the gap
  [unverified] - explain why it could not be confirmed
If any claim is [partial] or [unverified], the writer must revise."""

COORDINATOR = """You coordinate a Personal Research Agent team. At the start
of every session, read /mnt/memory/user-prefs/style.md and
/mnt/memory/user-prefs/trusted_sources.md so the brief matches the user's
preferences.

Given a topic:
1) Delegate to the Researcher (return when /workspace/citations.json exists).
2) Delegate to the Writer (return when /workspace/draft.md exists).
3) Delegate to the Fact-Checker (return when /workspace/check.md exists).
4) If check.md contains any [partial] or [unverified] claim, loop steps 2-3
   with the Writer fixing those claims, until the draft is clean.
5) Save the final brief to /mnt/session/outputs/brief.md.
6) Post at most two concise updates to the configured Slack channel through
   the slack MCP server: one after research starts and one final completion
   message after the Google Doc is filed. Do not post drafts or long content.
7) File the brief as a new Google Doc under a "Research" folder using the
   google_docs MCP server. Keep the document title equal to the topic.
8) Append a one-line summary of this brief to
   /mnt/memory/topic-context/<topic-slug>/log.md so future runs recall it."""

# --- Outcome rubric ---------------------------------------------------------
# The rubric is the loop's exit condition. It encodes both goals at once:
# the brief must be well-cited AND within the length budget. It also points
# the grader at the trusted-sources memory file and the Google Docs filing.
RUBRIC = """# Research Brief Rubric

## Content
- Topic clearly defined in the opening paragraph.
- 4-6 substantive claims, each supported by an inline citation.
- No claim without a source. 500-600 words total.

## Sources
- At least 5 distinct sources.
- All from /mnt/memory/user-prefs/trusted_sources.md or comparable quality
  (peer-reviewed, official, or a well-known publication).
- Each source linked by URL in an inline citation.

## Output
- Saved as /mnt/session/outputs/brief.md.
- Filed to a new Google Doc under "Research" via the google_docs MCP server.
"""


def slugify(text: str) -> str:
    """Turn a topic into a filesystem- and store-name-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "topic"


def validate_vault_id(
    vault_id: str,
    env_var: str = "GOOGLE_DOCS_VAULT_ID",
    provider: str = "Google Docs",
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
    url_env: str = "GOOGLE_DOCS_MCP_URL",
    vault_env: str = "GOOGLE_DOCS_VAULT_ID",
) -> None:
    """Catch missing or placeholder URLs before agent creation."""
    parsed = urlparse(url)
    if not url or "REPLACE-ME" in url or parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError(
            f"Set {url_env} to a valid https MCP endpoint, or use a "
            f"{vault_env} whose credential contains an MCP server URL."
        )


def mcp_url_from_vault(client: Anthropic, vault_id: str, provider: str) -> str:
    """Read an MCP URL from a provider credential in a Managed Agents vault."""
    credentials = list(
        client.beta.vaults.credentials.list(
            vault_id, betas=[MANAGED_AGENTS_BETA],
        )
    )
    mcp_credentials = [
        credential for credential in credentials
        if getattr(credential.auth, "type", None) == "mcp_oauth"
    ]
    provider_credentials = [
        credential for credential in mcp_credentials
        if provider.lower() in (
            f"{credential.display_name or ''} "
            f"{getattr(credential.auth, 'mcp_server_url', '')}"
        ).lower()
    ]

    if len(provider_credentials) == 1:
        return provider_credentials[0].auth.mcp_server_url
    if len(mcp_credentials) == 1:
        return mcp_credentials[0].auth.mcp_server_url

    names = [
        f"{credential.display_name or credential.id}: "
        f"{getattr(credential.auth, 'mcp_server_url', '<no mcp url>')}"
        for credential in mcp_credentials
    ]
    raise RuntimeError(
        f"Could not uniquely identify the {provider} MCP credential in "
        f"vault {vault_id}. Set the matching MCP URL env var explicitly. "
        f"Found MCP credentials: {names or 'none'}"
    )


def resolve_google_docs_connection(client: Anthropic) -> tuple[str, str]:
    """Return (vault_id, mcp_url), deriving the URL from the vault when possible."""
    return resolve_required_mcp_connection(
        client,
        provider="google",
        vault_env="GOOGLE_DOCS_VAULT_ID",
        url_env="GOOGLE_DOCS_MCP_URL",
    )


def resolve_required_mcp_connection(
    client: Anthropic,
    provider: str,
    vault_env: str,
    url_env: str,
) -> tuple[str, str]:
    """Return (vault_id, mcp_url) for a required vault-backed MCP connection."""
    vault_id = os.environ.get(vault_env, "").strip()
    mcp_url = os.environ.get(url_env, "").strip()
    validate_vault_id(vault_id, vault_env, provider.title())
    mcp_url = mcp_url or mcp_url_from_vault(client, vault_id, provider)
    validate_mcp_url(mcp_url, url_env, vault_env)
    os.environ[url_env] = mcp_url
    print(f"{provider} vault.id = {vault_id} (existing vault)")
    print(f"{provider} MCP URL = {mcp_url}")
    return vault_id, mcp_url


def build_user_prefs(client: Anthropic) -> str:
    """Create and seed the read_only user-preferences memory store.

    Seed it once; it rides along on every session. Because we attach it
    read_only at session time, no agent or poisoned tool call can overwrite
    the user's standing preferences.
    """
    prefs = client.beta.memory_stores.create(
        name="capstone-user-prefs",
        description="User preferences for research briefs (tone, length, sources).",
    )
    client.beta.memory_stores.memories.create(
        prefs.id,
        path="/style.md",
        content=(
            "Tone: concise, analytical, no fluff.\n"
            "Length: 500-600 words.\n"
            "Avoid bullet lists in the body; use them only for the sources list."
        ),
    )
    client.beta.memory_stores.memories.create(
        prefs.id,
        path="/trusted_sources.md",
        content=(
            "Prefer: anthropic.com, arxiv.org, stanford.edu, mit.edu, "
            "nature.com, the IEA, and official government sources.\n"
            "Avoid: clickbait, press-release rewrites, anonymous blogs."
        ),
    )
    print(f"user-prefs store = {prefs.id}")
    return prefs.id


def get_or_create_topic_store(client: Anthropic, topic: str, slug: str) -> str:
    """Reuse the per-topic store if it exists; otherwise create it.

    This store is attached read_write so the coordinator can append a running
    log. Across runs it accumulates context: the agent remembers what it has
    already covered on a topic.
    """
    name = f"capstone-topic-{slug}"
    existing = [s for s in client.beta.memory_stores.list().data if s.name == name]
    if existing:
        print(f"reusing topic store = {existing[0].id}")
        return existing[0].id
    store = client.beta.memory_stores.create(
        name=name, description=f"Per-topic research log for: {topic}"
    )
    print(f"created topic store = {store.id}")
    return store.id


def build_agents(
    client: Anthropic,
    google_docs_mcp_url: str,
    slack_mcp_url: str,
    slack_channel: str,
) -> str:
    """Create the three specialists and the coordinator. Returns the
    coordinator id.

    All agents use the course default Haiku model. Tool scoping still maps to
    the subtask so each agent stays focused.
    """
    researcher = client.beta.agents.create(
        name="Capstone Researcher",
        model=MODEL,
        system=RESEARCHER,
        tools=[{
            "type": "agent_toolset_20260401",
            "default_config": {"enabled": False},
            "configs": [
                {"name": "web_search", "enabled": True},
                {"name": "web_fetch", "enabled": True},
                {"name": "read", "enabled": True},
                {"name": "write", "enabled": True},
            ],
        }],
    )

    writer = client.beta.agents.create(
        name="Capstone Writer",
        model=MODEL,
        system=WRITER,
        # Drafting is low risk, so the full built-in toolset is fine here.
        tools=[{"type": "agent_toolset_20260401"}],
    )

    fact_checker = client.beta.agents.create(
        name="Capstone Fact-Checker",
        # Verification is where errors are most expensive, so the tool scope is tight.
        model=MODEL,
        system=FACT_CHECKER,
        tools=[{
            "type": "agent_toolset_20260401",
            "default_config": {"enabled": False},
            "configs": [
                {"name": "web_fetch", "enabled": True},
                {"name": "read", "enabled": True},
                {"name": "write", "enabled": True},
            ],
        }],
    )

    coordinator_system = (
        COORDINATOR
        + f"\n\nSlack target channel: {slack_channel}. "
        "Use the slack MCP server for the two short status updates only."
    )

    # The SaaS MCP servers live on the coordinator ONLY; the specialists never
    # touch it. multiagent.agents lists the roster it can delegate to.
    coordinator = client.beta.agents.create(
        name="Capstone Research Lead",
        model=MODEL,
        system=coordinator_system,
        mcp_servers=[
            {
                "type": "url",
                "name": "google_docs",
                "url": google_docs_mcp_url,
            },
            {
                "type": "url",
                "name": "slack",
                "url": slack_mcp_url,
            },
        ],
        tools=[
            {"type": "agent_toolset_20260401"},
            {"type": "mcp_toolset", "mcp_server_name": "google_docs"},
            {
                "type": "mcp_toolset",
                "mcp_server_name": "slack",
                "default_config": {"permission_policy": {"type": "always_allow"}},
            },
        ],
        multiagent={
            "type": "coordinator",
            "agents": [
                {"type": "agent", "id": researcher.id},
                {"type": "agent", "id": writer.id},
                {"type": "agent", "id": fact_checker.id},
            ],
        },
    )
    print(f"coordinator = {coordinator.id}")
    return coordinator.id


def build_environment(client: Anthropic) -> str:
    """Create the cloud environment the agents run in.

    Networking is limited with an explicit allowance for the web tools plus
    the Google Docs MCP. Package managers are on so the writer can clean up
    fetched HTML into tidy markdown.
    """
    env = client.beta.environments.create(
        name="capstone-env",
        config={
            "type": "cloud",
            "packages": {"pip": ["beautifulsoup4", "markdownify"]},
            "networking": {
                "type": "limited",
                "allowed_hosts": ["docs.googleapis.com", "www.googleapis.com"],
                "allow_mcp_servers": True,
                "allow_package_managers": True,
            },
        },
    )
    print(f"environment = {env.id}")
    return env.id


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python lab13.py "<topic>"')
    topic = " ".join(sys.argv[1:])
    slug = slugify(topic)

    client = Anthropic()

    # --- Step 1: environment and vault --------------------------------------
    env_id = build_environment(client)
    google_docs_vault_id, google_docs_mcp_url = resolve_google_docs_connection(client)
    slack_vault_id, slack_mcp_url = resolve_required_mcp_connection(
        client,
        provider="slack",
        vault_env="SLACK_VAULT_ID",
        url_env="SLACK_MCP_URL",
    )
    slack_channel = os.environ.get("SLACK_CHANNEL", "#research").strip() or "#research"

    # --- Step 2: the agent roster -------------------------------------------
    coordinator_id = build_agents(
        client,
        google_docs_mcp_url,
        slack_mcp_url,
        slack_channel,
    )

    # --- Step 3: the two memory stores --------------------------------------
    user_prefs_id = build_user_prefs(client)
    topic_store_id = get_or_create_topic_store(client, topic, slug)

    # --- Step 4: start the session with both stores attached ----------------
    # user-prefs is read_only (preferences must never be overwritten);
    # topic-context is read_write (the coordinator appends a running log).
    session = client.beta.sessions.create(
        agent={"type": "agent", "id": coordinator_id},
        environment_id=env_id,
        vault_ids=[google_docs_vault_id, slack_vault_id],
        resources=[
            {
                "type": "memory_store",
                "memory_store_id": user_prefs_id,
                "access": "read_only",
            },
            {
                "type": "memory_store",
                "memory_store_id": topic_store_id,
                "access": "read_write",
            },
        ],
        title=topic,
    )
    print(f"session.id = {session.id}\n")

    # --- Step 5: define the outcome and run ---------------------------------
    # One call kicks off the whole pipeline: research, draft, fact-check,
    # grade, and on a satisfied grade, file to Google Docs. max_iterations is
    # the safety rail against a runaway loop.
    with client.beta.sessions.events.stream(session.id) as stream:
        client.beta.sessions.events.send(
            session.id,
            events=[{
                "type": "user.define_outcome",
                "description": (
                    f"Produce a research brief on: {topic}. "
                    f"Run it through the Personal Research Agent pipeline and "
                    f"file the result to Google Docs. Post concise progress and "
                    f"completion updates to Slack channel {slack_channel}."
                ),
                "rubric": {"type": "text", "content": RUBRIC},
                "max_iterations": 8,
            }],
        )

        satisfied = False
        for event in stream:
            if event.type == "session.thread_created":
                # A child thread spawned for a specialist.
                print(f"+ thread {event.agent_name}")
            elif event.type == "agent.thread_message_received":
                # A specialist returned a result to the coordinator.
                print(f"  <- {event.from_agent_name} returned")
            elif event.type == "agent.mcp_tool_use":
                # The coordinator reaching into Google Docs or Slack.
                print(f"  [mcp: {event.name}]")
            elif event.type == "span.outcome_evaluation_end":
                # The grader scored the draft against the rubric.
                print(f"  iter {event.iteration}: {event.result}")
                satisfied = event.result == "satisfied"
            elif event.type == "agent.message":
                for b in event.content:
                    if b.type == "text":
                        print(b.text, end="", flush=True)
            elif event.type == "session.status_idle":
                print("\n--- session idle ---")
                break

    # Google Docs and Slack happened in-session while Step 5 streamed.
    # The coordinator filed the brief and posted Slack updates via MCP tools as
    # part of the run (watch for the [mcp: ...] lines above).
    if not satisfied:
        print("Outcome not satisfied within max_iterations; final Slack update may be absent.")

    # --- Step 6: retrieve the finished brief locally ------------------------
    out_dir = Path("./outputs")
    out_dir.mkdir(exist_ok=True)
    for f in client.beta.files.list(scope_id=session.id, betas=[MANAGED_AGENTS_BETA]):
        if f.filename == "brief.md":
            target = out_dir / f"{slug}.md"
            client.beta.files.download(f.id).write_to_file(str(target))
            print(f"saved: {target}")

    print_session_cost(client, session.id, MODEL, betas=[MANAGED_AGENTS_BETA])


if __name__ == "__main__":
    main()
