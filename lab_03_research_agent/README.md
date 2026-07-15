# Lab 03 - Research agent that files a brief to Google Docs

A `Research Brief` agent that web-searches a topic, writes a concise cited
brief, then creates a Google Doc with it via a remote MCP server.

## Env vars

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_DOCS_VAULT_ID="vlt_..."
# Optional only if the vault has multiple MCP credentials:
export GOOGLE_DOCS_MCP_URL="https://your-google-docs-mcp.example.com/mcp"
```

Create/connect the Google Docs credential in Claude Managed Agents Vaults first,
then paste the vault id into `GOOGLE_DOCS_VAULT_ID`. The notebook/script reads
the MCP URL from that vault credential when possible. The OAuth token stays in
the vault and is attached to the session with `vault_ids`.

## Run

```bash
uv run --project .. --env-file ../.env python lab03.py
```

Imports the `RESEARCH_BRIEF_GDOCS_SYSTEM` four-ingredient prompt from
`../shared/prompts.py` via a `sys.path` insert.

## Output

You should see `[tool: web_search(...)]` and `[tool: web_fetch(...)]` lines, a
`[tool: write(...)]`, then an `[mcp: ...]` call as the agent creates the Google
Doc. The agent's final message reports the new document URL. Open it to verify
the brief and its inline citations.
