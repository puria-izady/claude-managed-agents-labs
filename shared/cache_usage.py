"""Helpers for inspecting Managed Agents prompt-cache usage.

Managed Agents session objects expose cumulative cache counters on
`session.usage`. These helpers keep the labs from repeating getattr-heavy
formatting code.
"""


def cache_usage_counts(usage) -> dict[str, int]:
    """Return cache read/write counters from a session usage object."""
    if usage is None:
        return {"cache_read": 0, "cache_creation": 0}

    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0

    cache_creation_detail = getattr(usage, "cache_creation", None)
    if cache_creation_detail is not None:
        five_min = getattr(cache_creation_detail, "ephemeral_5m_input_tokens", 0) or 0
        one_hour = getattr(cache_creation_detail, "ephemeral_1h_input_tokens", 0) or 0
        cache_creation = cache_creation or five_min + one_hour

    return {"cache_read": cache_read, "cache_creation": cache_creation}


def format_cache_usage(usage) -> str:
    """Format cache counters for notebook/script output."""
    counts = cache_usage_counts(usage)
    return (
        f"cache: {counts['cache_read']} read / "
        f"{counts['cache_creation']} write tokens"
    )
