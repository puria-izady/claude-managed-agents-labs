"""Shared Managed Agents cost meter for the course labs.

The numbers here are course estimates based on public Claude API list prices.
Use the Claude Console or your invoice for authoritative billing.
"""

from __future__ import annotations

from dataclasses import dataclass

from cache_usage import cache_usage_counts


@dataclass(frozen=True)
class ModelRates:
    input_per_mtok: float
    output_per_mtok: float
    cache_write_5m_per_mtok: float
    cache_write_1h_per_mtok: float
    cache_read_per_mtok: float


# Public Claude API prices in USD per million tokens, snapshot: 2026-07-07.
# Source: https://platform.claude.com/docs/en/about-claude/pricing
MODEL_RATES = {
    "claude-haiku-4-5": ModelRates(1.00, 5.00, 1.25, 2.00, 0.10),
    "claude-sonnet-5": ModelRates(2.00, 10.00, 2.50, 4.00, 0.20),
    "claude-sonnet-4-6": ModelRates(3.00, 15.00, 3.75, 6.00, 0.30),
    "claude-sonnet-4-5": ModelRates(3.00, 15.00, 3.75, 6.00, 0.30),
    "claude-opus-4-8": ModelRates(5.00, 25.00, 6.25, 10.00, 0.50),
}

DEFAULT_RATES = MODEL_RATES["claude-haiku-4-5"]
SESSION_RUNTIME_PER_HOUR = 0.08
WEB_SEARCH_PER_REQUEST = 0.01  # $10 per 1,000 searches


def rates_for_model(model: str) -> ModelRates:
    """Return known rates for a model id, falling back to Haiku 4.5."""
    model = model.lower()
    for prefix, rates in MODEL_RATES.items():
        if model.startswith(prefix):
            return rates
    return DEFAULT_RATES


def _cache_creation_counts(usage) -> tuple[int, int]:
    """Return (5m write tokens, 1h write tokens) from a usage object."""
    cache_creation = getattr(usage, "cache_creation", None)
    total = getattr(usage, "cache_creation_input_tokens", 0) or 0
    if cache_creation is None:
        return total, 0

    five_min = getattr(cache_creation, "ephemeral_5m_input_tokens", 0) or 0
    one_hour = getattr(cache_creation, "ephemeral_1h_input_tokens", 0) or 0
    remainder = max(total - five_min - one_hour, 0)
    return five_min + remainder, one_hour


def estimate_session_cost(session, model: str) -> dict[str, float | int]:
    """Estimate Managed Agents cost from a retrieved session object.

    The session should be re-fetched after it goes idle so `usage` and `stats`
    are current.
    """
    rates = rates_for_model(model)
    usage = getattr(session, "usage", None)
    stats = getattr(session, "stats", None)

    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache = cache_usage_counts(usage)
    cache_write_5m, cache_write_1h = _cache_creation_counts(usage)

    server_tool_use = getattr(usage, "server_tool_use", None)
    web_search_requests = getattr(server_tool_use, "web_search_requests", 0) or 0
    active_seconds = getattr(stats, "active_seconds", 0) or 0

    input_cost = input_tokens * rates.input_per_mtok / 1_000_000
    output_cost = output_tokens * rates.output_per_mtok / 1_000_000
    cache_write_cost = (
        cache_write_5m * rates.cache_write_5m_per_mtok / 1_000_000
        + cache_write_1h * rates.cache_write_1h_per_mtok / 1_000_000
    )
    cache_read_cost = cache["cache_read"] * rates.cache_read_per_mtok / 1_000_000
    runtime_cost = active_seconds / 3600 * SESSION_RUNTIME_PER_HOUR
    web_search_cost = web_search_requests * WEB_SEARCH_PER_REQUEST

    total = (
        input_cost
        + output_cost
        + cache_write_cost
        + cache_read_cost
        + runtime_cost
        + web_search_cost
    )
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache["cache_read"],
        "cache_write_tokens": cache["cache_creation"],
        "active_seconds": active_seconds,
        "web_search_requests": web_search_requests,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "cache_write_cost": cache_write_cost,
        "cache_read_cost": cache_read_cost,
        "runtime_cost": runtime_cost,
        "web_search_cost": web_search_cost,
        "total_cost": total,
    }


def format_session_cost(session, model: str) -> str:
    """Return a concise multiline cost report for notebooks and scripts."""
    return format_sessions_cost([session], model)


def format_sessions_cost(sessions, model: str) -> str:
    """Return a per-session plus total cost report."""
    rows = []
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "active_seconds": 0.0,
        "web_search_requests": 0,
        "input_cost": 0.0,
        "output_cost": 0.0,
        "cache_write_cost": 0.0,
        "cache_read_cost": 0.0,
        "runtime_cost": 0.0,
        "web_search_cost": 0.0,
        "total_cost": 0.0,
    }

    for session in sessions:
        c = estimate_session_cost(session, model)
        for key in totals:
            totals[key] += c[key]
        rows.append(
            f"  session {getattr(session, 'id', '<unknown>')}: ${c['total_cost']:.4f} "
            f"({c['input_tokens']} in / {c['output_tokens']} out; "
            f"{c['cache_read_tokens']} cache read / {c['cache_write_tokens']} cache write; "
            f"{c['active_seconds']:.1f}s runtime)"
        )

    return (
        "\nEstimated lab cost (USD, list-price estimate):\n"
        + "\n".join(rows)
        + "\n"
        f"  total across {len(rows)} session(s): ${totals['total_cost']:.4f}\n"
        f"  total tokens: {totals['input_tokens']} input / "
        f"{totals['output_tokens']} output; {totals['cache_read_tokens']} cache read / "
        f"{totals['cache_write_tokens']} cache write\n"
        f"  total active runtime: {totals['active_seconds']:.1f}s\n"
        f"  total line items: input ${totals['input_cost']:.4f}, "
        f"output ${totals['output_cost']:.4f}, "
        f"cache write ${totals['cache_write_cost']:.4f}, "
        f"cache read ${totals['cache_read_cost']:.4f}, "
        f"runtime ${totals['runtime_cost']:.4f}, "
        f"web search ${totals['web_search_cost']:.4f}\n"
        "  Note: this is not an invoice. Check Claude Console billing for authoritative cost."
    )


def print_sessions_cost(client, session_ids, model: str, *, betas=None) -> None:
    """Re-fetch several sessions and print each estimate plus the total."""
    sessions = [
        client.beta.sessions.retrieve(session_id, betas=betas)
        for session_id in dict.fromkeys(session_ids)
    ]
    print(format_sessions_cost(sessions, model))


def print_session_cost(client, session_id: str, model: str, *, betas=None) -> None:
    """Re-fetch one session and print the current cost estimate."""
    print_sessions_cost(client, [session_id], model, betas=betas)
