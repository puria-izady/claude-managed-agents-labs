"""Wait for a Managed Agents session output to appear in the Files API."""

from __future__ import annotations

import time


def wait_for_session_file(client, session_id: str, filename: str, *, betas):
    """Return the named output after up to five scoped listings, two seconds apart."""
    for attempt in range(5):
        for file in client.beta.files.list(scope_id=session_id, betas=betas):
            if file.filename == filename:
                return file
        if attempt < 4:
            time.sleep(2)
    raise RuntimeError(
        f"Session {session_id} did not produce {filename!r} after five file listings. "
        "Confirm that the agent wrote it to /mnt/session/outputs/."
    )
