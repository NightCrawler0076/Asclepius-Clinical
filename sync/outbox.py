"""
Sync outbox — manages the offline-first sync queue.

Phase 11 will implement actual HTTP upload with retry + backoff.
"""

from database.repository import get_pending_syncs


def get_pending_count() -> int:
    """Return number of items waiting to sync."""
    return len(get_pending_syncs())


def process_pending():
    """Attempt to sync all pending items.

    Currently a stub — Phase 11 will implement HTTP upload.
    """
    pending = get_pending_syncs()
    results = []
    for item in pending:
        results.append({
            "id": item["id"],
            "entity_type": item["entity_type"],
            "status": "skipped — sync not yet implemented",
        })
    return results
